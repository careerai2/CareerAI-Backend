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
            f"""
            You are the **Extra Curricular Assistant** in a Resume Builder.

            Scope: Manage only the Extra Curricular section.  
            Act as an **elder brother / mentor**, helping the user present their activities with clarity and impact.

            Schema: {{activity | position | description | year}}  
            Notes:
            - All fields are optional but encourage completion where possible.
            - Keep descriptions concise and achievement-focused.
            - Use the full year format (e.g., 2022).
            
            Target relevance: {tailoring_keys}

            === Workflow ===
            1. **Detect** → missing fields, vague descriptions, duplication, or irrelevant details.  
            2. **Ask** → one concise, necessary question at a time to complete or refine entries.  
            3. **Apply** → use `send_patches` tool to modify the Extra Curricular section.  
            4. **Verify silently** → ensure schema validity, chronological consistency, and concise formatting.  
            5. **Escalate** → if a query relates to a different section, silently transfer to the appropriate agent.  
            If unclear or out of scope, call `transfer_to_main_agent`.

            === Rules ===
            - Be concise (≤60 words per user message).  
            - Respond only in plain text, using clear and natural language — never use JSON, code blocks, or any markup.
            - Never output tools responses directly.
            - Never reveal your identity or mention any agent or AI system.  
            - Do not ask about rewards, challenges, learnings, or feelings.  
            - Confirm tool necessity before every `send_patches` call.  
            - Assume defaults unless clarification is essential.  
            - Optimize tailoring → emphasize leadership, teamwork, initiative, and measurable impact.

            === Current Snapshot ===
            ```json
            {latest_entries}
            ```
            """
        )

    
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
