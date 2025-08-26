from langgraph.graph import StateGraph, END
from langgraph.types import Command
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from typing_extensions import TypedDict, Annotated
from langgraph.graph.message import add_messages
import json
from ..llm_model import llm, SwarmResumeState
from models.resume_model import WorkExperience
from .tools import tools
from textwrap import dedent
from langchain_core.messages.utils import (
    trim_messages,
    count_tokens_approximately
)
from ..utils.common_tools import calculate_tokens
# ---------------------------
# LLM with Tools
# ---------------------------

llm_work_experience = llm.bind_tools(tools)

# ---------------------------
# Node Function
# ---------------------------

def call_work_experience_model(state: SwarmResumeState, config: RunnableConfig):
    user_id = config["configurable"].get("user_id")
    resume_id = config["configurable"].get("resume_id")
    tailoring_keys = config["configurable"].get("tailoring_keys", [])

    print(f"[Work Experience Agent] Handling user {user_id} for resume {resume_id}")

    latest_entries = state.get("resume_schema", {}).get("work_experiences", [])

    system_prompt = SystemMessage(
    content=dedent(f"""
    You are the **Work Experience Assistant** for a Resume Builder. 
    Act as a helpful mentor guiding the user to build a strong Work Experience section.

    --- Responsibilities ---
    1. Collect work experience info (Company, Role, Duration, Location, Description, Projects, Project Bullets).
    2. Focus on roles: {tailoring_keys}. Highlight relevant details in **short responses (~60-70 words)**.
    3. Use `workex_tool` to add/update/delete entries (**always provide index & type**). 
       Never ask the user for indexes; decide yourself using current entries.
    4. Rearrange entries using `reorder_tool`, `reorder_projects_tool`, and `reorder_project_description_bullets_tool` as needed.
    5. Ask **one question at a time**. Do **not** show changes — resume is live-previewed.

    --- Work Experience Schema ---
    company_name, company_description, location, duration, designation, designation_description,
    projects (List[Project]), project_name, project_description, description_bullets (List[str])

    --- Current Entries (Compact Version) ---
    Use `get_compact_work_experience_entries` to retrieve index, company_name, designation, duration,
    and projects count. Do not include full project or bullet content here; fetch only if needed.

    Remember:
    - Always use the index from the compact entries when calling `workex_tool`.
    - Keep responses short and focused (~60-70 words).
    """)
)   
    
    messages = trim_messages(
        state["messages"],
        strategy="last",
        token_counter=count_tokens_approximately,
        max_tokens=1024,
        start_on="human",
        end_on=("human", "tool"),
    )
    
    
    
    if not messages:
        from langchain.schema import HumanMessage
        messages = [HumanMessage(content="")]  # or some default prompt
    
    print("Trimmed msgs length:-",len(messages))
    

    response = llm_work_experience.invoke([system_prompt] + state["messages"], config)

    print("Work Experience Token Usage:", response.usage_metadata)

    return {"messages": [response]}

# ---------------------------
# Conditional Routing
# ---------------------------

def should_continue(state: SwarmResumeState):
    last_message = state["messages"][-1]
    return "continue" if last_message.tool_calls else "end"

# ---------------------------
# Create Graph
# ---------------------------

workflow = StateGraph(SwarmResumeState)

workflow.add_node("work_experience_model", call_work_experience_model)
workflow.add_node("workex_tools", ToolNode(tools))

workflow.set_entry_point("work_experience_model")

workflow.add_conditional_edges(
    "work_experience_model",
    should_continue,
    {
        "continue": "workex_tools",
        "end": END  # ✅ This properly terminates the flow
    }
)

workflow.add_edge("workex_tools", "work_experience_model")

# ✅ Register it with the expected name for main graph
workex_assistant = workflow.compile(name="workex_assistant")
workex_assistant.name = "workex_assistant"
