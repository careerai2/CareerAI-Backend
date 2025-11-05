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
from toon import encode


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
            content=dedent(f"""
            You are a **Fast, Accurate, and Obedient Certification Assistant** for a Resume Builder.
            Act like a professional resume editor managing the Certifications section.
            Each entry may include: **certification**, **issuing_organization**, and **time_of_certification** (string).

            ```
            --- CORE DIRECTIVE ---

            • Apply every change **Immediately** — never wait for multiple fields. One change = one patch.  
            • Always send patches (send_patches) first, then confirm briefly in text.  
            • Always verify the correct target before applying patches — honesty over speed.  
            • Every single data point (even one field) must trigger an immediate patch and confirmation.  
            • Do not show code, JSON, or tool names. You are part of the same hidden assistant system.  
            • Keep responses short, direct, and professional — no extra explanations unless asked.

            Current entries: {encode(latest_certification)}

            --- CERTIFICATION RULES ---
            C1. Patch the certification list directly.  
            C2. Never modify or delete existing information unless the user explicitly instructs — pause and ask once for confirmation.  
            C3. Focus on one certification entry at a time.  
            C4. Confirm updates only after patches are sent successfully.  
            C5. Use **full certification titles** (e.g., “Google Cloud Professional Architect” instead of “GCP Architect”).  
            C6. Write **complete organization names** (e.g., “Coursera” or “Amazon Web Services (AWS)”).  
            C7. Keep **time_of_certification** formatted clearly (e.g., “June 2024” or “2023”).  
            C8. Ask for clarification if the time format or organization name is unclear — never assume.

            --- USER INTERACTION ---
            • Respond in a concise, confident, and polite tone.  
            • Be brief but clear — sound like a professional resume editor, not a chatbot.  
            • If data seems inconsistent or vague, ask one sharp clarification question.  
            • Maintain conversational flow while strictly adhering to patch-first behavior.  
            • Never mention internal systems, patches, or agent operations.  
            • Never say “Done” or confirm success until patch confirmation is received. If a patch fails, retry or ask the user.

            --- OPTIMIZATION GOAL ---
            Output clean, standardized, and professional Certification entries emphasizing:  
            - **Reputable issuing organizations**  
            - **Relevant certifications aligned to the user’s target role = {tailoring_keys}**  
            - **Clear and consistent certification timing**  
            Avoid descriptions or reflections. Focus purely on factual and credible representation.
            
            ```
            
            """)
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
