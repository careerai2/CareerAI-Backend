from langgraph.graph import StateGraph, END
from langgraph.types import Command
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from typing_extensions import TypedDict, Annotated
from langgraph.graph.message import add_messages
import json

from .tools import tools
from ..llm_model import llm,SwarmResumeState
from models.resume_model import PositionOfResponsibility
from langchain_core.messages.utils import (
    trim_messages,
    count_tokens_approximately
)
from ..utils.common_tools import calculate_tokens
from utils.safe_trim_msg import safe_trim_messages
import assistant.resume.chat.token_count as token_count

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

    latest_entries = state.get("resume_schema", {}).get("positions_of_responsibility")
    # print(latest_entries)
    system_prompt = SystemMessage(
        f"""
        You are the **Position Of Responsibility (POR) Assistant** for a Resume Builder.
        Act as a helpful mentor guiding the user to build a strong POR section.

        --- Responsibilities ---
        1. Collect POR info (Role, Role Description, Organization, Organization Description, Location, Duration, Responsibilities).
        2. Focus on roles: {tailoring_keys}. Highlight relevant details in **short responses (~60-70 words)**.
        3. Use `position_of_responsibility_tool` to add/update/delete entries (**always provide index & type**). 
        Never ask the user for indexes; decide yourself using current entries.
        4. Rearrange entries using `reorder_tool` and responsibilities using `reorder_responsibilities_tool` as needed.
        5. Ask **one question at a time**. Do **not** show changes — resume is live-previewed.
        6. Route to appropriate agent if user talks about a different section.
        7. Call `transfer_to_main_agent` if request is unclear.

        --- POR Schema ---
        role, role_description, organization, organization_description,
        location, duration, responsibilities (List[str])

        --- Current Entries (Compact Version) ---
        {latest_entries if latest_entries else "None"}

        Remember:
        - Always use the index from compact entries when calling `position_of_responsibility_tool`.
        - Keep responses short and focused (~60-70 words).
        """
    )

    messages = safe_trim_messages(state["messages"], max_tokens=1024)
    print("Trimmed msgs length:-",len(messages))
    

    response = llm_internship.invoke([system_prompt] + messages, config)
    
        
    token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
    token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)


    print("POR Response Token Usage:", response.usage_metadata)

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
