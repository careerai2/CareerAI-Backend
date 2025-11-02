from httpx import patch
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, AIMessage,HumanMessage,FunctionMessage
from langchain_core.runnables import RunnableConfig
from ..llm_model import llm,SwarmResumeState,InternshipState
from models.resume_model import Internship
# from .state import SwarmResumeState
from .tools import tools, fetch_internship_info,transfer_tools,send_patches
from textwrap import dedent
from utils.safe_trim_msg import safe_trim_messages
from ..utils.common_tools import extract_json_from_response,get_patch_field_and_index
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
llm_error_handler = llm.bind_tools(tools)  # tool can be added if needed
llm_builder = llm  # tool can be added if needed
llm_retriever = llm # tool can be added if needed

default_msg = AIMessage(content="Sorry, I couldn't process that. Could you please retry?")


instruction = {
    "company_name": "Use official registered name only. | Avoid abbreviations unless globally recognized (e.g., IBM). | Apply Title Case. | Example: **Google LLC.**",
    "location": "Format: **City, Country.** | Example: *Bengaluru, India.*",
    "designation": "Write the exact internship title. | Capitalize each word. | Example: **Software Engineering Intern.**",
    "duration": "Format: **MMM YYYY – MMM YYYY** (or *Present* if ongoing). | Example: *Jun 2024 – Aug 2024.*",
    "company_description": "",
    "designation_description": ""
  }

MAX_TOKENS = 350

