from langgraph.graph import StateGraph, END
from langgraph.types import Command
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from ..llm_model import llm,SwarmResumeState,InternshipState
from models.resume_model import Internship
# from .state import SwarmResumeState
from .tools import tools, fetch_internship_info,updater_tools,transfer_tools
from textwrap import dedent
from utils.safe_trim_msg import safe_trim_messages
from ..utils.common_tools import extract_json_from_response
import assistant.resume.chat.token_count as token_count
import json 
from typing import Dict, Any, Optional
import re
from app_instance import app
from langgraph.types import Interrupt,interrupt
from .functions import add_internship,update_internship
from redis_config import redis_client as r 
# ---------------------------
# 2. LLM with Tools
# ---------------------------

llm_internship = llm.bind_tools(tools + transfer_tools)
llm_updater = llm.bind_tools(updater_tools + transfer_tools)
llm_retriever = llm
llm_builder = llm.bind_tools([])

# ---------------------------
# 3. State
# ---------------------------

# ---------------------------
# 4. Node Functions
# ---------------------------
#      • Decide indexes and update types (add/update/delete) yourself — never ask the user.
# def update_internship_entry(state: SwarmResumeState, updates: Dict[str, Any], schema: Dict[str, type]) -> Optional[Dict[str, Any]]:
#     """Update internship entry with immediate validation and state persistence."""
    
#     # Validate updates against schema
#     for field, value in updates.items():
#         if field not in schema:
#             print(f"⚠️ Unknown field '{field}' - skipping")
#             continue
            
#         expected_type = schema[field]
#         if not isinstance(value, expected_type):
#             print(f"⚠️ Field '{field}' expects {expected_type.__name__}, got {type(value).__name__}")
#             return None

#     # Initialize entry if it doesn't exist
#     if state["internship"].entry is None:
#         state["internship"].entry = {
#             "company_name": "",
#             "company_description": "",
#             "location": "",
#             "designation": "",
#             "designation_description": "",
#             "duration": "",
#             "internship_work_description_bullets": []
#         }

#     # Apply updates immediately
#     for field, value in updates.items():
#         if field in schema:  # Double-check for safety
#             state["internship"].entry[field] = value
#             print(f"✅ Updated {field}: {value}")

#     # Validate complete entry if all required fields are present
#     required_fields = list(schema.keys())
#     missing_fields = [f for f in required_fields if not state["internship"].entry.get(f)]
    
#     if missing_fields:
#         print(f"📝 Still need: {', '.join(missing_fields)}")
#     else:
#         print("🎉 Internship entry complete!")

#     return state["internship"].entry



def call_internship_model(state: SwarmResumeState, config: RunnableConfig):
    """Main chat loop for internship assistant with immediate state updates."""
    tailoring_keys = config["configurable"].get("tailoring_keys", [])
    current_entries = state.get("resume_schema", {}).get("internships", [])
    
    tailored_current_entries = [
        {
            "index": idx,
            "company_name": entry.get("company_name"),
        }
        for idx, entry in enumerate(current_entries)
    ]
    
    print("Tailored current entries:", tailored_current_entries)

    
    internship_state = state["internship"]
    if isinstance(internship_state, dict):
        internship_state = InternshipState.model_validate(internship_state)

    entry = getattr(internship_state, "entry", None)
    active_agent = getattr(internship_state, "active_agent", None)
    
    if active_agent == "update_internship_agent":
       return Command(goto="update_entry_model")

    print(entry)

    system_prompt = SystemMessage(
    content=dedent(f"""
        You are the **Internship Assistant** for a Resume Builder.
        Your role: Chat with the user to gather and refine internship information.

        --- Chat Behavior ---
        • Ask **one clear, focused question at a time**.
        • Keep responses concise (60-70 words max).
        • Professional yet friendly tone.
        • ✅ The moment the user provides any information that matches a schema field, you **must immediately call the `update_entry_state` tool** before asking the next question.
        • Acknowledge user input briefly before moving to the next question.

        --- Tool Usage ---
        • use "transfer_to_update_internship_agent" tool when user wants to update existing internship entry.
        • Do **not** wait until all fields are collected; update the state progressively, one field at a time.
        • Never skip tool invocation if a field is mentioned, even partially filled.
        • `transfer_to_enhancer_pipeline`: to update in the final resume entry by enhancing it call it when most of the fields are updated **ALWAYS call this after the tool `update_entry_state`**. 
        
        
        --- Required Schema Fields ---
        {{company_name, company_description, location, designation, designation_description, duration, internship_work_description_bullets (as an array of strings)}}

        --- Current Entries (Your Local State,uses this to track changes)---
        {entry}

        --- Total Current Entries (User's Resume's Internship section have)---
        {tailored_current_entries}
        
        --- Guidelines ---
        • Validate all updates match schema types.
        • Use bullet points as strings in the array.
        • if there is no current entry then start from scratch.
    """)
)

    messages = safe_trim_messages(state["messages"], max_tokens=512)
    response = llm_internship.invoke([system_prompt] + messages, config)
    
    # print("Internship Response:", response.content)

    # Update token counters
    token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
    token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)

    print("internship_model response:", response.content)
    print("Internship Token Usage:", response.usage_metadata)
    
    return {"messages": [response]}



