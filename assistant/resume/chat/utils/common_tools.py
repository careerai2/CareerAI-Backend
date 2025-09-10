from redis_config import redis_client as r
from websocket_manger import ConnectionManager
from app_instance import app
import json
from models.resume_model import *
from ..llm_model import llm
from langchain_core.tools import tool
# from pydantic.json import 



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


def get_graph_state(user_id: str, resume_id: str, key: str) -> dict:
    """Fetch the graph state for a specific user and resume."""
    try:
        redis_key = f"state:{user_id}:{resume_id}:{key}"
        data = r.get(redis_key)

        if not data:
            default_state = {
                "entry": Internship().model_dump() if hasattr(Internship, "model_dump") else {},
                "retrived_info": "None"
            }
            r.set(redis_key, json.dumps(default_state))
            return default_state

        # data is already a str
        return json.loads(data)

    except Exception as e:
        print(f"Error fetching graph state: {e}")
        return {}


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


from langgraph.types import Interrupt,interrupt
from langchain_core.runnables import RunnableConfig



@tool(
    description="Use this tool to request assistance from a human when the task is too complex or requires subjective judgment. Provide a clear and concise query to get the best help.",
    return_direct=True
)
async def human_assistance(query: str,config:RunnableConfig) -> str:
    """Request assistance from a human."""
    
    user_id = config["configurable"].get("user_id")
    
    await app.state.connection_manager.send_json_to_user(
        user_id,
        {"type": "system", "message": query}
    )

    human_response = interrupt({"query": query})
    return human_response["data"]


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
    
import os 

def load_kb(role: str,field:str):
    # Build the path dynamically
    file_path = os.path.join("assistant", "resume", "roles", f"{role}.json")
    
    with open(file_path, "r", encoding="utf-8") as f:
        kb = json.load(f)

    # Ensure the specified field key exists
    return kb.get(field, {})


import re
import json
from typing import Optional, Dict, Any

def extract_json_from_response(content: str) -> Optional[Dict[str, Any]]:
    """Extract JSON from LLM response using multiple patterns."""
    patterns = [
        r"```json\s*([\s\S]*?)\s*```",  # JSON fenced block
        r"```\s*([\s\S]*?)\s*```",      # Generic fenced block
        r"(\{[\s\S]*\})"                # Any JSON object (greedy, multiline)
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError as e:
                # print(f"Failed to parse with error: {e}")  # Debug if needed
                continue
    
    print("No valid JSON found in response")
    return None
