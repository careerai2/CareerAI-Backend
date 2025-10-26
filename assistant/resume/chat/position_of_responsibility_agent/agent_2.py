from httpx import patch
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, AIMessage,HumanMessage,FunctionMessage
from langchain_core.runnables import RunnableConfig
from ..llm_model import llm,SwarmResumeState
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


# ---------------------------
# 2. LLM with Tools
# ---------------------------

MAX_TOKENS = 325

llm_por = llm.bind_tools(tools)
# llm_por = llm  # tool can be added if needed
llm_builder = llm  # tool can be added if needed
llm_retriever = llm # tool can be added if needed

default_msg = AIMessage(content="Sorry, I couldn't process that. Could you please retry?")


instruction = {
    "role": "Write the exact position title. | Capitalize each word. | Example: **Event Coordinator.**",
    "role_description": "Limit to 1–2 lines max. | Clearly describe the purpose scope of the role. | Example: *Coordinated logistics and scheduling for technical workshops.*",
    "organization" : "Use the official registered name only. | Avoid abbreviations unless globally recognized (e.g., IEEE). | Apply Title Case. | Example: **Institute of Electrical and Electronics Engineers (IEEE).**",
    "duration": "Format: **MMM YYYY – MMM YYYY** (or *Present* if ongoing). | Example: *Jan 2024 – Apr 2024.*",
     "location": "Format: **City, Country.** | Example: *Bengaluru, India.*",
  }

MAX_TOKEN = 325    

# main model
async def call_por_model(state: SwarmResumeState, config: RunnableConfig):
    """Main chat loop for Por assistant with immediate state updates."""
    tailoring_keys = config["configurable"].get("tailoring_keys", [])
    
    
    current_entries = state.get("resume_schema", {}).get("positions_of_responsibility", [])

    
    error_msg = state.get("por", {}).get("error_msg", None)
    
    print("POR State in por_model:", state.get("por", {}))
    
    if error_msg is not None:
        print(f"⚠️ POR patch failed with error: {error_msg}")
        
       

        # Give LLM a short controlled prompt to reply politely
        recovery_prompt = f"""
            The last POR patch operation failed with: '{error_msg}'.
            You have access to all tools, including send_patches.

            Rules for your response:
            1. Try to fix the issue automatically using the available tools (e.g., retry sending the patch).
            2. If automatic recovery is not possible, politely inform the user about the failure without revealing internal or technical details.
            3. Do NOT mention your identity, the identity of other agents, or that you are an AI/model/assistant.
            4. If a transfer or handoff is needed, perform it silently; do not notify or ask the user.
            5. Keep the response concise, polite, and human-like.
            """

        
        messages = safe_trim_messages(state["messages"], max_tokens=MAX_TOKEN)
        # Make it human-like using the same LLM pipeline
        response = await llm_por.ainvoke([recovery_prompt], config)
        print("por_model (error recovery) response:", response.content)
        
        
         # Reset error so it doesn’t loop forever
        state["por"]["error_msg"] = None

        return {
            "messages": [response],
            "por": {
                    "error_msg": None,
                }
            }
    
  
    
    system_prompt = SystemMessage(
    content=dedent(f"""
        You are a Human-like **POR (Position of Responsibility) Assistant** for a Resume Builder.
        Your role: Help users add and modify their **Position of Responsibility (POR)** section in the resume **(Current entries provided to You so start accordingly)** & also help refine and optimize this section with precision, brevity, and tailoring.

        --- Workflow ---
        • Ask one clear, single-step question at a time.
        • **Always immediately apply any user-provided information using `send_patches`. Do not wait for confirmation, except when deleting or overwriting existing entries. This must never be skipped.**
        • Use tools as needed; refer to their descriptions to know what they do.
        • Never reveal your identity or the identity of any other agent. Do not mention being an AI, model, or assistant. If a transfer or handoff is required, perform it silently without notifying or asking the user. Always behave as a human assistant..
        • **While generating patches for responsibilities, remember that `responsibilities` is an array of strings like ["", ""] — so create your patches accordingly.**
        • Always apply patches directly to the entire `positions_of_responsibility` section (list) — not individual entries.
        • Keep outputs concise (~60–70 words max).
        • For each POR, aim to get 3 main details:
            1. The role and the organization
            2. The user’s key responsibilities or achievements in that role
            3. The duration and location (if relevant)
        • DO NOT ask about challenges, learnings, or emotions.
        • The `send_patches` tool will validate your generated patches; if patches are invalid, it will respond with an error — you must then retry generating correct patches or ask the user for clarification.
        • If you are confident about a new addition or edit, you may apply it directly without asking for confirmation.

        --- Schema ---
            {{
                role,role_description,organization,organization_description,location,duration,responsibilities[]
            }}

        --- Current Entries (Visible to Human) ---
        Always use the following as reference when updating POR entries:
        {current_entries}

        --- Guidelines ---
        • Always use correct indexes for the PORs.
        • Focus on clarity, brevity, and alignment with {tailoring_keys}.
        • Resume updates are **auto-previewed** — **never show raw code or JSON changes**.  
            - The **current entries are already visible to the user**, so do **not restate them** when asking questions or making changes.
    """))


    try:
 
        messages = safe_trim_messages(state["messages"], max_tokens=MAX_TOKENS)
        # messages = safe_trim_messages(state["messages"], max_tokens=512)
        response = llm_por.invoke([system_prompt] + messages, config)
        
        # print("Internship Response:", response.content)

        # Update token counters
        token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
        token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)

        

        
        if not getattr(state["messages"][-1:], "tool_calls", None):

            print("\n\n\n")
            
       
        
            
            token_count.total_turn_Input_Tokens = 0
            token_count.total_turn_Output_Tokens = 0

        print("por_model response:", response.content)
        print("Por Model Token Usage:", response.usage_metadata)
        
        print("\n\n\n\n")
        
        return {"messages": [response]}
    except Exception as e:
        print("Error in por_model:", e)
        return {"messages": [AIMessage(content="Sorry! can you repeat")],"next_node": END}