def call_updater_model(state: SwarmResumeState, config: RunnableConfig):
    """Main chat loop for internship assistant with immediate state updates."""
    tailoring_keys = config["configurable"].get("tailoring_keys", [])
    current_entries = state.get("resume_schema", {}).get("internships", [])
    
    internship_state = state["internship"]
    if isinstance(internship_state, dict):
        internship_state = InternshipState.model_validate(internship_state)

    entry = getattr(internship_state, "entry", None)
    
    tailored_current_entries = [
        {
            "index": idx,
            "company_name": entry.get("company_name"),
        }
        for idx, entry in enumerate(current_entries)
    ]

    print("Tailored current entries:", tailored_current_entries)


    system_prompt = SystemMessage(
    content=dedent(f"""
        You are the **Internship Assistant** for a Resume Builder.
        Your task: chat with the user to gather internship details and update entries step by step.
        User is targeting for role {tailoring_keys}.
        
        --- Rules ---
        • Ask one clear question at a time.
        • Keep replies under 40 words, professional but friendly.
        • Update progressively: call `update_entry_state` as soon as a schema field is mentioned.
        • When most of the important fields (company, role, duration, 1–2 bullets) are filled → call `transfer_to_enhancer_pipeline`.
        • If no entry exists → ask for company name → else ask which entry (1st, 2nd, etc.).

        --- Tools ---
        • transfer_to_add_internship_agent → when user wants to add new entry.
        • get_entry_by_company_name → Ask the user which entry from current Entries in resume they want to update ASAP call this tool to fill your current entry.
        • update_entry_state → for every schema field update.  
        • transfer_to_enhancer_pipeline → Call it to update the final resume entry by enhancing it once most fields are filled or think its is right time to add.

        --- Schema Fields ---
        company_name, company_description, location, designation, 
        designation_description, duration, internship_work_description_bullets

        --- Current Entries to update ---
        {entry if entry else "No entry. Start with company name or index."}

        --- Current Entries in Resume ---
        {tailored_current_entries}
    """)
        )

    
    



    messages = safe_trim_messages(state["messages"], max_tokens=512)
    response = llm_updater.invoke([system_prompt] + messages, config)
    
    # print("Internship Response:", response.content)

    # Update token counters
    token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
    token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)

    print("internship_updater_model response:", response.content)
    print("Internship_update Token Usage:", response.usage_metadata)
    
    return {"messages": [response]}



