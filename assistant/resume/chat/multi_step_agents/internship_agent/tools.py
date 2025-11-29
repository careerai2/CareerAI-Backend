from langchain.tools import tool
from models.resume_model import *
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from ...handoff_tools import *
from config.redis_config import redis_client as r 
from langgraph.prebuilt import InjectedState
import jsonpatch
from assistant.resume.chat.llm_model import SwarmResumeState
from config.env_config import show_internship_logs
from config.log_config import get_logger



logger = get_logger("Internship_Agent_Tools")

@tool
async def send_patches(
    patches: list[dict],
    state: Annotated[SwarmResumeState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    config: RunnableConfig
):
    """
    - Apply list of JSON Patches (RFC 6902) operations to the internships section of the resume.
    - Ensures all operations (add, replace, remove, move, copy) are valid and aligned with the correct internship index.
    - Updates backend storage and syncs changes to the frontend automatically.

    Example patches:
    [
        {"op": "replace", "path": "/0/company_name", "value": "CareerAi"},                     # modify field
        {"op": "add", "path": "/-", "value": {"company_name": "OpenAI", "role": "ML Intern"}}, # add new internship
        {"op": "remove", "path": "/1"},                                                        # remove internship
        {
    "op": "add",                                                                               # adding first bullet point to an internship at index 0 
    "path": "/0/internship_work_description_bullets/-",
    "value": "Designed a database from scratch for the organization's admin portal using Redis, NoSQL, and SQL for optimized data management and speed."
  }
    ]
    """


    try:
        # print("PATCH:", patches)


        # Extract config context
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")

        if not user_id or not resume_id:
            raise ValueError("Missing user_id or resume_id in context.")

        if not patches:
            raise ValueError("Missing 'patches' for state update operation.")
        
        current_entry_length = 0
        
        if not state["resume_schema"]:
            raise ValueError("Resume schema state not initialized.")    

        
        current_internships = state["resume_schema"].model_dump().get("internships", [])

        
        # print(f"Current internships before patch: current_internships")
        if not isinstance(current_internships, list):
            current_internships = []

        # ✅ checking patch validation internships list
        try:
            jsonpatch.apply_patch(current_internships, patches,in_place=False)
            if show_internship_logs:
                logger.info(f"Applied patch list to internships: {patches}")
        except jsonpatch.JsonPatchException as e:
            raise ValueError(f"Invalid JSON Patch operations: {e}")

        tool_message = ToolMessage(
            content="Successfully transferred to the pipeline to add the patches in an enhanced manner.",
            tool_call_id=tool_call_id,
            name="send_patches",
            status="success"
        )

        # ✅ Success structure
        return Command(
            goto="query_generator_model",
            update={
                "messages": [tool_message],
                "internship": {
                    "error_msg": None,
                    "patches": patches,
                }
            },
        )
        
    except Exception as e:
        logger.error(f"❌ Error applying internship entry patches: {e}")

        # Create a detailed feedback ToolMessage
        fallback_msg = ToolMessage(
            content=f"The send_patches tool failed due to: {str(e)}",
            name="send_patches",              # or "system_feedback"
            tool_call_id=tool_call_id,
            status="error"
        )
        fallback_error_msg = f"Error in send_patches tool: {e}"

        # ✅ Return a Command that routes back to the calling agent node
        return Command(
            goto="internship_model",          # returns control to the same node that called this tool
            update={
                "messages": [fallback_msg],   # required for _validate_tool_command
                "internship": {
                    "error_msg": fallback_error_msg,
                    "patches": patches,
                }
            },
        )








core_tools = [

    send_patches,
   
        ]


transfer_tools = [transfer_to_main_agent, transfer_to_por_agent,
         transfer_to_workex_agent, transfer_to_education_agent,transfer_to_acads_agent,
         transfer_to_scholastic_achievement_agent, transfer_to_extra_curricular_agent,transfer_to_certification_assistant_agent]
    
tools = core_tools + transfer_tools