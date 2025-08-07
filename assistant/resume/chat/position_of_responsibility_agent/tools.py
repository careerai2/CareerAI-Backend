from langchain.tools import tool
from pydantic import BaseModel, field_validator
import json
from typing import Literal
from models.resume_model import PositionOfResponsibility
from typing import Optional, Literal
from pydantic import BaseModel, field_validator
import json
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from ..utils.common_tools import get_resume, save_resume, send_patch_to_frontend
from ..handoff_tools import *


class PositionOfResponsibilityToolInput(BaseModel):
    type: Literal["add", "update", "delete"] = "add"  # Default operation
    updates: Optional[PositionOfResponsibility] = None
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
    name_or_callable="position_of_responsibility_tool",
    description="Add, update, or delete a position of responsibility entry in the user's resume. "
                "Requires index for update/delete operations.",
    args_schema=PositionOfResponsibilityToolInput,
    infer_schema=True,
    return_direct=False,
    response_format="content",
    parse_docstring=False
)
async def position_of_responsibility_tool(
    index: int,
    config: RunnableConfig,
    type: Literal["add", "update", "delete"] = "add",
    updates: Optional[PositionOfResponsibility] = None,
) -> None:
    """Add, update, or delete a position of responsibility entry in the user's resume.
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
            if index < len(new_resume['positions_of_responsibility']):
                del new_resume['positions_of_responsibility'][index]
            else:
                raise IndexError("Index out of range for position of responsibility entries.")

        elif type == "add":
            base_entry = PositionOfResponsibility().model_dump()  # All fields None
            base_entry.update(updates_data or {})
            new_resume['positions_of_responsibility'].append(base_entry)

        elif type == "update":
            if index < len(new_resume['positions_of_responsibility']):
                for k, v in updates_data.items():
                    new_resume['positions_of_responsibility'][index][k] = v
            else:
                raise IndexError("Index out of range for position of responsibility entries.")

        # ---- Save & Notify ----
        save_resume(user_id, resume_id, new_resume)

        await send_patch_to_frontend(user_id, new_resume)

        print(f"✅ Position Of Responsibility section updated for {user_id}")

    except Exception as e:
        print(f"❌ Error updating position of responsibility for user {user_id}: {e}")





tools = [position_of_responsibility_tool, transfer_to_extra_curricular_agent, transfer_to_main_agent,
         transfer_to_workex_agent, transfer_to_internship_agent
         ,transfer_to_education_agent,transfer_to_scholastic_achievement_agent]

