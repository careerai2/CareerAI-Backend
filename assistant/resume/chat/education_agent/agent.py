from pyexpat.errors import messages
from langgraph.graph import StateGraph, END
from langgraph.types import Command
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from typing_extensions import TypedDict, Annotated
from langgraph.graph.message import add_messages
import json

from ..handoff_tools import transfer_to_internship_agent, transfer_to_main_agent
from .tools import tools
from ..llm_model import llm,SwarmResumeState
from models.resume_model import Education
from langchain_core.messages.utils import (
    trim_messages,
    count_tokens_approximately
)
from ..utils.common_tools import calculate_tokens
from langchain_core.messages import convert_to_messages
from textwrap import dedent


# ---------------------------
# 1. Define State
# ---------------------------

class EducationState(TypedDict):
    education_messages: Annotated[list, add_messages]
    education_entries: list[Education]


llm_education = llm.bind_tools(tools)

# ---------------------------
# 3. Node Function
# ---------------------------

def call_education_model(state: SwarmResumeState, config: RunnableConfig):



    latest_education = state.get("resume_schema", {}).get("education_entries", [])
    tailoring_keys = config["configurable"].get("tailoring_keys", [])
    

    

    system_prompt = SystemMessage(
    f"""
    You are an Education Assistant for a Resume Builder. Act like a mentor guiding the user.

    Instructions:
    {{
        "role": "mentor",
        "goal": "Build a strong Education section",
        "steps": [
            "Ask for degree, institute, start & end years, CGPA",
            "Tailor entries to {tailoring_keys} if relevant",
            "Use 'education_tool' to add/update entries (always include index)",
            "Use 'reorder_tool' with old_index → new_index when needed",
            "Check for existing entries before adding; confirm update if exists",
            "Route to other agents/tools if user switches section",
            "Call 'transfer_to_main_agent' if request is unclear"
        ]
    }}

    Education Schema:
    {{
        "college": "Optional[str]",
        "degree": "Optional[str]",
        "start_year": "Optional[int]",
        "end_year": "Optional[int]",
        "cgpa": "Optional[float]"
    }}

    Current Entries: use 'get_education_entries_tool'
    Remember:
        - Always use the index from the compact entries when calling `internship_tool`.
        - Keep your chat responses to the point and concise - do not repeat points added in the resume schema context.
    """
)

    
    messages = trim_messages(
        state["messages"],
        strategy="last",
        token_counter=count_tokens_approximately,
        max_tokens=1024,
        start_on="human",
        end_on=("human", "tool"),
    )
    messages = convert_to_messages(messages)
    # messages = state["messages"]

    if not messages or len(messages) < 1:
        from langchain.schema import HumanMessage
        messages = [HumanMessage(content="")]  # or some default prompt

    print("Trimmed msgs length:-",len(messages))


    response = llm_education.invoke([system_prompt] + messages, config)

    print("Education Response Token Usage:", response.usage_metadata)

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
