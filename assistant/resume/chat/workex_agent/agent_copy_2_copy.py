from httpx import patch
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, AIMessage,HumanMessage,FunctionMessage
from langchain_core.runnables import RunnableConfig
from ..llm_model import llm,SwarmResumeState,InternshipState,WorkexState
from models.resume_model import Internship
# from .state import SwarmResumeState
from .tools import tools
from textwrap import dedent
from utils.safe_trim_msg import safe_trim_messages
from ..utils.common_tools import extract_json_from_response
import assistant.resume.chat.token_count as token_count
import json 
from .functions import apply_patches,update_workex_field,new_query_pdf_knowledge_base
import re
from .mappers import FIELD_MAPPING

# ---------------------------
# 2. LLM with Tools
# ---------------------------


llm_workEx = llm.bind_tools(tools)
# llm_workex = llm  # tool can be added if needed
llm_builder = llm  # tool can be added if needed
llm_retriever = llm # tool can be added if needed
llm_replier = llm # tool can be added if needed



# ---------------------------
# 3. State
# ---------------------------

# in file llm_model.py


# ---------------------------
# 4. Node Functions
# ---------------------------

STATIC_SYSTEM_PROMPT = SystemMessage(
    content=dedent("""
    You are a Work Experience Resume Assistant.
    Rules:
    - Be concise, professional, action-oriented.
    - Ask one question at a time; confirm before deletions/overwrites.
    - Apply changes immediately via send_patches.
    - No duplicate company names.
    - Each work experience may have multiple projects.
    - Projects: Ask first if user wants to add a project, then collect project_name, project_description, bullets.
    - Use JSON Patch (RFC 6902) strictly.
    - Chat naturally; do not reveal your role or message transfers.
    Schema:
    WorkExperience: {company_name, company_description, location, designation, designation_description, duration, projects[]}
    Project: {project_name, project_description, description_bullets[]}
    Tools:
    - send_patches, update_index_and_focus, get_full_workex_entries
    """)
)
def workex_model(state: SwarmResumeState, config: RunnableConfig):
    """Main chat loop for workex assistant with immediate state updates."""
    
    tailoring_keys = config["configurable"].get("tailoring_keys", [])
    current_entries = state.get("resume_schema", {}).get("work_experiences", [])
    workex_state = state.get("workex", {})

    if isinstance(workex_state, dict):
        workex_state = WorkexState.model_validate(workex_state)

    index = getattr(workex_state, "index", None)
    entry = current_entries[index] if index is not None and 0 <= index < len(current_entries) else None
    current_entry_msg = entry if entry else ("No entry is currently focused." if current_entries else "No workex entries exist yet.")

    # Dynamic context for this turn (lightweight)
    dynamic_context_prompt = SystemMessage(
        content=dedent(f"""
        Current focus entry: {current_entry_msg}
        Tailoring keys: {tailoring_keys if tailoring_keys else 'None'}
        """)
    )
    

    # Trim conversation history (keep last 2-3 messages)
    recent_messages = safe_trim_messages(state["messages"], max_tokens=256)

    # Invoke LLM: static system prompt + dynamic context + recent messages
    response = llm_workEx.invoke([STATIC_SYSTEM_PROMPT, dynamic_context_prompt] + recent_messages, config)

    # Update token counters
    token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
    token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)
    token_count.total_turn_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
    token_count.total_turn_Output_Tokens += response.usage_metadata.get("output_tokens", 0)

    # Reset per-turn token counters
    if not getattr(state["messages"][-1:], "tool_calls", None):
        token_count.total_turn_Input_Tokens = 0
        token_count.total_turn_Output_Tokens = 0
    
    print("\n\nWorkex_model response:", response.content)
    print("Workex node Token Usage:", response.usage_metadata)
    
    print("\n\n\n\n")

    return {"messages": [response]}


