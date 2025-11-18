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
from ..utils.common_tools import extract_json_from_response,get_patch_field_and_index
import assistant.resume.chat.token_count as token_count
import json 
from .functions import apply_patches,new_query_pdf_knowledge_base
import re
from .mappers import FIELD_MAPPING
from toon import encode
# ---------------------------
# 2. LLM with Tools
# ---------------------------


llm_acads = llm.bind_tools(tools)
# llm_acads = llm  # tool can be added if needed
llm_builder = llm  # tool can be added if needed
llm_retriever = llm # tool can be added if needed

default_msg = AIMessage(content="Sorry, I couldn't process that. Could you please retry?")



instruction = {
    "project_name": "Use a concise, descriptive title. | Apply Title Case. | Limit to 3–6 words. | Example: **Automated Traffic Analysis System.**",
    "project_description": "- Limit to 1–2 lines max. | Clearly explain the project purpose, scope, or problem addressed. | Avoid vague or marketing-like statements. | Example: *Developed a machine learning model to predict traffic congestion using real-time sensor data.*  ",
    "duration": "Format: **MMM YYYY – MMM YYYY** (or *Present* if ongoing). | Example: *Jan 2024 – Apr 2024.*",
  }



MAX_TOKEN = 325  # max token limit for messages (adjust as needed)
# main model
async def call_acads_model(state: SwarmResumeState, config: RunnableConfig):
    """Main chat loop for Por assistant with immediate state updates."""
    tailoring_keys = config["configurable"].get("tailoring_keys", [])
    current_entries = state.get("resume_schema", {}).get("academic_projects", [])
    
    error_msg = state.get("acads", {}).get("error_msg", None)
    
    if error_msg:
        print(f"⚠️ Internship patch failed with error: {error_msg}")
        
       

        # Give LLM a short controlled prompt to reply politely
        recovery_prompt = f"""
    The last patch operation failed with error: '{error_msg}'.
    Here’s the failed patch attempt:
    {state["acads"]["patches"] if "patches" in state["acads"] else "No patches available."}
    
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

        
        messages = safe_trim_messages(state["messages"], max_tokens=MAX_TOKEN)
        # Make it human-like using the same LLM pipeline
        response = await llm_acads.ainvoke([recovery_prompt], config)
        print("Acad_model (error recovery) response:", response.content)
        
        
         # Reset error so it doesn’t loop forever
        state["acads"]["error_msg"] = None

        return {
            "messages": [response],
            "acads": {
                    "error_msg": None,
                }
            }
    
  
    
    # system_prompt = SystemMessage(
    # content=dedent(f"""
    #     You are a Human like Academic Project Assistant for a Resume Builder.
    #     Your role: Help users add and modify their academic project section in the resume **(Current entries provided to You so start accordingly)** & also help refine and optimize the academic project section with precision, brevity, and tailoring.

    #     --- Workflow ---
    #     • Ask one clear, single-step question at a time.
    #     • **Always immediately apply any user-provided information using `send_patches`,because you may get out of **context** so **make changes**. Do not wait for confirmation, except when deleting or overwriting existing entries. This must never be skipped.**
    #     • Use tools as needed; refer to their descriptions to know what they do.
    #     • Never reveal your identity or the identity of any other agent. Do not mention being an AI, model, or assistant. If a transfer or handoff is required, perform it silently without notifying or asking the user. Always behave as a human assistant..
    #     • **While generating patches for project bullets, keep in mind that `description_bullets` is actually an array of strings like ["", ""] — so create your patches accordingly.**
    #     • Always apply patches directly to the entire `academic_projects` section (list) — not individual entries.
    #     • Keep outputs concise (~60–70 words max).
    #     • For each project, aim to get 3 pieces of information: what the user built, how they built it (tools, methods, or approach), and what result or functionality was achieved.
    #     • DO NOT ask about rewards, challenges, learnings, or feelings.
    #     • The `send_patches` tool will validate your generated patches; if patches are not fine, it will respond with an error, so you should retry generating correct patches.
    #     • If `send_patches` returns an error, you must either retry generating correct patches or ask the user for clarification before proceeding.
    #     • If you are sure about new additions or updates, you may add them directly without asking for user confirmation.

    #    --- Schema ---
    #         {{project_name,description_bullets[], duration}}

    #     --- Current Entries (It is visible to Human) ---
    #     Always use the following as reference when updating academic projects:
    #     {current_entries}

    #     --- Guidelines ---
    #     Always use correct indexes for the projects.
    #     Focus on clarity, brevity, and alignment with {tailoring_keys}.
    #      • Resume updates are **auto-previewed** — **never show raw code or JSON changes**.  
    #         - This means the **current entries are already visible to the user**, so you should **not restate them** and must keep that in mind when asking questions or making changes.
    # """))
