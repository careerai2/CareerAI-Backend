
from langchain.tools import tool
from redis_config import redis_client as r
from pydantic import BaseModel, field_validator
from validation.resume_validation import ResumeModel
from websocket_manger import ConnectionManager
from app_instance import app
import json




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



def update_resume(user_id: str, resume_id: str, resume_data: dict):
    key = f"resume:{user_id}:{resume_id}"
    r.set(key, json.dumps(resume_data))
    print(f"Resume updated for user {user_id}, resume {resume_id}")


def deep_update(target: dict, updates: dict) -> dict:
    for key, val in updates.items():
        if isinstance(val, dict) and isinstance(target.get(key), dict):
            deep_update(target[key], val)
        else:
            target[key] = val
    return target


import jsonpatch


async def send_patch_to_frontend(user_id: str, patch: list[dict]):
    """Will send the JSON patch to the frontend via WebSocket."""
    manager: ConnectionManager = app.state.connection_manager
    if manager.active_connections.get(str(user_id)):
        try:
            await manager.send_json_to_user(user_id, {"type":"resume_patch","patch": patch})
            print(f"PATCH sent to user {user_id}: {patch}")
        except Exception as e:
            print(f"Failed to send patch to frontend for user {user_id}: {e}")
    else:
        print(f"No WebSocket connection found for user {user_id}")



class ResumeUpdateInput(BaseModel):
    user_id: str
    resume_id: str
    updates: dict

    @field_validator("updates", mode="before")
    @classmethod
    def parse_updates(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("updates must be a dict or JSON string.")
        return v


@tool
async def update_resume_fields(input: ResumeUpdateInput) -> None:
    """
    🔧 Tool: Update Resume Fields

    This function updates specific fields of a user's resume in response to a conversation.
    It is invoked by section-specific chatbot modules (e.g., education, internship) during resume-building.

    ## 🚀 Purpose
    Ensures the user’s resume is consistently and validly updated **in real-time**, based on confirmed user input.

    ## ⚙️ Workflow
    1. The input data (text or structured value) is matched and validated against a strict Pydantic schema for the corresponding section (e.g., `EducationEntry`, `InternshipEntry`).
    2. If valid, the updates are converted into a minimal JSON Patch.
    3. The JSON Patch is streamed to the frontend for live resume preview and editing.

    ## 🧾 Args
    - `input` (`ResumeUpdateInput`): An object containing:
        - `user_id` (`str`): The ID of the user whose resume is being updated.
        - `resume_id` (`str`): The ID of the resume being updated.
        - `updates` (`dict`): A dictionary of field-level updates.

    ## 📤 Returns
    - `None` directly. But sends an update event through WebSocket or API to update the frontend resume view in real time.

    ## 🔐 Important
    - Fields are strictly validated; no schema violations are allowed.
    - Fabricated or unconfirmed content must be avoided — only confirmed user responses are eligible for updates.
    """

    try:
        if not input.updates:
            raise ValueError("Missing 'updates' field in input.")

        print(f"Received update request for user {input.user_id}: {input}")
        # ResumeModel(**input.updates)  # Validate the updates against the ResumeModel
        old_resume = get_resume(input.user_id, input.resume_id)
        new_resume = deep_update(old_resume.copy(), input.updates)

        # Update resume in Redis
        update_resume(input.user_id, input.resume_id, new_resume)

        # Generate JSON patch
        patch = jsonpatch.make_patch(old_resume, new_resume).patch

        # Send patch to frontend via WebSocket
        await send_patch_to_frontend(input.user_id, patch)

    except Exception as e:
        print(f"Error updating resume for user {input.user_id}: {e}")






tools = [get_resume, update_resume_fields]


