from redis_config import redis_client as r
from websocket_manger import ConnectionManager
from app_instance import app
import json
from models.resume_model import *
from ..llm_model import llm




def get_resume(user_id: str, resume_id: str) -> dict:
    """Fetch the resume for a specific user.

    Args:
        user_id (str): The ID of the user whose resume is to be fetched.
        resume_id (str): The ID of the resume to fetch.

    Returns:
        dict: The resume data for the user, or an empty dict if not found.
    """
    data = r.get(f"resume:{user_id}:{resume_id}")
    
    
    return json.loads(data) if data else {}


def get_tailoring_keys(user_id: str, resume_id: str) -> list:
    """Fetch the tailoring keys for a specific user's resume.

    Args:
        user_id (str): The ID of the user whose resume is to be fetched.
        resume_id (str): The ID of the resume to fetch.

    Returns:
        list: The tailoring keys for the resume, or an empty list if not found.
    """
    data = r.get(f"resume:{user_id}:{resume_id}")
    
    if not data:
        return []
    
    data = json.loads(data)
    
    # print(data.get("tailoring_keys"))  # Debugging line
    if "tailoring_keys" in data:
        return data["tailoring_keys"]

    return []



def save_resume(user_id: str, resume_id: str, resume: dict):
    key = f"resume:{user_id}:{resume_id}"
    r.set(key, json.dumps(resume))



async def send_patch_to_frontend(user_id: str, resume: ResumeLLMSchema):
    """Will send the JSON patch to the frontend via WebSocket."""
    manager: ConnectionManager = app.state.connection_manager
    if manager.active_connections.get(str(user_id)):
        try:
            await manager.send_json_to_user(user_id, {"type":"resume_update","resume": resume})
            # print(f"New resume sent to user {user_id}")
        except Exception as e:
            print(f"Failed to send patch to frontend for user {user_id}: {e}")
    else:
        print(f"No WebSocket connection found for user {user_id}")



from typing import List,Union
from langchain_core.messages import BaseMessage
from langchain_core.messages.utils import (
    trim_messages,
    count_tokens_approximately
)


def normalize_content(content: Union[str, list, dict]) -> str:
    """Convert message content into a plain string for token counting."""
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        # Some LangChain messages are a list of chunks
        return " ".join([normalize_content(c) for c in content])
    elif isinstance(content, dict):
        # Tool calls etc.
        return str(content)
    else:
        return str(content)

def calculate_tokens(messages: List[BaseMessage], system_prompt=None):
    """
    Calculate approximate token usage for input (system + messages).
    Returns a dict with counts.
    """
    total_tokens = 0

    # Add system prompt if present
    if system_prompt:
        system_text = normalize_content(system_prompt.content)
        system_tokens = count_tokens_approximately(system_text)
        total_tokens += system_tokens
    else:
        system_tokens = 0

    # Add user/AI messages
    msg_tokens = 0
    for m in messages:
        msg_text = normalize_content(m.content)
        msg_tokens += count_tokens_approximately(msg_text)

    total_tokens += msg_tokens

    return {
        "system_tokens": system_tokens,
        "message_tokens": msg_tokens,
        "input_tokens": total_tokens,
    }