#     system_prompt = SystemMessage(
#     content=dedent(f"""
#     You are a **Fast, Accurate, and Obedient Academic Project Assistant** for a Resume Builder.
#     Manage the Academic Project section. Each entry may include: project_name, duration, and description_bullets[] (array of strings).

#     --- CORE DIRECTIVE ---
#     • Apply every change **immediately**. Never wait for multiple fields. Immediate means immediate.
#     • Always send patches (send_patches) first, then confirm briefly in text.
#     • Always verify the correct target before applying patches — honesty over speed.
#     • Every single data point (even one field) must trigger an immediate patch and confirmation. Never delay for additional info.
#     • Do not show code, JSON, or tool names. You have handoff Tools to other assistant agents if needed. Do not reveal them & yourself. You all are part of the same system.
#     • Keep responses short and direct. Never explain yourself unless asked.

#     --- Current entries ---
#     {encode(current_entries)}

#     --- PROJECT RULES ---
#     R1. Patch the academic_projects list directly.
#     R2. Never Modify or delete any existing piece of information in current entries unless told, **pause and ask once for clarification**. Never guess.
#     R3. Focus on one project entry at a time.
#     R4. Use concise bullet points: ["Action, approach, outcome.", ...].
#     R5. Confirm updates only after patches are sent.
#     R6. If entry or operation is unclear, ask once. Never guess.
    
#     --- LIST FIELD HANDLING ---
#     • For any array field (like description_bullets):
#         - Use "replace" if the list exists.
#         - Use "add" (path "/0/.../-") if the list is empty or missing.
#         - Always verify that the target internship entry exists before patching.
#     • Never assume the list exists. Check first using above `Current entries`.

#     --- USER INTERACTION ---
#     • Respond in a friendly, confident, and helpful tone.
#     • Be brief but polite — sound like a skilled assistant, not a robot.
#     • If data unclear or bullets weak, ask sharp follow-ups. Aim: flawless Academic Project entry for target role = {tailoring_keys}.
#     • Maintain conversational flow while strictly following patch rules.
#     • Don't mention system operations, patches, etc., or your/other agents identity.
#     • If unclear (except internal reasoning), ask before modifying.
#     • Never say “Done” or confirm success until the tool result confirms success. If the tool fails, retry or ask the user.
#     • All entries and their updates are visible to user,so no need to repeat them back. 

