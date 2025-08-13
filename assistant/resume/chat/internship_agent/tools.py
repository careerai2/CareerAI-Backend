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
from ..utils.update_summar_skills import update_summary_and_skills
from ..handoff_tools import *

class InternshipToolInput(BaseModel):
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
    index: int,
    config: RunnableConfig,
    type: Literal["add", "update", "delete"] = "add",
    updates: Optional[Internship] = None,
) -> None:
    """Add, update, or delete an internship entry in the user's resume. 
    Index is required for update/delete operations.
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
        
        
        print("Total updates:", new_resume["total_updates"])
        
        
        if new_resume.get("total_updates") > 5:
            updated_service = await update_summary_and_skills(new_resume, new_resume.get("tailoring_keys", []))

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

        print(f"✅ Internship section updated for {user_id}")

        return new_resume

    except Exception as e:
        print(f"❌ Error updating internship for user {user_id}: {e}")





class MoveOperation(BaseModel):
    old_index: int
    new_index: int

# ---- Pydantic input schema ----
class ReorderToolInput(BaseModel):
    operations: list[MoveOperation]


# ---- Tool function ----
@tool(
    name_or_callable="reorder_tool",
    description="Reorder the internship entries in the user's resume.",
    args_schema=ReorderToolInput,
    infer_schema=True,
    return_direct=False,
    response_format="content",
    parse_docstring=False
)
async def reorder_Tool(
    operations: ReorderToolInput,
    config: RunnableConfig,
) -> None:
    """Reorder the internship entries in the user's resume.
    """

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
        if "internships" not in new_resume:
            raise ValueError("No internship entries found in the resume.")

        total_entry = len(new_resume['internships'])

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
            entry = new_resume['internships'].pop(old_index)
            new_resume['internships'].insert(new_index, entry)

        # ---- Save & Notify ----
        save_resume(user_id, resume_id, new_resume)
        await send_patch_to_frontend(user_id, new_resume)

        print(f"✅ Internship section reordered for {user_id}")

        return new_resume

    except Exception as e:
        print(f"❌ Error reordering Internships for user: {e}")




# ---- Tool function ----
@tool(
    name_or_callable="reorder_internship_work_description_bullets_tool",
    description="Reorder the internship_work_description_bullets in a particular internships entry of the user's resume.",
    infer_schema=True,
    return_direct=False,
    response_format="content",
    parse_docstring=False
)
async def reorder_bullet_points_tool(
    operations: list[MoveOperation],
    entry_at: int,
    config: RunnableConfig,
) -> None:
    """Reorder the internship_work_description_bullets in a particular Internship entry of the user's resume."""

    try:
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")

        if not user_id or not resume_id:
            raise ValueError("Missing user_id or resume_id in context.")

        if not operations or len(operations) == 0:
            raise ValueError("Missing 'operations' for reorder operation.")

        new_resume = get_resume(user_id, resume_id)

        if "internships" not in new_resume:
            raise ValueError("No internships entries found in the resume.")

        total_entry = len(new_resume['internships'])
        if entry_at < 0 or entry_at >= total_entry:
            raise IndexError(f"Entry index {entry_at} out of range.")

        bullets = new_resume['internships'][entry_at].get('internship_work_description_bullets', [])
        total_bullet_points = len(bullets)

        if total_bullet_points == 0:
            raise ValueError("No bullet points found in the specified entry.")

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
            item = bullets.pop(op.old_index)
            bullets.insert(op.new_index, item)

        # ✅ Save changes
        save_resume(user_id, resume_id, new_resume)
        await send_patch_to_frontend(user_id, new_resume)

        print(f"✅ Reordered responsibilities for user {user_id}")
        return new_resume

    except Exception as e:
        print(f"❌ Error reordering responsibilities: {e}")




tools = [internship_Tool, reorder_Tool, reorder_bullet_points_tool, transfer_to_main_agent, transfer_to_por_agent,
         transfer_to_workex_agent, transfer_to_education_agent,
         transfer_to_scholastic_achievement_agent, transfer_to_extra_curricular_agent]
    