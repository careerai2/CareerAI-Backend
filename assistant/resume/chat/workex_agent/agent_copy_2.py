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
from ..utils.common_tools import extract_json_from_response,retrive_entry_from_resume,get_patch_field_and_index
import assistant.resume.chat.token_count as token_count
import json 
from .functions import apply_patches,new_query_pdf_knowledge_base
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


# ---------------------
# INSTRUCTIONS

instruction = {
    "company_name":"Use official registered name only. | Avoid abbreviations unless globally recognized (e.g., IBM). | Apply Title Case. | Example: **Google LLC.**",
    "location":"- Format: **City, Country.** | Example: *Bengaluru, India.*",
    "duration":"- Format: **Month Year – Month Year** or **Month Year – Present.** | Example: *June 2020 – August 2022.*",
    "designation":" Write the exact work title. | Capitalize each word. | Example: **Software Engineering Intern.**",
    "project_name":"Use a concise, descriptive title. | Apply Title Case.  | Example: **Backend API Development.**",

}





# ---------------------------
# 3. State
# ---------------------------

# in file llm_model.py


# ---------------------------
# 4. Node Functions
# ---------------------------

MAX_TOKENS = 350

# main model
def workex_model(state: SwarmResumeState, config: RunnableConfig):
    """Main chat loop for workex assistant with immediate state updates."""
    
    tailoring_keys = config["configurable"].get("tailoring_keys", [])
    current_entries = state.get("resume_schema", {}).get("work_experiences", [])
    

    
    system_prompt = SystemMessage(
    content=dedent(f"""
        You are a Human like Work Experience Assistant for a Resume Builder.
        Your role: Help users add and modify their work experience section in the resume **(Current entries provided to You so start accordingly)** & also help refine and optimize the Work Experience section with precision, brevity, and tailoring.

        --- Workflow ---
        • Ask one clear, single-step question at a time.
        • **Always immediately apply any user-provided information using send_patches. Do not wait for confirmation, except when deleting or overwriting existing entries. This must never be skipped.**
        • Use tools as needed, refer their description to know what they do.
        • Never reveal your identity or the identity of any other agent. Do not mention being an AI, model, or assistant. If a transfer or handoff is required, perform it silently without notifying or asking the user. Always behave as a human assistant..
        • **While generating patches for project description bullets, remember that description_bullets is an array of strings like ["", ""] so create your patches accordingly.**
        • Always apply patches directly to the entire work experience section (list) — not individual sub-fields — unless a specific project update is needed.
        • Keep outputs concise (~60–70 words max).
        • For each work experience, aim to get: the user’s role, the work done or project details, outcomes, and their impact.
        • DO NOT ask about challenges, learnings, or feelings.
        • The send_patches first will validate your generated patches; if patches are not fine, it will respond with an error, so you should retry generating correct patches or ask the user for clarification before proceeding.
        • If you are confident about new updates, you can apply them directly without asking for confirmation.

        --- Schema ---
        {{
            company_name,
            location,
            duration,
            designation,
            projects: [{{project_name,description_bullets[]}}]
        }}

        --- Current Entries (It is visible to Human) ---
        Always use the following as reference when updating work experiences:
        {current_entries}

        --- Guidelines ---
        Always use correct indexes for the work experience and its projects.
        Focus on clarity, brevity, and alignment with {tailoring_keys}.
         • Resume updates are **auto-previewed** — **never show raw code or JSON changes**.  
           - The **current entries are already visible to the user**, so you should **not restate them** and must keep that in mind when asking questions or making changes.

    """))




    

    messages = safe_trim_messages(state["messages"], max_tokens=MAX_TOKENS )
    # messages = safe_trim_messages(state["messages"], max_tokens=512)
    response = llm_workEx.invoke([system_prompt] + messages, config)
    
    # print("Internship Response:", response.content)

    # Update token counters
    token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
    token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)

    
    if not getattr(state["messages"][-1:], "tool_calls", None):

        print("\n\n\n")
        
        print("\nTurn Total Input Tokens:", token_count.total_turn_Input_Tokens)
        print("Turn Total Output Tokens:", token_count.total_turn_Output_Tokens)
        print("\n\n")
  
    print("Workex_model response:", response.content)
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

   
        # 🔄 Loop over each query + patch
        unique_fields = set()
        for patch in patches:
            
            if patch.get("op") in ("remove", "delete"):
                continue
            _, patch_field, _ = get_patch_field_and_index(patch.get("path", ""))
            unique_fields.add(patch_field)

        print(f"\n🧠 Unique fields to fetch: {unique_fields}\n")

        all_results = []
        section = "Work Experience Document Formatting Guidelines"

        for field in unique_fields:
            kb_field = FIELD_MAPPING.get(field)
            print(f"Fetching KB info for field: {field} -> KB field: {kb_field}")

            if field == "responsibilities":
                # Fetch action verbs
                action_verbs_info = new_query_pdf_knowledge_base(
                    query_text=str(query),
                    role=["por"],
                    section=section,
                    subsection="Action Verbs (to use in description bullets)",
                    field=kb_field,
                    n_results=5,
                    debug=False
                )
                all_results.append(f"[Action Verbs] => {action_verbs_info}")

                # Fetch schema rules
                schema_info = new_query_pdf_knowledge_base(
                    query_text=str(query),
                    role=["por"],
                    section=section,
                    subsection="Schema Requirements & Formatting Rules",
                    field=kb_field,
                    n_results=5,
                    debug=False
                )
                all_results.append(f"[{field}] {schema_info}")

            else:
                retrieved_info = instruction.get(field, '')
                all_results.append(f"[{field}] {retrieved_info}")
                

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
        
        # index = state.get("workex", {}).get("index")
        # current_entries = state.get("resume_schema", {}).get("workexs", [])
        # entry = current_entries[index] if index is not None and 0 <= index < len(current_entries) else "New Entry"

        # print("Current Entry in Builder:", entry)

        if not retrieved_info or retrieved_info.strip() in ("None", ""):
            print("No retrieved info available, skipping building.")
            state["messages"].append(SystemMessage(content="No retrieved info available, skipping building."))
            return

        prompt = f"""
        You are a professional Work Experiences resume builder.

        ***INSTRUCTIONS:***
        1. Treat the incoming JSON Patch values as the **source of truth**. Do NOT change their meaning. It will be applied directly to the current entries.
        2. Your task is to **refine formatting and style** only before it gets applied. Based on the retrieved guidelines, improve phrasing, clarity, and impact of the patch values, but do not change their truth.
        3. Do NOT replace, remove, or add values outside the incoming patch.
        4. Do NOT change patch paths or operations.
        5. Return strictly a **valid JSON Patch array** (RFC6902). No explanations or extra text.

        ***GUIDELINES REFERENCE:***
        {retrieved_info}


        ***INCOMING PATCHES:***
        {patches}
        """
            
        # messages = safe_trim_messages(state["messages"], max_tokens=MAX_TOKENS )
        # last_human_msg = next((msg for msg in reversed(messages) if isinstance(msg, HumanMessage)), None)


        response = llm_builder.invoke(prompt, config)
        
        token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
        token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)

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
            
            print("\n\n\n\n")
    except Exception as e:
        print("Error in save_entry_state:", e)
        return None
    

