import json
import jsonpatch

from config.redis_config import redis_service 
from pydantic import ValidationError
from models.resume_model import * 

from .update_summar_skills import update_summary_and_skills
from .common_tools import send_patch_to_frontend
from .ws_utils import send_patch_to_frontend

from utils.mapper import ResumeSectionLiteral


ValidSectionLiteral = Literal["certifications","education_entries","work_experiences","internships","achievements","positions_of_responsibility","extra_curriculars","academic_projects"]


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
        current_resume = redis_service.get_resume_by_threadId(thread_id)
        if not current_resume:
            return {"status": "error", "message": "Resume not found in Redis."}


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
            
            print("\n\n\n\n✅ Summary & Skills updated after 10 updates.\n\n")
            print(f"New Summary: {result.summary}")
            print(f"\n\nNew Skills: {result.skills}\n\n\n\n")
            
            if result.summary and result.summary.strip() != "" and result.summary.strip().lower() not in ["n/a","na","not available","no summary"]:
                current_resume["summary"] = result.summary
            if result.skills and len(result.skills) > 0:
                current_resume["skills"] = result.skills
            current_resume["total_updates"] = 0
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

