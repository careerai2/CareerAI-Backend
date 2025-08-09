from langgraph.graph import StateGraph, END
from langgraph.types import Command
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from typing_extensions import TypedDict, Annotated
from langgraph.graph.message import add_messages
import json

from ..handoff_tools import transfer_to_main_agent, transfer_to_education_agent
from .tools import tools
from ..llm_model import llm,SwarmResumeState
from models.resume_model import ScholasticAchievement

# ---------------------------
# 1. Define State
# ---------------------------

# class SwarmResumeState(TypedDict):
#     user_id: str
#     resume_id: str
#     messages: Annotated[list, add_messages]  # All conversation messages

# ---------------------------
# 2. LLM with Tools

llm_scholastic_achievement = llm.bind_tools(tools)

# ---------------------------
# 3. Node Function
# ---------------------------

def call_scholastic_achievement_model(state: SwarmResumeState, config: RunnableConfig):

    user_id = config["configurable"].get("user_id")
    resume_id = config["configurable"].get("resume_id")
    tailoring_keys = config["configurable"].get("tailoring_keys", [])

    print(f"[Scholastic Achievement Agent] Handling user {user_id} for resume {resume_id}")
    
    latest_entries = state.get("resume_schema", {}).get("achievements", [])
    
    system_prompt = SystemMessage(
        f"""
        You are the **Scholastic Achievement Assistant** for a Resume Builder application.
        Act as an **elder brother / mentor**, guiding the user to build a strong Scholastic Achievement section.

        --- Responsibilities ---
        1. Collect and organize scholastic achievement info as mentioned in the schema.
        2. The user is targeting these roles: {tailoring_keys}. Ensure the generated content highlights relevant details—such as bullet points and descriptions—that showcase suitability for these roles.
        3. Always create or update entries using the `scholastic_achievement_tool` in real time **don't forget to provide index**.
        4. Ask one question at a time to fill missing details.
        5. If user asks about different section check ur tools or route them to that agent
        6. If u didn't understand the request → call `transfer_to_main_agent`.

        Scholastic Achievement Schema Context:
        ```json
        { json.dumps(ScholasticAchievement.model_json_schema(), indent=2) }
        ```

        Current Entries:
        ```json
        { json.dumps(latest_entries, indent=2) }
        ```
        """
    )

    response = llm_scholastic_achievement.invoke([system_prompt] + state["messages"], config)
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
workflow.add_node("scholastic_achievement_model", call_scholastic_achievement_model)
workflow.add_node("tools", ToolNode(tools))

# Entry point
workflow.set_entry_point("scholastic_achievement_model")

# Conditional edges
workflow.add_conditional_edges(
    "scholastic_achievement_model",
    should_continue,
    {"continue": "tools", "end": END}
)
workflow.add_edge("tools", "scholastic_achievement_model")

scholastic_achievement_assistant = workflow.compile(name="scholastic_achievement_assistant")
scholastic_achievement_assistant.name = "scholastic_achievement_assistant"
