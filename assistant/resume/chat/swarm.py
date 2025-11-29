from fastapi import WebSocket, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import AIMessage
from fastapi import WebSocket
from models.resume_model import ResumeLLMSchema
# from .utils.save_chat_msg import save_chat_message
from langgraph_swarm import create_swarm
import json



# Multi step agents
from assistant.resume.chat.multi_step_agents.internship_agent.agent import internship_assistant
from assistant.resume.chat.multi_step_agents.acads_agent.agent import acads_assistant
from assistant.resume.chat.multi_step_agents.workex_agent.agent import workex_assistant
from assistant.resume.chat.multi_step_agents.position_of_responsibility_agent.agent import position_of_responsibility_assistant

from .main_agent.agent import main_assistant

# Single step agents
from assistant.resume.chat.single_step_agents.education_agent.agent import education_assistant 
from assistant.resume.chat.single_step_agents.certifications_agent.agent import certification_assistant 
from assistant.resume.chat.single_step_agents.extra_curricular_agent.agent import extra_curricular_assistant
from assistant.resume.chat.single_step_agents.scholastic_achievement_agent.agent import scholastic_achievement_assistant

from config.redis_config import redis_service
from utils.mapper import Fields


from langgraph.checkpoint.memory import InMemorySaver
from .llm_model import SwarmResumeState
from config.redis_config import redis_client as r
from config.postgress_db import get_postgress_db
from  config.log_config import get_logger


logger = get_logger("Auto Save")

memory = InMemorySaver()



graph = create_swarm(
    state_schema=SwarmResumeState,
    agents=[main_assistant, education_assistant, internship_assistant, 
            position_of_responsibility_assistant,
            workex_assistant,
            extra_curricular_assistant,
            scholastic_achievement_assistant,
            acads_assistant,
            certification_assistant
            ],
    default_active_agent="main_assistant"
).compile(checkpointer=memory)

from langchain_core.messages import AIMessage
from pydantic import BaseModel, ValidationError
import json

async def update_resume(thread_id: str, new_resume: dict):
    """
    Updates the resume and Redis, 
    validating against ResumeLLMSchema before saving.
    """
    logger.info(f"Resume AutoSave triggered for thread_id: {thread_id}")
    # print(new_resume)
    try:
        
       
        # ✅ Step 1: Validate resume against schema
        validated_resume = ResumeLLMSchema(**new_resume)

        # ✅ Step 2: Try updating LangGraph state
        # print(validated_resume.model_dump_json())
     
        # logger.info(f" Resume in AutoSave:\n\n{validated_resume}\n\n")
       
        key = f"resume:{thread_id}"
        r.set(key,  json.dumps(validated_resume.model_dump(),default=str))
        # r.set(key,  json.dumps(new_resume))

        # logger.info(f"✅ Resume updated and saved to Redis with key")

    except ValidationError as ve:
        logger.error(f"❌ Resume validation failed: {ve}")
    except Exception as e:
        logger.error(f"❌ Error updating resume state: {e}")
        
    # logger.info(f"Resume AutoSave FINISHED for thread_id: {thread_id}")




class ask_agent_input(BaseModel):
    # sectionId: str
    selected_text:str
    field: Fields
    question: str
    entryIndex:int | None = None    
    
    # entry_index: str | None = None  




# async def set_agent(thread_id: str, field: Fields):
#     """
#     Set the active agent of the graph and ask about a particular section of the resume.
#     """
#     try:

#         agent_name = agent_map(field) or "main_assistant"

    
#         graph.update_state(
#             config={
#                 "configurable": {
#                     "thread_id": thread_id
#                 }
#             },
#             values={
#                 "active_agent": agent_name,
#                     "messages": [
#                         AIMessage(content=f"Active Agent is set to {agent_name}")
#                     ]
#             }
#         )



#         print(f"Ask agent executed {thread_id}")

#     except ValidationError as ve:
#         print(f"❌ Resume validation failed: {ve}")
#     except Exception as e:
#         print(f"❌ Error updating resume state: {e}")




async def stream_graph_to_websocket(user_input: str | ask_agent_input, websocket: WebSocket, user_id: str, resume_id: str,tailoring_keys: list[str] = None, db: AsyncSession = Depends(get_postgress_db)):
    # print(f"Streaming graph for user {user_id} with input {user_input}")
    # print(f"Tailoring keys for user {user_id}: {tailoring_keys}")
    

    resume = redis_service.get_resume(user_id, resume_id)


    print(user_input)
    
    # await save_chat_message(db, user_id, resume_id, user_input, sender='user', type='sent')
    
    # if isinstance(user_input, dict):
    #     try:
    #         user_input = ask_agent_input(**user_input)
    #     except ValidationError:
    #         # If it fails, maybe it's just a string message in dict form
    #         if "message" in user_input:
    #             user_input = user_input["message"]
    #         else:
    #             raise


    # For specific agent input
   
        
    input = user_input
    thread_id=f"{user_id}:{resume_id}"

        # snapshot = graph.get_state(config={"configurable": {"thread_id": thread_id}})
        
        # if  snapshot.values.get("messages"):
        #     print(len(snapshot.values.get("messages")))
        # print(snapshot.values.get("internship",{"entry":{},"retrived_info":"None"}))

    
    async for event in graph.astream(
        {
            "messages": [
                {"role": "user", "content": f"{input}"}
            ],
            "resume_schema": resume,
            "internship": {},
            # "internship": get_graph_state(user_id, resume_id, "internship"),
            "workex": {},
            "por":{},
            "acads":{},
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
            
            if not isinstance(msg, AIMessage):
                continue
        
            content = msg.content

        # ✅ Ignore internal error messages or empty strings
            if not content or "Error:" in content or "not a valid tool" in content:
                print(f"⚠️ Skipping internal or invalid message: {content}")
                continue
            
            
            try:
            #  await save_chat_message(db, user_id, resume_id, content, sender='bot', type='received')
                await websocket.send_json({"type": "chat", "message": content})
            except Exception as e:
                print(f"Error saving chat message: {e}")


