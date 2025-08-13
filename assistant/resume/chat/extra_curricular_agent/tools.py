from langchain.tools import tool
from pydantic import BaseModel, field_validator
import json
from typing import Literal
from models.resume_model import ExtraCurricular
from typing import Optional, Literal
from pydantic import BaseModel, field_validator
import json
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from ..utils.common_tools import get_resume, save_resume, send_patch_to_frontend
from ..utils.update_summar_skills import update_summary_and_skills
from ..handoff_tools import *


class ExtracurricularToolInput(BaseModel):
    type: Literal["add", "update", "delete"] = "add"  # Default operation
    updates: Optional[ExtraCurricular] = None
    index: int    # Required for update/delete

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
    name_or_callable="extra_curricular_tool",
    description="Add, update, or delete an extra curricular entry in the user's resume. "
                "Requires index for update/delete operations.",
    args_schema=ExtracurricularToolInput,
    infer_schema=True,
    return_direct=False,
    response_format="content",
    parse_docstring=False
)
async def extra_curricular_Tool(
    index: int,
    config: RunnableConfig,
    type: Literal["add", "update", "delete"] = "add",
    updates: Optional[ExtraCurricular] = None,
) -> None:
    """Add, update, or delete an extra curricular entry in the user's resume.
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
            if index < len(new_resume['extra_curriculars']):
                del new_resume['extra_curriculars'][index]
            else:
                raise IndexError("Index out of range for internship entries.")

        elif type == "add":
            base_entry = ExtraCurricular().model_dump()  # All fields None
            base_entry.update(updates_data or {})
            new_resume['extra_curriculars'].append(base_entry)

        elif type == "update":
            if index < len(new_resume['extra_curriculars']):
                for k, v in updates_data.items():
                    new_resume['extra_curriculars'][index][k] = v
            else:
                raise IndexError("Index out of range for extra curricular entries.")
            
        if new_resume.get("total_updates", 0) > 5:
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

        print(f"✅ ExtraCurricular section updated for {user_id}")
        
        return new_resume

    except Exception as e:
        print(f"❌ Error updating extra curricular for user {user_id}: {e}")





class MoveOperation(BaseModel):
    old_index: int
    new_index: int


# ---- Tool function ----
@tool(
    name_or_callable="reorder_tool",
    description="Reorder the education entries in the user's resume.",
    infer_schema=True,
    return_direct=False,
    response_format="content",
    parse_docstring=False
)
async def reorder_Tool(
    operations: list[MoveOperation],
    config: RunnableConfig,
) -> None:
    """Reorder the education entries in the user's resume.
    """

    try:
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")
        
        print(operations)

        if not user_id or not resume_id:
            raise ValueError("Missing user_id or resume_id in context.")

        # ✅ Validate operation
        if operations is None or len(operations) is 0:
            raise ValueError("Missing 'operations' for reorder operation.")
        
        
        new_resume = get_resume(user_id, resume_id)
                
        # Ensure key exists
        if "extra_curriculars" not in new_resume:
            raise ValueError("No extra curricular entries found in the resume.")

        for op in operations:
            old_index = op.old_index
            new_index = op.new_index
            
            if not isinstance(op, MoveOperation):
                raise ValueError("Invalid operation type. Expected 'MoveOperation'.")
            
            if old_index < 0 or old_index >= len(new_resume['education_entries']):
                raise IndexError(f"Old index {old_index} out of range for education entries.")
            if new_index < 0 or new_index >= len(new_resume['education_entries']):
                raise IndexError(f"New index {new_index} out of range for education entries.")


        # ---- Handle operations ----
        for op in sorted(operations, key=lambda x: x.old_index):
            old_index = op.old_index
            new_index = op.new_index

            # Move the entry
            entry = new_resume['extra_curriculars'].pop(old_index)
            new_resume['extra_curriculars'].insert(new_index, entry)

        # ---- Save & Notify ----
        save_resume(user_id, resume_id, new_resume)
        await send_patch_to_frontend(user_id, new_resume)

        print(f"✅ extra_curriculars section reordered for {user_id}")

        return new_resume

    except Exception as e:
        print(f"❌ Error reordering extra_curriculars for user: {e}")





tools = [extra_curricular_Tool, transfer_to_main_agent, transfer_to_por_agent,
         transfer_to_workex_agent, transfer_to_internship_agent
         ,transfer_to_education_agent,transfer_to_scholastic_achievement_agent]

