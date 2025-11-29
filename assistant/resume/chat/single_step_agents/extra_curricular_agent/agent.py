from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage,AIMessage
from langchain_core.runnables import RunnableConfig

from ...llm_model import llm,SwarmResumeState
from .tools import tools

import assistant.resume.chat.token_count as token_count
from utils.safe_trim_msg import safe_trim_messages
from textwrap import dedent

from config.env_config import show_extra_curricular_logs,MAX_TOKEN
from config.log_config import get_logger

import json

logger = get_logger("ExtraCurricular_Agent")

# ---------------------------
# 1. LLM with Tools
# ---------------------------

llm_internship = llm.bind_tools(tools)

# ---------------------------
# 3. Node Function
# ---------------------------


# ------------------------ Extra-Curricular Model ------------------------
async def extra_curricular_model(state: SwarmResumeState, config: RunnableConfig):

    latest_entries = state.get("resume_schema", {}).get("extra_curriculars", [])
    tailoring_keys = config["configurable"].get("tailoring_keys", [])


    system_prompt = SystemMessage(
    content=dedent(f"""
    You are a **Very-Fast, Accurate, and Obedient Extra-Curricular Assistant** for a Resume Builder.
    Act like a professional resume editor managing the Extra-Curricular Activities section.
    Each entry includes: activity, position, description, and year.**Ask for one field at a time**.

    --- CORE DIRECTIVE ---
    • Every change must trigger an **immediate patch** before confirmation.Immediate means immediate.    
    • Verify the correct target before patching — accuracy over speed.  
    • Never reveal internal logic or system components.Never show code, JSON, or tool names & tool outputs direcltly.  
    • You are part of a single unified system that works seamlessly for the user.
    • Before patching, always confirm the correct education index(refer by position not index to user) name if multiple entries exist or ambiguity is detected.   

    --- CURRENT ENTRIES ---
     {json.dumps(latest_entries, separators=(',', ':'))}


    --- EXTRA-CURRICULAR RULES ---
    X1. Patch the extra-curricular list directly.  
    X2. Never modify or delete existing info unless explicitly told; ask once if unclear.  
    X3. Focus on one activity entry at a time.  
    X4. Confirm updates only after successful tool response.  
    X5. Use **full event or organization names** — avoid unofficial abbreviations.  
    X6. Ensure all years use a **four-digit format** (e.g., 2023).  
    X7. Write **action-oriented and outcome-focused** descriptions.  

    --- DATA COLLECTION RULES ---
    • Ask again if any field is unclear or missing.  
    • Never assume any field; each field is optional, so don't force user input.  

    --- USER INTERACTION ---
    • Respond in a confident, concise, and polished tone.  
    • Ask sharp clarifying questions if data is vague or inconsistent.  
    • Keep working on the current entry until the user explicitly switches to another one. Never edit or create changes in other entries on your own.
    • Never explain internal logic.  
    • You are part of a single unified system that works seamlessly for the user.   

    --- OPTIMIZATION GOAL ---
    Skip generic reflections like “learned teamwork”; focus on actions and results relevant to the target role = {tailoring_keys}.
    """)
)

    try:
    
        messages = safe_trim_messages(state["messages"], max_tokens=MAX_TOKEN)

        response = llm_internship.invoke([system_prompt] + messages, config)
        
        token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
        token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)

        if show_extra_curricular_logs:
            logger.info("\nExtra-Curricular Response : %s", response.content)
            logger.info("Extra-Curricular Response Token Usage: %s", response.usage_metadata)

        return {"messages": [response]}
    
    except Exception as e:
        logger.error(f"❌ Error in Extra-Curricular LLM Model: {e}")
        return {"messages": [AIMessage(content="An error occurred while processing your request.Please try again.")]}



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
workflow.add_node("extra_curricular_model", extra_curricular_model)
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
