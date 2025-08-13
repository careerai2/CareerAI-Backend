from ..handoff_tools import *
from pydantic import BaseModel, EmailStr, field_validator
from typing import Literal, Union
import json
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from ..utils.common_tools import get_resume, save_resume, send_patch_to_frontend




# Now skills is also allowed
ALLOWED_FIELDS = {"title", "summary", "name", "email", "phone_number", "skills"}

class TopLevelFieldUpdateInput(BaseModel):
    field: Literal["title", "summary", "name", "email", "phone_number", "skills"]
    value: Union[str, EmailStr, list[str]]

    @field_validator("value", mode="before")
    @classmethod
    def validate_value(cls, v):
        if isinstance(v, str):
            return v.strip()
        if isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        return v


@tool(
    name_or_callable="update_top_level_field",
    description="Update a top-level field in the resume (scalars like name, email or list fields like skills).",
    args_schema=TopLevelFieldUpdateInput,
    infer_schema=True,
    return_direct=False,
    response_format="content",
    parse_docstring=False,
)
async def update_top_level_field(
    field: Literal["title", "summary", "name", "email", "phone_number", "skills"],
    value: Union[str, EmailStr, list[str]],
    config: RunnableConfig,
) -> None:
    """
    Updates a top-level field in the resume.
    If the field is list type (like skills), the given list is appended (no duplicates).
    """
    try:
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")

        if not user_id or not resume_id:
            raise ValueError("Missing user_id or resume_id in context.")

        # Fetch resume
        resume = get_resume(user_id, resume_id)

        # Ensure field is allowed
        if field not in ALLOWED_FIELDS:
            raise ValueError(f"Field '{field}' is not allowed to be updated via this tool.")

        # Handle list fields differently
        if field == "skills":
            if field not in resume or not isinstance(resume[field], list):
                resume[field] = []
            existing_values = set(resume[field])
            for val in value:
                if val not in existing_values:
                    resume[field].append(val)
                    existing_values.add(val)
        else:
            resume[field] = value

        # Save and send patch
        save_resume(user_id, resume_id, resume)
        await send_patch_to_frontend(user_id, resume)

        print(f"✅ Field '{field}' updated for {user_id}")

        return resume

    except Exception as e:
        print(f"❌ Error updating field '{field}' in resume: {e}")



tools = [update_top_level_field, transfer_to_extra_curricular_agent, transfer_to_por_agent,
         transfer_to_workex_agent, transfer_to_internship_agent
         ,transfer_to_education_agent,transfer_to_scholastic_achievement_agent]