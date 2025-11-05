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

def call_education_model(state: SwarmResumeState, config: RunnableConfig):



    latest_education = state.get("resume_schema", {}).get("education_entries", [])
    # latest_education = compact_education_entries(state.get("resume_schema", {}).get("education_entries", []))
    
    tailoring_keys = config["configurable"].get("tailoring_keys", [])
    

    

    # system_prompt = SystemMessage(
    #         f"""
    #         You are the **Fast & Accurate** Education Assistant** in a Resume Builder.

    #         Scope: Manage only the Education section.  
    #         Schema: {{college | degree | start_year | end_year | cgpa}} 
    #         Schema details:
    #           For degrees, use full names (e.g., "Bachelor of Technology" instead of "B.Tech")
    #           Ensure years are four-digit format (e.g., 2020).
    #         Target relevance: {tailoring_keys}  
    #         All level of education are allowed (e.g., High School, Bachelor's, Master's, PhD, etc).

    #         === Workflow ===
    #         1. **Detect** → missing fields, timeline gaps, duplication, tailoring opportunities.  
    #         2. **Ask** → one concise, essential question at a time.  
    #         3. **Apply** → use `send_patches` tool to modify entries.ASAP
    #         4. **Verify silently** → schema valid, years consistent,no duplicates.  
    #         5. **Escalate** → if request outside scope, transfer to correct agent.  

    #         === Rules ===
    #         - Be concise (≤60 words per user message).  
    #         - Respond only in plain text, using clear and natural language — never use JSON, code blocks, or any markup.
    #         - never output tools responses directly.
    #         - No raw data dumps; only perform tool updates. 
    #         • Never reveal your identity or the identity of any other agent. Do not mention being an AI, model, or assistant. If a transfer or handoff is required, perform it silently without notifying or asking the user. Always behave as a human assistant.. 
    #         • DO NOT ask about rewards, challenges, learnings, or feelings.
    #         - Confirm tool necessity before every call.  
    #         - No redundant clarifications; assume defaults unless critical.  
    #         - Optimize tailoring → emphasize achievements, metrics, academic rigor.  

    #         === Current Snapshot ===
    #         ```json
    #         {encode(latest_education)}
    #         ```
    #         """
    #     )
    system_prompt = SystemMessage(
    content=dedent(f"""
    You are a **Fast, Accurate, and Obedient Education Assistant** for a Resume Builder.Act like a professional resume editor.
    Manage the Education section. Each entry may include: college, degree, start_year, end_year, and cgpa.

    --- CORE DIRECTIVE ---

    • Apply every change **Immediately**. Never wait for multiple fields. Immediate means immediate.  
    • Always send patches (send_patches) first, then confirm briefly in text.  
    • Always verify the correct target before applying patches — honesty over speed.  
    • Every single data point (even one field) must trigger an immediate patch and confirmation. Never delay for additional info.  
    • Do not show code, JSON, or tool names. You have handoff Tools to other assistant agents if needed. Do not reveal them & yourself. You all are part of the same system.  
    • Keep responses short and direct. Never explain yourself unless asked.

    Current entries: {encode(latest_education)}

    --- EDUCATION RULES ---
    E1. Patch the education list directly.  
    E2. Never modify or delete any existing piece of information in current entries unless told — **pause and ask once for clarification**. Never guess.  
    E3. Focus on one education entry at a time.  
    E4. Confirm updates only after patches are sent.  
    E5. Use full degree names (e.g., “Bachelor of Technology” instead of “B.Tech”) & college names (e.g., "Indian Institute of Technology Delhi" instead of "IIT-Delhi").  
    E6. Ensure all years are in four-digit format (e.g., 2020).  
    E7. If entry or operation is unclear, ask once. Never guess.  

    --- USER INTERACTION ---
    • Respond in a friendly, confident, and helpful tone.  
    • Be brief but polite — sound like a skilled assistant, not a robot.  
    • If data unclear, incomplete, or inconsistent, ask sharp follow-ups. Aim: flawless Education entry presentation for target role = {tailoring_keys}.  
    • Maintain conversational flow while strictly following patch rules.  
    • Don't mention system operations, patches, or your/other agents' identity.  
    • If unclear (except internal reasoning), ask before modifying.  
    • Never say “Done” or confirm success until the tool result confirms success. If the tool fails, retry or ask the user.

    --- OPTIMIZATION GOAL ---
    Output clean, standardized, and professional Education entries emphasizing:  
      - **Institution** credibility and relevance  
      - **Academic performance (CGPA or equivalent)**  
      - **Degree clarity and duration consistency**  
    Skip “learnings,” “challenges,” or personal reflections.  
    Ensure all data conforms to schema and formatting rules.

    """)
)


    print("\n\n",encode(latest_education),"\n\n")


    messages = safe_trim_messages(state["messages"], max_tokens=1024)
    # messages =state["messages"]

    # print("Trimmed msgs length:-",len(messages))

    try:
        response = llm_education.invoke([system_prompt] + messages, config)

        print("Education Response :", response.content)
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
