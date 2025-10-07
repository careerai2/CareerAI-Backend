from httpx import patch
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, AIMessage,HumanMessage,FunctionMessage
from langchain_core.runnables import RunnableConfig
from ..llm_model import llm,SwarmResumeState,AcadState
from models.resume_model import Internship
# from .state import SwarmResumeState
from .tools import tools
from textwrap import dedent
from utils.safe_trim_msg import safe_trim_messages
from ..utils.common_tools import extract_json_from_response
import assistant.resume.chat.token_count as token_count
import json 
from .functions import apply_patches,new_query_pdf_knowledge_base
import re
from .mappers import FIELD_MAPPING

# ---------------------------
# 2. LLM with Tools
# ---------------------------


llm_acads = llm.bind_tools(tools)
# llm_acads = llm  # tool can be added if needed
llm_builder = llm  # tool can be added if needed
llm_retriever = llm # tool can be added if needed

default_msg = AIMessage(content="Sorry, I couldn't process that. Could you please retry?")




# main model
def call_acads_model(state: SwarmResumeState, config: RunnableConfig):
    """Main chat loop for Por assistant with immediate state updates."""
    tailoring_keys = config["configurable"].get("tailoring_keys", [])
    current_entries = state.get("resume_schema", {}).get("academic_projects", [])
    acads_state = state.get("acads", {})
    
    tailored_current_entries = [
    (idx, entry.get("organization"))
    for idx, entry in enumerate(current_entries)
    ]

 
    # print("Internship State in Model Call:", acads_state)
    
    if isinstance(acads_state, dict):
        acads_state = AcadState.model_validate(acads_state)

    index = getattr(acads_state, "index", None)
    
    
    
    if index is not None and 0 <= index < len(current_entries):
        entry = current_entries[index]
    else:
        entry = None
        
    # print("Current Index in State:", index)
    print("Tailored Entries:-", tailored_current_entries)
    # print("Current Entry:-",entry)
    
    if current_entries and entry:
        current_entry_msg = entry
    elif current_entries and not entry:
        current_entry_msg = f"No entry is currently focused."
    else:
        current_entry_msg = "No Por entries exist yet."

    print("retrived_msg",state["acads"])
    
    system_prompt = SystemMessage(
            content=dedent(f"""
            You are a **Human like Academic Project Assistant** for a Resume Builder.
            Your role: chat naturally, guiding users to refine academic project entries with clarity, brevity, and alignment to {tailoring_keys}.
            Always be supportive, not interrogative. KEEP RESPONSES UNDER 125 WORDS.

            --- Workflow ---
            • Gather details conversationally (one clear question at a time).
            • Avoid duplicate project names.
            • Confirm with the user only if a change may DELETE existing info.
            • Once the user provides info, IMMEDIATELY use Tool `send_patches` to transmit it. No extra confirmation needed unless deleting or overwriting.
            • For each project, aim to get 3 pieces of information: what the project was about, what the user specifically did, and the result or technical outcome.
            • DO NOT ask about challenges, learnings, or feelings.
            • Suggest improvements to existing info (stronger verbs, more impact, technical precision).
            • Keep each bullet between 90–150 characters.

            --- Tool Usage ---
            • `send_patches`: Minimal JSON Patch ops (RFC 6902). Example:
            [
                {{ "op": "replace", "path": "/project_name", "value": "Heat Transfer Analysis of Disc Brake" }},
                {{ "op": "add", "path": "/description_bullets/-", "value": "Simulated braking heat distribution using COMSOL to compare three rotor materials" }}
            ]
            • `update_index_and_focus`: Switch focus to another academic project.
            • `get_full_academic_projects`: Fetch details for vague references to older entries.
            • Additional tools for each section are available—call them when the user wants to move sections.

            --- Schema ---
            {{project_name, project_description, description_bullets[], duration}}

            --- Current Entries (compact) ---
            {tailored_current_entries if tailored_current_entries else "No entries yet."}

            --- Current Entry in Focus ---
            {current_entry_msg}

            --- Guidelines ---
            • Be concise, friendly, and professional.
            • Use action-oriented phrasing (e.g., Designed, Analyzed, Implemented, Modeled, Simulated).
            • Apply info immediately via `send_patches`.
            • Suggest improvements, confirm before deleting/overwriting.
            • Append one bullet per patch to `/description_bullets/-`.
            """)
        )


    try:
 
        messages = safe_trim_messages(state["messages"], max_tokens=256)
        # messages = safe_trim_messages(state["messages"], max_tokens=512)
        response = llm_acads.invoke([system_prompt] + messages, config)
        
        # print("Internship Response:", response.content)

        # Update token counters
        token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
        token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)

        

        
        if not getattr(state["messages"][-1:], "tool_calls", None):

            print("\n\n\n")
            
       
        
            
            token_count.total_turn_Input_Tokens = 0
            token_count.total_turn_Output_Tokens = 0

        print("acads_model response:", response.content)
        print("Por Model Token Usage:", response.usage_metadata)
        
        print("\n\n\n\n")
        
        return {"messages": [response]}
    except Exception as e:
        print("Error in acads_model:", e)
        return {"messages": [AIMessage(content="Sorry! can you repeat")],"next_node": END}















