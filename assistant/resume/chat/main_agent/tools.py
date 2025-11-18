from ..handoff_tools import *
from pydantic import BaseModel, EmailStr, field_validator
from typing import Literal, Union
import json
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from ..utils.common_tools import get_resume, save_resume, send_patch_to_frontend
from redis_config import redis_client as r



# Now skills is also allowed
ALLOWED_FIELDS = {"title", "summary", "name", "email", "phone_number", "skills","interests"}

class TopLevelFieldUpdateInput(BaseModel):
    field: Literal["title", "summary", "name", "email", "phone_number", "skills","interests"]
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
    field: Literal["title", "summary", "name", "email", "phone_number", "skills","interests"],
    value: Union[str, EmailStr, list[str]],
    config: RunnableConfig,
) -> None:
    """
    Updates a top-level field in the resume.
    If the field is list type (like skills,interests), the given list is appended (no duplicates).
    """
    print("Field",field)
    print("\nValue",value)
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
        if field == "skills" or field == "interests":
            if field not in resume or not isinstance(resume[field], list):
                resume[field] = []
            existing_values = set(resume[field])
            for val in value:
                if val not in existing_values:
                    resume[field].append(val)
                    existing_values.add(val)
        else:
            if isinstance(value, list):
                if len(value) == 1:
                    value = value[0]  # unwrap single-element list
            else:
                raise ValueError(f"Field '{field}' expects a string, but got a list: {value}")
            resume[field] = value

        # Save and send patch
        save_resume(user_id, resume_id, resume)
        await send_patch_to_frontend(user_id, resume)

        print(f"✅ Field '{field}' updated for {user_id}")

        return {"status": True}

    except Exception as e:
        print(f"❌ Error updating field '{field}' in resume: {e}")
        return {"status": False,"error": str(e)}


@tool
async def get_full_resume(config: RunnableConfig):
    """
    Get entire resume of the user.
    Returns: user's resume .
    """
    try:
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")
        
        entries_raw = r.get(f"resume:{user_id}:{resume_id}")
        resume_data = json.loads(entries_raw) if entries_raw else {}

        return resume_data

    except Exception as e:
        print(f"Error in get_full_resume: {e}")
        return {"error": "Failed to retrieve full resume","message":str(e)}


tools = [update_top_level_field, get_full_resume, transfer_to_extra_curricular_agent, transfer_to_por_agent,
         transfer_to_workex_agent, transfer_to_internship_agent,transfer_to_acads_agent
         ,transfer_to_education_agent,transfer_to_scholastic_achievement_agent,transfer_to_certification_assistant_agent]