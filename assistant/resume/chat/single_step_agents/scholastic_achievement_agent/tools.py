from langchain.tools import tool
import json
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
# from ...utils.common_tools import apply_patches_global
from ...utils.apply_patches import apply_patches_global
from ...handoff_tools import *
from ...llm_model import SwarmResumeState


from config.env_config import show_scholastic_achievement_logs
from config.log_config import get_logger

import jsonpatch

logger = get_logger("ScholasticAchievement_Tool")




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
        {"op": "replace", "path": "/0/title", "value": "Top Performer Award"},  # update
        {"op": "add", "path": "/-", "value": {"title": "Top 1%", "year": "2023"}}   # add at end
    ]
    """

    try:        
    
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")

        if not user_id or not resume_id:
            raise ValueError("Missing user_id or resume_id in context.")

        if not patches:
            raise ValueError("Missing 'patches' for state update operation.")
        
        current_entries = state["resume_schema"].model_dump().get("achievements", [])
        
        try:
            jsonpatch.apply_patch(current_entries, patches,in_place=False)
        except jsonpatch.JsonPatchException as e:
            raise ValueError(f"Invalid JSON Patch operations: {e}")
        
        # ✅ Apply patches to backend storage
        # result = await apply_patches(f"{user_id}:{resume_id}", patches)
        result = await apply_patches_global(f"{user_id}:{resume_id}", patches,"achievements")
        
        
        if result and result.get("status") == "success":
            if show_scholastic_achievement_logs:
                logger.info("✅ Successfully applied Achivement entry patches: %s", patches)
            return "Patches applied successfully.",
        
        elif result and result.get("status") == "error":
            raise ValueError(result.get("message", "Unknown error during patch application."))
        else:
            raise ValueError("Unknown error during patch application.")
    
        

    except Exception as e:
        logger.error(f"❌ Error applying Achivement entry patches: {e}")

        return f"""The send_patches tool failed due to: \n{e}. \n
                Please either retry generating valid patches or inform the user 
                that the update could not be applied."""







core_tools = [
    send_patches,
]

transfer_tools = [transfer_to_extra_curricular_agent, transfer_to_por_agent,
         transfer_to_workex_agent, transfer_to_internship_agent,transfer_to_acads_agent
         ,transfer_to_education_agent, transfer_to_main_agent,transfer_to_certification_assistant_agent]

tools = core_tools + transfer_tools 