from httpx import patch
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, AIMessage,HumanMessage,FunctionMessage
from langchain_core.runnables import RunnableConfig
from ..llm_model import llm,SwarmResumeState,InternshipState
from models.resume_model import Internship
# from .state import SwarmResumeState
from .tools import tools, fetch_internship_info,transfer_tools
from textwrap import dedent
from utils.safe_trim_msg import safe_trim_messages
from ..utils.common_tools import extract_json_from_response
import assistant.resume.chat.token_count as token_count
import json 
from .functions import apply_patches,update_internship_field,new_query_pdf_knowledge_base,query_tech_handbook
import re
from .mappers import FIELD_MAPPING

# ---------------------------
# 2. LLM with Tools
# ---------------------------


llm_internship = llm.bind_tools([*tools, *transfer_tools])
# llm_internship = llm  # tool can be added if needed
llm_builder = llm  # tool can be added if needed
llm_retriever = llm # tool can be added if needed

default_msg = AIMessage(content="Sorry, I couldn't process that. Could you please retry?")
from langchain.schema import HumanMessage

def queryKb(state: SwarmResumeState, config: RunnableConfig):
    try:
        # find last human message
        last_human_msg = next(
            (msg for msg in reversed(state["messages"]) if isinstance(msg, HumanMessage)),
            None
        )

        if last_human_msg is None:
            return {"next_node": "internship_model"}  # no human message found

        last_msg_content = last_human_msg.content
        # print("Last Human Message =>", last_msg_content)

        # query the tech handbook
        retived_msg = query_tech_handbook(
            query_text=last_msg_content,
            role=["tech"], #role needs to be find from tailoring keys will do later
            n_results=3
        )
        

        state["internship"]["knowledge"] = retived_msg

        print("retrived_msg",state["internship"])
    except Exception as e:
        print("Error querying message:", e)
        return {"messages": [AIMessage(content="Sorry! can you repeat")], "next_node": END}


# main model
def call_internship_model(state: SwarmResumeState, config: RunnableConfig):
    """Main chat loop for internship assistant with immediate state updates."""
    tailoring_keys = config["configurable"].get("tailoring_keys", [])
    current_entries = state.get("resume_schema", {}).get("internships", [])
    internship_state = state.get("internship", {})
    
    tailored_current_entries = [
    (idx, entry.get("company_name"))
    for idx, entry in enumerate(current_entries)
    ]
 
    # print("Internship State in Model Call:", internship_state)
    
    if isinstance(internship_state, dict):
        internship_state = InternshipState.model_validate(internship_state)

    index = getattr(internship_state, "index", None)
    
    
    
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
        current_entry_msg = "No internship entries exist yet."

    print("retrived_msg",state["internship"])
    
#     system_prompt = SystemMessage(
#     content=dedent(f"""
#     You are a **Human like Internship Assistant** for a Resume Builder.
#     Your role: chat naturally, guiding users to refine internship entries with clarity, brevity, and alignment to {tailoring_keys}.
#     Always be supportive, not interrogative. KEEP RESPONSES UNDER 125 WORDS.

#     --- Workflow ---
#     • Gather details conversationally (one clear question at a time). 
#     • Avoid duplicate company names.
#     • Confirm with user only if a change may DELETE existing info.
#     • Once user provides info, IMMEDIATELY use Tool `send_patches` to transmit it. No extra confirmation needed unless deleting or overwriting.
#     • For each internship, aim to get 3 pieces of information: what the user did, the outcome, and its impact.
#     • DO NOT ask about challenges, learnings, or feelings.
#     • Suggest improvements to existing info (better phrasing, more impact, clarity).
#     • Keep each bullet between 90–150 characters.

#     --- Tool Usage ---
#     • `send_patches`: Minimal JSON Patch ops (RFC 6902). Example:
#       [
#         {{ "op": "replace", "path": "/company_name", "value": "Google" }},
#         {{ "op": "add", "path": "/internship_work_description_bullets/-", "value": "Implemented ML pipeline" }}
#       ]
#     • `update_index_and_focus`: Switch focus to another internship entry.
#     • `get_full_internship_entries`: Fetch details for vague references to older entries.
#     • Additional tools for each section are available—call them when the user wants to move sections.

