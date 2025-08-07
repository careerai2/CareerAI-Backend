from redis_config import redis_client as r
from websocket_manger import ConnectionManager
from app_instance import app
import json
from models.resume_model import *





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
            print(f"New resume sent to user {user_id}")
        except Exception as e:
            print(f"Failed to send patch to frontend for user {user_id}: {e}")
    else:
        print(f"No WebSocket connection found for user {user_id}")


