from langgraph.graph import StateGraph, END
from langgraph.types import Command
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from typing_extensions import TypedDict, Annotated
from langgraph.graph.message import add_messages
import json

from .tools import tools
from ..utils.tools import internship_Tool
from ..llm_model import llm,SwarmResumeState
from models.resume_model import PositionOfResponsibility

# ---------------------------
# 1. Define State
# ---------------------------

# class InternshipState(TypedDict):
#     user_id: str
#     resume_id: str
#     messages: Annotated[list, add_messages]  # All conversation messages

# ---------------------------
# 2. LLM with Tools
# ---------------------------

llm_internship = llm.bind_tools(tools)

# ---------------------------
# 3. Node Function
# ---------------------------

def call_por_model(state: SwarmResumeState, config: RunnableConfig):
   
    user_id = config["configurable"].get("user_id")
    resume_id = config["configurable"].get("resume_id")
    tailoring_keys = config["configurable"].get("tailoring_keys", [])

    print(f"[Position Of Responsibility Agent] Handling user {user_id} for resume {resume_id}")

    latest_entries = state.get("resume_schema", {}).get("position_of_responsibility", [])

    system_prompt = SystemMessage(
        f"""
        You are the **Position Of Responsibility Assistant** for a Resume Builder application.
        Act as an **elder brother / mentor**, guiding the user to build a strong Position Of Responsibility section.

        --- Responsibilities ---
        1. Collect and organize Position Of Responsibility info as mentioned in the schema below.
        2. The user is targeting these roles: {tailoring_keys}. Ensure the generated content highlights relevant details—such as bullet points and descriptions—that showcase suitability for these roles.
        3. Always create or update entries using the `position_of_responsibility_tool` in real time **don't forget to provide index**.
        4. Ask one question at a time to fill missing details.
        5. If user asks about different section check ur tools or route them to that agent
        6. If u didn't understand the request → call `transfer_to_main_agent`.


        Position Of Responsibility Schema Context:
        ```json
        { json.dumps(PositionOfResponsibility.model_json_schema(), indent=2) }
        ```
        """
    )

    response = llm_internship.invoke([system_prompt] + state["messages"], config)
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
workflow.add_node("por_model", call_por_model)
workflow.add_node("por_tools", ToolNode(tools))

# Entry point
workflow.set_entry_point("por_model")

# Conditional edges
workflow.add_conditional_edges(
    "por_model",
    should_continue,
    {"continue": "por_tools", "end": END}
)
workflow.add_edge("por_tools", "por_model")

position_of_responsibility_assistant = workflow.compile(name="Position_of_responsibility_assistant")
position_of_responsibility_assistant.name = "Position_of_responsibility_assistant"
