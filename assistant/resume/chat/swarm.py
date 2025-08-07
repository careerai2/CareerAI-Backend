from langgraph.runtime import get_runtime
from langgraph.prebuilt import create_react_agent
from langgraph_swarm import create_handoff_tool
from typing_extensions import TypedDict, Annotated
from langchain_core.messages import AnyMessage, SystemMessage,HumanMessage,AIMessage
from langgraph.graph import StateGraph, MessagesState, START,END,add_messages
from langgraph_swarm import SwarmState
from fastapi import WebSocket
from models.resume_model import ResumeLLMSchema
from assistant.resume.chat.utils.tools import get_resume
from utils.convert_objectIds import convert_objectids
import json
from langgraph_swarm import create_swarm


from .education_agent.agent import education_assistant
from .internship_agent.agent import internship_assistant
from .main_agent.agent import main_assistant
from .position_of_responsibility_agent.agent import position_of_responsibility_assistant
from .workex_agent.agent import workex_assistant
from .extra_curricular_agent.agent import extra_curricular_assistant
from .scholastic_achievement_agent.agent import scholastic_achievement_assistant

from .utils.common_tools import get_resume


from langgraph.checkpoint.memory import InMemorySaver
from .llm_model import SwarmResumeState




memory = InMemorySaver()



graph = create_swarm(
    state_schema=SwarmResumeState,
    agents=[main_assistant, education_assistant, internship_assistant, 
            position_of_responsibility_assistant,
            workex_assistant,
            extra_curricular_assistant,
            scholastic_achievement_assistant
            ],
    default_active_agent="main_assistant"
).compile(checkpointer=memory)


async def stream_graph_to_websocket(user_input: str, websocket: WebSocket, user_id: str, resume_id: str,tailoring_keys: list[str] = None):
    # print(f"Streaming graph for user {user_id} with input {user_input}")
    # print(f"Tailoring keys for user {user_id}: {tailoring_keys}")
    async for event in graph.astream(
        {
            "messages": [
                {"role": "user", "content": f"{user_input}"}
            ],
            "resume_schema": get_resume(user_id, resume_id),
            "user_id": user_id,
            "resume_id": resume_id
        },
        config={
        "configurable": {
            "thread_id": f"{user_id}:{resume_id}",
            "user_id": user_id,
            "resume_id": resume_id,
            "tailoring_keys": tailoring_keys or []
        }
    }
        # context={"user_id": user_id, "resume_id": resume_id},  # for graphs
    ):
        
            
        for value in event.values():
            msg = value["messages"][-1]
            content = msg.content
            if isinstance(msg, AIMessage):
                print(f"Agent '{msg.name}' responded")
                content = msg.content
            if content and len(content) > 0:
                await websocket.send_json({"type": "message", "message": content})
