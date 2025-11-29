from langchain.tools import tool
from models.resume_model import *
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from ...handoff_tools import *
import jsonpatch
from ...llm_model import SwarmResumeState
from config.env_config import show_workex_logs
from config.log_config import get_logger


logger = get_logger("workex_tools")




@tool
async def send_patches(
    patches: list[dict],
    state: Annotated[SwarmResumeState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    config: RunnableConfig
):
    """
    - Apply list of JSON Patches (RFC 6902) operations to the POR section of the resume.
    - Ensures all operations (add, replace, remove, move, copy) are valid and aligned with the correct internship index.
    - Updates backend storage and syncs changes to the frontend automatically.

    ``` json
    
    Example patches:
    [
        {"op": "replace", "path": "/0/company_name", "value": "Google LLC"},                                # modify field
        {"op": "add", "path": "/-", "value": {                                                              # add new work experience
            "company_name": "OpenAI",
            "location": "San Francisco, USA",
            "projects": [
                {
                    "project_name": "Real-Time Chat Infrastructure",
                    "description_bullets": [
                        "Built scalable WebSocket servers using Node.js and Redis.",
                        "Reduced message latency by 25% under peak loads."
                    ]
                }
            ]
        }},
        {"op": "remove", "path": "/1"},                                                                     # remove a work experience
        {"op": "move", "from": "/2", "path": "/0"},                                                         # reorder entries
        {"op": "copy", "from": "/0/projects/0/project_name", "path": "/1/last_project_name"}                 # copy a field
    ]
    ```
    """

    try:

        # Extract config context
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")

        if not user_id or not resume_id:
            raise ValueError("Missing user_id or resume_id in context.")

        if not patches:
            raise ValueError("Missing 'patches' for state update operation.")

    
        current_entries = state["resume_schema"].model_dump().get("work_experiences", [])


        try:
            jsonpatch.apply_patch(current_entries, patches,in_place=False)
            logger.info(f"\nApplied patch list to work experiences: {patches}\n")
        except jsonpatch.JsonPatchException as e:
            raise ValueError(f"Invalid JSON Patch operations: {e}")
    
    
        
        tool_message = ToolMessage(
            content="Successfully transferred to the pipeline to add the patches in an enhanced manner.",
            name="send_patches",
            tool_call_id=tool_call_id,
        )

        # ✅ Success structure
        return Command(
            goto="query_generator_model",
            update={
                "messages": [tool_message],
                "workex": {
                    "patches": patches,
                }
            },
        )

    except Exception as e:
        logger.error(f"❌ Error applying Workex entry patches: {e}")


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
            goto="workex_model",
            update={
                "messages": [fallback_msg],
                "workex": {
                    "error_msg": fallback_error_msg,
                    "patches": patches,
                }
                
            },
        )




core_tools = [
        send_patches,
         ]

transfer_tools = [
    transfer_to_extra_curricular_agent, transfer_to_por_agent,transfer_to_acads_agent,
         transfer_to_scholastic_achievement_agent, transfer_to_internship_agent
         ,transfer_to_education_agent, transfer_to_main_agent,transfer_to_certification_assistant_agent
        ]

tools = core_tools + transfer_tools

