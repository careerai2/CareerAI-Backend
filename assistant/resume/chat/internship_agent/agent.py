from langgraph.graph import StateGraph, END
from langgraph.types import Command
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage,AIMessage,ToolMessage
from langchain_core.runnables import RunnableConfig
from typing_extensions import TypedDict, Annotated
from langgraph.graph.message import add_messages
from ..llm_model import llm,SwarmResumeState
from models.resume_model import Internship
from .tools import tools
from langchain_core.messages.utils import (
    trim_messages,
    count_tokens_approximately
)
from ..utils.common_tools import calculate_tokens
from textwrap import dedent
from utils.safe_trim_msg import safe_trim_messages
import assistant.resume.chat.token_count as token_count
# ---------------------------
# 2. LLM with Tools
# ---------------------------

llm_internship = llm.bind_tools(tools)

# ---------------------------
# 3. Node Function
# ---------------------------


class InternshipState(SwarmResumeState):
    pass

def call_internship_model(state: SwarmResumeState, config: RunnableConfig):
   
    user_id = config["configurable"].get("user_id")
    resume_id = config["configurable"].get("resume_id")
    tailoring_keys = config["configurable"].get("tailoring_keys", [])
    
    # print(f"[Internship Agent] Handling user {user_id} for resume {resume_id} with tailoring keys {tailoring_keys}")
    
    # latest_entries = state.get("resume_schema", {}).get("internships", [])
    
    current_entries = state.get("resume_schema", {}).get("internships", [])
    # current_entries = compact_internship_entries(state.get("resume_schema", {}).get("internships", []))

    system_prompt = SystemMessage(
    content=dedent(f"""
        You are the Internship Assistant for a Resume Builder.
        Your role: refine and optimize the Internship section with precision, brevity, and tailoring.

        --- Workflow ---
        • Ask one clear, single-step question at a time.
        • Use tools (internship_Tool, internship_bullet_tool, reorder_Tool) as needed.
        • Decide indexes and update types (add/update/delete) yourself — never ask the user.
        • Use use_knowledge_base to fetch exact action verbs, must-haves, and good-to-haves. Present them first in concise bullet points before creating or editing an entry.
        • Keep outputs concise (~60–70 words max).

        --- Schema ---
        {{company_name, company_description, location, designation, designation_description, duration, internship_work_description_bullets[]}}

        --- Current Entries (Compact) ---
        Always use the following as reference when updating internships:
        {current_entries}

        --- Guidelines ---

        Always reference internships by index from compact entries.

        Focus on clarity, brevity, and alignment with {tailoring_keys}.

        Resume updates are auto-previewed — never show raw code/JSON changes.

"""))

    
    # print(system_prompt.content)

    
    messages = safe_trim_messages(state["messages"], max_tokens=1024)
    # messages =state["messages"]
    
    # print(messages)
    print("Trimmed msgs length:-",len(messages))
 

    response = llm_internship.invoke([system_prompt] + messages, config)
    
    token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
    token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)


    print("Internship Token Usage:", response.usage_metadata)

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
