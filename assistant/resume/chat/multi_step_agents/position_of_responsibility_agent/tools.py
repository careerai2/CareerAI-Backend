from langchain.tools import tool
import json
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from ...handoff_tools import *
from ...llm_model import SwarmResumeState

import jsonpatch
from config.log_config import get_logger
from config.env_config import show_por_logs


logger = get_logger("POR_Agent_Tool")

@tool
async def send_patches(
    patches: list[dict],   # <-- instead of entry
    state: Annotated[SwarmResumeState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    config: RunnableConfig
):
    """
    - Apply list of JSON Patches (RFC 6902) operations to the POR section of the resume.
    - Ensures all operations (add, replace, remove, move, copy) are valid and aligned with the correct internship index.
    - Updates backend storage and syncs changes to the frontend automatically.
    
    ```json
    
    Example patches:
    [
        {"op": "replace", "path": "/0/role", "value": "Full Stack Developer"},                                   # update role at index 0
        {"op": "replace", "path": "/0/organization", "value": "CareerAI"},                                       # update organization name
        {"op": "replace", "path": "/0/duration", "value": "June 2022 - August 2022"},                            # modify duration
        {"op": "replace", "path": "/0/responsibilities/1", "value": "Integrated APIs and optimized backend performance"},  # update specific responsibility in array

        {"op": "add", "path": "/-", "value": {                                                                   # add new experience entry
            "role": "Software Engineer Intern",
            "duration": "July 2023 - Present",
            "responsibilities": [
                "Developed microservices for user management",
            ]
        }}
    ]
    ```

    """
    
    try:

            
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")

        if not user_id or not resume_id:
            raise ValueError("Missing user_id or resume_id in context.")

        if not patches:
            raise ValueError("Missing 'patches' for state update operation.")

        current_entries = state["resume_schema"].model_dump().get("positions_of_responsibility", [])

        
        if not isinstance(current_entries, list):
            current_entries = []

        try:
            jsonpatch.apply_patch(current_entries, patches,in_place=False)
        except jsonpatch.JsonPatchException as e:
            raise ValueError(f"Invalid JSON Patch operations: {e}")
    
        
        tool_message = ToolMessage(
            content="Successfully transferred to the pipeline to add the patches in an enhanced manner.",
            name="send_patches",
            tool_call_id=tool_call_id,
        )
        
        if show_por_logs:
            logger.info("✅ Successfully applied POR entry patches: %s", patches)

        
  
        return Command(
            goto="query_generator_model",
            update={
                "messages": [tool_message],
                "por": {
                    "retrived_info": "",
                    "patches": patches,
                },
            },
        )

    except Exception as e:
        logger.error(f"❌ Error applying por entry patches: {e}")

        fallback_error_msg = f"Error in send_patches tool: {e}"
        fallback_msg = ToolMessage(
            content=(
                f"""The send_patches tool failed due to: {e}. 
                Please either retry generating valid patches or inform the user 
                that the update could not be applied."""
            ),
            name="send_patches",
            tool_call_id=tool_call_id,
        )

        # ❌ Do not raise ToolException if you want router to handle it
        return Command(
            goto="por_model",
            update={
                "messages": [fallback_msg],
                "por": {
                    "error_msg": fallback_error_msg,
                    "patches": patches,
                }
                
            },
        )





core_tools = [
    
    send_patches,

      ]


transfer_tools = [
       transfer_to_extra_curricular_agent, transfer_to_main_agent,transfer_to_acads_agent,
         transfer_to_workex_agent, transfer_to_internship_agent
         ,transfer_to_education_agent,transfer_to_scholastic_achievement_agent,transfer_to_certification_assistant_agent
    ]

tools = core_tools + transfer_tools
