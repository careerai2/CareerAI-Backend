from config.redis_config import redis_service
from websocket_manger import ConnectionManager
from app_instance import app
import json
from models.resume_model import * 
from utils.mapper import resume_section_map,ResumeSectionLiteral,Fields
import jsonpatch
from pydantic import ValidationError
import jsonpointer
from .update_summar_skills import update_summary_and_skills
import re
import json
from typing import Optional, Dict, Any

# def get_resume(user_id: str, resume_id: str) -> dict:
#     """Fetch the resume for a specific user.

#     Args:
#         user_id (str): The ID of the user whose resume is to be fetched.
#         resume_id (str): The ID of the resume to fetch.

#     Returns:
#         dict: The resume data for the user, or an empty dict if not found.
#     """
#     data = r.get(f"resume:{user_id}:{resume_id}")
    
    
#     return json.loads(data) if data else {}


# def get_resume_by_threadId(thread_id: str) -> dict:
#     """Fetch the resume for a specific user.

#     Args:
#         user_id (str): The ID of the user whose resume is to be fetched.
#         resume_id (str): The ID of the resume to fetch.

#     Returns:
#         dict: The resume data for the user, or an empty dict if not found.
#     """
#     data = r.get(f"resume:{thread_id}")
    
    
#     return json.loads(data) if data else {}



def get_graph_state(user_id: str, resume_id: str, key: str) -> dict:
    """Fetch the graph state for a specific user and resume."""
    try:

        default_state = {
        "error_msg": None,
        "retrieved_info": "None",
        "generated_query": "",
        "save_node_response": "",
        "pathches": []
        }
           
        return default_state

    except Exception as e:
        print(f"Error fetching graph state: {e}")
        return {}






# def get_tailoring_keys(user_id: str, resume_id: str) -> list:
#     """Fetch the tailoring keys for a specific user's resume.

#     Args:
#         user_id (str): The ID of the user whose resume is to be fetched.
#         resume_id (str): The ID of the resume to fetch.

#     Returns:
#         list: The tailoring keys for the resume, or an empty list if not found.
#     """
#     data = r.get(f"resume:{user_id}:{resume_id}")
    
#     if not data:
#         return []
    
#     data = json.loads(data)
    
#     # print(data.get("tailoring_keys"))  # Debugging line
#     if "tailoring_keys" in data:
#         return data["tailoring_keys"]

#     return []



# def save_resume(user_id: str, resume_id: str, resume: dict):
#     key = f"resume:{user_id}:{resume_id}"
#     r.set(key, json.dumps(resume))



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


async def retrive_entry_from_resume(
    threadId: str,
    section: ResumeSectionLiteral,
    entryIndex: Optional[int] = None
):
    try:
        resume = redis_service.get_resume_by_threadId(threadId)
        
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
        
        if entryIndex is None:
            return section_entries
        
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
        current_resume_raw = redis_service.get_resume_by_threadId(thread_id) 
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
        redis_service.save_resume_by_threadId(thread_id,current_resume)

        # Notify frontend
        user_id = thread_id.split(":")[0]
        print(f"User ID: {user_id}, Section: {section}, Applied patches: {patches}")
        await send_patch_to_frontend(user_id, current_resume)

        return {"status": "success", "message": f"{section} updated successfully.", "index": index}

    except ValidationError as ve:
        return {"status": "error", "message": f"Validation error: {ve.errors()}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}



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




def get_unique_indices(patch_list: List[Dict]) -> List[int]:
    indices = set()
    import re
    for patch in patch_list:
        match = re.match(r"^/(\d+)(/.*)?$", patch["path"])
        if match:
            indices.add(int(match.group(1)))
    return list(indices)


ValidSectionLiteral = Literal[
    "certifications",
    "education_entries",
    "work_experiences",
    "internships",
    "achievements",
    "positions_of_responsibility",
    "extra_curriculars",
    "academic_projects"
]


async def apply_patches_global(
    thread_id: str,
    patches: list[dict],
    section: ValidSectionLiteral

):
    """
    Apply JSON Patch (RFC 6902) operations to any section of the resume.

    Args:
        thread_id (str): Combined user_id:resume_id identifier.
        patches (list[dict]): List of JSON Patch operations.
        section (str): Target section (e.g., 'certifications', 'education', 'projects').

    The function:
        - Loads resume from Redis
        - Applies patches to the given section
        - Saves back to Redis
        - Syncs updates to frontend
        - Pushes undo info to Redis
    """

    try:
        if not patches:
            return {"status": "success", "message": "No patches to apply."}

        # Load current resume from Redis
        current_resume_raw = redis_service.get_resume_by_threadId(thread_id)
        if not current_resume_raw:
            return {"status": "error", "message": "Resume not found in Redis."}

        try:
            current_resume = json.loads(current_resume_raw)
        except json.JSONDecodeError:
            return {"status": "error", "message": "Corrupted resume data in Redis."}

        # Ensure the target section exists
        current_section = current_resume.get(section, [])
        if not isinstance(current_section, list):
            current_section = []
            

        # Apply patches
        try:
            jsonpatch.apply_patch(current_section, patches, in_place=True)
            print(f"✅ Applied patches to {section}: {patches}")
        except jsonpatch.JsonPatchException as e:
            return {"status": "error", "message": f"Failed to apply patch list: {e}"}

        # Save back to resume
        current_resume[section] = current_section

        # update Summary & Skills after 10 updates
        if current_resume["total_updates"] == 10:
            result = await update_summary_and_skills(current_resume=current_resume)
            current_resume["summary"] = result.summary
            current_resume["skills"] = result.skills
        else:
            current_resume["total_updates"] += 1
            
            
        # Save updated resume to Redis
        try:
            redis_service.save_resume_by_threadId(thread_id,current_resume)
        except TypeError as e:
            return {"status": "error", "message": f"Failed to serialize updated resume: {e}"}

       
        
        
        # Identify user safely
        user_id = thread_id.split(":", 1)[0] if ":" in thread_id else thread_id

        # Notify frontend
        await send_patch_to_frontend(user_id, current_resume)

       
        # print(f"User {user_id}: Applied patches to {section} section successfully.")
        return {"status": "success", "message": f"{section.capitalize()} section updated successfully."}

    except ValidationError as ve:
        return {"status": "error", "message": f"Validation error: {ve.errors()}"}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}