# Retriever Model
def retriever_model(state: SwarmResumeState, config: RunnableConfig):
    """Fetch relevant info from knowledge base."""
    entry = state.get("internship", {}).get("entry", {})

    print("Retriever :-", entry)

    if not entry or not entry.get("internship_work_description_bullets"):
        print("No internship work bullets yet, cannot retrieve info.")
        state["messages"].append(SystemMessage(content="No internship work bullets yet, cannot retrieve info."))
        return {"next_node": "internship_model"}
    
    
    prompt = f"""
    You are a expert in providing guidelines for building strong internship entries for resumes.
    
    only provide the instruction that need to be followed in consise manner.
    Do not add any extra information. Also instruction should be relevant to the fields that entry have. 
    
    Retrieve relevant info for the given internship entry:\n
         "ActionVerbs": ["Developed", "Implemented", "Optimized", "Engineered", "Automated", "Tested", "Designed", "Deployed", "Refactored", "Collaborated", "Researched", "Analyzed", "Documented"],
    "Requirements": [
      "Company name, brief description, and location",
      "Internship duration (start – end dates or months/years)",
      "Designation/title and brief description of responsibilities",
      "Internship work details in 3-5 bullet points",
      "Technologies, tools, and frameworks used",
      "Quantifiable impact wherever possible",
      "Team collaboration and mentorship experience",
      "Exposure to Agile/Scrum or other methodologies",
      "Cross-functional project involvement",
      "Learning outcomes and skills gained",
      "Awards, recognitions, or special contributions"
    ],
    "Guidelines": [
      {{ "field": "company_name", "instruction": "Provide the official company name. Avoid abbreviations unless commonly recognized." }},
      {{ "field": "company_description", "instruction": "Write 1-2 lines about what the company does, focusing on domain and products/services." }},
      {{ "field": "location", "instruction": "Mention city and country of the office you worked at." }},
      {{ "field": "designation", "instruction": "State your internship title or role." }},
      {{ "field": "designation_description", "instruction": "Briefly describe your role and key responsibilities in 1-2 lines." }},
      {{ "field": "duration", "instruction": "Use the format 'MMM YYYY – MMM YYYY' or 'MMM YYYY – Present'. Ensure clarity for ATS." }},
      {{ "field": "internship_work_description_bullets", "instruction": "Each bullet should start with a strong action verb, include relevant technology/tools, and quantify impact if possible." }}
    ]
        
        -------entry------
        {entry}
        """


    # Call the tool to fetch info
    response = llm_retriever.invoke(prompt, config)

    print("Retrieved info saved:", response)
    if response.content.strip():
        state["internship"]["retrived_info"] = str(response.content)
    else:
        state["internship"]["retrived_info"] = ""
        print("Retriever returned empty info")

    # print("Retrieved info saved:", response)
    return {"next_node": "builder_model"}



def builder_model(state: SwarmResumeState, config: RunnableConfig):
    """Build or refine internship entry based on retrieved info."""
    try:
        entry = state.get("internship", {}).get("entry", {})
        retrived_info = state.get("internship", {}).get("retrived_info", "")
        
        # print("Builder stage entry:", entry)
        # print("Builder stage retrieved info:", retrived_info)

        if not entry:
            print("No internship entry provided, skipping building.")
            state["messages"].append(SystemMessage(content="No internship entry provided, skipping building."))
            return {"next_node": "internship_model"}
        
        if not retrived_info or retrived_info == "None" or retrived_info.strip() == "":
            print("No retrieved info available, skipping building.")
            state["messages"].append(SystemMessage(content="No retrieved info available, skipping building."))
            return {"next_node": "internship_model"}


        prompt = f"""Build the best internship entry using retrieved info and current entry.
        
    ***INSTRUCTIONS:***
        ####Always respond in json format only.
        1. Structly follow the retrieved info to enhance the current entry.
        2. Ensure all fields are filled accurately.
        3. Use bullet points for 'internship_work_description_bullets'.
        
        
        current entry:
        ```json
            {entry}
        ```
        
        retrieved info:
        {retrived_info}
                                    
                                """

        response = llm_builder.invoke(prompt, config)
        
        # if response.content.strip():
        #     state["internship"]["retrived_info"] = response.content
        # else:
        #     state["internship"]["retrived_info"] = ""
        #     print("Retriever returned empty info")
            
        print("Builder Response:", extract_json_from_response(response.content))
        
        state["internship"]["entry"] = Internship.model_validate(extract_json_from_response(response.content))
        
        
        # print("Builder stage state:", state["internship"]["entry"])
        # state["messages"].append(response)
        return {"next_node": "save_entry_state"}
        # return {"next_node":"internship_model"}
    except Exception as e:
        print("Error in builder_model:", e)
        # return {"next_node": "internship_model"}
        return {END: END}




async def save_entry_state(state: SwarmResumeState, config: RunnableConfig):
    """Parse LLM response and update internship entry state."""
    try:

        entry = state["internship"]["entry"]
        thread_id = config["configurable"]["thread_id"]
        
        internship_state = state["internship"]
        if isinstance(internship_state, dict):
            internship_state = InternshipState.model_validate(internship_state)

        entry = getattr(internship_state, "entry", None)
        index = getattr(internship_state, "index", None)
        active_agent = getattr(internship_state, "active_agent", None)
    
        print("Saving entry state:")
        print("Active Agent:", active_agent)
        
        if active_agent == "update_internship_agent" and index is not None:
            result = await update_internship(thread_id, index, Internship.model_validate(entry))
        else:
            print("Adding new internship entry")
            result  = await add_internship(thread_id, Internship.model_validate(entry))
        
        print("Result of adding internship:", result)
        
        if result["status"] == "success":
            print("internship added")
            # r.set(f"state:{thread_id}:internship", json.dumps(InternshipState().model_dump()))

    except Exception as e:
        print("Error in save_entry_state:", e)
        return None
