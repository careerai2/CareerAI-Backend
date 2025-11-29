from websocket_manger import ConnectionManager
from app_instance import app
from models.resume_model import * 


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




async def send_bullet_response(user_id: str, res:str):
    """Will send the JSON patch to the frontend via WebSocket."""
    manager: ConnectionManager = app.state.connection_manager
    if manager.active_connections.get(str(user_id)):
        try:
            await manager.send_json_to_user(user_id, {"type":"bullet_response","generated_text": res})
        except Exception as e:
            print(f"Failed to send bullet to frontend for user {user_id}: {e}")
    else:
        print(f"No WebSocket connection found for user {user_id}")
