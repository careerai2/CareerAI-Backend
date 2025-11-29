# from langchain.tools import tool
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from ...llm_model import SwarmResumeState
from ...handoff_tools import *
import jsonpatch
from config.log_config import get_logger



logger = get_logger("Acads_Agent_Tool")



@tool
async def send_patches(
    patches: list[dict],   # <-- instead of entry
    state: Annotated[SwarmResumeState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    config: RunnableConfig
):
    """
    - Apply list of JSON Patches (RFC 6902) operations to the academic projects section of the resume.
    - Ensures all operations (add, replace, remove, move, copy) are valid and aligned with the correct project index.
    - Updates backend storage and syncs changes to the frontend automatically.

    ```
    Example patches:
    [
        {"op": "replace", "path": "/0/project_name", "value": "CareerAI"},                         # modify field
        {"op": "replace", "path": "/1/duration", "value": "June 2022 - August 2022"},              # update duration
        {"op": "add", "path": "/-", "value": {"project_name": "OpenAI", "duration": "July 2023 - Present"}}, # add new project
        {"op": "remove", "path": "/2"},                                                            # remove project
        {"op": "move", "from": "/1", "path": "/0"}                                                 # reorder projects
    ]
    ```

    """

    try:
        logger.info(f"Send Patch PATCH:", patches)
        
        
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")

        if not user_id or not resume_id:
            raise ValueError("Missing user_id or resume_id in context.")

        if not patches:
            raise ValueError("Missing 'patches' for state update operation.")
        
      
        
        
        
        current_entries = state["resume_schema"].model_dump().get("academic_projects", [])   

        # print(f"Current acads entries count: {current_entry_length}")
    # ✅ checking patch validation internships list
        try:
            jsonpatch.apply_patch(current_entries, patches,in_place=False)
            logger.info(f"Applied patch list to Acad. Projects successfully.")
        except jsonpatch.JsonPatchException as e:
            raise ValueError(f"Invalid JSON Patch operations: {e}")
    
        tool_message = ToolMessage(
            content="Successfully transferred to the pipeline to the patches in a enhanced manner.",
            name="send_patches",
            tool_call_id=tool_call_id,
        )

        
  
        return Command(
            goto="query_generator_model",
            update={
                "messages": [tool_message],
                "acads": {
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
            name="system_feedback",
            tool_call_id=tool_call_id,
            status="error"
        )

        # ❌ Do not raise ToolException if you want router to handle it
        return Command(
            goto="acads_model",
            update={
                "messages": [fallback_msg],
                "acads": {
                    # "error_msg": fallback_error_msg,
                    "patches": patches,
                }
                
            },
        )



tools = [
    send_patches,
]

transfer_tools = [
    transfer_to_extra_curricular_agent, transfer_to_main_agent,
         transfer_to_workex_agent, transfer_to_internship_agent,transfer_to_acads_agent
         ,transfer_to_education_agent,transfer_to_scholastic_achievement_agent,transfer_to_certification_assistant_agent]

