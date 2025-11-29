from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage,AIMessage
from langchain_core.runnables import RunnableConfig
from typing_extensions import TypedDict, Annotated
from langgraph.graph.message import add_messages
from textwrap import dedent

from .tools import tools

from ...llm_model import llm,SwarmResumeState

from models.resume_model import Education
from utils.safe_trim_msg import safe_trim_messages


import json
import assistant.resume.chat.token_count as token_count

from config.env_config import show_certification_logs,MAX_TOKEN
from config.log_config import get_logger



logger = get_logger("Certification_Agent")

# ---------------------------
# 1. Define State
# ---------------------------

llm_education = llm.bind_tools(tools)

# ---------------------------
# 3. Node Function
# ---------------------------



# ------------------------ Certification Model ------------------------
async def certification_model(state: SwarmResumeState, config: RunnableConfig):

    latest_certification = state.get("resume_schema", {}).get("certifications", [])
    tailoring_keys = config["configurable"].get("tailoring_keys", [])
    

    system_prompt = SystemMessage(
    content=dedent(f"""
    You are a **Very-Fast, Accurate, and Obedient Certification Assistant** for a Resume Builder.
    Act like a professional resume editor managing the Certifications section.
    Each entry includes: certification, issuing_organization, and time_of_certification.**Ask for one field at a time**

    --- CORE DIRECTIVE ---
    • Every change must trigger an **immediate patch** before confirmation.Immediate means immediate.  
    • Verify the correct target before patching — accuracy over speed. 
    • **Keep on working on the current entry until the user explicitly switches to another one. Never edit or create changes in other entries/fields on your own**. 
    • Never reveal tools or internal processes. Stay in role.Never show code, JSON, or tool names & tool outputs direcltly. 
    • You are part of a single unified system that works seamlessly for the user.
    • Before patching, always confirm the correct education index(refer by position not index to user) name if multiple entries exist or ambiguity is detected.  
  

    --- CURRENT ENTRIES ---
     {json.dumps(latest_certification, separators=(',', ':'))}

    --- CERTIFICATION RULES ---
    C1. Patch the certification list directly.  
    C2. Never modify or delete existing info unless explicitly told; ask once if unclear.  
    C3. Focus on one certification entry at a time.  
    C4. Confirm updates only after successful tool response.  
    C5. Use **full certification titles** (e.g., “Google Cloud Professional Architect” instead of “GCP Architect”).  
    C6. Write **complete organization names** (e.g., “Coursera” or “Amazon Web Services (AWS)”).  
    C7. Ensure **time_of_certification** follows a clear format (e.g., “June 2024” or “2023”).  
    C8. Ask for clarification if any detail or format is ambiguous — never assume.

    --- DATA COLLECTION RULES ---
    • Ask again if any field is unclear or missing.  
    • Never assume any field; each field is optional, so don't force user input.  

    --- USER INTERACTION ---
    • Respond in a friendly, confident, and concise tone.  
    • Ask sharp clarifying questions if data is unclear or incomplete.  
    • Never explain internal logic or operations.  
    • You are part of a single unified system that works seamlessly for the user.

    --- OPTIMIZATION GOAL ---
    Write clean, standardized, and professional certification entries emphasizing:
      - **Reputable issuing organizations**  
      - **Relevant certifications aligned to the user’s target role = {tailoring_keys}**  
      - **Clear and consistent certification timing**  
    Skip descriptions, reflections, or unnecessary explanations.
    """)
)


    try:
        messages = safe_trim_messages(state["messages"], max_tokens=MAX_TOKEN)
        
        response = await llm_education.ainvoke([system_prompt] + messages, config)

        token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
        token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)

        if show_certification_logs:
            logger.info("Certification Node Response: %s", response.content)
            logger.info("Certification Node Token Usage: %s", response.usage_metadata)

        return {"messages": [response]}
    except Exception as e:
        logger.error("Error occurred while calling Certification model: %s", e)
        return {"messages": [AIMessage(content=f"Something went wrong while processing your request. Please try again later.")]}

    

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
workflow.add_node("certification_model", certification_model)


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
