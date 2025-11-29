from langchain.tools import tool
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

# from ...utils.common_tools import apply_patches_global
from ...utils.apply_patches import apply_patches_global
from ...handoff_tools import *
from ...llm_model import SwarmResumeState

from config.env_config import show_extra_curricular_logs
from config.log_config import get_logger

import jsonpatch

logger = get_logger("ExtraCurricular_Tool")


@tool
async def send_patches(
    patches: list[dict],  
    state: Annotated[SwarmResumeState, InjectedState],
    config: RunnableConfig
):
    """
    - Apply list of JSON Patches (RFC 6902) operations.
    - Ensures all operations (add, replace, remove, move, copy) are valid and aligned with the correct index.
    - Updates backend storage and syncs changes to the frontend automatically.



    Example:
    [
       
        {"op": "replace", "path": "/1/description", "value": "Coordinated 50+ volunteers for campus events"}, # update
        {"op": "add", "path": "/-", "value": { "activity": "Robotics Club",                       # add at end
            "position": "Team Lead",
            "description": "Designed and built autonomous robots for regional competitions",
            "year": "2023"
        }}
    ]
    """

    try:
        
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")

        if not user_id or not resume_id:
            raise ValueError("Missing user_id or resume_id in context.")

        if not patches:
            raise ValueError("Missing 'patches' for state update operation.")
        
        current_entries = state["resume_schema"].model_dump().get("extra_curriculars", [])
        
        try:
            jsonpatch.apply_patch(current_entries, patches,in_place=False)
        except jsonpatch.JsonPatchException as e:
            raise ValueError(f"Invalid JSON Patch operations: {e}")
        
        result = await apply_patches_global(f"{user_id}:{resume_id}", patches,"extra_curriculars")
        
        if result and result.get("status") == "success":
            if show_extra_curricular_logs:
                logger.info("✅ Successfully applied certification entry patches: %s", patches)
            return "Patches applied successfully.",
        
        elif result and result.get("status") == "error":
            raise ValueError(result.get("message", "Unknown error during patch application."))
        else:
            raise ValueError("Unknown error during patch application.")
    
        

    except Exception as e:
        logger.error(f"❌ Error applying certification entry patches: {e}")
        return  f"""The send_patches tool failed due to:\n {e}. \n
                Please either retry generating valid patches or inform the user 
                that the update could not be applied."""





core_tools = [send_patches]

transfer_tools = [transfer_to_main_agent, transfer_to_por_agent,
         transfer_to_workex_agent, transfer_to_internship_agent,transfer_to_acads_agent
         ,transfer_to_education_agent,transfer_to_scholastic_achievement_agent,transfer_to_certification_assistant_agent]

tools = transfer_tools + core_tools