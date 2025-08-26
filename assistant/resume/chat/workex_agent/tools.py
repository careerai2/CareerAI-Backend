from langchain.tools import tool
from pydantic import BaseModel, field_validator
import json
from typing import Literal
from models.resume_model import *
from typing import Optional, Literal
from pydantic import BaseModel, field_validator
import json
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from ..utils.common_tools import get_resume, save_resume, send_patch_to_frontend
from ..handoff_tools import *
from ..utils.update_summar_skills import update_summary_and_skills
from redis_config import redis_client as r


@tool
def get_compact_work_experience_entries(config: RunnableConfig):
    """
    Get all work experience entries in a concise format.
    Returns: list of dicts with only non-null fields (projects included as counts or ignored).
    """
    try:
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")
        
        entries_raw = r.get(f"resume:{user_id}:{resume_id}")
        resume_data = json.loads(entries_raw) if entries_raw else {}
        entries = resume_data.get("work_experiences", [])

        entries = [e for e in entries if e and isinstance(e, dict)]

        compact = []
        for i, e in enumerate(entries):
            entry_dict = {
                "index": i,
                **{k: v for k, v in {
                    "company_name": e.get("company_name"),
                    "company_description": e.get("company_description"),
                    "designation": e.get("designation"),
                    # "designation_description": e.get("designation_description"),
                    "location": e.get("location"),
                    "duration": e.get("duration"),
                    "projects_count": len(e.get("projects", [])) if e.get("projects") else None
                }.items() if v not in [None, "", [], {}]}
            }
            compact.append(entry_dict)

        print("Compact work experience entries:", compact)
        return compact

    except Exception as e:
        print(f"Error in get_compact_work_experience_entries: {e}")
        return []


@tool
def get_work_experience_entry_by_index(index: int, config: RunnableConfig):
    """
    Get a single work experience entry by index.
    Returns full entry including projects and bullets.
    """
    try:
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")
        
        
        entries_raw = r.get(f"resume:{user_id}:{resume_id}")
        resume_data = json.loads(entries_raw) if entries_raw else {}
        entries = resume_data.get("work_experiences", [])

        if index is not None and 0 <= index < len(entries):
            print(entries[index])
            return entries[index]
        else:
            return {"error": "Invalid index or entry not found"}

    except Exception as e:
        print(f"Error in get_work_experience_entry_by_index: {e}")
        return {"error": str(e)}



class WorkExperienceToolInput(BaseModel):
    type: Literal["add", "update", "delete"] # Default operation
    updates: Optional[WorkExperience] = None
    index: int  # Required for update/delete

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
    name_or_callable="workex_tool",
    description="Add, update, or delete a work experience entry in the user's resume. "
                "Requires index for update/delete operations.",
    args_schema=WorkExperienceToolInput,
    infer_schema=True,
    return_direct=False,
    response_format="content",
    parse_docstring=False
)
async def workex_Tool(
    index: int,
    config: RunnableConfig,
    type: Literal["add", "update", "delete"],
    updates: Optional[WorkExperience] = None,
) -> None:
    """Add, update, or delete a work experience entry in the user's resume. 
    Index and Type are required for all operations.
    """
    try:
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")
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
            if index < len(new_resume['work_experiences']):
                del new_resume['work_experiences'][index]
            else:
                raise IndexError("Index out of range for work experience entries.")

        elif type == "add":
            base_entry = WorkExperience().model_dump()  # All fields None
            base_entry.update(updates_data or {})
            new_resume['work_experiences'].append(base_entry)

        elif type == "update":
            if index < len(new_resume['work_experiences']):
                for k, v in updates_data.items():
                    new_resume['work_experiences'][index][k] = v
            else:
                raise IndexError("Index out of range for work experience entries.")

        if new_resume["total_updates"] > 5:
            updated_service = await update_summary_and_skills(new_resume, new_resume.get("tailoring_keys", []))

            print(f"Updated service: {updated_service}")
            if updated_service is not None:
                if updated_service.summary:
                    new_resume["summary"] = updated_service.summary
                if updated_service.skills and 0 < len(updated_service.skills) <= 10:
                    new_resume["skills"] = updated_service.skills
                new_resume["total_updates"] = 0
        else:
            new_resume["total_updates"] = new_resume.get("total_updates", 0) + 1



        # ---- Save & Notify ----
        save_resume(user_id, resume_id, new_resume)

        await send_patch_to_frontend(user_id, new_resume)

        print(f"✅ Work Experience section updated for {user_id}")
        
        return {"status":"success"}

    except Exception as e:
        print(f"❌ Error updating work experience for user {user_id}: {e}")
        return {"status":"error", "message": str(e)}