#     --- Schema ---
#     {{company_name, company_description, location, designation, designation_description, duration, internship_work_description_bullets[]}}

#     --- Current Entries (compact) ---
#     {tailored_current_entries if tailored_current_entries else "No entries yet."}

#     --- Current Entry in Focus ---
#     {current_entry_msg}

#     --- Guidelines ---
#     • Be concise, friendly, and professional.
#     • Use action-oriented phrasing.
#     • Apply info immediately via `send_patches`.
#     • Suggest improvements, confirm before deleting/overwriting.
#     • Append one bullet per patch to `/internship_work_description_bullets/-`.
#     """)
# )
    system_prompt = SystemMessage(
    content=dedent(f"""
    You are a **Human-like Internship Assistant** for a Resume Builder.
    Your role: chat naturally, guiding users to refine internship entries with clarity, brevity, and alignment to {tailoring_keys}.
    Always be supportive, not interrogative. KEEP RESPONSES UNDER 125 WORDS.

    --- Workflow ---
    • Gather details conversationally (one clear question at a time).
    • Avoid duplicate company names.
    • Confirm with user only if a change may DELETE existing info.
    • Once user provides info, IMMEDIATELY use Tool `send_patches` to transmit it. No extra confirmation needed unless deleting or overwriting.
    • For each internship, aim to get 3 pieces of information: what the user did, the outcome, and its impact.
    • DO NOT ask about challenges, learnings, or feelings.
    • Suggest improvements to existing info (better phrasing, more impact, clarity).
    • Keep each bullet between 90–150 characters.

    --- Tool Usage ---
    • `send_patches`: Minimal JSON Patch ops (RFC 6902). Example:
      [
        {{ "op": "replace", "path": "/company_name", "value": "Google" }},
        {{ "op": "add", "path": "/internship_work_description_bullets/-", "value": "Implemented ML pipeline" }}
      ]
    • `update_index_and_focus`: Switch focus to another internship entry.
    • `get_full_internship_entries`: Fetch details for vague references to older entries.
    • Additional tools for each section are available—call them when the user wants to move sections.

    --- Schema ---
    {{company_name, company_description, location, designation, designation_description, duration, internship_work_description_bullets[]}}

    --- Current Entries (compact) ---
    {tailored_current_entries if tailored_current_entries else "No entries yet."}

    --- Current Entry in Focus ---
    {current_entry_msg}

    --- Knowledge Guidance (Retrieved Context) ---
    Use the following retrieved examples and suggestions to **inspire and guide** your phrasing:
    {state["internship"]["knowledge"]}

    When suggesting or refining bullets:
    • Draw ideas or structure from the retrieved examples above if they’re relevant.
    • Prioritize quantified outcomes (%, time saved, scalability metrics, etc.).
    • Never copy them verbatim — adapt naturally to the user’s context.
    • If no retrieved content is relevant, proceed as usual.

    --- Guidelines ---
    • Be concise, friendly, and professional.
    • Use action-oriented phrasing.
    • Apply info immediately via `send_patches`.
    • Suggest improvements, confirm before deleting/overwriting.
    • Append one bullet per patch to `/internship_work_description_bullets/-`.
    • Optionally guide users by giving small feedback like:
      “You could quantify this by mentioning requests handled or performance gain.”
    """)
)



    try:
 
        messages = safe_trim_messages(state["messages"], max_tokens=256)
        # messages = safe_trim_messages(state["messages"], max_tokens=512)
        response = llm_internship.invoke([system_prompt] + messages, config)
        
        # print("Internship Response:", response.content)

        # Update token counters
        token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
        token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)

        

        
        if not getattr(state["messages"][-1:], "tool_calls", None):

            print("\n\n\n")
            
       
        
            
            token_count.total_turn_Input_Tokens = 0
            token_count.total_turn_Output_Tokens = 0

        print("internship_model response:", response.content)
        print("Internship Token Usage:", response.usage_metadata)
        
        print("\n\n\n\n")
        
        return {"messages": [response]}
    except Exception as e:
        print("Error in internship_model:", e)
        return {"messages": [AIMessage(content="Sorry! can you repeat")],"next_node": END}















