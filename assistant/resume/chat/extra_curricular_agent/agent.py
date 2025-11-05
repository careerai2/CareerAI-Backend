from langgraph.graph import StateGraph, END
from langgraph.types import Command
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from typing_extensions import TypedDict, Annotated
from langgraph.graph.message import add_messages
import json

from ..llm_model import llm,SwarmResumeState
from models.resume_model import ExtraCurricular
from .tools import tools
import assistant.resume.chat.token_count as token_count
from utils.safe_trim_msg import safe_trim_messages
from toon import encode
from textwrap import dedent


# ---------------------------
# 1. Define State
# ---------------------------

# class SwarmResumeState(TypedDict):
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

def call_extra_curricular_model(state: SwarmResumeState, config: RunnableConfig):

    user_id = config["configurable"].get("user_id")
    resume_id = config["configurable"].get("resume_id")
    tailoring_keys = config["configurable"].get("tailoring_keys", [])

    print(f"[Extra Curricular Agent] Handling user {user_id} for resume {resume_id}")

    latest_entries = state.get("resume_schema", {}).get("extra_curriculars", [])

    system_prompt = SystemMessage(
        content=dedent(f"""
        You are a **Fast, Accurate, and Obedient Extra-Curricular Assistant** for a Resume Builder.
        Act like a professional resume editor managing the Extra-Curricular Activities section.
        Each entry may include: **activity**, **position**, **description**, and **year**.

        ```
        --- CORE DIRECTIVE ---

        • Apply every change **Immediately** — never wait for multiple fields. One change = one patch.  
        • Always send patches (send_patches) first, then confirm briefly in text.  
        • Always verify the correct target before applying patches — honesty over speed.  
        • Every single data point (even one field) must trigger an immediate patch and confirmation.  
        • Do not show code, JSON, or tool names. You are part of the same hidden assistant system.  
        • Keep responses short, direct, and polished — no explanations unless asked.

        Current entries: {encode(latest_entries)}

        --- EXTRA-CURRICULAR RULES ---
        X1. Patch the extra-curricular list directly.  
        X2. Never modify or delete existing information unless the user explicitly instructs — pause and ask once for confirmation.  
        X3. Focus on one activity entry at a time.  
        X4. Confirm updates only after patches are sent successfully.  
        X5. Use **full organization or event names**, never abbreviations unless official.  
        X6. Ensure all years are in four-digit format (e.g., 2023).  
        X7. Write activity descriptions professionally — brief, action-oriented, and achievement-focused.  
        X8. If unclear or incomplete, ask one sharp follow-up instead of guessing.

        --- USER INTERACTION ---
        • Respond in a confident, professional, and helpful tone.  
        • Be brief but polite — sound like a skilled resume editor, not a machine.  
        • If data is unclear or inconsistent, ask concise clarifying questions.  
        • Maintain conversational flow while strictly following patch rules.  
        • Never mention internal operations, patches, or agent identities.  
        • Never say “Done” or confirm success until tool results confirm success. If a patch fails, retry or ask the user.

        --- OPTIMIZATION GOAL ---
        Output clean, standardized, and professional Extra-Curricular entries emphasizing:  
        - **Leadership roles and achievements**  
        - **Institution / organization credibility**  
        - **Concise, action-based descriptions**  
        - **Consistent year formatting**  
        Skip generic reflections like “learned teamwork” — focus on measurable impact and relevance to the target role = {tailoring_keys}.
        """
        ))


    
    messages = safe_trim_messages(state["messages"], max_tokens=1024)
    # messages =state["messages"]
    
    # print(messages)
    print("Trimmed msgs length:-",len(messages))

    response = llm_internship.invoke([system_prompt] + messages, config)
    
    token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
    token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)


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
workflow.add_node("extra_curricular_model", call_extra_curricular_model)
workflow.add_node("tools", ToolNode(tools))

# Entry point
workflow.set_entry_point("extra_curricular_model")

# Conditional edges
workflow.add_conditional_edges(
    "extra_curricular_model",
    should_continue,
    {"continue": "tools", "end": END}
)
workflow.add_edge("tools", "extra_curricular_model")

extra_curricular_assistant = workflow.compile(name="extra_curricular_assistant")
extra_curricular_assistant.name = "extra_curricular_assistant"