class MoveOperation(BaseModel):
    old_index: int
    new_index: int


@tool(
    name_or_callable="reorder_tool",
    description="Reorder the work experience entries in the user's resume.",
    infer_schema=True,
    return_direct=False,
    response_format="content",
    parse_docstring=False
)
async def reorder_tool(operations: list[MoveOperation], config: RunnableConfig) -> None:
    """Reorder the work experience entries in the user's resume."""

    try:
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")
        
        # print(operations)

        if not user_id or not resume_id:
            raise ValueError("Missing user_id or resume_id in context.")

        # ✅ Validate operation
        if operations is None or len(operations) is 0:
            raise ValueError("Missing 'operations' for reorder operation.")
        
        
        new_resume = get_resume(user_id, resume_id)
                
        # Ensure key exists
        if "work_experiences" not in new_resume:
            raise ValueError("No work_experiences entries found in the resume.")

        total_entry = len(new_resume['work_experiences'])

        for op in operations:
            old_index = op.old_index
            new_index = op.new_index
            
            if not isinstance(op, MoveOperation):
                raise ValueError("Invalid operation type. Expected 'MoveOperation'.")

            if old_index < 0 or old_index >= total_entry:
                raise IndexError(f"Old index {old_index} out of range for internship entries.")
            if new_index < 0 or new_index >= total_entry:
                raise IndexError(f"New index {new_index} out of range for internship entries.")


        # ---- Handle operations ----
        for op in sorted(operations, key=lambda x: x.old_index):
            old_index = op.old_index
            new_index = op.new_index

            # Move the entry
            entry = new_resume['work_experiences'].pop(old_index)
            new_resume['work_experiences'].insert(new_index, entry)

        # ---- Save & Notify ----
        save_resume(user_id, resume_id, new_resume)
        await send_patch_to_frontend(user_id, new_resume)

        print(f"✅ work_experiences section reordered for {user_id}")

        return {"status":"success"}

    except Exception as e:
        print(f"❌ Error reordering resume for user in work_experiences: {e}")
        return {"status":"error", "message": str(e)}





# ---- Tool function ----
@tool(
    name_or_callable="reorder_projects_tool",
    description="Reorder the responsibilities in a particular work_experience entry of the user's resume.",
    infer_schema=True,
    return_direct=False,
    response_format="content",
    parse_docstring=False
)
async def reorder_projects_tool(
    operations: list[MoveOperation],
    entry_at: int,
    config: RunnableConfig,
) -> None:
    """Reorder the projects in a particular work_experience entry of the user's resume."""

    try:
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")

        if not user_id or not resume_id:
            raise ValueError("Missing user_id or resume_id in context.")

        if not operations or len(operations) == 0:
            raise ValueError("Missing 'operations' for reorder operation.")

        new_resume = get_resume(user_id, resume_id)

        if "work_experiences" not in new_resume:
            raise ValueError("No work_experiences entries found in the resume.")

        total_entry = len(new_resume['work_experiences'])
        if entry_at < 0 or entry_at >= total_entry:
            raise IndexError(f"Entry index {entry_at} out of range.")

        projects = new_resume['work_experiences'][entry_at].get('projects', [])
        total_bullet_points = len(projects)

        if total_bullet_points == 0:
            raise ValueError("No projects found in the specified entry.")

        # ✅ Validate all moves before doing anything
        for op in operations:
            if not isinstance(op, MoveOperation):
                raise ValueError("Invalid operation type. Expected 'MoveOperation'.")
            if op.old_index < 0 or op.old_index >= total_bullet_points:
                raise IndexError(f"Old index {op.old_index} out of range.")
            if op.new_index < 0 or op.new_index >= total_bullet_points:
                raise IndexError(f"New index {op.new_index} out of range.")

        # ✅ Handle moves safely — process in a way that avoids shifting index issues
        # Sort by old_index to ensure correct order of pops
        for op in sorted(operations, key=lambda x: x.old_index):
            item = projects.pop(op.old_index)
            projects.insert(op.new_index, item)

        # ✅ Save changes
        save_resume(user_id, resume_id, new_resume)
        await send_patch_to_frontend(user_id, new_resume)

        print(f"✅ Reordered projects for user {user_id}")
        return {"status":"success"}

    except Exception as e:
        print(f"❌ Error reordering projects: {e}")
        return {"status":"error", "message": str(e)}