# Query generator for Retriever 
def query_generator_model(state: SwarmResumeState, config: RunnableConfig):
    """Fetch relevant info from knowledge base."""
    # current_entries = state.get("resume_schema", {}).get("academic_projects", [])
    tailoring_keys = config["configurable"].get("tailoring_keys", [])
    patches = state.get("acads", {}).get("patches", [])
   

    prompt = f"""
        You are an expert query generator for a vector database of Academic Project writing guidelines. 
        Your goal is to create concise, retrieval-friendly queries to fetch the most relevant 
        academic project writing formats, phrasing rules, and content guidelines.

        --- Instructions ---
        • Reply ONLY with the generated query as plain text (1–2 sentences max).
        • Focus strictly on the fields listed in 'patched_fields'.
        • Always include:
        - Field name (exactly as in schema).
        - Current field value from patches.
        - Formatting requirements for that field (technical tone, brevity, clarity, structure).
        • If a domain/field/topic is provided (e.g., Mechanical Engineering, Data Analysis, Simulation, Research),
        include it naturally in the query.
        • Use synonyms and natural phrasing (e.g., academic writing guidelines, best practices, format, phrasing suggestions) 
        so it matches academic or technical handbook-style content.
        • Do not add filler or unrelated information.

        --- Patches (only these matter) ---
        {patches}

        --- Targeting Domain/Field (if any) ---
        {tailoring_keys if tailoring_keys else "None"}
    """

 

    try:

        # Call the retriever LLM
        response = llm_retriever.invoke(prompt, config)
        
        token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
        token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)
        
        


        print("Query generated:", response)
        if response.content.strip():
            state["acads"]["generated_query"] = str(response.content)
        else:
            state["acads"]["generated_query"] = ""
            print("Retriever returned empty info")

        print("Query generator Token Usage:", response.usage_metadata)
        print("\n\n\n\n")
        # return {"next_node": "builder_model"}
        return {"next_node": END}
    except Exception as e:
        print("Error in query generator:", e)
        
        return {"messages":AIMessage(content="Sorry,Can't process your request now"),"next_node": END}
















# Knowledge Base Retriever
def retriever_node(state: SwarmResumeState, config: RunnableConfig):
    try:
        query = state.get("acads", {}).get("generated_query", [])
        patches = state.get("acads", {}).get("patches", [])
        
        # print("Por in retriver node",state["acads"])
        
        if not query or (isinstance(query, str) and query.strip() in ("None", "")):
            print("No query generated, skipping retrieval.")
            state["acads"]["retrieved_info"] = []
            return {"next_node": "builder_model"}

       

        all_results = []

        # 🔄 Loop over each query + patch
        for i, patch in enumerate(patches):
            section = "Academic Project Document Formatting Guidelines"
            patch_field = patch.get("path", "").lstrip("/") 
            patch_field = patch_field.split("/", 1)[0]
            kb_field = FIELD_MAPPING.get(patch_field) 
            
            print("Patch Field",patch_field)
            print("\Kb_field",kb_field)
            
            print(f"\n🔍 Running retriever for query {i+1}: on field {patch_field} mapped to KB field {kb_field}")
        
            
            if patch_field == "description_bullets":
                retrieved_info = new_query_pdf_knowledge_base(
                query_text=str(query),   # now it's a string
                role=["acads"],
                section=section,
                subsection="Action Verbs (to use in description bullets)",
                field=kb_field,
                n_results=5,
                debug=False
            )
                all_results.append(f"[Action Verbs] => {retrieved_info}")

            # Extract actual query text from patch dict
            patch_query = patch.get("value", "")  

            print(f"\n🔍 Running retriever for query {i+1}: {patch_query}")

         

            retrieved_info = new_query_pdf_knowledge_base(
                query_text=str(query),   # now it's a string
                role=["acads"],
                section=section,
                subsection="Schema Requirements & Formatting Rules",
                field=kb_field,
                n_results=5,
                debug=False
            )

            print(f"Retriever returned {retrieved_info} results for patch {i+1}.\n\n")

            all_results.append(f"[{patch_field}] {retrieved_info}")

        all_results = "\n".join(all_results)
        
        print("All retrieved info:", all_results,"Type of All results:-",type(all_results))
        # Save everything back
        state["acads"]["retrieved_info"] = all_results
        # state["acads"]["last_query"] = queries
        state["acads"]["generated_query"] = ""  # clear after use

        print("\n✅ Retrieved info saved:", all_results)
        print("\n\n\n\n")

        return {"next_node": "builder_model"}

    except Exception as e:
        print("Error in retriever:", e)
        return {END: END}



















