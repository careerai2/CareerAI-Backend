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
from utils.safe_trim_msg import safe_trim_messages
import assistant.resume.chat.token_count as token_count
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
    content = dedent(f"""
        You are the **Work Experience Assistant** in a Resume Builder.
        Guide the user to craft impactful work experience entries.

        --- Goal ---
        - Gather details: Company, Role, Duration, Location, Descriptions, Projects, Bullets.
        - Emphasize relevance to: {tailoring_keys}.
        - Respond concisely (~60-70 words).

        --- Workflow ---
        1. Collect info step by step (one question at a time).
        2. **Use use_knowledge_base to fetch exact action verbs, must-haves, and good-to-haves. Present them first in concise bullet points before creating or editing an entry.
        3. Modify entries with `workex_tool` (always include `index` & `type` from Current Entries).
        4. Reorder using `reorder_tool`, `reorder_projects_tool`, or `reorder_project_description_bullets_tool` when needed.
        5. Do not display changes; the resume is live-previewed.

        --- Tools ---
        - workex_tool → add/update/delete entries.
        - reorder_tool → reorder entries.
        - reorder_projects_tool → reorder projects.
        - reorder_project_description_bullets_tool → reorder bullets.

        --- Schema ---
        - company_name, company_description, location, duration, designation, designation_description  
        - projects: [project_name, project_description, description_bullets]

        --- Current Entries (Compact) ---
        ```json
        {latest_entries}
        ```

        --- Rules ---
        - Infer indexes from compact entries (never ask user).  
        - Stay concise, professional, and tailored to {tailoring_keys}.
        """)

)   

    messages = safe_trim_messages(state["messages"], max_tokens=1024)
    
    
    print("Trimmed msgs length:-",len(messages))
    

    response = llm_work_experience.invoke([system_prompt] + messages, config)

    token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
    token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)

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
