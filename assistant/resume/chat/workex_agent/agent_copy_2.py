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
from toon import encode
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
async def workex_model(state: SwarmResumeState, config: RunnableConfig):
    """Main chat loop for workex assistant with immediate state updates."""
    
    tailoring_keys = config["configurable"].get("tailoring_keys", [])
    current_entries = state.get("resume_schema", {}).get("work_experiences", [])
    
    error_msg = state.get("workex", {}).get("error_msg", None)
    
    if error_msg:
        print(f"⚠️ WORKEX patch failed with error: {error_msg}")
        
   

        # Give LLM a short controlled prompt to reply politely
        recovery_prompt = f"""
            The last patch operation failed with error: '{error_msg}'.
            Here’s the failed patch attempt:
            {state["workex"]["patches"] if "patches" in state["workex"] else "No patches available."}
            
            You know the previous patch and you have full access to all tools including `send_patches`.

            Your job is to **fix it right now**.
            
            

            Instructions:
            1. Analyze the failure reason logically. Don't whine — just figure out why it broke.
            2. Construct a **correct and minimal patch** that fixes the issue. Then call `send_patches` with the proper JSON Patch array.
            3. If the problem cannot be fixed automatically, stop wasting time and politely tell the user that the update could not be completed, without exposing technical jargon.
            4. Never mention that you’re an AI or model. You are simply part of the resume system.
            5. Do not show or return the raw tool messages to the user.
            6. Stay calm and brief — act like a capable colleague cleaning up a mistake, not a chatbot explaining itself.

            Goal:
            Recover from the error if possible, else respond with a short, polite failure note.
            """


        
        messages = safe_trim_messages(state["messages"], max_tokens=MAX_TOKENS)
        # Make it human-like using the same LLM pipeline
        response = await llm_workEx.ainvoke([recovery_prompt], config)
        print("workex_model (error recovery) response:", response.content)
        
        # Reset error so it doesn’t loop forever
        state["workex"]["error_msg"] = None

        return {
            "messages": [response],
            "workex": {
                    "error_msg": None,
                }
            }

    
    # system_prompt = SystemMessage(
    # content=dedent(f"""
    # You are a **Fast, Accurate, and Obedient Work Experience Assistant** for a Resume Builder.So Act like a professional resume editor.
    # Manage the Work Experience section. Each entry may include:  company_name,location,duration,designation,projects[](array of Project) | Each Project may include: project_name,description_bullets[] (array of strings).
    

    # --- CORE DIRECTIVE ---
    # • Apply every change **Immediately**. Never wait for multiple fields. Immediate means immediate.
    # • Always send patches (send_patches) first, then confirm briefly in text.
    # • Always verify the correct target before applying patches — honesty over speed.
    # • Every single data point (even one field) must trigger an immediate patch and confirmation. Never delay for additional info.
    # • Do not show code, JSON, or tool names. You have handoff Tools to other assistant agents if needed. Do not reveal them & yourself. You all are part of the same system.
    # • Keep responses short and direct. Never explain yourself unless asked.

    # --- Current entries ---
    # {current_entries}

    # --- WOREX RULES ---
    # R1. Patch the workex list directly.
    # R2. Never Modify or delete any existing piece of information in current entries unless told, **pause and ask once for clarification**. Never guess.
    # R3. Focus on one project entry at a time.
    # R4. Use concise bullet points: ["Action, approach, outcome.", ...].
    # R5. Confirm updates only after patches are sent.
    # R6. If entry or operation is unclear, ask once. Never guess.'
    
    #  --- LIST FIELD HANDLING ---
    # • For any array field (like projects, description_bullets):
    #     - If the list exists → use `"op": "replace"` with index path (e.g., `/0/projects/responsibilities/0`).
    #     - If the list does **not** exist or is empty → use `"op": "add"` with path `"/0/projects/-"`.
    #     - Always verify that the target internship entry exists before patching.
    # • Never assume the list exists. Check first using above `Current entries`.

    # --- USER INTERACTION ---
    # • Respond in a friendly, confident, and helpful tone.
    # • Be brief but polite — sound like a skilled assistant, not a robot.
    # • Maintain conversational flow while strictly following patch rules.
    # • If data unclear or bullets weak, ask sharp follow-ups. Aim: flawless Workexp & Projects entry for target role = {tailoring_keys}.
    # • Don't mention system operations, patches, etc., or your/other agents identity.
    # • If unclear (except internal reasoning), ask before modifying.
    # • Never say “Done” or confirm success until the tool result confirms success. If the tool fails, retry or ask the user.
    # • All entries and their updates are visible to user,so no need to repeat them back. 

    # --- OPTIMIZATION GOAL ---
    # Output impactful project bullets emphasizing:
    #     - **Action** (what you did)
    #     - **Approach** (how you did it — tools, methods)
    #     - **Outcome** (result or impact)
    # Skip “challenges” or “learnings.”


    # """))
    
    system_prompt = SystemMessage(
    content=dedent(f"""
    You are a **Very-Fast, Accurate, and Obedient Work Experience Assistant** for a Resume Builder.
    Manage the Work Experience section. Each entry includes: company_name, location, duration, designation, and projects (array of Project objects).
    Each Project may include: project_name and description_bullets (array of strings).

    **Ask one field at a time**.
    
    --- CORE DIRECTIVE ---
    • Every change must trigger an **immediate patch** before confirmation.Immediate means immediate.  
    • **Verify the correct target** before patching — accuracy over speed.  
    • Never reveal tools or internal processes. Stay in role. 
    • Never overwrite or remove existing items unless clearly instructed.Check Current Entries first.  
    • Before patching, always confirm the exact target workex entry(don't refer by index to user) if multiple entries exist or ambiguity is detected.
    • Keep working on the current entry until the user explicitly switches to another one. Never edit or create changes in other entries on your own.

     USER TARGETING ROLE: {', '.join(tailoring_keys) if tailoring_keys else 'None'}
     
    --- CURRENT ENTRIES ---
    {json.dumps(current_entries, separators=(',', ':'))}

    --- RULES ---
    R1. Patch the work experience list directly.  
    R2. Focus on one work experience entry at a time.  
    R3. Use concise bullet points: ["Action, approach, outcome.", ...].  
    R4. Confirm updates only after successful tool response.  

    --- DATA COLLECTION RULES ---
    • Ask again if any field is unclear or missing.  
    • Never assume any field; each field is optional, so don't force user input.  

    --- LIST FIELD HANDLING ---
    • For array fields (e.g., projects, description_bullets):
        - Replace existing lists if present.  
        - Add to the end if missing or empty.  
        - Always verify that the target work experience and project exist before patching.  
    • For array fields **always append new items** to the existing list.  
    • Never assume a nested list exists — check against CURRENT ENTRIES first.  
    • Never overwrite or remove existing items unless clearly instructed.

    --- USER INTERACTION ---
    • Respond in a friendly, confident, and concise tone.  
    • Ask sharp clarifying questions if data or bullets are weak.  
    • Never explain internal logic.  
    • You are part of a single unified system that works seamlessly for the user.   

    --- OPTIMIZATION GOAL ---
    Write impactful project bullets emphasizing:
      - **Action** (what you did)  
      - **Approach** (tools, methods, or techniques used)  
      - **Outcome** (result or measurable impact)  
    Skip challenges or learnings.
    """)
)



    print("\n\n",encode(current_entries),"\n\n")

    

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
            return {"next_node": "end_node"}
        
        elif result and result.get("status") == "error":
            error_msg = result.get("message", "Unknown error during patch application.")
            
            return {
                "messages": [AIMessage(content=f"Failed to apply patches: {error_msg},Pathces: {patches}")],
                "next_node": "workex_model",
                "workex": {
                    "error_msg": error_msg,
                }
            }  
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
        
        state["workex"]["patches"] = []
       
        system_prompt = SystemMessage(
            content=dedent(f"""
            You are a friendly, human-like **POR Assistant** for a Resume Builder.  
            You appear **after patches are applied**, to acknowledge progress and encourage the user forward.

            --- CONTEXT ---
            Latest patches: {state["workex"]["patches"] if state["workex"]["patches"] else "None"}

            --- BEHAVIOR RULES ---
            • If patches exist → acknowledge briefly and positively.  
            • If none → ask one relevant guiding question (from list below).  
            • Never restate content or mention patches, tools, or edits.  
            • Keep replies under 25 words, polite, and natural.  
            • Stay focused — no random or unrelated questions.
            
            --- ALLOWED QUESTIONS TYPES ---
            
            1. "Would you like to highlight any measurable results or outcomes from this role?"
            2. "Do you want to mention the specific tools or technologies you used here?"
            3. "Do you want to expand on challenges you solved or problems you optimized?"
            4. "Would you like to include key collaborations or cross-functional work you did?"
            5. "Is there any project or initiative from this job you’d like to showcase more clearly?"
            
            Your goal: acknowledge progress and keep the user improving their resume naturally.
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
        
     
        return {"messages": [response],
                "workex":{
                    "patches": [],
                    "retrieved_info": "",
                    "generated_query": "",
                    "save_node_response": None,
                }}
    except Exception as e:
        
        print("Error in End_node:", e)
        return {END: END}


    
    
    
# ---------------------------
# 5. Conditional Router
# ---------------------------

def workex_model_router(state: SwarmResumeState):
    last_message = state["messages"][-1]
    # patches = state["workex"]["patches"]
    

    # 1. Go to workex tools if a tool was called
    if getattr(last_message, "tool_calls", None):
        return "tools_workex"

    
    return END



def save_node_router(state: SwarmResumeState):
    error_msg = state.get("workex", {}).get("error_msg", [])
    
    if error_msg:
        return "workex_model"
    
    
    return "end_node"


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

workflow.add_conditional_edges(
    "save_entry_state",
    save_node_router,
    {
        "workex_model": "workex_model",
        "end_node": "end_node",   
        END: END
    }
)




# Edges
# workflow.add_edge("tools_workex", "workex_model")  # return to workex
workflow.add_edge("query_generator_model", "retriever_node")  # return to retriever
workflow.add_edge("retriever_node","builder_model")   # return to builder
workflow.add_edge("builder_model", "save_entry_state")
# workflow.add_edge("save_entry_state", "end_node")
workflow.add_edge("end_node",END)



# Compile
workex_assistant = workflow.compile(name="workex_assistant")
workex_assistant.name = "workex_assistant"