# Builder Model
def builder_model(state: SwarmResumeState, config: RunnableConfig):
    """Refine acads patches using retrieved info."""
    try:
        
        retrieved_info = state.get("acads", {}).get("retrieved_info", "")
        patches = state.get("acads", {}).get("patches", [])
        # print("Patches in Builder :-", patches)
        
        index = state.get("acads", {}).get("index")
        current_entries = state.get("resume_schema", {}).get("academic_projects", [])
        entry = current_entries[index] if index is not None and 0 <= index < len(current_entries) else "New Entry"

        # print("Current Entry in Builder:", entry)
        print(patches)

        if not retrieved_info or retrieved_info.strip() in ("None", ""):
            print("No retrieved info available, skipping building.")
            state["messages"].append(SystemMessage(content="No retrieved info available, skipping building."))
            return

        prompt = dedent(f"""You are reviewing acads resume entries using JSON Patches.

        ***INSTRUCTIONS:***
        • Respond in **valid JSON array only** (list of patches).
        • Input is the current entry + current patches + retrieved info.
        • **Do NOT change any existing patch values, ops, or paths.** The patches must remain exactly as provided.
        • Use the retrieved info only as **guidance and best practice** for evaluating the patches.
        • Do NOT add, remove, or replace patches—your task is only to verify and suggest improvements conceptually (no changes to JSON output).
        • Your response must strictly maintain the original JSON Patch structure provided.

        --- Current Entry on which the patches are applied ---
        {entry}

        --- Current Patches ---
        {patches}

        --- Retrieved Info (use only as guidance for best practices) ---
        {retrieved_info}
        """)

            


            
        # messages = safe_trim_messages(state["messages"], max_tokens=256)
        # last_human_msg = next((msg for msg in reversed(messages) if isinstance(msg, HumanMessage)), None)


        response = llm_builder.invoke(prompt, config)
        
        token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
        token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)

        

        # Extract refined patches from LLM output
        refined_patches = extract_json_from_response(response.content)

        print("Builder produced refined patches:", refined_patches)

        print("\n\nBuilder_model token usage:", response.usage_metadata)
        
        print("\n\n\n\n")
        # Replace patches in state
        if refined_patches is not None and not isinstance(refined_patches, list) and len(refined_patches) > 0:
            state["acads"]["patches"] = [refined_patches]
        elif refined_patches is not None :    
            state["acads"]["patches"] = refined_patches

        return {"next_node": "save_entry_state"}

    except Exception as e:
        print("Error in builder_model:", e)
        return {"messages":default_msg,"next_node": END}













async def save_entry_state(state: SwarmResumeState, config: RunnableConfig):
    """Parse LLM response and update acads entry state."""
    try:

        # print("Internship State in save_entry_state:", state.get("acads", {}))
        thread_id = config["configurable"]["thread_id"]
        patches = state.get("acads", {}).get("patches", [])
        index = state.get("acads", {}).get("index", None)

        print("patches In save Node:", patches)
        patch_field = [patch["path"] for patch in patches if "path" in patch]

        result = await apply_patches(thread_id, patches)
        
        print("Apply patches result:", result)
        
        if result and result.get("status") == "success":
            print("Entry state updated successfully in Redis.")
            state["acads"]["save_node_response"] = f"patches applied successfully on fields {', '.join(patch_field)}."
            if "index" in result:
                state["acads"]["index"] = result.get("index", index)  # Update index if changed
            state["acads"]["patches"] = []  # Clear patches after successful application
            # print("Internship State after save_entry_state:", state.get("acads", {}))
            
            print("\n\n\n\n")
    except Exception as e:
        print("Error in save_entry_state:", e)
        return {"messages":AIMessage(content="Sorry,Can't process your request now"),"next_node": END}
    
    
    
    
    
    
    
    

