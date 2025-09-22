from pyexpat.errors import messages
from langgraph.graph import StateGraph, END
from langgraph.types import Command
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage,AIMessage,ToolMessage
from langchain_core.runnables import RunnableConfig
from typing_extensions import TypedDict, Annotated
from langgraph.graph.message import add_messages
import json
from langchain_core.messages import HumanMessage
from ..handoff_tools import transfer_to_internship_agent, transfer_to_main_agent
from .tools import tools
from ..llm_model import llm,SwarmResumeState
from models.resume_model import Education
from langchain_core.messages.utils import (
    trim_messages,
    count_tokens_approximately
)
from langchain_core.messages import convert_to_messages
from textwrap import dedent
from utils.safe_trim_msg import safe_trim_messages
import assistant.resume.chat.token_count as token_count
# from assistant.resume.chat.education_agent.functions import compact_education_entries 

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
    # latest_education = compact_education_entries(state.get("resume_schema", {}).get("education_entries", []))
    
    tailoring_keys = config["configurable"].get("tailoring_keys", [])
    

    

    system_prompt = SystemMessage(
            f"""
            You are the **Education Assistant** in a Resume Builder.

            Scope: Manage only the Education section.  
            Schema: {{college | degree | start_year | end_year | cgpa}} 
            Target relevance: {tailoring_keys}  

            === Workflow ===
            1. **Detect** → missing fields, timeline gaps, duplication, tailoring opportunities.  
            2. **Ask** → one concise, essential question at a time.  
            3. **Apply** → use `education_Tool` (add/update/delete) or `reorder_Tool` (chronology/importance). **It is your responsibilty to get the indexs from current entry and type them** 
            4. **Verify silently** → schema valid, years consistent, Chemical Engineering relevance strong, no duplicates.  
            5. **Escalate** → if request outside scope, transfer to correct agent.  

            === Rules ===
            - Be concise (≤60 words per user message).  
            - No raw data dumps; only perform tool updates.  
            - Confirm tool necessity before every call.  
            - No redundant clarifications; assume defaults unless critical.  
            - Optimize tailoring → emphasize achievements, metrics, academic rigor.  

            === Current Snapshot ===
            ```json
            {latest_education}
            ```
            """
        )

    print(system_prompt)


    messages = safe_trim_messages(state["messages"], max_tokens=1024)
    # messages =state["messages"]

    print("Trimmed msgs length:-",len(messages))

    try:
        response = llm_education.invoke([system_prompt] + messages, config)

        print("Education Response Token Usage:", response.usage_metadata)

        token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
        token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)


        return {"messages": [response]}
    except Exception as e:
        print("Error occurred while calling education model:", e)
        # return {"messages": [HumanMessage(content="An error occurred while processing your request.")]}


# ---------------------------
# 4. Conditional Routing
# ---------------------------
def should_continue(state: SwarmResumeState):
    last_message = state["messages"][-1]
    # print(last_message)
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