# Query generator for Retriever 
def query_generator_model(state: SwarmResumeState, config: RunnableConfig):
    """Fetch relevant info from knowledge base."""
    # current_entries = state.get("resume_schema", {}).get("internships", [])
    tailoring_keys = config["configurable"].get("tailoring_keys", [])
    patches = state.get("internship", {}).get("patches", [])
   

    prompt = f"""
            You are an expert query generator for a vector database of internship guidelines. 
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

    try:

        # Call the retriever LLM
        response = llm_retriever.invoke(prompt, config)
        
        token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
        token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)
        
        


        print("Query generated:", response)
        if response.content.strip():
            state["internship"]["generated_query"] = str(response.content)
        else:
            state["internship"]["generated_query"] = ""
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
        query = state.get("internship", {}).get("generated_query", [])
        patches = state.get("internship", {}).get("patches", [])

        if not query or (isinstance(query, str) and query.strip() in ("None", "")):
            print("No query generated, skipping retrieval.")
            state["internship"]["retrieved_info"] = []
            return {"next_node": "builder_model"}

       

        all_results = []

        # 🔄 Loop over each query + patch
        for i, patch in enumerate(patches):
            section = "Internship Document Formatting Guidelines"
            patch_field = patch.get("path", "").lstrip("/") 
            patch_field = patch_field.split("/", 1)[0]
            kb_field = FIELD_MAPPING.get(patch_field) 
            
            
            print(f"\n🔍 Running retriever for query {i+1}: on field {patch_field} mapped to KB field {kb_field}")
        
            
            if patch_field == "internship_work_description_bullets":
                retrieved_info = new_query_pdf_knowledge_base(
                query_text=str(query),   # now it's a string
                role=["internship"],
                section=section,
                subsection="Action Verbs (to use in work descriptions)",
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
                role=["internship"],
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
        state["internship"]["retrieved_info"] = all_results
        # state["internship"]["last_query"] = queries
        state["internship"]["generated_query"] = ""  # clear after use

        print("\n✅ Retrieved info saved:", all_results)
        print("\n\n\n\n")

        return {"next_node": "builder_model"}

    except Exception as e:
        print("Error in retriever:", e)
        return {END: END}



















# Builder Model
def builder_model(state: SwarmResumeState, config: RunnableConfig):
    """Refine internship patches using retrieved info."""
    try:
        
        retrieved_info = state.get("internship", {}).get("retrieved_info", "")
        patches = state.get("internship", {}).get("patches", [])
        # print("Patches in Builder :-", patches)
        
        index = state.get("internship", {}).get("index")
        current_entries = state.get("resume_schema", {}).get("internships", [])
        entry = current_entries[index] if index is not None and 0 <= index < len(current_entries) else "New Entry"

        # print("Current Entry in Builder:", entry)

        if not retrieved_info or retrieved_info.strip() in ("None", ""):
            print("No retrieved info available, skipping building.")
            state["messages"].append(SystemMessage(content="No retrieved info available, skipping building."))
            return

        prompt = dedent(f"""You are reviewing internship resume entries using JSON Patches.

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
        if refined_patches is not None and not isinstance(refined_patches, list):
            state["internship"]["patches"] = [refined_patches]
        elif refined_patches is not None :    
            state["internship"]["patches"] = refined_patches

        return {"next_node": "save_entry_state"}

    except Exception as e:
        print("Error in builder_model:", e)
        return {"messages":default_msg,"next_node": END}













async def save_entry_state(state: SwarmResumeState, config: RunnableConfig):
    """Parse LLM response and update internship entry state."""
    try:

        # print("Internship State in save_entry_state:", state.get("internship", {}))
        thread_id = config["configurable"]["thread_id"]
        patches = state.get("internship", {}).get("patches", [])
        index = state.get("internship", {}).get("index", None)

        patch_field = [patch["path"] for patch in patches if "path" in patch]

        result = await apply_patches(thread_id, patches)
        
        print("Apply patches result:", result)
        
        if result and result.get("status") == "success":
            print("Entry state updated successfully in Redis.")
            state["internship"]["save_node_response"] = f"patches applied successfully on fields {', '.join(patch_field)}."
            if "index" in result:
                state["internship"]["index"] = result.get("index", index)  # Update index if changed
            state["internship"]["patches"] = []  # Clear patches after successful application
            # print("Internship State after save_entry_state:", state.get("internship", {}))
            
            print("\n\n\n\n")
    except Exception as e:
        print("Error in save_entry_state:", e)
        return {"messages":AIMessage(content="Sorry,Can't process your request now"),"next_node": END}
    
    
    
    
    
    
    
    

