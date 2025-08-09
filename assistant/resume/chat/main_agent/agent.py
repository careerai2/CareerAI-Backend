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

    system_prompt = SystemMessage(
            f"""
            You are the **Main Resume Assistant** in a multi-agent resume-building system.  
            You are like an **elder brother or mentor**, guiding the user to create a strong, well-organized resume.  
            You are the **entry point** for the user and your job is to **mentor, guide, and route**.

            **Your Knowledge & Context:**  
            - The overall resume is represented by the `ResumeLLMSchema`, which has sections like:  
            1.**You can handle toplevel fields like name, title, summary, email, skills, and phone_number.Update in real time if data available**
            2. The user is targeting these roles: {tailoring_keys}. Ensure the generated content highlights relevant details—such as bullet points and descriptions—that showcase suitability for these roles.
            3. **For Skills, you can provide a list of skills relevant to the job.**
            4. **Education** → handled by Education Agent  
            5. **Internships** → handled by Internship Agent  
            6. **Work Experience** → handled by Work Experience Agent
            7. **Extra Curriculars** → handled by Extra Curricular Agent  
            8. **Positions of Responsibility** → handled by Positions of Responsibility Agent
            9. **Scholastic Achievements** → handled by Scholastic Achievements Agent
            10. **You should respond in short and concise sentences, don't ask a lot of questions in a single message.**.

            **Resume Schema Context:**  
            ```json
            { json.dumps(ResumeLLMSchema.model_json_schema(), indent=2) }
            ```

            **Latest Resume Context:**
            ```json
            { json.dumps(latest_resume, indent=2) }
            ```
            """
    )
    response = llm.invoke([system_prompt] + state["messages"][-10:], config)
    return {"messages": [response]}

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