# ---- Tool function ----
@tool(
    name_or_callable="reorder_projects_description_bullets_tool",
    description="Reorder the description bullets in a particular project entry of a particular work_experience entry of the user's resume.",
    infer_schema=True,
    return_direct=False,
    response_format="content",
    parse_docstring=False
)
async def reorder_project_description_bullets_tool(
    operations: list[MoveOperation],
    workex_entry_at: int,
    project_at: int,
    config: RunnableConfig,
) -> None:
    """Reorder the description bullets in a particular project entry of a particular work_experience entry of the user's resume."""

    try:
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")

        if not user_id or not resume_id:
            raise ValueError("Missing user_id or resume_id in context.")

        if not operations or len(operations) == 0:
            raise ValueError("Missing 'operations' for reorder operation.")

        new_resume = get_resume(user_id, resume_id)

        if "work_experiences" not in new_resume:
            raise ValueError("No work_experiences entries found in the resume.")

        total_entry = len(new_resume['work_experiences'])
        
        if workex_entry_at < 0 or workex_entry_at >= total_entry:
            raise IndexError(f"Entry index {workex_entry_at} out of range.")

        projects = new_resume['work_experiences'][workex_entry_at].get('projects', [])
        total_bullet_points = len(projects)

        if total_bullet_points == 0:
            raise ValueError("No projects found in the specified entry.")
        
        
                # ✅ Validate all moves before doing anything
        for op in operations:
            if not isinstance(op, MoveOperation):
                raise ValueError("Invalid operation type. Expected 'MoveOperation'.")
            if op.old_index < 0 or op.old_index >= total_bullet_points:
                raise IndexError(f"Old index {op.old_index} out of range.")
            if op.new_index < 0 or op.new_index >= total_bullet_points:
                raise IndexError(f"New index {op.new_index} out of range.")
            

        if project_at < 0 or project_at >= total_bullet_points:
            raise IndexError(f"Project index {project_at} out of range.")

        project_description_bullets = projects[project_at].get('description_bullets', [])
        
        if len(project_description_bullets) == 0:
            raise ValueError("No description bullets found in the specified project.")



        # ✅ Handle moves safely — process in a way that avoids shifting index issues
        # Sort by old_index to ensure correct order of pops
        for op in sorted(operations, key=lambda x: x.old_index):
            item = project_description_bullets.pop(op.old_index)
            project_description_bullets.insert(op.new_index, item)

        # ✅ Save changes
        save_resume(user_id, resume_id, new_resume)
        await send_patch_to_frontend(user_id, new_resume)

        print(f"✅ Reordered projects for user {user_id}")
        return {"status":"success"}

    except Exception as e:
        print(f"❌ Error reordering projects: {e}")
        return {"status":"error", "message": str(e)}



tools = [workex_Tool,reorder_tool,reorder_projects_tool,                     
         reorder_project_description_bullets_tool, 
         get_compact_work_experience_entries,
         get_work_experience_entry_by_index,
         transfer_to_extra_curricular_agent, transfer_to_por_agent,
         transfer_to_scholastic_achievement_agent, transfer_to_internship_agent
         ,transfer_to_education_agent, transfer_to_main_agent
         ]