# Query generator for Retriever 
def query_generator_model(state: SwarmResumeState, config: RunnableConfig):
    """Fetch relevant info from knowledge base."""
    # current_entries = state.get("resume_schema", {}).get("workexs", [])
    tailoring_keys = config["configurable"].get("tailoring_keys", [])
    patches = state.get("workex", {}).get("patches", [])
   

    prompt = f"""
            You are an expert query generator for a vector database of Work Experience guidelines. 
            Your goal is to create concise, retrieval-friendly queries to fetch the most relevant 
            guidelines, formatting rules, and suggestions.

            --- Instructions ---
            • Reply ONLY with the generated query as plain text (1–2 sentences max).
            • Focus strictly on the fields listed in 'patched_fields'.
            • Always include:
            - Field name (exactly as in schema).
            - Current field value from patches.
            - Formatting requirements for that field (capitalization, length, structure).
            • If a role/domain is provided (e.g., Tech, Research), include it in the query.
            • Use synonyms and natural phrasing (e.g., guidelines, best practices, format, points) 
            so it matches book-style content.
            • Do not add filler or unrelated information.
            
            --- Patches (only these matter) ---
            {patches}
            
            --- Targeting Role (if any) ---
            {tailoring_keys if tailoring_keys else "None"}
            """



    # Call the retriever LLM
    response = llm_retriever.invoke(prompt, config)
    
    token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
    token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)
    
    token_count.total_turn_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
    token_count.total_turn_Output_Tokens += response.usage_metadata.get("output_tokens", 0)

    print("Query generated:", response)
    if response.content.strip():
        state["workex"]["generated_query"] = str(response.content)
    else:
        state["workex"]["generated_query"] = ""
        print("Retriever returned empty info")

    print("Query generator Token Usage:", response.usage_metadata)
    print("\n\n\n\n")
    return {"next_node": "builder_model"}



