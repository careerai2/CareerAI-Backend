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
from ..utils.common_tools import get_resume, save_resume, send_patch_to_frontend,check_patch_correctness,apply_patches_global
from ..utils.update_summar_skills import update_summary_and_skills
from ..handoff_tools import *
from redis_config import redis_client as r
from ..llm_model import SwarmResumeState
from .functions import apply_patches




@tool
async def send_patches(
    patches: list[dict],   # <-- instead of entry
    state: Annotated[SwarmResumeState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    config: RunnableConfig
):
    """
    Apply JSON Patch (RFC 6902) operations to the certication section.

    - Works with the full project list.
    - Generates valid list-level patches for each entry.
    - Keeps backend and frontend in sync automatically.

    Example:
    [
        {"op": "replace", "path": "/0/certification", "value": "AWS Certified Solutions Architect"},
        {"op": "replace", "path": "/1/issuing_organization", "value": "Amazon Web Services"},
        {"op": "add", "path": "/-", "value": {"certification": "Data Analyst", "issuing_organization": "Coursera", "time_of_certification": "2023-05"}}
    ]
    """

    try:
        print("PATCH:", patches)
        
        
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")

        if not user_id or not resume_id:
            raise ValueError("Missing user_id or resume_id in context.")

        if not patches:
            raise ValueError("Missing 'patches' for state update operation.")
        
        current_entry_length = 0
        
        if state["resume_schema"]:
            current_entries = getattr(state["resume_schema"], "certifications", []) or []
            current_entry_length = len(current_entries)

        # print(f"Current acads entries count: {current_entry_length}")

        check_patch_result = check_patch_correctness(patches, current_entry_length)
        
        if check_patch_result != True:
            raise ValueError("Something Went Wrong, Try Again")
        
        # ✅ Apply patches to backend storage
        # result = await apply_patches(f"{user_id}:{resume_id}", patches)
        result = await apply_patches_global(f"{user_id}:{resume_id}", patches,"certifications")
        
        print("Apply patches result:", result)
        
        if result and result.get("status") == "success":
            return {"messages": [
                ToolMessage(
                content="✅ Certification section updated successfully.",
                name="system_feedback",
                tool_call_id=tool_call_id,
                metadata={"end_workflow": True}
            )       
            ]}
        
        elif result and result.get("status") == "error":
            raise ValueError(result.get("message", "Unknown error during patch application."))
        else:
            raise ValueError("Unknown error during patch application.")
    
        

    except Exception as e:
        print(f"❌ Error applying certification entry patches: {e}")

        
        fallback_msg = ToolMessage(
            content=(
                f"""The send_patches tool failed due to: {e}. 
                Please either retry generating valid patches or inform the user 
                that the update could not be applied."""
            ),
            name="system_feedback",
            tool_call_id=tool_call_id,
        )

        # ❌ Do not raise ToolException if you want router to handle it
        return {"messages": [fallback_msg]}




tools = [send_patches,
        #  get_compact_education_entries,
         transfer_to_main_agent, transfer_to_por_agent,transfer_to_acads_agent,
         transfer_to_workex_agent, transfer_to_internship_agent
         ,transfer_to_scholastic_achievement_agent,transfer_to_extra_curricular_agent]