# End Node (Runs after save_entry_node)
def End_node(state: SwarmResumeState, config: RunnableConfig):
    """Main chat loop for internship assistant with immediate state updates."""

    try:
        save_node_response = state.get("internship", {}).get("save_node_response", None)
        
        print("End Node - save_node_response:", save_node_response)

        current_entries = state.get("resume_schema", {}).get("internships", [])
        internship_state = state.get("internship", {})
        
    
        # print("Internship State in Model Call:", internship_state)
        
        if isinstance(internship_state, dict):
            internship_state = InternshipState.model_validate(internship_state)

        index = getattr(internship_state, "index", None)
        
        
        
        if index is not None and 0 <= index < len(current_entries):
            entry = current_entries[index]
        else:
            entry = None
                
                
        system_prompt = SystemMessage(
            content=dedent(f"""
                You are a human-like Internship Assistant for a Resume Builder.

                Focus on **chat engagement**, not on re-outputting or editing entries. 
                The user already knows what was updated in their internship section.

                Last node message: {save_node_response if save_node_response else "None"}

                -- CURRENT ENTRY IN FOCUS --
                {entry if entry else "No entry selected."}

                Your responses should be **friendly, warm, and brief**. 
                Only ask for additional details if truly needed. 
                Occasionally, ask general internship-related questions to keep the conversation flowing. 

                DO NOT suggest edits, additions, or updates. 
                Your goal is to **motivate and encourage the user** to continue working on their resume.
            """)
        )


        # # Include last 3 messages for context (or fewer if less than 3)
        messages = state["messages"]
        
        response = llm.invoke([system_prompt] + messages, config)
        
                
        if save_node_response:
            state["internship"]["save_node_response"] = None  # Clear after using
        

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

def internship_model_router(state: SwarmResumeState):
    last_message = state["messages"][-1]
    # patches = state["internship"]["patches"]
    
    # print("\n\nPatches in Router:-", patches)

    # 1. Go to internship tools if a tool was called
    if getattr(last_message, "tool_calls", None):
        return "tools_internship"

    #  # 2. If there are patches to process, go to query generator
    # if patches and len(patches) > 0:
    #     print("Patches exist, going to query_generator_model")
    #     return "query_generator_model"
    
    # 3. Otherwise continue the chat (stay in internship_model)
    

    
    return END








# ---------------------------
# 6. Create Graph
# ---------------------------

workflow = StateGraph(SwarmResumeState)


# Tool nodes for each model
internship_tools_node = ToolNode([*tools,*transfer_tools])         # For internship_model


# Nodes
workflow.add_node("query_node", queryKb)
workflow.add_node("internship_model", call_internship_model)
workflow.add_node("query_generator_model", query_generator_model)
workflow.add_node("retriever_node", retriever_node)
workflow.add_node("builder_model", builder_model)
workflow.add_node("save_entry_state", save_entry_state)
workflow.add_node("end_node", End_node)



# Tool Nodes
workflow.add_node("tools_internship", internship_tools_node)



# Entry Point
workflow.set_entry_point("query_node")
# workflow.set_entry_point("internship_model")



# Conditional routing
workflow.add_conditional_edges(
    "internship_model",
    internship_model_router,
    {
        "tools_internship": "tools_internship",          # <- per-model tool node
        # "retriever_model": "retriever_model",
        "internship_model": "internship_model",
        END: END
    }
)




# Edges
# workflow.add_edge("tools_internship", "internship_model")  # return to internship
workflow.add_edge("query_node", "internship_model")  # return to retriever
workflow.add_edge("query_generator_model", "retriever_node")  # return to retriever
workflow.add_edge("retriever_node","builder_model")   # return to builder
workflow.add_edge("builder_model", "save_entry_state")
workflow.add_edge("save_entry_state", "end_node")
workflow.add_edge("end_node",END)



# Compile
internship_assistant = workflow.compile(name="internship_assistant")
internship_assistant.name = "internship_assistant"
