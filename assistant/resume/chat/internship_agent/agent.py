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
from ..llm_model import llm,SwarmResumeState
from models.resume_model import Internship

# ---------------------------
# 1. Define State
# ---------------------------

class InternshipState(TypedDict):
    user_id: str
    resume_id: str
    messages: Annotated[list, add_messages]  # All conversation messages

# ---------------------------
# 2. LLM with Tools
# ---------------------------

tools = [transfer_to_main_agent, transfer_to_education_agent, internship_Tool]
llm_internship = llm.bind_tools(tools)

# ---------------------------
# 3. Node Function
# ---------------------------

def call_internship_model(state: SwarmResumeState, config: RunnableConfig):
   
    user_id = config["configurable"].get("user_id")
    resume_id = config["configurable"].get("resume_id")
    tailoring_keys = config["configurable"].get("tailoring_keys", [])
    
    print(f"[Internship Agent] Handling user {user_id} for resume {resume_id} with tailoring keys {tailoring_keys}")
    
    # Eg: [Internship Agent] Handling user 688a1bfa90accd05bcc8eb7b for resume 6894c8ea3b357837e5def6cd 
    # with tailoring keys ['consult'] # can use this to tailor the responses by using in prompt

    system_prompt = SystemMessage(
        f"""
        You are the **Internship Assistant** for a Resume Builder application.
        Act as an **elder brother / mentor**, guiding the user to build a strong Internship section.

        --- Responsibilities ---
        1. Collect and organize internship info (Company, Role, Duration, Location, Achievements).
        2. Create or update entries using `internship_tool` in real time **don't forget to provide index**.
        3. Ask one question at a time to fill missing details.

        Internship Schema Context:
        ```json
        { json.dumps(Internship.model_json_schema(), indent=2) }
        ```
        """
    )

    response = llm_internship.invoke([system_prompt] + state["messages"], config)
    return {"messages": [response]}

# ---------------------------
# 4. Conditional Routing
# ---------------------------

def should_continue(state: InternshipState):
    last_message = state["messages"][-1]
    return "continue" if last_message.tool_calls else "end"

# ---------------------------
# 5. Create Graph
# ---------------------------

workflow = StateGraph(InternshipState)

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
