from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

# from ...utils.common_tools import apply_patches_global
from ...utils.apply_patches import apply_patches_global
from ...handoff_tools import *
from ...llm_model import SwarmResumeState

import jsonpatch

from config.env_config import show_education_logs
from config.log_config import get_logger


from config.env_config import show_education_logs
from config.log_config import get_logger


logger = get_logger("Education_Agent_Tools")

@tool
async def send_patches(
    patches: list[dict],   
    state: Annotated[SwarmResumeState, InjectedState],
    config: RunnableConfig
):
    """
        - Apply list of JSON Patches (RFC 6902) operations to the education section of the resume.
        - Ensures all operations (add, replace, remove, move, copy) are valid and aligned with the correct education index.
        - Updates backend storage and syncs changes to the frontend automatically.

        Example patches:
        [
            {"op": "replace", "path": "/0/cgpa", "value": "8.6"},                                   # modify field
            {"op": "add", "path": "/-", "value": {"institution": "IIT Delhi", "degree": "B.Tech"}},  # add new entry
            {"op": "remove", "path": "/1"},                                                         # remove education
            {"op": "move", "from": "/2", "path": "/0"},                                             # reorder entries
            {"op": "copy", "from": "/0/degree", "path": "/1/prev_degree"}                           # copy a field
        ]
    """

    logger.debug(f"🔧 send_patches called with patches: {patches}")
    try:
        
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")

        if not user_id or not resume_id:
            raise ValueError("Missing user_id or resume_id in context.")

        if not patches:
            raise ValueError("Missing 'patches' for state update operation.")
        
        
  
        current_entries = state["resume_schema"].model_dump().get("education_entries", [])   

        try:
            jsonpatch.apply_patch(current_entries, patches,in_place=False)
        except jsonpatch.JsonPatchException as e:
            raise ValueError(f"Invalid JSON Patch operations,: {e}")
        
        result = await apply_patches_global(f"{user_id}:{resume_id}", patches,"education_entries")
        
        if result and result.get("status") == "success":
            if show_education_logs:
                logger.info(f"✅ Education Patches applied successfully: {patches}")
            return "Education Patches applied successfully.",
                
        elif result and result.get("status") == "error":
            raise ValueError(result.get("message", "Unknown error during patch application."))
        else:
            raise ValueError("Unknown error during patch application.")
    
        

    except Exception as e:
        logger.error(f"❌ Error applying Education entry patches:\n{e}")

        return f"""The send_patches tool failed due to:\n**{e}**.\n Please either retry generating valid patches or inform the user 
                that the update could not be applied."""








core_tools = [
    send_patches,
]


transfer_tools  = [
         transfer_to_main_agent, transfer_to_por_agent,transfer_to_acads_agent,
         transfer_to_workex_agent, transfer_to_internship_agent
         ,transfer_to_scholastic_achievement_agent,transfer_to_extra_curricular_agent,transfer_to_certification_assistant_agent]




tools = core_tools + transfer_tools
