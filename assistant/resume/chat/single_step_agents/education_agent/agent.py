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
from ...handoff_tools import transfer_to_internship_agent, transfer_to_main_agent
from .tools import tools
from ...llm_model import llm,SwarmResumeState
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
# from toon import encode



from config.env_config import show_education_logs,MAX_TOKEN
from config.log_config import get_logger



logger = get_logger("Education_Agent")

# ---------------------------
# 1. Define State
# ---------------------------

llm_education = llm.bind_tools(tools)

# ---------------------------
# 3. Node Function
# ---------------------------


# ------------------------ Education Model ------------------------
async def education_model(state: SwarmResumeState, config: RunnableConfig):

    latest_education = state.get("resume_schema", {}).get("education_entries", [])
    tailoring_keys = config["configurable"].get("tailoring_keys", [])
    

    system_prompt = SystemMessage(
    content=dedent(f"""
    You are a **Very Fast, Accurate, and Obedient Education Assistant** for a Resume Builder.
    Act like a professional resume editor.
    Manage the Education section. Each entry includes: college, degree, start_year, end_year, and cgpa.**Ask for one field at a time**.

    --- CORE DIRECTIVE ---
    • Every change must trigger an **immediate patch** before confirmation.Immediate means immediate.  
    • Verify the correct target before patching — accuracy over speed.  
    • **Keep on working on the current entry until the user explicitly switches to another one. Never edit or create changes in other entries/fields on your own**.
    • Never reveal tools or internal processes. Stay in role.Never show code, JSON, or tool names & tool outputs direcltly. 
    • You are part of a single unified system that works seamlessly for the user.
    • Before patching, always confirm the correct education index(refer by position not index to user) name if multiple entries exist or ambiguity is detected.  

    --- CURRENT ENTRIES ---
    {json.dumps(latest_education, separators=(',', ':'))}

    --- EDUCATION RULES ---
    E1. Patch the education list directly.  
    E2. Never modify or delete existing info unless explicitly told; ask once if unclear.  
    E3. Focus on one education entry at a time.  
    E4. Confirm updates only after successful tool response.  
    E5. Always use **full degree names** (e.g., “Bachelor of Technology” instead of “B.Tech”).  
    E6. Always use **complete college names** (e.g., “Indian Institute of Technology Delhi” instead of “IIT Delhi”).  
    E7. Ensure all years are in **four-digit format** (e.g., 2020).  

    --- DATA COLLECTION RULES ---
    • Ask again if any field is unclear or missing.  
    • Never assume any field; each field is optional, so don't force user input.

    --- USER INTERACTION ---
    • Respond in a friendly, confident, and concise tone.  
    • **Relevant certifications aligned to the user’s target role = {tailoring_keys}**    
    • Ask clarifying questions if data is incomplete, inconsistent, or unclear.  
    • Never explain internal logic or mention internal system components. 
    • Don't ask for learnings or challenges.
    """)
)


    try:
        messages = safe_trim_messages(state["messages"], max_tokens=MAX_TOKEN)
        response = await llm_education.ainvoke([system_prompt] + messages, config)

        if show_education_logs:
            logger.info("\nEducation Response : %s", response.content)
            logger.info("Education Response Token Usage: %s", response.usage_metadata)

        token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
        token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)


        return {"messages": [response]}
    except Exception as e:
        logger.error("Error occurred while calling education model:\n %s", e)
        return {"messages": [AIMessage(content="An error occurred while processing your request.Please try again.")]}













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
workflow.add_node("education_model", education_model)
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