# End Node (Runs after save_entry_node)
async def End_node(state: SwarmResumeState, config: RunnableConfig):
    """Main chat loop for workex assistant with immediate state updates."""

    try:
        # thread_id = config["configurable"]["thread_id"]
        save_node_response = state.get("workex", {}).get("save_node_response", None)
        
        print("End Node - save_node_response:", save_node_response)
        
        # updated_workexs = await retrive_entry_from_resume(thread_id,"work_experiences")

       
        system_prompt = SystemMessage(
            content=dedent(f"""
            You are a tail of a human-like Worex Assistant for a Resume Builder.

            Focus solely on engaging the user in a supportive, professional, and encouraging manner. 
            Do not repeat, edit, or reference any work experience entries, projects, or technical details.

            Last node message: {save_node_response if save_node_response else "None"}

            --- Guidelines for this node ---
            • Be warm, concise, and positive.
            • DO NOT ask about rewards, challenges, learnings, or feelings.
            • Only request more details if absolutely necessary.
            • Occasionally ask general, open-ended questions about work experiences or professional growth to keep the conversation natural.
            • Never mention patches, edits, or technical updates—simply acknowledge the last node response if relevant.
            • Your primary goal is to motivate and encourage the user to continue improving their resume and highlight impactful experiences.
        """)
        )


        # # Include last 3 messages for context (or fewer if less than 3)
        
        messages = safe_trim_messages(state["messages"], max_tokens=MAX_TOKENS)
        
        response = llm_replier.invoke([system_prompt] + messages, config)
        
                
        if save_node_response:
            state["workex"]["save_node_response"] = None  # Clear after using
        

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