# ---------------------------
# 5. Conditional Router
# ---------------------------



def internship_model_router(state: SwarmResumeState):
    last_message = state["messages"][-1]

    # 1. Go to internship tools if a tool was called
    if getattr(last_message, "tool_calls", None):
        return "tools_internship"

    # 2. Check if entry has any work bullets to move to retriever
    internship_state = state["internship"]
    if isinstance(internship_state, dict):
        internship_state = InternshipState.model_validate(internship_state)

    entry = getattr(internship_state, "entry", None)

    if entry and entry.internship_work_description_bullets:
        return "retriever_model"

    # 3. Otherwise continue the chat (stay in internship_model)
    return END



def updater_model_router(state: SwarmResumeState):
    last_message = state["messages"][-1]

    # 1. If tool was called → go to updater tools
    if getattr(last_message, "tool_calls", None):
        return "tools_updater"

    # 2. Otherwise stay in updater model until entry is complete
    return END



def retriever_model_router(state: SwarmResumeState):
    last_message = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        return "tools_retriever"
    return "builder_model"  # let node return string to pick next


def builder_model_router(state: SwarmResumeState):
    last_message = state["messages"][-1]

    # 1. Go to builder tools if a tool was called
    if getattr(last_message, "tool_calls", None):
        return "tools_builder"

    # 2. Simply return END - no need to validate InternshipState here
    # The builder_model function already handles the entry saving
    return "save_entry_state"


# ---------------------------
# 6. Create Graph
# ---------------------------

workflow = StateGraph(SwarmResumeState)


# Tool nodes for each model
internship_tools_node = ToolNode(tools)         # For internship_model
updater_tools_node = ToolNode(updater_tools)         # For internship_model
retriever_tools_node = ToolNode([fetch_internship_info])  # For retriever_model
builder_tools_node = ToolNode([])               # For builder_model (if needed)

# Nodes
workflow.add_node("internship_model", call_internship_model)
workflow.add_node("update_entry_model", call_updater_model)
workflow.add_node("retriever_model", retriever_model)
workflow.add_node("builder_model", builder_model)
workflow.add_node("save_entry_state", save_entry_state)
# workflow.add_node("tools", ToolNode(tools))

workflow.add_node("tools_internship", internship_tools_node)
workflow.add_node("tools_updater", updater_tools_node)
workflow.add_node("tools_retriever", retriever_tools_node)
workflow.add_node("tools_builder", builder_tools_node)


# Entry
# workflow.set_entry_point("update_entry_model")
workflow.set_entry_point("internship_model")

# Conditional routing
workflow.add_conditional_edges(
    "internship_model",
    internship_model_router,
    {
        "tools_internship": "tools_internship",          # <- per-model tool node
        "retriever_model": "retriever_model",
        "internship_model": "internship_model",
        END: END
    }
)


workflow.add_conditional_edges(
    "update_entry_model",
    updater_model_router,
    {
        "tools_updater": "tools_updater",
        "update_entry_model": "update_entry_model",  # keep looping updater
        END: END
    }
)


workflow.add_conditional_edges(
    "retriever_model",
    retriever_model_router,
    {
        "tools_retriever": "tools_retriever",
        "builder_model": "builder_model",
        "internship_model": "internship_model",
        END: END
    }
)


workflow.add_conditional_edges(
    "builder_model",
    builder_model_router,  # same router can work
    {
        "tools_builder": "tools_builder",
        # "retriever_model": "retriever_model",
        # "internship_model": "internship_model",
        "save_entry_state": "save_entry_state",
        END: END
    }
)



# workflow.add_edge("tools", "internship_model")

# Conditional routing
workflow.add_edge("tools_internship", "internship_model")  # return to internship
workflow.add_edge("tools_updater", "update_entry_model")  # return to updater
workflow.add_edge("tools_retriever", "retriever_model")    # return to retriever
workflow.add_edge("tools_builder", "builder_model")        # return to builder
workflow.add_edge("builder_model", "save_entry_state")
workflow.add_edge("save_entry_state", END)

# Compile
internship_assistant = workflow.compile(name="internship_assistant")
internship_assistant.name = "internship_assistant"