# main model
async def call_internship_model(state: SwarmResumeState, config: RunnableConfig):
    """Main chat loop for internship assistant with immediate state updates."""
    tailoring_keys = config["configurable"].get("tailoring_keys", [])
    current_entries = state.get("resume_schema", {}).get("internships", [])
    
    # save_node_response = state.get("internship", {}).get("save_node_response", None)
    
    error_msg = state.get("internship", {}).get("error_msg", None)
    
    if error_msg:
        print(f"⚠️ Internship patch failed with error: {error_msg}")
        
   

        # Give LLM a short controlled prompt to reply politely
        recovery_prompt = f"""
            The last internship patch operation failed with: '{error_msg}'.
            You have access to all tools, including send_patches.

            Rules for your response:
            1. Try to fix the issue automatically using the available tools (e.g., retry sending the patch).
            2. If automatic recovery is not possible, politely inform the user about the failure without revealing internal or technical details.
            3. Do NOT mention your identity, the identity of other agents, or that you are an AI/model/assistant.
            4. If a transfer or handoff is needed, perform it silently; do not notify or ask the user.
            5. Keep the response concise, polite, and human-like.
            
            **Don't ever return the ToolMessage to user direclty**
            """

        
        messages = safe_trim_messages(state["messages"], max_tokens=MAX_TOKENS)
        # Make it human-like using the same LLM pipeline
        response = await llm_internship.ainvoke([recovery_prompt], config)
        print("internship_model (error recovery) response:", response.content)
        
        # Reset error so it doesn’t loop forever
        state["internship"]["error_msg"] = None

        return {
            "messages": [response],
            "internship": {
                    "error_msg": None,
                }
            }
 

    print("Current Entries in Internship Model:", current_entries)

    # system_prompt = SystemMessage(
    # content=dedent(f"""
    #     You are a Human like Internship Assistant for a Resume Builder.
    #     Your role: Help users add and modify their internship section in the resume **(Current entries provided to You so start accordingly)** & also help in refine and optimize the Internship section with Focus on clarity, brevity, and alignment with {tailoring_keys}.
        
        
    #     --- MUST TO OBEY ---
    #     • Any information provided by user regarding internship must added **IMMEDIATELY** using send_patch tool.
    #     • Always respond in **Human-Readable text**, never ever in raw code,markdown or JSON.
    #     • Current entries are already visible to the user, so avoid restating them when asking questions or applying changes.
    #     • Never reveal your identity or the identity of any other agent. Do not mention being an AI, model, or assistant. If a transfer or handoff is required, perform it silently without notifying or asking the user.
    #     • Always apply patches directly to the entire internship section (list) — not individual entries — .
    #     • - **ToolMessages** are strictly for internal communication. Do **not** expose or send them to the user directly.  
            

        
    #     --- Workflow ---
    #     • Ask one clear, single-step question at a time.
    #     • If unclear about add or update just confirm with user.Don't make assumptions.
    #     • Use tools as needed, refer their description to know what they do.
    #     • **While generating patches for internship bullets, keep in mind that the bullets is actually an array of strings like ["",""] so create your patches accordingly*
    #     • Keep your response to user concise (~60–70 words max) .
    #     • For each internship, aim to get 3 pieces of information: what the user did, the outcome, and its impact.
    #     • DO NOT ask about challenges, learnings, or feelings.
        

    #     --- Schema ---
    #     {{company_name,location, designation,duration, internship_work_description_bullets[]}}

    #     --- Current Entries (Auto-previewed to user) ---
    #     {current_entries}
        
    #     --- PATCH Example ---
    #      Example patch:
    # [
    #     {{"op": "replace", "path": "/0/company_name", "value": "CareerAi"}},
    #     {{"op": "replace", "path": "/1/role", "value": "Software Intern"}},
    #     {{"op": "add", "path": "/-", "value": {{"company_name": "OpenAI", "role": "ML Intern"}}}}
    # ]
    


    # """))
    system_prompt = SystemMessage(
    content=dedent(f"""
    You are an Internship Assistant for a Resume Builder.
        Your primary role is to help users add, modify, and optimize the Internship section of their resume.

        --- 🛑 ABSOLUTE GUARDRAIL ---
        **NEVER output raw code, JSON, Markdown blocks, tool-call syntax, or system messages to the user.** All tool usage and internal operations are strictly for system communication and must remain invisible to the user. Do not mention your identity or being an assistant.

        --- 🎯 CORE DIRECTIVE: IMMEDIATE PATCHING ---
        **R1. IMMEDIATE ACTION:** If the user provides ANY new or modified internship information, you **MUST** immediately generate and execute the `send_patch` tool call. Do this *before* generating any user-facing text.
        **R2. PATCH SCOPE:** Always apply patches directly to the entire internship section (list) — not individual entries.
        **R3. BULLET FORMAT:** When patching bullets, remember that `internship_work_description_bullets` is an array of strings like `["Action, outcome, impact.", "Next point."]`

        --- 🗣️ USER INTERACTION RULES ---
        * **Response Style:** Always respond in **Human-Readable text**.
        * **Brevity:** Keep your responses concise and focused (aim for 2-3 short sentences max).
        * **State Awareness:** Current entries are visible to the user; do not list, summarize, or explicitly confirm existing entries when asking for new information.
        * **Question Strategy:** Ask one clear, single-step question at a time.
        * **Clarity:** If the user's intent is ambiguous (add or update), ask for confirmation before patching.

        --- 📝 OPTIMIZATION GOAL ---
        For each internship, aim to gather and refine bullets based on the 'Action, Outcome, Impact' structure. Specifically, ask questions to get:
        1.  What the user **did** (Action).
        2.  The resulting **achievement** or **metric** (Outcome).
        3.  The **significance** or **benefit** (Impact).
        * DO NOT ask about challenges, learnings, or feelings.

        --- SCHEMA ---
        {{company_name, location, designation, duration, internship_work_description_bullets[]}}

        --- Current Entries (Auto-previewed to user) ---
        {current_entries}

    """))
    
    


    try:
 
        messages = safe_trim_messages(state["messages"], max_tokens=MAX_TOKENS)
        # messages = safe_trim_messages(state["messages"], max_tokens=512)
        response =  llm_internship.invoke([system_prompt] + messages, config)
        
        # print("Internship Response:", response.content)

        # Update token counters
        token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
        token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)

        

        
        if not getattr(state["messages"][-1:], "tool_calls", None):

            print("\n\n\n")

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

        # Loop over each patch
        for i, patch in enumerate(patches):
            patch_path = patch.get("path", "")
            patch_value = patch.get("value", "")
            index, patch_field,append = get_patch_field_and_index(patch_path)
            kb_field = FIELD_MAPPING.get(patch_field)

            print(f"\n🔍 Patch {i+1}: internship index={index}, field={patch_field}, KB field={kb_field}")

            section = "Internship Document Formatting Guidelines"
            
            retrieved_info = None  # initialize here to avoid UnboundLocalError

            if patch_field == "internship_work_description_bullets":
                retrieved_info = new_query_pdf_knowledge_base(
                    query_text=str(query),  # query string
                    role=["internship"],
                    section=section,
                    subsection="Action Verbs (to use in work descriptions)",
                    field=kb_field,
                    n_results=5,
                    debug=False
                )
                all_results.append(f"[Action Verbs] => {retrieved_info}")

                retrieved_info = new_query_pdf_knowledge_base(
                    query_text=str(patch_value),  # use patch value as query
                    role=["internship"],
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



        all_results_str = "\n".join(all_results)
        state["internship"]["retrieved_info"] = all_results_str
        state["internship"]["generated_query"] = ""  # clear after use

        print("\n✅ Retrieved info saved:", all_results_str, "\n\n")

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
        
        # index = state.get("internship", {}).get("index")
        current_entries = state.get("resume_schema", {}).get("internships", [])
        # entry = current_entries[index] if index is not None and 0 <= index < len(current_entries) else "New Entry"

        # print(index)
        print(current_entries)
        # print("\nCurrent Entry in Builder:", entry)

        if not retrieved_info or retrieved_info.strip() in ("None", ""):
            print("No retrieved info available, skipping building.")
            state["messages"].append(SystemMessage(content="No retrieved info available, skipping building."))
            return

        prompt = f"""
        You are a professional internship resume builder.

        ***INSTRUCTIONS:***
        1. Treat the incoming JSON Patch values as the **source of truth**. Do NOT change their meaning. It will be applied directly to the current entry.
        2. Your task is to **refine formatting and style** only before it gets applied. Based on the retrieved guidelines, improve phrasing, clarity, and impact of the patch values, but do not change their truth.
        3. Do NOT replace, remove, or add values outside the incoming patch.
        4. Do NOT change patch paths or operations.
        5. Return strictly a **valid JSON Patch array** (RFC6902). No explanations or extra text.

        ***GUIDELINES REFERENCE:***
        {retrieved_info}


        ***INCOMING PATCHES:***
        {patches}
        """





            


            
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


        patch_field = [patch["path"] for patch in patches if "path" in patch]

        result = await apply_patches(thread_id, patches)
        
        print("Apply patches result:", result)
        
        if result and result.get("status") == "success":
            print("Entry state updated successfully in Redis.")
            state["internship"]["save_node_response"] = f"patches applied successfully on fields {', '.join(patch_field)}."
            
            state["internship"]["patches"] = []  # Clear patches after successful application
            return{
                "next_node": "end_node",
            }
        elif result and result.get("status") == "error":
            error_msg = result.get("message", "Unknown error during patch application.")
            
            return {
                "messages": [AIMessage(content=f"Failed to apply patches: {error_msg},Pathces: {patches}")],
                "next_node": "internship_model",
                "internship": {
                    "error_msg": error_msg,
                }
            }
            print("\n\n\n\n")
    except Exception as e:
        print("Error in save_entry_state:", e)
        return {"messages":AIMessage(content="Sorry,Can't process your request now"),"next_node": END}
    
    
    
    
    


# End Node (Runs after save_entry_node)
async def End_node(state: SwarmResumeState, config: RunnableConfig):
    """Main chat loop for internship assistant with immediate state updates."""

    try:
        save_node_response = state.get("internship", {}).get("save_node_response", None)
        
        print("End Node - save_node_response:", save_node_response)

        # current_entries = state.get("resume_schema", {}).get("internships", [])
        internship_state = state.get("internship", {})
        
    
        # print("Internship State in Model Call:", internship_state)
        
        if isinstance(internship_state, dict):
            internship_state = InternshipState.model_validate(internship_state)

 
                        
        
        
        # system_prompt = SystemMessage(
        #     content=dedent(f"""
        #     You are a human-like Internship Assistant for a Resume Builder.

        #     Focus solely on engaging the user in a supportive, professional, and encouraging manner. 
        #     Do not repeat, edit, or reference any internship entries or technical details.

        #     Last node message: {save_node_response if save_node_response else "None"}

        #     --- Guidelines for this node ---
        #     • Be warm, concise, and positive.
        #     • DO NOT ask about rewards, challenges, learnings, or feelings.
        #     • Only request more details if absolutely necessary.
        #     • Occasionally ask general, open-ended questions about internships to keep the conversation natural.
        #     • Never mention patches, edits, or technical updates—simply acknowledge the last node response if relevant.
        #     • Your primary goal is to motivate and encourage the user to continue improving their resume.
        #     """)
        # )
        
        system_prompt = SystemMessage(
            content=dedent(f"""
            You are a human-like Internship Assistant for a Resume Builder.

            Focus solely on engaging the user in a supportive, professional, and encouraging manner. 
            Do not repeat, edit, or reference any internship entries or technical details.

            Last node message: {save_node_response if save_node_response else "None"}

            --- Guidelines for this node ---
            • Be concise and professional.
            • DO NOT ask about rewards, challenges, learnings, or feelings.
            • **ToolMessages** are strictly for internal communication. Do **not** expose or send them to the user directly.  
            • ONLY ask one of the following questions if necessary:
              - "What would you like to fill next?"
              - "Is there anything else you'd like to update or add?"
              - "Would you like to add impact and outcome for this experience?"
              - "Would you like to refine any part of this internship further?"
              - "Do you want to add any specific tools or technologies you used here?"
              - "Would you like to include measurable results or achievements ?"
              - "Nice work! Want to expand this part a bit more ?"
              - "Would you like to summarize this experience in one strong sentence ?"
              - "Should I help you make this point more impactful?"
            • Never mention patches, edits, or technical updates—simply acknowledge the last node response if relevant.
            • Your primary goal is to motivate and encourage the user to continue improving their resume.
            """)
        )


        # # Include last 3 messages for context (or fewer if less than 3)
        # messages = state["messages"]
        messages = safe_trim_messages(state["messages"], max_tokens=MAX_TOKENS)
        
        
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


def save_node_router(state: SwarmResumeState):
    error_msg = state.get("internship", {}).get("error_msg", [])
    
    if error_msg:
        return "internship_model"
    
    
    return "end_node"








# ---------------------------
# 6. Create Graph
# ---------------------------

workflow = StateGraph(SwarmResumeState)


# Tool nodes for each model
internship_tools_node = ToolNode([*tools,*transfer_tools])         # For internship_model


# Nodes
workflow.add_node("internship_model", call_internship_model)
workflow.add_node("query_generator_model", query_generator_model)
workflow.add_node("retriever_node", retriever_node)
workflow.add_node("builder_model", builder_model)
workflow.add_node("save_entry_state", save_entry_state)
workflow.add_node("end_node", End_node)



# Tool Nodes
workflow.add_node("tools_internship", internship_tools_node)




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

# Conditional routing
workflow.add_conditional_edges(
    "save_entry_state",
    save_node_router,
    {
        "internship_model": "internship_model",
        "end_node": "end_node",   
        END: END
    }
)




# Edges
# workflow.add_edge("tools_internship", "internship_model")  # return to internship
workflow.add_edge("query_generator_model", "retriever_node")  # return to retriever
workflow.add_edge("retriever_node","builder_model")   # return to builder
workflow.add_edge("builder_model", "save_entry_state")
# workflow.add_edge("save_entry_state", "end_node")
workflow.add_edge("end_node",END)



# Compile
internship_assistant = workflow.compile(name="internship_assistant")
internship_assistant.name = "internship_assistant"