# End Node (Runs after save_entry_node)
def End_node(state: SwarmResumeState, config: RunnableConfig):
    """Main chat loop for acads assistant with immediate state updates."""

    try:
        save_node_response = state.get("acads", {}).get("save_node_response", None)
        
        print("End Node - save_node_response:", save_node_response)

        current_entries = state.get("resume_schema", {}).get("academic_projects", [])
        acads_state = state.get("acads", {})
        
    
        # print("Internship State in Model Call:", acads_state)
        
        if isinstance(acads_state, dict):
            acads_state = AcadState.model_validate(acads_state)

        index = getattr(acads_state, "index", None)
        
        
        
        if index is not None and 0 <= index < len(current_entries):
            entry = current_entries[index]
        else:
            entry = None
                
                
        system_prompt = SystemMessage(
        content=dedent(f"""
        You are a human-like POR (Position of Responsibility) Assistant for a Resume Builder.

        Focus on **chat engagement**, not on re-outputting or editing entries. 
        The user already knows what was updated in their POR section.

        Last node message: {save_node_response if save_node_response else "None"}

        --- CURRENT ENTRY IN FOCUS ---
        {entry if entry else "No entry selected."}

        Your responses should be **friendly, warm, and brief**.
        Only ask for additional details if truly needed.
        Occasionally, ask general POR-related questions to keep the conversation flowing 
        (e.g., leadership experiences, event management, team coordination, or impact highlights).

        DO NOT suggest edits, additions, or updates.
        Your goal is to **motivate, appreciate, and encourage** the user to continue refining their resume.
    """)
)


        messages = safe_trim_messages(state["messages"], max_tokens=256)
        # # Include last 3 messages for context (or fewer if less than 3)
        messages = state["messages"]
        
        response = llm.invoke([system_prompt] + messages, config)
        
                
        if save_node_response:
            state["acads"]["save_node_response"] = None  # Clear after using
        

        # Update token counters
        token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
        token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)

        

        
        print("\n\n\n")
        
        print("End Node Response", response.content)
        print("\End Node Token Usage:", response.usage_metadata)
        
        print("\n\n\n\n")
        
   


        return {"messages": [response]}
    except Exception as e:
        print("Error in End_node:", e)
        
        return {"messages":AIMessage(content="Something went worng"),"next_node": END}


    
    
    
# ---------------------------
# 5. Conditional Router
# ---------------------------

def acads_model_router(state: SwarmResumeState):
    last_message = state["messages"][-1]
    # patches = state["acads"]["patches"]
    
    # print("\n\nPatches in Router:-", patches)

    # 1. Go to acads tools if a tool was called
    if getattr(last_message, "tool_calls", None):
        return "tools_acads"

    #  # 2. If there are patches to process, go to query generator
    # if patches and len(patches) > 0:
    #     print("Patches exist, going to query_generator_model")
    #     return "query_generator_model"
    
    # 3. Otherwise continue the chat (stay in acads_model)
    

    
    return END








# ---------------------------
# 6. Create Graph
# ---------------------------

workflow = StateGraph(SwarmResumeState)


# Tool nodes for each model
acads_tools_node = ToolNode(tools)         # For acads_model


# Nodes
workflow.add_node("acads_model", call_acads_model)  
workflow.add_node("query_generator_model", query_generator_model)
workflow.add_node("retriever_node", retriever_node)
workflow.add_node("builder_model", builder_model)
workflow.add_node("save_entry_state", save_entry_state)
workflow.add_node("end_node", End_node)



# Tool Nodes
workflow.add_node("tools_acads", acads_tools_node)




workflow.set_entry_point("acads_model")



# Conditional routing
workflow.add_conditional_edges(
    "acads_model",
    acads_model_router,
    {
        "tools_acads": "tools_acads",          # <- per-model tool node
        # "retriever_model": "retriever_model",
        "acads_model": "acads_model",
        END: END
    }
)




# Edges
# workflow.add_edge("tools_acads", "acads_model")  # return to acads
workflow.add_edge("query_generator_model", "retriever_node")  # return to retriever
workflow.add_edge("retriever_node","builder_model")   # return to builder
workflow.add_edge("builder_model", "save_entry_state")
workflow.add_edge("save_entry_state", "end_node")
workflow.add_edge("end_node",END)



# Compile
acads_assistant = workflow.compile(name="acads_assistant")
acads_assistant.name = "acads_assistant"

