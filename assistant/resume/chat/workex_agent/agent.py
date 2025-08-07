from langgraph.graph import StateGraph, END
from langgraph.types import Command
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from typing_extensions import TypedDict, Annotated
from langgraph.graph.message import add_messages
import json

from ..handoff_tools import transfer_to_main_agent, transfer_to_education_agent
from ..utils.tools import internship_Tool
from ..llm_model import llm, SwarmResumeState
from models.resume_model import WorkExperience
from .tools import tools

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

    print(f"[Work Experience Agent] Handling user {user_id} for resume {resume_id}")

    system_prompt = SystemMessage(
        f"""
        You are the **Work Experience Assistant** for a Resume Builder application.
        Act as an **elder brother / mentor**, guiding the user to build a strong Work Experience section.

        --- Responsibilities ---
        1. Collect and organize work experience info as mentioned in the schema below.
        2. Create or update entries using `workex_tool` in real time and **don't forget to provide index**.
        3. Ask one question at a time to fill missing details.

        Work Experience Schema Context:
        ```json
        { json.dumps(WorkExperience.model_json_schema(), indent=2) }
        ```
        """
    )

    response = llm_work_experience.invoke([system_prompt] + state["messages"], config)
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
