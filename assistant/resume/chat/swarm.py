from fastapi import WebSocket, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import AIMessage,HumanMessage
from fastapi import WebSocket
from models.resume_model import ResumeLLMSchema
from .utils.common_tools import get_resume
from .utils.save_chat_msg import save_chat_message
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
from redis_config import redis_client as r
from postgress_db import get_postgress_db


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

from langchain_core.messages import AIMessage
from pydantic import BaseModel, ValidationError
import json

async def update_resume_state(thread_id: str, new_resume: dict):
    """
    Updates the resume_schema in LangGraph state and Redis, 
    validating against ResumeLLMSchema before saving.
    """
    try:
        # ✅ Step 1: Validate resume against schema
        validated_resume = ResumeLLMSchema(**new_resume)

        # ✅ Step 2: Try updating LangGraph state
        graph.update_state(
            config={
                "configurable": {
                    "thread_id": thread_id
                }
            },
            values={
                "resume_schema": validated_resume.model_dump(),
                "messages": [
                    AIMessage(content="Resume schema updated externally.")
                ]
            }
        )

        key = f"resume:{thread_id}"
        r.set(key, validated_resume.json())

        print(f"Resume state & Redis updated for {thread_id}")

    except ValidationError as ve:
        print(f"❌ Resume validation failed: {ve}")
    except Exception as e:
        print(f"❌ Error updating resume state: {e}")


from enum import Enum

class AgentName(str, Enum):
    MAIN_ASSISTANT = "main_assistant"
    EDUCATION_ASSISTANT = "education_assistant"
    INTERNSHIP_ASSISTANT = "internship_assistant"
    WORKEX_ASSISTANT = "workex_assistant"
    POR_ASSISTANT = "Position_of_responsibility_assistant"
    SCHOLASTIC_ACHIEVEMENT_ASSISTANT = "scholastic_achievement_assistant"
    EXTRA_CURRICULAR_ASSISTANT = "extra_curricular_assistant"


class ask_agent_input(BaseModel):
    agent_name: AgentName
    selection: str
    question: str




async def set_agent(thread_id: str, agent_name: ask_agent_input):
    """
    Set the active agent of the graph and ask about a particular section of the resume.
    """
    try:


        graph.update_state(
            config={
                "configurable": {
                    "thread_id": thread_id
                }
            },
            values={
                "active_agent": agent_name,
                    "messages": [
                        AIMessage(content=f"Active Agent is set to {agent_name}")
                    ]
            }
        )


        print(f"Ask agent executed {thread_id}")

    except ValidationError as ve:
        print(f"❌ Resume validation failed: {ve}")
    except Exception as e:
        print(f"❌ Error updating resume state: {e}")




async def stream_graph_to_websocket(user_input: str | ask_agent_input, websocket: WebSocket, user_id: str, resume_id: str,tailoring_keys: list[str] = None, db: AsyncSession = Depends(get_postgress_db)):
    # print(f"Streaming graph for user {user_id} with input {user_input}")
    # print(f"Tailoring keys for user {user_id}: {tailoring_keys}")
    

    resume = get_resume(user_id, resume_id)
    
    print(user_input)
    
    # await save_chat_message(db, user_id, resume_id, user_input, sender_role='user')
    
    if isinstance(user_input, dict):
        try:
            user_input = ask_agent_input(**user_input)
        except ValidationError:
            # If it fails, maybe it's just a string message in dict form
            if "message" in user_input:
                user_input = user_input["message"]
            else:
                raise


    # For specific agent input
    if isinstance(user_input, ask_agent_input):
        print("I am running ask_agent_input")
        await set_agent(f"{user_id}:{resume_id}", user_input.agent_name.value)
        input = (
            f"Selected part: {user_input.selection} | "
            f"Question: {user_input.question if user_input.question else 'I need help with the selected part.'}"
        )
    else:
            
        if(user_input is None or user_input.strip() == ""):
            print(f"❌ Invalid input from user {user_id} for resume {resume_id}")
            return
        
        input = user_input

    async for event in graph.astream(
        {
            "messages": [
                {"role": "user", "content": f"{input}"}
            ],
            "resume_schema": resume,
        },
        config={
        "configurable": {
            "thread_id": f"{user_id}:{resume_id}",
            "user_id": user_id,
            "resume_id": resume_id,
            "tailoring_keys": tailoring_keys or []
        }
    },
        # context={"user_id": user_id, "resume_id": resume_id},  # for graphs
    ):
        
            
        for value in event.values():
            msg = value["messages"][-1]
            content = msg.content
            if isinstance(msg, AIMessage):
                # print(f"Agent '{msg.name}' responded")
                content = msg.content
            if content and len(content) > 0:
               try:
                #  await save_chat_message(db, user_id, resume_id, content, sender_role='assistant')
                 await websocket.send_json({"type": "message", "message": content})
               except Exception as e:
                   print(f"Error saving chat message: {e}")


