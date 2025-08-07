from langgraph.graph import StateGraph, END
from langgraph.types import Command
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from typing_extensions import TypedDict, Annotated
from langgraph.graph.message import add_messages
import json

from ..handoff_tools import transfer_to_internship_agent, transfer_to_main_agent
from .tools import education_Tool
from ..llm_model import llm,SwarmResumeState
from models.resume_model import Education

# ---------------------------
# 1. Define State
# ---------------------------

class EducationState(TypedDict):
    user_id: str
    resume_id: str
    messages: Annotated[list, add_messages]  # Conversation messages

# ---------------------------
# 2. LLM with Tools
# ---------------------------

tools = [transfer_to_internship_agent, transfer_to_main_agent, education_Tool]


llm_education = llm.bind_tools(tools)

# ---------------------------
# 3. Node Function
# ---------------------------

def call_education_model(state: SwarmResumeState, config: RunnableConfig):
    user_id = state["user_id"]
    resume_id = state["resume_id"]
    print(f"[Education Agent] Handling user {user_id} for resume {resume_id}")

    system_prompt = SystemMessage(
        f"""
        You are the **Education Assistant** for a Resume Builder application.  
        Act as an **elder brother / mentor**, guiding the user to create a strong Education section.

        --- Responsibilities ---
        1. Guide user to provide Degree, Institute, Start & End Years.
        2. Encourage adding CGPA/Percentage and achievements.
        3. Create or update entries using `education_tool` in real time **don't forget to provide index**.
        4. Ask one question at a time to fill missing details.
        5. If user asks about different section check ur tools or route them to that agent
        6. If u didn't understand the request → call `transfer_to_main_agent`.

        Education Schema Context:
        ```json
        { json.dumps(Education.model_json_schema(), indent=2) }
        ```
        """
    )

    response = llm_education.invoke([system_prompt] + state["messages"], config)
    return {"messages": [response]}

# ---------------------------
# 4. Conditional Routing
# ---------------------------

def should_continue(state: EducationState):
    last_message = state["messages"][-1]
    return "continue" if last_message.tool_calls else "end"

# ---------------------------
# 5. Create Graph
# ---------------------------

workflow = StateGraph(EducationState)

# Add nodes
workflow.add_node("education_model", call_education_model)
workflow.add_node("tools", ToolNode(tools))

# Entry point
workflow.set_entry_point("education_model")

# Conditional edges
workflow.add_conditional_edges(
    "education_model",
    should_continue,
    {"continue": "tools", "end": END}
)
workflow.add_edge("tools", "education_model")

education_assistant = workflow.compile(name="education_assistant")
education_assistant.name = "education_assistant"