# Query generator for Retriever 
def query_generator_model(state: SwarmResumeState, config: RunnableConfig):
    """Fetch relevant info from knowledge base."""
    # current_entries = state.get("resume_schema", {}).get("positions_of_responsibility", [])
    tailoring_keys = config["configurable"].get("tailoring_keys", [])
    patches = state.get("por", {}).get("patches", [])
   

    prompt = f"""
            You are an expert query generator for a vector database of Position of Responsibility (POR) guidelines. 
            Your goal is to create concise, retrieval-friendly queries to fetch the most relevant 
            guidelines, formatting rules, and phrasing suggestions for POR entries.

            --- Instructions ---
            • Reply ONLY with the generated query as plain text (1–2 sentences max).
            • Focus strictly on the fields listed in 'patched_fields'.
            • Always include:
            - Field name (exactly as in schema).
            - Current field value from patches.
            - Formatting requirements for that field (capitalization, length, structure).
            • If a role/domain is provided (e.g., Leadership, Club, Event, Team), include it in the query.
            • Use synonyms and natural phrasing (e.g., guidelines, best practices, format, points, phrasing) 
            so it matches book-style or handbook-like content.
            • Do not add filler or unrelated information.

            --- Patches (only these matter) ---
            {patches}

            --- Targeting Role (if any) ---
            {tailoring_keys if tailoring_keys else "None"}
        """
    print("Por in query node",state["por"])

    try:

        # Call the retriever LLM
        response = llm_retriever.invoke(prompt, config)
        
        token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
        token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)
        
        


        print("Query generated:", response)
        if response.content.strip():
            state["por"]["generated_query"] = str(response.content)
        else:
            state["por"]["generated_query"] = ""
            print("Retriever returned empty info")

        print("Query generator Token Usage:", response.usage_metadata)
        print("\n\n\n\n")
        # return {"next_node": "builder_model"}
        return {"next_node": END}
    except Exception as e:
        print("Error in query generator:", e)
        
        return {"messages":AIMessage(content="Sorry,Can't process your request now"),"next_node": END}














