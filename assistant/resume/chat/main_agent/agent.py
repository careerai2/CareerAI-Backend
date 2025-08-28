from langgraph.graph import StateGraph
from models.resume_model import ResumeLLMSchema
from ..handoff_tools import transfer_to_education_agent, transfer_to_internship_agent
from ..llm_model import llm,SwarmResumeState
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
import json
from .tools import tools
from langchain_core.messages.utils import (
    trim_messages,
    count_tokens_approximately
)
from ..utils.common_tools import calculate_tokens
from langchain_core.messages import HumanMessage

from utils.safe_trim_msg import safe_trim_messages
# ---------------------------
# 1. LLM Setup
# ---------------------------

llm = llm.bind_tools(tools)

# ---------------------------
# 2. Graph Nodes
# ---------------------------

def call_model(state: SwarmResumeState, config: RunnableConfig):
    # user_id = state["user_id"]
    # resume_id = state["resume_id"]
    
    user_id = config["configurable"].get("user_id")
    resume_id = config["configurable"].get("resume_id")
    tailoring_keys = config["configurable"].get("tailoring_keys", [])
    print(f"Calling Main model for user {user_id} with resume {resume_id}")

    latest_resume = state.get("resume_schema", {})
    
    filtered_resume = {
        "title": latest_resume.get("title"),
        "summary": latest_resume.get("summary"),
        "name": latest_resume.get("name"),
        "email": latest_resume.get("email"),
        "phone_number": latest_resume.get("phone_number"),
        "skills": latest_resume.get("skills"),
        "interests": latest_resume.get("interests"),
    }

    # print("Filtered Resume:", filtered_resume)

    system_prompt = SystemMessage(
    f"""
    You are the **Main Resume Assistant**, acting like a mentor to guide the user in building a strong, well-organized resume.  
    Your job is to **mentor, guide, and route** the user to the right agent for each section.

    **You handle top-level fields:** name, title, summary, email, phone_number, skills, and interests.  
    - Update these in real time if data is available.  
    - Suggest relevant skills for the targeted roles: {tailoring_keys}.  
    - For interests, ask the user or update/delete as needed.

    **Other sections are handled by agents:**  
    - Education → Education Agent  
    - Internships → Internship Agent  
    - Work Experience → Work Experience Agent  
    - Extra Curricular → Extra Curricular Agent  
    - Positions of Responsibility → Positions of Responsibility Agent  
    - Scholastic Achievements → Scholastic Achievements Agent  

    **Rules:**  
    - Keep responses short and concise.  
    - Don’t repeat points already in the resume.  

    **Current Resume Context:**  
    ```json
    {filtered_resume}
    ```
    """
)

    try:
        messages = safe_trim_messages(state["messages"], max_tokens=1024)
    
    # print(messages)
        print("Trimmed msgs length:-",len(messages))
    
        if not messages or len(messages) < 1:
            messages = [HumanMessage(content="")]  # or some default prompt

        
        response = llm.invoke([system_prompt] + messages, config)

        print(f"Token Usage (Output): {response.usage_metadata}")

        
        return {"messages": [response]}
    except Exception as e:
        print("Error occurred while calling main model:", e)
        # return {"messages": [HumanMessage(content="An error occurred while processing your request.")]}

def should_continue(state: SwarmResumeState):
    last_message = state["messages"][-1]
    return "continue" if last_message.tool_calls else "end"

# ---------------------------
# 3. Create Graph
# ---------------------------

workflow = StateGraph(SwarmResumeState)

workflow.add_node("main_assistant", call_model)
workflow.add_node("tools", ToolNode(tools))  # ToolNode auto handles tool calls

workflow.set_entry_point("main_assistant")

workflow.add_conditional_edges(
    "main_assistant", should_continue, {"continue": "tools", "end": END}
)
workflow.add_edge("tools", "main_assistant")

main_assistant = workflow.compile(name="main_assistant")
main_assistant.name = "main_assistant"