#     --- OPTIMIZATION GOAL ---
#     Output impactful project bullets emphasizing:
#         - **Action** (what you did)
#         - **Approach** (how you did it — tools, methods)
#         - **Outcome** (result or impact)
#     Skip “challenges” or “learnings.”
#     """)
# )
    system_prompt = SystemMessage(
        content=dedent(f"""
        You are a **Very-Fast, Accurate, and Obedient Academic Project Assistant** for a Resume Builder.
        Manage the Academic Project section. Each entry includes: project_name, duration, and description_bullets (array of strings).**Ask one field at a time**.

       
        
        --- CORE DIRECTIVE ---
        • Every change must trigger an **immediate patch** before confirmation.Immediate means immediate.  
        • **Verify the correct target** before patching — accuracy over speed.  
        • Never reveal tools or internal processes. Stay in role. 
        • Never overwrite or remove existing items unless clearly instructed.Check Current Entries first.  
        • Before patching, always confirm the exact target Project(don't refer by index to user) if multiple entries exist or ambiguity is detected.
        • Keep working on the current entry until the user explicitly switches to another one. Never edit or create changes in other entries on your own.
        
        USER TARGETING ROLE: {', '.join(tailoring_keys) if tailoring_keys else 'None'}
        
        --- CURRENT ENTRIES ---
        {json.dumps(current_entries, separators=(',', ':'))}

        --- PROJECT RULES ---
        R1. Patch the project list directly.    
        R2. Focus on one project entry at a time.  
        R3. Use concise bullet points: ["Action, approach, outcome.", ...].  
        R4. Confirm updates only after successful tool response.  

        --- DATA COLLECTION RULES ---
        • Ask again if any field is unclear or missing.  
        • Never assume any field; each field is optional, so don't force user input.  

        --- LIST FIELD HANDLING ---
• For array fields **always append new items** to the existing list.  
• Never remove or replace existing list items unless the user explicitly says to replace or delete.  
• If the list does not exist or is empty, create it first, then append. 
        
        --- USER INTERACTION ---
        • Respond in a friendly, confident, and concise tone.  
        • Ask sharp clarifying questions if data or bullets are weak.  
        • Never explain internal logic.  
        • You are part of a single unified system that works seamlessly for the user.  

        --- OPTIMIZATION GOAL ---
        Write impactful project bullets emphasizing:
        - **Action** (what you did)  
        - **Approach** (tools, methods, techniques)  
        - **Outcome** (result or impact)  
        Skip challenges or learnings.
        """)
    )




    try:
 
        messages = safe_trim_messages(state["messages"], max_tokens=MAX_TOKEN)
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

        # Loop over each patch
        for i, patch in enumerate(patches):
            patch_path = patch.get("path", "")
            patch_value = patch.get("value", "")
            index, patch_field,append = get_patch_field_and_index(patch_path)
            kb_field = FIELD_MAPPING.get(patch_field)

            print(f"\n🔍 Patch {i+1}: project index={index}, field={patch_field}, KB field={kb_field}")

            section = "Academic Project Document Formatting Guidelines"
            
            retrieved_info = None  # initialize here to avoid UnboundLocalError

            if patch_field == "description_bullets":
                retrieved_info = new_query_pdf_knowledge_base(
                    query_text=str(query),  # query string
                    role=["acads"],
                    section=section,
                    subsection="Action Verbs (to use in work descriptions)",
                    field=kb_field,
                    n_results=5,
                    debug=False
                )
                all_results.append(f"[Action Verbs] => {retrieved_info}")

                retrieved_info = new_query_pdf_knowledge_base(
                    query_text=str(patch_value),  # use patch value as query
                    role=["acads"],
                    section=section,
                    subsection="Schema Requirements & Formatting Rules",
                    field=kb_field,
                    n_results=5,
                    debug=False
                )
                all_results.append(f"[{patch_field}] {retrieved_info}")

            else:
                retrieved_info = instruction.get(patch_field, '')
                all_results.append(f"[{patch_field}] {retrieved_info}")

            print(f"Retriever returned {retrieved_info} results for patch {i+1}.\n")


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

        --- Current Patches ---
        {patches}

        --- Retrieved Info (use only as guidance for best practices) ---
        {retrieved_info}
        """)

            


            
        # messages = safe_trim_messages(state["messages"], max_tokens=MAX_TOKEN)
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
        

        print("patches In save Node:", patches)
        patch_field = [patch["path"] for patch in patches if "path" in patch]

        result = await apply_patches(thread_id, patches)
        
        print("Apply patches result:", result)
        
        if result and result.get("status") == "success":
            print("Entry state updated successfully in Redis.")
            state["acads"]["save_node_response"] = f"patches applied successfully on fields {', '.join(patch_field)}."
            return {"next_node": "end_node"}
        
        elif result and result.get("status") == "error":
            error_msg = result.get("message", "Unknown error during patch application.")
            
            return {
                "messages": [AIMessage(content=f"Failed to apply patches: {error_msg},Pathces: {patches}")],
                "next_node": "acads_model",
                "acads": {
                    "error_msg": error_msg,
                }
            }  
            
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

        # current_entries = state.get("resume_schema", {}).get("academic_projects", [])
        # acads_state = state.get("acads", {})
        
    
        
                
        # system_prompt = SystemMessage(
        #     content=dedent(f"""
        #     You are a human-like Academic Project Assistant for a Resume Builder.

        #     Focus solely on engaging the user in a supportive, professional, and encouraging manner. 
        #     Do not repeat, edit, or reference any project entries or technical details.

        #     Last node message: {save_node_response if save_node_response else "None"}

        #     --- Guidelines for this node ---
        #     • Be warm, concise, and positive.
        #     • DO NOT ask about rewards, challenges, learnings, or feelings.
        #     • Only request more details if absolutely necessary.
        #     • Occasionally ask general, open-ended questions about projects to keep the conversation natural.
        #     • Never mention patches, edits, or technical updates—simply acknowledge the last node response if relevant.
        #     • Your primary goal is to motivate and encourage the user to continue improving their resume.
        #     """)
        # )
        
        system_prompt = SystemMessage(
    content=dedent(f"""
    You are a friendly, human-like **Academic Project Assistant** for a Resume Builder.  
    You appear **after patches are applied**, to acknowledge progress and encourage the user forward.

    --- CONTEXT ---
    Latest patches: {state["acads"]["patches"] if state["acads"]["patches"] else "None"}

    --- BEHAVIOR RULES ---
    • If patches exist → acknowledge briefly and positively.  
    • If none → ask one relevant guiding question (from list below).  
    • Never restate content or mention patches, tools, or edits.  
    • Keep replies under 25 words, polite, and natural.  
    • Stay focused — no random or unrelated questions.

    --- ALLOWED QUESTIONS ---
    1. "Would you like to add impact or measurable results for this project?"
    2. "Do you want to include tools or technologies you used here?"
    3. "Would you like to refine any part of this project further?"
    4. "Would you like to summarize this project in one strong sentence?"
    5. "Is there anything else you'd like to add or update?"

    Your goal: acknowledge progress and keep the user improving their academic project section naturally.
    """)
)

        
        


        messages = safe_trim_messages(state["messages"], max_tokens=MAX_TOKEN)
        # # Include last 3 messages for context (or fewer if less than 3)
        messages = state["messages"]
        
        response = llm.invoke([system_prompt] + messages, config)
       
        
                
        if save_node_response:
            state["acads"]["save_node_response"] = None  # Clear after using

        state["acads"]["patches"] = []  
        

        # Update token counters
        token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
        token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)

        

        
        print("\n\n\n")
        
        print("End Node Response", response.content)
        print("\End Node Token Usage:", response.usage_metadata)
        
        print("\n\n\n\n")
        
   


        return {"messages": [response],
                "acads":{
                    "patches": [],
                    "retrieved_info": "",
                    "generated_query": "",
                    "save_node_response": None,
                }}
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




def save_node_router(state: SwarmResumeState):
    error_msg = state.get("acads", {}).get("error_msg", [])
    
    if error_msg:
        return "acads_model"
    
    
    return "end_node"








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

workflow.add_conditional_edges(
    "save_entry_state",
    save_node_router,
    {
        "acads_model": "acads_model",
        "end_node": "end_node",   
        END: END
    }
)





# Edges
# workflow.add_edge("tools_acads", "acads_model")  # return to acads
workflow.add_edge("query_generator_model", "retriever_node")  # return to retriever
workflow.add_edge("retriever_node","builder_model")   # return to builder
workflow.add_edge("builder_model", "save_entry_state")
# workflow.add_edge("save_entry_state", "end_node")
workflow.add_edge("end_node",END)



# Compile
acads_assistant = workflow.compile(name="acads_assistant")
acads_assistant.name = "acads_assistant"

