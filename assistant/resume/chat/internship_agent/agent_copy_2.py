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
from .functions import apply_patches,update_internship_field,new_query_pdf_knowledge_base
import re
from .mappers import FIELD_MAPPING

# ---------------------------
# 2. LLM with Tools
# ---------------------------


llm_internship = llm.bind_tools([*tools, *transfer_tools])
# llm_internship = llm  # tool can be added if needed
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

    system_prompt = SystemMessage(
    content=dedent(f"""
        You are the **Internship Assistant** for a Resume Builder.
        Your role: Chat with the user to gather and refine internship information.

        --- Tool Usage ---
        • When the user provides info for any schema field, you MUST call `apply_patches` with value that user provide.Don't Call with null or "" values.
        • `apply_patches` accepts ONLY JSON Patch format (RFC 6902).
        • Always generate minimal patches against the current entry which is in focus.
        • Example patch:
          [
            {{ "op": "replace", "path": "/company_name", "value": "Google" }},
            {{ "op": "add", "path": "/internship_work_description_bullets/-", "value": "Implemented ML pipeline" }}
          ]
        • `update_index_and_focus` => use this to change the current entry in focus useful when user wants to update any entry.
        • `get_full_internship_entries` => use this to retrieve all internship entries in full detail,useful when user is referring to specific entries and u are unable to find them.
        
        
        --- Required Schema Fields ---
        {{company_name, company_description, location, designation, designation_description, duration, internship_work_description_bullets (array of strings)}}

        --- Current Entry in Focus (it is visible to user in frontend) ---
        {entry if entry else "No entry selected.You can ask user to select an entry or add a new one."}

        --- Total Entries in Resume (index,company_name) ---
        {tailored_current_entries}
        
        --- Guidelines ---
        • One patch operation per user-provided fact.
        • Use `/field_name` for normal fields, `/internship_work_description_bullets/-` to append bullets.
        • If entry is empty, start with `add` operations.
        • Avoid duplicate entries of company names.
    """)
)


    messages = safe_trim_messages(state["messages"], max_tokens=256)
    # messages = safe_trim_messages(state["messages"], max_tokens=512)
    response = llm_internship.invoke([system_prompt] + messages, config)
    
    # print("Internship Response:", response.content)

    # Update token counters
    token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
    token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)

    token_count.total_turn_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
    token_count.total_turn_Output_Tokens += response.usage_metadata.get("output_tokens", 0)
    
    if not getattr(state["messages"][-1:], "tool_calls", None):

        print("\n\n\n")
        
        print("\nTurn Total Input Tokens:", token_count.total_turn_Input_Tokens)
        print("Turn Total Output Tokens:", token_count.total_turn_Output_Tokens)
        print("\n\n")
        
        token_count.total_turn_Input_Tokens = 0
        token_count.total_turn_Output_Tokens = 0

    print("internship_model response:", response.content)
    print("Internship Token Usage:", response.usage_metadata)
    
    print("\n\n\n\n")
    
    return {"messages": [response]}




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



    # Call the retriever LLM
    response = llm_retriever.invoke(prompt, config)
    
    token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
    token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)
    
    token_count.total_turn_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
    token_count.total_turn_Output_Tokens += response.usage_metadata.get("output_tokens", 0)

    print("Query generated:", response)
    if response.content.strip():
        state["internship"]["generated_query"] = str(response.content)
    else:
        state["internship"]["generated_query"] = ""
        print("Retriever returned empty info")

    print("Query generator Token Usage:", response.usage_metadata)
    print("\n\n\n\n")
    return {"next_node": "builder_model"}



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
            kb_field = FIELD_MAPPING.get(patch_field) 
        
            
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

        prompt = f"""You are refining internship resume entries using JSON Patches.

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
            """


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
        state["internship"]["patches"] = refined_patches

        return {"next_node": "save_entry_state"}

    except Exception as e:
        print("Error in builder_model:", e)
        return {END: END}




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
        return None
    

# End Node (Runs after save_entry_node)
def End_node(state: SwarmResumeState, config: RunnableConfig):
    """Main chat loop for internship assistant with immediate state updates."""

    try:
        save_node_response = state.get("internship", {}).get("save_node_response", None)
        
        print("End Node - save_node_response:", save_node_response)
        
        if save_node_response:
            state["internship"]["save_node_response"] = None  # Clear after using
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
                You are the Internship Assistant for a Resume Builder.

                The user's internship info was just saved on the focused entry. Last node message: {save_node_response if save_node_response else ""}
                
                -- CURRENT ENTRY IN FOCUS --
                {entry if entry else "No entry selected."}

                Reply briefly and warmly. Only ask for more info if needed. Occasionally ask general internship questions to keep the chat engaging.
            """)
        )
        messages = safe_trim_messages(state["messages"], max_tokens=256)
        # Include last 3 messages for context (or fewer if less than 3)
        messages = state["messages"][-7:]
        
        response = llm_replier.invoke([system_prompt] + messages, config)
        

        # Update token counters
        token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
        token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)

        token_count.total_turn_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
        token_count.total_turn_Output_Tokens += response.usage_metadata.get("output_tokens", 0)
        
        print("\n\n\n")
        
        print("End Node Response", response.content)
        print("\nInternship Token Usage:", response.usage_metadata)
        
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
internship_tools_node = ToolNode(tools)         # For internship_model


# Nodes
workflow.add_node("internship_model", call_internship_model)
workflow.add_node("query_generator_model", query_generator_model)
workflow.add_node("retriever_node", retriever_node)
workflow.add_node("builder_model", builder_model)
workflow.add_node("save_entry_state", save_entry_state)
workflow.add_node("end_node", End_node)



# Tool Nodes
workflow.add_node("tools_internship", internship_tools_node)



# Entry Point
# workflow.set_entry_point("end_node")
workflow.set_entry_point("internship_model")



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
workflow.add_edge("query_generator_model", "retriever_node")  # return to retriever
workflow.add_edge("retriever_node","builder_model")   # return to builder
workflow.add_edge("builder_model", "save_entry_state")
workflow.add_edge("save_entry_state", "end_node")
workflow.add_edge("end_node",END)



# Compile
internship_assistant = workflow.compile(name="internship_assistant")
internship_assistant.name = "internship_assistant"