# Knowledge Base Retriever
def retriever_node(state: SwarmResumeState, config: RunnableConfig):
    try:
        query = state.get("workex", {}).get("generated_query", [])
        patches = state.get("workex", {}).get("patches", [])

        if not query or (isinstance(query, str) and query.strip() in ("None", "")):
            print("No query generated, skipping retrieval.")
            state["workex"]["retrieved_info"] = []
            return {"next_node": "builder_model"}

       

        all_results = []

        # 🔄 Loop over each query + patch
        for i, patch in enumerate(patches):
            section = "Work Experience Document Formatting Guidelines"
            patch_field = patch.get("path", "").lstrip("/") 
            patch_field = patch_field.split("/", 1)[0]
            kb_field = FIELD_MAPPING.get(patch_field) 
            
            
            print(f"\n🔍 Running retriever for query {i+1}: on field {patch_field} mapped to KB field {kb_field}")
        
            
            if patch_field == "description_Bullets":
                retrieved_info = new_query_pdf_knowledge_base(
                query_text=str(query),   # now it's a string
                role=["workex"],
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

            print

            retrieved_info = new_query_pdf_knowledge_base(
                query_text=str(query),   # now it's a string
                role=["workex"],
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
        state["workex"]["retrieved_info"] = all_results
        # state["workex"]["last_query"] = queries
        state["workex"]["generated_query"] = ""  # clear after use

        print("\n✅ Retrieved info saved:", all_results)
        print("\n\n\n\n")

        return {"next_node": "builder_model"}

    except Exception as e:
        print("Error in retriever:", e)
        return {END: END}



# Builder Model
def builder_model(state: SwarmResumeState, config: RunnableConfig):
    """Refine workex patches using retrieved info."""
    try:
        
        retrieved_info = state.get("workex", {}).get("retrieved_info", "")
        patches = state.get("workex", {}).get("patches", [])
        # print("Patches in Builder :-", patches)
        
        index = state.get("workex", {}).get("index")
        current_entries = state.get("resume_schema", {}).get("workexs", [])
        entry = current_entries[index] if index is not None and 0 <= index < len(current_entries) else "New Entry"

        # print("Current Entry in Builder:", entry)

        if not retrieved_info or retrieved_info.strip() in ("None", ""):
            print("No retrieved info available, skipping building.")
            state["messages"].append(SystemMessage(content="No retrieved info available, skipping building."))
            return

        prompt = dedent(f"""You are refining workex resume entries using JSON Patches.

            ***INSTRUCTIONS:***
            • Respond in **valid JSON array only** (list of patches).
            • Input is the current entry + current patches + retrieved info.
            • Your goal: refine/improve the **values** of the patches using the retrieved info.
            • Keep good fields unchanged (don’t patch unnecessarily).
            • **Do NOT change the 'op' or 'path' of any patch.** Only the 'value' can be updated.
            • Use JSON Patch format strictly:
            - op: must remain exactly as in the input patch ("add", "replace", "remove")
            - path: must remain exactly as in the input patch
            - value: update only if refinement is necessary

            --- Current Entry on which the new patches to be applied ---
            {json.dumps(entry, indent=2)}

            --- Current Patches ---
            {json.dumps(patches, indent=2)}

            --- Retrieved Info ---
            {retrieved_info}
            """)
            
        # messages = safe_trim_messages(state["messages"], max_tokens=256)
        # last_human_msg = next((msg for msg in reversed(messages) if isinstance(msg, HumanMessage)), None)


        response = llm_builder.invoke(prompt, config)
        
        token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
        token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)

        token_count.total_turn_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
        token_count.total_turn_Output_Tokens += response.usage_metadata.get("output_tokens", 0)
        # Extract refined patches from LLM output
        refined_patches = extract_json_from_response(response.content)

        print("Builder produced refined patches:", refined_patches)

        print("\n\nBuilder_model token usage:", response.usage_metadata)
        
        print("\n\n\n\n")
        # Replace patches in state
        state["workex"]["patches"] = refined_patches

        return {"next_node": "save_entry_state"}

    except Exception as e:
        print("Error in builder_model:", e)
        return {END: END}




async def save_entry_state(state: SwarmResumeState, config: RunnableConfig):
    """Parse LLM response and update workex entry state."""
    try:

        # print("Internship State in save_entry_state:", state.get("workex", {}))
        thread_id = config["configurable"]["thread_id"]
        patches = state.get("workex", {}).get("patches", [])
        index = state.get("workex", {}).get("index", None)

        patch_field = [patch["path"] for patch in patches if "path" in patch]

        result = await apply_patches(thread_id, patches)
        
        print("Apply patches result:", result)
        
        if result and result.get("status") == "success":
            print("Entry state updated successfully in Redis.")
            state["workex"]["save_node_response"] = f"patches applied successfully on fields {', '.join(patch_field)}."
            if "index" in result:
                state["workex"]["index"] = result.get("index", index)  # Update index if changed
            state["workex"]["patches"] = []  # Clear patches after successful application
            # print("Internship State after save_entry_state:", state.get("workex", {}))
            
            print("\n\n\n\n")
    except Exception as e:
        print("Error in save_entry_state:", e)
        return None
    

# End Node (Runs after save_entry_node)
def End_node(state: SwarmResumeState, config: RunnableConfig):
    """Main chat loop for workex assistant with immediate state updates."""

    try:
        save_node_response = state.get("workex", {}).get("save_node_response", None)
        
        print("End Node - save_node_response:", save_node_response)

        current_entries = state.get("resume_schema", {}).get("work_experiences", [])
        workex_state = state.get("workex", {})
        
    
        # print("Internship State in Model Call:", workex_state)
        
        if isinstance(workex_state, dict):
            workex_state = WorkexState.model_validate(workex_state)

        index = getattr(workex_state, "index", None)
        
        
        
        if index is not None and 0 <= index < len(current_entries):
            entry = current_entries[index]
        else:
            entry = None
                
                
        system_prompt = SystemMessage(
            content=dedent(f"""
                You are the Workex Assistant for a Resume Builder.

                The user's workex info was just saved on the focused entry. Last node message: {save_node_response if save_node_response else ""}
                
                -- CURRENT ENTRY IN FOCUS --
                {entry if entry else "No entry selected."}

                Reply briefly and warmly. Only ask for more info if needed. Occasionally ask general workex questions to keep the chat engaging.
                
                YOU MUST REPLY A FRIENDLY MSG IN A CONTINUATION OF THE CHAT AND FLOW. 
            """)
        )

        # # Include last 3 messages for context (or fewer if less than 3)
        messages = state["messages"]
        
        # print("\n\n\nMessages in End Node:", messages)
        
        response = llm_replier.invoke([system_prompt] + messages, config)
        
                
        if save_node_response:
            state["workex"]["save_node_response"] = None  # Clear after using
        

        # Update token counters
        token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
        token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)

        token_count.total_turn_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
        token_count.total_turn_Output_Tokens += response.usage_metadata.get("output_tokens", 0)
        
        print("\n\n\n")
        
        print("End Node Response", response.content)
        print("\End Node Token Usage:", response.usage_metadata)
        
        print("\n\n\n\n")
        
        print("\nTurn Total Input Tokens:", token_count.total_turn_Input_Tokens)
        print("Turn Total Output Tokens:", token_count.total_turn_Output_Tokens)
        print("\n\n")
        
        token_count.total_turn_Input_Tokens = 0
        token_count.total_turn_Output_Tokens = 0
    

        return {"messages": [response]}
    except Exception as e:
        
        print("Error in End_node:", e)
        return {END: END}


    
    
    
