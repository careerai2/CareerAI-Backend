from langgraph.graph import StateGraph
from models.resume_model import ResumeLLMSchema
from ..llm_model import llm,SwarmResumeState
from langchain_core.messages import SystemMessage,AIMessage,ToolMessage
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
import assistant.resume.chat.token_count as token_count


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
    print(f"Calling Main model for user {user_id} with resume {resume_id} and tailoring_key = {tailoring_keys[0]}")

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
    You are the **Main Resume Assistant**, mentoring the user to build a strong, organized resume.  
    **Top-level fields you handle:** name, title, summary, email, phone_number, skills, interests. Update in real-time, suggest role-relevant skills ({tailoring_keys}), and manage interests.  

    **Other sections are handled by agents:** Education→education_agent, Internships→internship_agent, Work Experience→workex_agent, Extra Curricular→extra_curricular_agent, Positions of Responsibility→por_agent,Academic Projects→acads_agent, Scholastic Achievements→scholastic_achievement_agent. **Transfer directly without asking**.

    **Rules:** Keep responses concise (~80-90 words), don’t repeat existing points.  

    **Current Resume Context (top-level fields only):**  
    ```json
    {filtered_resume}
    ```
    """
)


    try:
        # messages =state["messages"]
        messages = safe_trim_messages(state["messages"], max_tokens=1024)
    
    # print(messages)
        print("Trimmed msgs length:-",len(messages))
    
        if not messages or len(messages) < 1:
            messages = [HumanMessage(content="")]  # or some default prompt

        
        response = llm.invoke([system_prompt] + messages, config)

        print(f"Token Usage (Output): {response.usage_metadata}")
        
        
        token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
        token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)

        # print("Total Input Tokens:", token_count.total_Input_Tokens)
        # print("Total Output Tokens:", token_count.total_Output_Tokens)

        print("response:", response)
        
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
