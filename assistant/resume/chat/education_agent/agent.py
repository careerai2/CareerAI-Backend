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
    
    # print(f"Latest Education Entries: {json.dumps(latest_education, indent=2)}")
    

    system_prompt = SystemMessage(
        f"""
        You are the **Education Assistant** for a Resume Builder application.  
        Act as an **elder brother / mentor**, guiding the user to create a strong Education section.

        --- Responsibilities ---
        1. Guide user to provide Degree, Institute, Start & End Years.
        2. Encourage adding CGPA/Percentage and achievements.
        3. The user is targeting these roles: {tailoring_keys}. Ensure the generated content highlights relevant details—such as bullet points and descriptions—that showcase suitability for these roles.
        4. Create or update entries using `education_tool` in real time **don't forget to provide index**.
        5. You can move entries using `reorder_tool` with `MoveOperation`, it requires old_index and new_index,to move the entry,***Don't ask user for indexes brainstorm yourself you already have current entries***.
        6. When adding new entry, first check if the entry already exists, Inform the user and ask if they want to update it even for bullet points.
        7. Ask one question at a time to fill missing details.
        8. If user asks about different section check ur tools or route them to that agent
        9. If u didn't understand the request → call `transfer_to_main_agent`.

        Education Schema Context:
        ```json
        { json.dumps(Education.model_json_schema(), indent=2) }
        ```
        Current Entries:
        ```json
        { json.dumps(latest_education, indent=2) }
        ```
        """
    )

    response = llm_education.invoke([system_prompt] + state["messages"], config)
    
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
