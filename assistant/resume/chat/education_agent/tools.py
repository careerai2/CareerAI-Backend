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




# ---- Pydantic input schema ----
class EducationToolInput(BaseModel):
    type: Literal["add", "update", "delete"] = "add"  # Default to add
    updates: Optional[Education] = None              # Optional for delete
    index: int               # Optional index

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
    config: RunnableConfig,
    type: Literal["add", "update", "delete"] = "add",
    updates: Optional[Education] = None,
) -> None:
    """Add, update, or delete an education entry in the user's resume. 
    Index is required for update/delete operations.
    """

    try:
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")

        print(f"Config: {config}")

        if not user_id or not resume_id:
            raise ValueError("Missing user_id or resume_id in context.")

        # ✅ Validate operation
        if type != "delete" and not updates:
            raise ValueError("Missing 'updates' for add/update operation.")
        if type in ["update", "delete"] and index is None:
            raise ValueError("Index is required for add/update/delete operation.")

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




tools_education = [get_resume, education_Tool]



