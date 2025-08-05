
from langchain.tools import tool
from redis_config import redis_client as r
from pydantic import BaseModel, field_validator
from validation.resume_validation import ResumeModel
from websocket_manger import ConnectionManager
from app_instance import app
import json
from typing import Literal
from models.resume_model import *
from copy import deepcopy  
from typing import Optional, Literal
from pydantic import BaseModel, field_validator
import json, jsonpatch
from copy import deepcopy
from langchain_core.tools import tool



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

def save_resume(user_id: str, resume_id: str, resume: dict):
    key = f"resume:{user_id}:{resume_id}"
    r.set(key, json.dumps(resume))


import jsonpatch


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

# ---- Pydantic input schema ----
class EducationToolInput(BaseModel):
    type: Literal["add", "update", "delete"] = "add"  # Default to add
    updates: Optional[Education] = None              # Optional for delete
    index: Optional[int] = None                      # Optional index

    @field_validator("updates", mode="before")
    @classmethod
    def parse_updates(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("updates must be a dict or JSON string.")
        return v


# ---- Tool function ----
@tool(
    name_or_callable="education_tool",
    description="Add, update, or delete an education entry in the user's resume. "
                "Requires index for update/delete operations.",
    args_schema=EducationToolInput,
    infer_schema=True,
    return_direct=False,
    response_format="content",
    parse_docstring=False
)
async def education_Tool(
    index: int | None,  # Optional index for update/delete operations
    user_id: str = "688a1bfa90accd05bcc8eb7b",
    resume_id: str = "688e0b6cddced7b7d4df3ae3",
    type: Literal["add", "update", "delete"] = "add",
    updates: Optional[Education] = None,
) -> None:
    """Add, update, or delete an education entry in the user's resume. 
    Index is required for update/delete operations.
    """

    try:
        if not user_id or not resume_id:
            raise ValueError("Missing user_id or resume_id in context.")

        # ✅ Validate operation
        if type != "delete" and not updates:
            raise ValueError("Missing 'updates' for add/update operation.")
        if type in ["update", "delete"] and index is None:
            raise ValueError("Index is required for update/delete operation.")

        print({
            "updates": updates,
            "type": type,
            "index": index
        })


        

        # Deep copy for JSON patch
        new_resume = get_resume(user_id, resume_id)
        
        # Ensure key exists
        if "education_entries" not in new_resume:
            new_resume["education_entries"] = []

        # Convert updates to dict safely (ignore unset fields for partial updates)
        updates_data = updates.model_dump(exclude_unset=True) if updates else None

        # ---- Handle operations ----
        if type == "delete":
            if index < len(new_resume['education_entries']):
                del new_resume['education_entries'][index]
            else:
                raise IndexError("Index out of range for education entries.")

        elif type == "add":
            base_entry = Education().model_dump()  # All fields None
            base_entry.update(updates_data or {})
            new_resume['education_entries'].append(base_entry)

        elif type == "update":
            if index < len(new_resume['education_entries']):
                # Merge only the provided fields
                for k, v in updates_data.items():
                    new_resume['education_entries'][index][k] = v
            else:
                raise IndexError("Index out of range for education entries.")

        # ---- Save & Notify ----
        save_resume(user_id, resume_id, new_resume)
        await send_patch_to_frontend(user_id, new_resume)

        print(f"✅ Education section updated for {user_id}")

    except Exception as e:
        print(f"❌ Error updating resume for user: {e}")












class InternshipToolInput(BaseModel):
    user_id: Optional[str] = None
    resume_id: Optional[str] = None
    type: Literal["add", "update", "delete"] = "add"  # Default operation
    updates: Optional[Internship] = None
    index: Optional[int] = None  # Required for update/delete

    @field_validator("updates", mode="before")
    @classmethod
    def parse_updates(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("updates must be a dict or JSON string.")
        return v


@tool(
    name_or_callable="internship_tool",
    description="Add, update, or delete an internship entry in the user's resume. "
                "Requires index for update/delete operations.",
    args_schema=InternshipToolInput,
    infer_schema=True,
    return_direct=False,
    response_format="content",
    parse_docstring=False
)
async def internship_Tool(
    index: int | None,
    user_id: str = "688a1bfa90accd05bcc8eb7b",
    resume_id: str = "688e0b6cddced7b7d4df3ae3",
    type: Literal["add", "update", "delete"] = "add",
    updates: Optional[Internship] = None,
) -> None:
    """Add, update, or delete an internship entry in the user's resume. 
    Index is required for update/delete operations.
    """
    try:
        if not user_id or not resume_id:
            raise ValueError("Missing user_id or resume_id in context.")

        # ✅ Validate operation
        if type != "delete" and not updates:
            raise ValueError("Missing 'updates' for add/update operation.")
        if type in ["update", "delete"] and index is None:
            raise ValueError("Index is required for update/delete operation.")

        print({
            "updates": updates,
            "type": type,
            "index": index
        })

        # Deep copy for JSON patch
        new_resume = get_resume(user_id, resume_id)
        if not new_resume:
            raise ValueError("Resume not found.")


        # Convert updates to dict safely (ignore unset fields for partial updates)
        updates_data = updates.model_dump(exclude_unset=True) if updates else None

        # ---- Handle operations ----
        if type == "delete":
            if index < len(new_resume['internships']):
                del new_resume['internships'][index]
            else:
                raise IndexError("Index out of range for internship entries.")

        elif type == "add":
            base_entry = Internship().model_dump()  # All fields None
            base_entry.update(updates_data or {})
            new_resume['internships'].append(base_entry)

        elif type == "update":
            if index < len(new_resume['internships']):
                for k, v in updates_data.items():
                    new_resume['internships'][index][k] = v
            else:
                raise IndexError("Index out of range for internship entries.")

        # ---- Save & Notify ----
        save_resume(user_id, resume_id, new_resume)

        await send_patch_to_frontend(user_id, new_resume)

        print(f"✅ Internship section updated for {user_id}")

    except Exception as e:
        print(f"❌ Error updating internship for user {user_id}: {e}")









tools_education = [get_resume, education_Tool]

tools_internship = [get_resume, internship_Tool]


