from langgraph.graph import StateGraph, END
from langgraph.types import Command
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from typing_extensions import TypedDict, Annotated
from langgraph.graph.message import add_messages
import json

from ..llm_model import llm,SwarmResumeState
from models.resume_model import ExtraCurricular
from .tools import tools

# ---------------------------
# 1. Define State
# ---------------------------

# class SwarmResumeState(TypedDict):
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

def call_extra_curricular_model(state: SwarmResumeState, config: RunnableConfig):

    user_id = config["configurable"].get("user_id")
    resume_id = config["configurable"].get("resume_id")
    tailoring_keys = config["configurable"].get("tailoring_keys", [])

    print(f"[Extra Curricular Agent] Handling user {user_id} for resume {resume_id}")

    latest_entries = state.get("resume_schema", {}).get("extra_curriculars", [])

    system_prompt = SystemMessage(
        f"""
        You are the **Extra Curricular Assistant** for a Resume Builder application.
        Act as an **elder brother / mentor**, guiding the user to build a strong Extra Curricular section.

        --- Responsibilities ---
        1. Collect and organize extra curricular info according to the schema given below.
        2. The user is targeting these roles: {tailoring_keys}. Ensure the generated content highlights relevant details—such as bullet points and descriptions—that showcase suitability for these roles.
        3. Always create or update entries using the `extra_curricular_tool` and  in real time **don't forget to provide index**.
        4. Ask one question at a time to fill missing details.
        5. If user asks about different section check ur tools or route them to that agent
        6. If u didn't understand the request → call `transfer_to_main_agent`.


        Extra Curricular Schema Context:
        ```json
        { json.dumps(ExtraCurricular.model_json_schema(), indent=2) }
        ```

        Current Entries:
        ```json
        { json.dumps(latest_entries, indent=2) }
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
workflow.add_node("extra_curricular_model", call_extra_curricular_model)
workflow.add_node("tools", ToolNode(tools))

# Entry point
workflow.set_entry_point("extra_curricular_model")

# Conditional edges
workflow.add_conditional_edges(
    "extra_curricular_model",
    should_continue,
    {"continue": "tools", "end": END}
)
workflow.add_edge("tools", "extra_curricular_model")

extra_curricular_assistant = workflow.compile(name="extra_curricular_assistant")
extra_curricular_assistant.name = "extra_curricular_assistant"
