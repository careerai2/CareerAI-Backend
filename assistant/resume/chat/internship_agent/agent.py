from langgraph.graph import StateGraph, END
from langgraph.types import Command
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from typing_extensions import TypedDict, Annotated
from langgraph.graph.message import add_messages
from ..llm_model import llm,SwarmResumeState
from models.resume_model import Internship
from .tools import tools
from langchain_core.messages.utils import (
    trim_messages,
    count_tokens_approximately
)
from ..utils.common_tools import calculate_tokens
from textwrap import dedent
from utils.safe_trim_msg import safe_trim_messages
# ---------------------------
# 2. LLM with Tools
# ---------------------------

llm_internship = llm.bind_tools(tools)

# ---------------------------
# 3. Node Function
# ---------------------------

def call_internship_model(state: SwarmResumeState, config: RunnableConfig):
   
    user_id = config["configurable"].get("user_id")
    resume_id = config["configurable"].get("resume_id")
    tailoring_keys = config["configurable"].get("tailoring_keys", [])
    
    # print(f"[Internship Agent] Handling user {user_id} for resume {resume_id} with tailoring keys {tailoring_keys}")
    
    # latest_entries = state.get("resume_schema", {}).get("internships", [])

    system_prompt = SystemMessage(
        content=dedent(f"""
        You are the **Internship Assistant** for a Resume Builder. 
        Act as a helpful mentor guiding the user to build a strong Internship section.

        --- Responsibilities ---
        1. Collect internship info (Company, Role, Duration, Location, Achievements).
        2. Focus on roles: {tailoring_keys}. Highlight relevant details in **short responses (~60-70 words)**.
        3. Use `internship_tool` to add/update/delete entries (**provide index & type(use your judgment to get it)**). 
        Never ask the user for indexes; decide yourself using current entries.
        4. Move entries using `reorder_tool` & `reorder_bullet_points_tool` if needed.
        5. Ask **one question at a time**. Do **not** show changes — resume is live-previewed.

        --- Internship Schema ---
        company_name, company_description, location, designation, designation_description, 
        duration, internship_work_description_bullets (List[str])

        --- Current Entries (Compact Version) ---
        Use `get_compact_internship_entries` to retrieve index, company_name, designation, duration, 
        and a short summary of bullets. Do not include full bullet content here; fetch only if needed.

        Remember:
        - Always use the index from the compact entries when calling `internship_tool`.
        - Keep responses short and focused (~60-70 words).
        """)
    )

    
    messages = safe_trim_messages(state["messages"], max_tokens=1024)
    
    # print(messages)
    print("Trimmed msgs length:-",len(messages))
 

    response = llm_internship.invoke([system_prompt] + messages, config)

    print("Internship Token Usage:", response.usage_metadata)

    return {"messages": [response]}

# ---------------------------
# 4. Conditional Routing
# ---------------------------

def should_continue(state: SwarmResumeState):
    last_message = state["messages"][-1]
    return "continue" if last_message.tool_calls else "end"

# ---------------------------
# 5. Create Graph
# ---------------------------

workflow = StateGraph(SwarmResumeState)

# Add nodes
workflow.add_node("internship_model", call_internship_model)
workflow.add_node("tools", ToolNode(tools))

# Entry point
workflow.set_entry_point("internship_model")

# Conditional edges
workflow.add_conditional_edges(
    "internship_model",
    should_continue,
    {"continue": "tools", "end": END}
)
workflow.add_edge("tools", "internship_model")

internship_assistant = workflow.compile(name="internship_assistant")
internship_assistant.name = "internship_assistant"