# ---------------------------
# 5. Conditional Router
# ---------------------------

def workex_model_router(state: SwarmResumeState):
    last_message = state["messages"][-1]
    # patches = state["workex"]["patches"]
    
    # print("\n\nPatches in Router:-", patches)

    # 1. Go to workex tools if a tool was called
    if getattr(last_message, "tool_calls", None):
        return "tools_workex"

    #  # 2. If there are patches to process, go to query generator
    # if patches and len(patches) > 0:
    #     print("Patches exist, going to query_generator_model")
    #     return "query_generator_model"
    
    # 3. Otherwise continue the chat (stay in workex_model)
    

    
    return END




# ---------------------------
# 6. Create Graph
# ---------------------------

workflow = StateGraph(SwarmResumeState)


# Tool nodes for each model
workex_tools_node = ToolNode(tools)         # For workex_model


# Nodes
workflow.add_node("workex_model", workex_model)
workflow.add_node("query_generator_model", query_generator_model)
workflow.add_node("retriever_node", retriever_node)
workflow.add_node("builder_model", builder_model)
workflow.add_node("save_entry_state", save_entry_state)
workflow.add_node("end_node", End_node)



# Tool Nodes
workflow.add_node("tools_workex", workex_tools_node)



# Entry Point
# workflow.set_entry_point("end_node")
workflow.set_entry_point("workex_model")



# Conditional routing
workflow.add_conditional_edges(
    "workex_model",
    workex_model_router,
    {
        "tools_workex": "tools_workex",          # <- per-model tool node
        # "retriever_model": "retriever_model",
        "workex_model": "workex_model",
        END: END
    }
)




# Edges
# workflow.add_edge("tools_workex", "workex_model")  # return to workex
workflow.add_edge("query_generator_model", "retriever_node")  # return to retriever
workflow.add_edge("retriever_node","builder_model")   # return to builder
workflow.add_edge("builder_model", "save_entry_state")
workflow.add_edge("save_entry_state", "end_node")
workflow.add_edge("end_node",END)



# Compile
workex_assistant = workflow.compile(name="workex_assistant")
workex_assistant.name = "workex_assistant"
