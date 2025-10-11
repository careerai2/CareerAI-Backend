from redis_config import redis_client as r
from websocket_manger import ConnectionManager
from app_instance import app
import json
from models.resume_model import *
from ..llm_model import llm
from langchain_core.tools import tool
# from pydantic.json import 
from utils.mapper import resume_section_map,ResumeSectionLiteral,Fields
import jsonpatch
from pydantic import BaseModel, field_validator,ValidationError
from langchain_core.runnables import RunnableConfig
import jsonpointer

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


def get_resume_by_threadId(thread_id: str) -> dict:
    """Fetch the resume for a specific user.

    Args:
        user_id (str): The ID of the user whose resume is to be fetched.
        resume_id (str): The ID of the resume to fetch.

    Returns:
        dict: The resume data for the user, or an empty dict if not found.
    """
    data = r.get(f"resume:{thread_id}")
    
    
    return json.loads(data) if data else {}






def get_graph_state(user_id: str, resume_id: str, key: str) -> dict:
    """Fetch the graph state for a specific user and resume."""
    try:
        redis_key = f"state:{user_id}:{resume_id}:{key}"
        data = r.get(redis_key)

        if not data:
            default_state = {
                "retrieved_info": "None",
                "generated_query": "",
                "save_node_response": "",
                "pathches": []
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


def generate_inverse_patch(original_obj, patches):
    inverse_patches = []
    for patch in patches:
        op = patch["op"]
        path = patch["path"]
        old_value = jsonpointer.resolve_pointer(original_obj, path)
        
        if op == "replace":
            inverse_patches.append({"op": "replace", "path": path, "value": old_value})
        elif op == "add":
            inverse_patches.append({"op": "remove", "path": path})
        elif op == "remove":
            inverse_patches.append({"op": "add", "path": path, "value": old_value})
    return inverse_patches


# @tool
def undo_last_patch(thread_id: str) -> dict:
    """ Undoes the last patch applied to the resume identified by thread_id."""
    undo_stack_key = f"undo_stack:{thread_id}"
    last_patch_raw = r.lpop(undo_stack_key)
    if not last_patch_raw:
        return {"status": "error", "message": "Nothing to undo"}

    last_patch_entry = json.loads(last_patch_raw)
    section = last_patch_entry["section"]
    index = last_patch_entry["index"]
    patches = last_patch_entry["patches"]

    # Load resume
    current_resume = json.loads(r.get(f"resume:{thread_id}"))
    current_section = current_resume.get(section, [])

    if index >= len(current_section):
        return {"status": "error", "message": "Index out of range for undo"}

    # Generate inverse patch
    inverse_patches = generate_inverse_patch(current_section[index], patches)

    print(f"Applying inverse patches: {inverse_patches}")
    # Apply inverse
    jsonpatch.apply_patch(current_section[index], inverse_patches, in_place=True)

    # Save back
    current_resume[section] = current_section
    r.set(f"resume:{thread_id}", json.dumps(current_resume))

    return {"status": "success", "message": "Undo applied","resume": current_resume }


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



def calculate_tokens():
    pass


async def retrive_entry_from_resume(
    threadId: str,
    section: ResumeSectionLiteral,
    entryIndex: Optional[int] = None
):
    try:
        resume = get_resume_by_threadId(threadId)
        
        if not resume:
            print("Resume not found")
            return None

        # Handle summary separately
        if section == "summary":
            return {"summary":resume.get("summary", {})}

        # For other sections, ensure entryIndex is provided
        if (section != "summary" and entryIndex is None):
            print("Invalid entry index")
            return None

        # Access the section safely
        section_entries = resume.get(section, [])
        if entryIndex >= len(section_entries):
            print(f"Entry index {entryIndex} out of range for section {section}")
            return None

        return section_entries[entryIndex]

    except Exception as e:
        print(f"Error while retrieving the entry. Error msg: {e}")
        return None



from typing import Optional


async def apply_section_patches(
    thread_id: str,
    section: ResumeSectionLiteral,
    patches: list[dict],
    index: Optional[int] = None
):
    """
    Adds or updates an entry in the given resume section and syncs with Redis + frontend.
    Sections: internships, education_entries, work_experiences, achievements, etc.
    """
    
    print(f"Applying patches to section '{section}' with index '{index}': {patches}")
    try:
        if not patches:
            print("No patches to apply, skipping save.")
            return {"status": "success", "message": "No patches to apply."}

        # Load resume from Redis
        current_resume_raw = r.get(f"resume:{thread_id}")
        if not current_resume_raw:
            raise ValueError("Resume not found for the given thread_id.")
        current_resume = json.loads(current_resume_raw)

        # Ensure section exists in resume
        current_section = current_resume.get(section, [])
        
        
        if not isinstance(current_section, list):
            # Summary or other non-list sections
            current_section = current_resume.get(section, {})

        # Special case: summary (dict, not list)
        if section == "summary":
            print("Updating summary section")
            jsonpatch.apply_patch(current_resume, patches, in_place=True)
            

        else:
            # Ensure index handling
            if index is not None:
                try:
                    index = int(index)
                except ValueError:
                    print(f"Invalid index provided: {index}, will create new entry.")
                    index = None

            if index is not None and 0 <= index < len(current_section):
                print(f"Updating existing entry at index {index} in section '{section}'")
                jsonpatch.apply_patch(current_section[index], patches, in_place=True)

            # Save section back
            current_resume[section] = current_section

        # Save back to Redis
        r.set(f"resume:{thread_id}", json.dumps(current_resume))

        # Notify frontend
        user_id = thread_id.split(":")[0]
        print(f"User ID: {user_id}, Section: {section}, Applied patches: {patches}")
        await send_patch_to_frontend(user_id, current_resume)

        return {"status": "success", "message": f"{section} updated successfully.", "index": index}

    except ValidationError as ve:
        return {"status": "error", "message": f"Validation error: {ve.errors()}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}



# def get_patch_field_and_index(patch_path: str):
#     """
#     Extracts internship index and field from a JSON Patch path.
#     Examples:
#       /0/company_name  -> index=0, field='company_name'
#       /1/duration      -> index=1, field='duration'
#       /internship_work_description_bullets -> index=None, field='internship_work_description_bullets'
#     """
#     parts = patch_path.lstrip("/").split("/")
#     if len(parts) == 0:
#         return None, ""
#     if parts[0].isdigit():
#         return int(parts[0]), parts[-1]
#     return None, parts[-1]

def get_patch_field_and_index(patch_path: str):
    """
    Extracts internship index and field from a JSON Patch path.
    Handles:
      - "/0/company_name" -> index=0, field='company_name'
      - "/1/role" -> index=1, field='role'
      - "/internship_work_description_bullets" -> index=None, field='internship_work_description_bullets'
      - "/-" -> index=None, field=None (append operation)
      - "/1/internship_work_description_bullets/-" -> index=1, field='internship_work_description_bullets', append=True
    Returns:
      index: int | None
      field: str | None
      append: bool
    """
    parts = patch_path.lstrip("/").split("/")
    append = False
    
    if not parts:
        return None, None, False
    
    # Check if the last part is '-' -> append operation
    if parts[-1] == "-":
        append = True
        parts = parts[:-1]  # remove the '-' to get actual field
    
    if not parts:
        # Path was just "/-"
        return None, None, append
    
    # First part is index if digit
    if parts[0].isdigit():
        index = int(parts[0])
        field = parts[1] if len(parts) > 1 else None
        return index, field, append
    
    # Path without index
    return None, parts[-1], append