def retriever_node(state: SwarmResumeState, config: RunnableConfig):
    try:
        query = state.get("por", {}).get("generated_query", [])
        patches = state.get("por", {}).get("patches", [])

        if not query or (isinstance(query, str) and query.strip() in ("None", "")):
            print("No query generated, skipping retrieval.")
            state["por"]["retrieved_info"] = []
            return {"next_node": "builder_model"}

        # Collect all unique fields to avoid redundant fetches
        unique_fields = set()
        for patch in patches:
            _, patch_field, _ = get_patch_field_and_index(patch.get("path", ""))
            unique_fields.add(patch_field)

        print(f"\n🧠 Unique fields to fetch: {unique_fields}\n")

        all_results = []
        section = "Position of Responsibility Document Formatting Guidelines"

        for field in unique_fields:
            kb_field = FIELD_MAPPING.get(field)
            print(f"Fetching KB info for field: {field} -> KB field: {kb_field}")

            if field == "responsibilities":
                # Fetch action verbs
                action_verbs_info = new_query_pdf_knowledge_base(
                    query_text=str(query),
                    role=["por"],
                    section=section,
                    subsection="Action Verbs (to use in responsibilities)",
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

        # Join and store results
        all_results_str = "\n".join(all_results)
        state["por"]["retrieved_info"] = all_results_str
        state["por"]["generated_query"] = ""  # clear after use

        print("\n✅ Retrieved info saved:", all_results_str)
        return {"next_node": "builder_model"}

    except Exception as e:
        print("Error in retriever:", e)
        return {END: END}















# Builder Model
def builder_model(state: SwarmResumeState, config: RunnableConfig):
    """Refine por patches using retrieved info."""
    try:
        
        retrieved_info = state.get("por", {}).get("retrieved_info", "")
        patches = state.get("por", {}).get("patches", [])


        print(patches)

        if not retrieved_info or retrieved_info.strip() in ("None", ""):
            print("No retrieved info available, skipping building.")
            state["messages"].append(SystemMessage(content="No retrieved info available, skipping building."))
            return

        prompt = dedent(f"""You are reviewing por resume entries using JSON Patches.

        *** INSTRUCTIONS:    ***
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
            state["por"]["patches"] = [refined_patches]
        elif refined_patches is not None :    
            state["por"]["patches"] = refined_patches

        return {"next_node": "save_entry_state"}

    except Exception as e:
        print("Error in builder_model:", e)
        return {"messages":default_msg,"next_node": END}













async def save_entry_state(state: SwarmResumeState, config: RunnableConfig):
    """Parse LLM response and update por entry state."""
    try:

        # print("Internship State in save_entry_state:", state.get("por", {}))
        thread_id = config["configurable"]["thread_id"]
        patches = state.get("por", {}).get("patches", [])

        print("patches In save Node:", patches)
        patch_field = [patch["path"] for patch in patches if "path" in patch]

        result = await apply_patches(thread_id, patches)
        
        print("Apply patches result:", result)
        
        if result and result.get("status") == "success":
            print("Entry state updated successfully in Redis.")
            state["por"]["save_node_response"] = f"patches applied successfully on fields {', '.join(patch_field)}."
            return {"next_node": "end_node"}
        
        elif result and result.get("status") == "error":
            error_msg = result.get("message", "Unknown error during patch application.")
            
            return {
                "messages": [AIMessage(content=f"Failed to apply patches: {error_msg},Pathces: {patches}")],
                "next_node": "por_model",
                "por": {
                    "error_msg": error_msg,
                }
            }  
            
            print("\n\n\n\n")
    except Exception as e:
        print("Error in save_entry_state:", e)
        return {"messages":AIMessage(content="Sorry,Can't process your request now"),"next_node": END}
    
    
    
    
    
    
    
    

# End Node (Runs after save_entry_node)
def End_node(state: SwarmResumeState, config: RunnableConfig):
    """Main chat loop for por assistant with immediate state updates."""

    try:
        save_node_response = state.get("por", {}).get("save_node_response", None)
        
        print("End Node - save_node_response:", save_node_response)

     
        # system_prompt = SystemMessage(
        #     content=dedent(f"""
        #     You are a human-like POR Assistant for a Resume Builder.

        #     Focus solely on engaging the user in a supportive, professional, and encouraging manner. 
        #     Do not repeat, edit, or reference any por entries or technical details.

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
            You are a human-like POR Assistant for a Resume Builder.

            Focus solely on engaging the user in a supportive, professional, and encouraging manner. 
            Do not repeat, edit, or reference any por entries or technical details.

            Last node message: {save_node_response if save_node_response else "None"}

            --- Guidelines for this node ---
            • Be warm, concise, and positive.
            • DO NOT ask about rewards, challenges, learnings, or feelings.
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
        messages = safe_trim_messages(state["messages"], max_tokens=MAX_TOKENS)
        
        response = llm.invoke([system_prompt] + messages, config)
                
        if save_node_response:
            state["por"]["save_node_response"] = None  # Clear after using
        

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

def por_model_router(state: SwarmResumeState):
    last_message = state["messages"][-1]
    # patches = state["por"]["patches"]
    
    # print("\n\nPatches in Router:-", patches)

    # 1. Go to por tools if a tool was called
    if getattr(last_message, "tool_calls", None):
        return "tools_por"

    #  # 2. If there are patches to process, go to query generator
    # if patches and len(patches) > 0:
    #     print("Patches exist, going to query_generator_model")
    #     return "query_generator_model"
    
    # 3. Otherwise continue the chat (stay in por_model)
    

    
    return END



def save_node_router(state: SwarmResumeState):
    error_msg = state.get("por", {}).get("error_msg", [])
    
    if error_msg:
        return "por_model"
    
    
    return "end_node"









# ---------------------------
# 6. Create Graph
# ---------------------------

workflow = StateGraph(SwarmResumeState)


# Tool nodes for each model
por_tools_node = ToolNode(tools)         # For por_model


# Nodes
workflow.add_node("por_model", call_por_model)
workflow.add_node("query_generator_model", query_generator_model)
workflow.add_node("retriever_node", retriever_node)
workflow.add_node("builder_model", builder_model)
workflow.add_node("save_entry_state", save_entry_state)
workflow.add_node("end_node", End_node)



# Tool Nodes
workflow.add_node("tools_por", por_tools_node)




workflow.set_entry_point("por_model")



# Conditional routing
workflow.add_conditional_edges(
    "por_model",
    por_model_router,
    {
        "tools_por": "tools_por",          # <- per-model tool node
        # "retriever_model": "retriever_model",
        "por_model": "por_model",
        END: END
    }
)


workflow.add_conditional_edges(
    "save_entry_state",
    save_node_router,
    {
        "por_model": "por_model",
        "end_node": "end_node",   
        END: END
    }
)




# Edges
# workflow.add_edge("tools_por", "por_model")  # return to por
workflow.add_edge("query_generator_model", "retriever_node")  # return to retriever
workflow.add_edge("retriever_node","builder_model")   # return to builder
workflow.add_edge("builder_model", "save_entry_state")
# workflow.add_edge("save_entry_state", "end_node")
workflow.add_edge("end_node",END)



# Compile
position_of_responsibility_assistant = workflow.compile(name="Position_of_responsibility_assistant")
position_of_responsibility_assistant.name = "Position_of_responsibility_assistant"

