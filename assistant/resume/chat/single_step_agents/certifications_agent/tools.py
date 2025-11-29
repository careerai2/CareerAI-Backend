from langchain_core.tools import tool
from models.resume_model import *
from langchain_core.runnables import RunnableConfig



from ...handoff_tools import *
# from ...utils.common_tools import apply_patches_global
from ...utils.apply_patches import apply_patches_global
from ...llm_model import SwarmResumeState

import jsonpatch

from config.env_config import show_certification_logs
from config.log_config import get_logger


logger = get_logger("Certification_Agent_Tools")

@tool
async def send_patches(
    patches: list[dict],   # <-- instead of entry
    state: Annotated[SwarmResumeState, InjectedState],
    config: RunnableConfig
):
    """
    - Apply list of JSON Patches (RFC 6902) operations.
    - Ensures all operations (add, replace, remove, move, copy) are valid and aligned with the correct index.
    - Updates backend storage and syncs changes to the frontend automatically.


    Example Patches:
    [
        {"op": "replace", "path": "/0/certification", "value": "AWS Certified Solutions Architect"}, # update
        {"op": "replace", "path": "/1/issuing_organization", "value": "Amazon Web Services"},
        {"op": "add", "path": "/-", "value": {"certification": "Data Analyst", "issuing_organization": "Coursera", "time_of_certification": "2023-05"}} # add at end
    ]
    """

    try:
        
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")

        if not user_id or not resume_id:
            raise ValueError("Missing user_id or resume_id in context.")

        if not patches:
            raise ValueError("Missing 'patches' for state update operation.")
        
        current_entries = state["resume_schema"].model_dump().get("certifications", [])
        
        try:
            jsonpatch.apply_patch(current_entries, patches,in_place=False)
        except jsonpatch.JsonPatchException as e:
            raise ValueError(f"Invalid JSON Patch operations: {e}")

        
   
        result = await apply_patches_global(f"{user_id}:{resume_id}", patches,"certifications")
        
        
        if result and result.get("status") == "success":
            if show_certification_logs:
                logger.info(f"✅ Patches applied successfully to certifications: {patches}")
            return "Patches applied successfully.",
        
        elif result and result.get("status") == "error":
            raise ValueError(result.get("message", "Unknown error during patch application."))
        else:
            raise ValueError("Unknown error during patch application.")
    
        

    except Exception as e:
        logger.error(f"❌ Error applying certification entry patches: {e}")


        # ❌ Do not raise ToolException if you want router to handle it
        return   f"""The send_patches tool failed due to:\n {e}.\n 
                Please either retry generating valid patches or inform the user 
                that the update could not be applied."""




core_tools = [
    send_patches,
         ]


transfer_tools = [
    transfer_to_main_agent, transfer_to_por_agent,transfer_to_acads_agent,
         transfer_to_workex_agent, transfer_to_internship_agent
         ,transfer_to_scholastic_achievement_agent,transfer_to_extra_curricular_agent
    
]


tools = core_tools + transfer_tools



