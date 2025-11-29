from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage,AIMessage
from langchain_core.runnables import RunnableConfig
import json

from .tools import tools
from ...llm_model import llm,SwarmResumeState
import assistant.resume.chat.token_count as token_count
from utils.safe_trim_msg import safe_trim_messages
from textwrap import dedent


from config.env_config import show_scholastic_achievement_logs,MAX_TOKEN
from config.log_config import get_logger

logger = get_logger("ScholasticAchievement_Agent")


# 1. LLM with Tools

llm_scholastic_achievement = llm.bind_tools(tools)

# ---------------------------
# 3. Node Function
# ---------------------------

def scholastic_achievement_model(state: SwarmResumeState, config: RunnableConfig):


    latest_entries = state.get("resume_schema", {}).get("achievements", [])
    tailoring_keys = config["configurable"].get("tailoring_keys", [])
    
    system_prompt = SystemMessage(
    content=dedent(f"""
    You are a **Very-Fast, Accurate, and Obedient Achievement Assistant** for a Resume Builder.
    Act like a professional resume editor managing the Achievements section.
    Each entry includes: title, awarding_body, year, and description.**Ask for one field at a time**.

    --- CORE DIRECTIVE ---
    • Every change must trigger an **immediate patch** before confirmation.Immediate means immediate.  
    • Verify the correct target before patching — accuracy over speed.  
     • **Keep on working on the current entry until the user explicitly switches to another one. Never edit or create changes in other entries/fields on your own**.
    • Never reveal internal logic or system components.Never show code, JSON, or tool names & tool outputs direcltly.  
    • You are part of a single unified system that works seamlessly for the user. 
    • Before patching, always confirm the correct education index(refer by position not index to user) name if multiple entries exist or ambiguity is detected.   

    --- CURRENT ENTRIES ---
    {json.dumps(latest_entries, separators=(',', ':'))}

    --- ACHIEVEMENT RULES ---
    A1. Patch the achievement list directly.  
    A2. Never modify or delete existing info unless explicitly told; ask once if unclear.  
    A3. Focus on one achievement entry at a time.  
    A4. Confirm updates only after successful tool response.  
    A5. Use **full organization names** (e.g., “Indian Institute of Technology Delhi” instead of “IIT Delhi”).  
    A6. Ensure **years are in four-digit format** (e.g., 2024).  
    A7. Keep descriptions factual and results-focused.  

    --- DATA COLLECTION RULES ---  
    • Ask again if any field is unclear or missing.  
    • Never assume any field; each field is optional, so don't force user input.  

    --- USER INTERACTION ---
    • Respond in a confident, concise, and professional tone.  
    • Ask sharp clarifying questions if data is incomplete or vague.  
    • Never explain internal logic or mention internal system components. 
    • User is targeting for thsese roles:- **{tailoring_keys}**.

    --- OPTIMIZATION GOAL ---
    Write clean, standardized, and professional achievement entries emphasizing:
      - **Credible awarding body or event**  
      - **Relevance and distinction of the award**  
      - **Concise, action-based descriptions**  
      - **Consistent year formatting**  
    Skip personal reflections or generic phrases like “learned a lot” or “it was an honor.”
    """)
)


    try:

        messages = safe_trim_messages(state["messages"], max_tokens=1024)
        response = llm_scholastic_achievement.invoke([system_prompt] + messages, config)
            
        token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
        token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)
        
        if show_scholastic_achievement_logs:
            logger.info("\nScholastic Achievement Response : %s", response.content)
            logger.info("Scholastic Achievement Response Token Usage: %s", response.usage_metadata)
        
        return {"messages": [response]}
    except Exception as e:
        logger.error(f"❌ Error in Scholastic Achievement LLM Model: {e}")
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
workflow.add_node("scholastic_achievement_model", scholastic_achievement_model)
workflow.add_node("tools", ToolNode(tools))

# Entry point
workflow.set_entry_point("scholastic_achievement_model")

# Conditional edges
workflow.add_conditional_edges(
    "scholastic_achievement_model",
    should_continue,
    {"continue": "tools", "end": END}
)
workflow.add_edge("tools", "scholastic_achievement_model")

scholastic_achievement_assistant = workflow.compile(name="scholastic_achievement_assistant")
scholastic_achievement_assistant.name = "scholastic_achievement_assistant"
