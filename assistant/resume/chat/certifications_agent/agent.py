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

Max_TOKENS = 325

def call_education_model(state: SwarmResumeState, config: RunnableConfig):



    latest_certification = state.get("resume_schema", {}).get("certifications", [])
    # latest_education = compact_education_entries(state.get("resume_schema", {}).get("education_entries", []))
    
    tailoring_keys = config["configurable"].get("tailoring_keys", [])
    

    

    system_prompt = SystemMessage(
            f"""
            You are the **Certification Assistant** in a Resume Builder.

            Scope: Manage only the Certification section.  
            Schema: {{ certification |issuing_organization | time_of_certification}} 
            schema details: 
                - certification → Write the certification name in Title Case (e.g., "AWS Certified Solutions Architect").  
                - issuing_organization → Write the full official name of the issuing organization in Title Case (e.g., "Amazon Web Services").  
                - time_of_certification → Write the date in " Date Month YYYY" format (e.g., "24 July 2026").

            Target relevance: {tailoring_keys}  

            === Workflow ===
            1. **Detect** → missing fields, timeline gaps, duplication, tailoring opportunities.  
            2. **Ask** → one concise, essential question at a time.  
            3. **Apply** → use `send_patches` to modify the current certification section .• Always apply patches directly to the entire `academic_projects` section (list) — not individual entries.
            4. **Verify silently** → schema valid, years consistent, no duplicates.  
            5. **Escalate** → if request outside scope, transfer to correct agent.  

            === Rules ===
            - Be concise (≤60 words per user message).  
            - Respond only in plain text, using clear and natural language — never use JSON, code blocks, or any markup.
            - never output tools responses directly.
            - No raw data dumps; only perform tool updates. 
            • Never reveal your identity or the identity of any other agent. Do not mention being an AI, model, or assistant. If a transfer or handoff is required, perform it silently without notifying or asking the user. Always behave as a human assistant.. 
            • DO NOT ask about rewards, challenges, learnings, or feelings.
            - Confirm tool necessity before every call.  
            - No redundant clarifications; assume defaults unless critical.  
            - Optimize tailoring → emphasize achievements, metrics, academic rigor.  

            === Current Entries ===
            ```json
            {latest_certification}
            ```
            """
        )


    messages = safe_trim_messages(state["messages"], max_tokens=Max_TOKENS)
    

    try:
        response = llm_education.invoke([system_prompt] + messages, config)

        token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
        token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)

        print("\Certification Node Token Usage:", response.usage_metadata)

        return {"messages": [response]}
    except Exception as e:
        print("Error occurred while calling Certification model:", e)
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
workflow.add_node("certification_model", call_education_model)
workflow.add_node("tools", ToolNode(tools))

# Entry point
workflow.set_entry_point("certification_model")

# Conditional edges
workflow.add_conditional_edges(
    "certification_model",
    should_continue,
    {"continue": "tools", "end": END}
)
workflow.add_edge("tools", "certification_model")

certification_assistant = workflow.compile(name="certification_assistant")
certification_assistant.name = "certification_assistant"
