from langchain.tools import tool
from pydantic import BaseModel, field_validator
import json
from typing import Literal
from models.resume_model import PositionOfResponsibility
from typing import Optional, Literal
from pydantic import BaseModel, field_validator
import json
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from ..utils.common_tools import get_resume, save_resume, send_patch_to_frontend,check_patch_correctness
from ..handoff_tools import *
from ..utils.update_summar_skills import update_summary_and_skills
from redis_config import redis_client as r
from ..llm_model import SwarmResumeState
from .functions import update_por_field

@tool
def get_compact_por_entries(config: RunnableConfig):
    """
    Get all POR entries in a concise format.
    Returns: list of dicts with only non-null fields (responsibilities count instead of full list).
    """
    try:
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")
        
        entries_raw = r.get(f"resume:{user_id}:{resume_id}")
        resume_data = json.loads(entries_raw) if entries_raw else {}
        entries = resume_data.get("positions_of_responsibility", [])

        # Filter invalid entries
        entries = [e for e in entries if e and isinstance(e, dict)]

        compact = []
        for i, e in enumerate(entries):
            entry_dict = {
                "index": i,
                **{k: v for k, v in {
                    "role": e.get("role"),
                    "role_description": e.get("role_description"),
                    "organization": e.get("organization"),
                    "organization_description": e.get("organization_description"),
                    "location": e.get("location"),
                    "duration": e.get("duration"),
                    "responsibilities_count": len(e.get("responsibilities", [])) if e.get("responsibilities") else None
                }.items() if v not in [None, "", [], {}]}
            }
            compact.append(entry_dict)

        print("Compact POR entries:", compact)
        return compact

    except Exception as e:
        print(f"Error in get_compact_por_entries: {e}")
        return {"status": "error", "message": str(e)}


@tool
def get_por_entry_by_index(config: RunnableConfig):
    """
    Get a single POR entry by index.
    Returns full entry including responsibilities.
    """
    try:
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")
        index = config["configurable"].get("index")
        
        entries_raw = r.get(f"resume:{user_id}:{resume_id}")
        resume_data = json.loads(entries_raw) if entries_raw else {}
        entries = resume_data.get("positions_of_responsibility", [])

        if index is not None and 0 <= index < len(entries):
            print(entries[index])
            return entries[index]
        else:
            return {"error": "Invalid index or entry not found"}

    except Exception as e:
        print(f"Error in get_por_entry_by_index: {e}")
        return {"error": str(e)}


class PositionOfResponsibilityToolInput(BaseModel):
    type: Literal["add", "update", "delete"] # Default operation
    updates: Optional[PositionOfResponsibility] = None
    index: int  # Required for update/delete

    @field_validator("updates", mode="before")
    @classmethod
    def parse_updates(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("updates must be a dict or JSON string.")
        return v


@tool(
    name_or_callable="position_of_responsibility_tool",
    description="Add, update, or delete a position of responsibility entry in the user's resume. "
                "Requires index for update/delete operations.",
    args_schema=PositionOfResponsibilityToolInput,
    infer_schema=True,
    return_direct=False,
    response_format="content",
    parse_docstring=False
)
async def position_of_responsibility_tool(
    index: int,
    config: RunnableConfig,
    type: Literal["add", "update", "delete"],
    updates: Optional[PositionOfResponsibility] = None,
) -> None:
    """Add, update, or delete a position of responsibility entry in the user's resume.
    Index and Type are required for update/delete operations.
    """
    try:
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")
        if not user_id or not resume_id:
            raise ValueError("Missing user_id or resume_id in context.")

        # ✅ Validate operation
        if type != "delete" and not updates:
            raise ValueError("Missing 'updates' for add/update operation.")
        if type in ["update", "delete"] and index is None:
            raise ValueError("Index is required for update/delete operation.")

        # Deep copy for JSON patch
        new_resume = get_resume(user_id, resume_id)
        if not new_resume:
            raise ValueError("Resume not found.")


        # Convert updates to dict safely (ignore unset fields for partial updates)
        updates_data = updates.model_dump(exclude_unset=True) if updates else None

        # ---- Handle operations ----
        if type == "delete":
            if index < len(new_resume['positions_of_responsibility']):
                del new_resume['positions_of_responsibility'][index]
            else:
                raise IndexError("Index out of range for position of responsibility entries.")

        elif type == "add":
            base_entry = PositionOfResponsibility().model_dump()  # All fields None
            base_entry.update(updates_data or {})
            new_resume['positions_of_responsibility'].append(base_entry)

        elif type == "update":
            if index < len(new_resume['positions_of_responsibility']):
                for k, v in updates_data.items():
                    new_resume['positions_of_responsibility'][index][k] = v
            else:
                raise IndexError("Index out of range for position of responsibility entries.")
        
        
        if new_resume.get("total_updates", 0) > 5:
            updated_service = await update_summary_and_skills(new_resume, new_resume.get("tailoring_keys", []))

            if updated_service is not None:
                if updated_service.summary:
                    new_resume["summary"] = updated_service.summary
                if updated_service.skills and 0 < len(updated_service.skills) <= 10:
                    new_resume["skills"] = updated_service.skills
                new_resume["total_updates"] = 0
        else:
            new_resume["total_updates"] = new_resume.get("total_updates", 0) + 1
            
            
        # ---- Save & Notify ----
        save_resume(user_id, resume_id, new_resume)

        await send_patch_to_frontend(user_id, new_resume)

        print(f"✅ Position Of Responsibility section updated for {user_id}")

        return {"status":"success"}

    except Exception as e:
        print(f"❌ Error updating position of responsibility for user {user_id}: {e}")
        return {"status":"error","message":str(e)}







class MoveOperation(BaseModel):
    old_index: int
    new_index: int

# ---- Pydantic input schema ----
class ReorderToolInput(BaseModel):
    operations: list[MoveOperation]


@tool(
    name_or_callable="reorder_tool",
    description="Reorder the positions_of_responsibility entries in the user's resume.",
    args_schema=ReorderToolInput,
    infer_schema=True,
    return_direct=False,
    response_format="content",
    parse_docstring=False
)
async def reorder_Tool(operations: ReorderToolInput,config: RunnableConfig,) -> None:
    """Reorder the positions_of_responsibility entries in the user's resume."""

    try:
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")
        
        # print(operations)

        if not user_id or not resume_id:
            raise ValueError("Missing user_id or resume_id in context.")

        # ✅ Validate operation
        if operations is None or len(operations) is 0:
            raise ValueError("Missing 'operations' for reorder operation.")
        
        
        new_resume = get_resume(user_id, resume_id)
                
        # Ensure key exists
        if "positions_of_responsibility" not in new_resume:
            raise ValueError("No positions_of_responsibility entries found in the resume.")

        total_entry = len(new_resume['positions_of_responsibility'])

        for op in operations:
            old_index = op.old_index
            new_index = op.new_index
            
            if not isinstance(op, MoveOperation):
                raise ValueError("Invalid operation type. Expected 'MoveOperation'.")

            if old_index < 0 or old_index >= total_entry:
                raise IndexError(f"Old index {old_index} out of range for internship entries.")
            if new_index < 0 or new_index >= total_entry:
                raise IndexError(f"New index {new_index} out of range for internship entries.")


        # ---- Handle operations ----
        for op in sorted(operations, key=lambda x: x.old_index):
            old_index = op.old_index
            new_index = op.new_index

            # Move the entry
            entry = new_resume['positions_of_responsibility'].pop(old_index)
            new_resume['positions_of_responsibility'].insert(new_index, entry)

        # ---- Save & Notify ----
        save_resume(user_id, resume_id, new_resume)
        await send_patch_to_frontend(user_id, new_resume)

        print(f"✅ positions_of_responsibility section reordered for {user_id}")

        return {"status": "success"}

    except Exception as e:
        print(f"❌ Error reordering resume for user in positions_of_responsibility: {e}")
        return {"status": "error", "message": str(e)}





# ---- Tool function ----
@tool(
    name_or_callable="reorder_responsibilities_tool",
    description="Reorder the responsibilities in a particular positions_of_responsibility entry of the user's resume.",
    infer_schema=True,
    return_direct=False,
    response_format="content",
    parse_docstring=False
)
async def reorder_responsibilities_tool(
    operations: list[MoveOperation],
    entry_at: int,
    config: RunnableConfig,
) -> None:
    """Reorder the responsibilities in a particular positions_of_responsibility entry of the user's resume."""

    try:
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")

        if not user_id or not resume_id:
            raise ValueError("Missing user_id or resume_id in context.")

        if not operations or len(operations) == 0:
            raise ValueError("Missing 'operations' for reorder operation.")

        new_resume = get_resume(user_id, resume_id)

        if "positions_of_responsibility" not in new_resume:
            raise ValueError("No positions_of_responsibility entries found in the resume.")

        total_entry = len(new_resume['positions_of_responsibility'])
        if entry_at < 0 or entry_at >= total_entry:
            raise IndexError(f"Entry index {entry_at} out of range.")

        responsibilities = new_resume['positions_of_responsibility'][entry_at].get('responsibilities', [])
        total_bullet_points = len(responsibilities)

        if total_bullet_points == 0:
            raise ValueError("No responsibilities found in the specified entry.")

        # ✅ Validate all moves before doing anything
        for op in operations:
            if not isinstance(op, MoveOperation):
                raise ValueError("Invalid operation type. Expected 'MoveOperation'.")
            if op.old_index < 0 or op.old_index >= total_bullet_points:
                raise IndexError(f"Old index {op.old_index} out of range.")
            if op.new_index < 0 or op.new_index >= total_bullet_points:
                raise IndexError(f"New index {op.new_index} out of range.")

        # ✅ Handle moves safely — process in a way that avoids shifting index issues
        # Sort by old_index to ensure correct order of pops
        for op in sorted(operations, key=lambda x: x.old_index):
            item = responsibilities.pop(op.old_index)
            responsibilities.insert(op.new_index, item)

        # ✅ Save changes
        save_resume(user_id, resume_id, new_resume)
        await send_patch_to_frontend(user_id, new_resume)

        print(f"✅ Reordered responsibilities for user {user_id}")
        return {"status": "success"}

    except Exception as e:
        print(f"❌ Error reordering responsibilities: {e}")
        return {"status": "error", "message": str(e)}





@tool
async def get_entry_by_company_name(
    company_name: str,
    state: Annotated[SwarmResumeState, InjectedState],
    config: RunnableConfig
):
    """get the internship entry by company name."""
    try:
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")

        if not user_id or not resume_id:
            raise ValueError("Missing user_id or resume_id in context.")

        resume = get_resume(user_id, resume_id)
        
        entries = resume.get("internships", [])
        
        if len(entries) == 0:
            raise ValueError("No internship entries found in the resume.Add an entry first.")
        
        entry = next((e for e in entries if e.get("company_name", "").lower() == company_name.lower()), None)
        
        if not entry:
            raise ValueError(f"No internship entry found for company '{company_name}'.")
        
        key = f"state:{user_id}:{resume_id}:internship"

        # Load existing state from Redis if present
        saved_state = r.get(key)
        if saved_state:
            if isinstance(saved_state, bytes):   # handle redis-py default
                saved_state = saved_state.decode("utf-8")
            saved_state = json.loads(saved_state)
        else:
            saved_state = {"entry": {}, "retrived_info": "None"}
        
        
        # Update entry while preserving retrived_info
        saved_state["entry"] = entry
        saved_state["index"] = entries.index(entry)
        

        # Save back to Redis
        status = r.set(key, json.dumps(saved_state))

        return {
            "status": "success" if status else "failed",
        }

    except Exception as e:
        print(f"❌ Error getting entry by company name: {e}")
        return {"status": "error", "message": str(e)}


import jsonpatch

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
        print("PATCH:", patches)
        
        
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")

        if not user_id or not resume_id:
            raise ValueError("Missing user_id or resume_id in context.")

        if not patches:
            raise ValueError("Missing 'patches' for state update operation.")

        current_entries = state["resume_schema"].model_dump().get("positions_of_responsibility", [])

        
        print(f"Current POR before patch: {current_entries}")
        if not isinstance(current_entries, list):
            current_entries = []

        # print(f"Current acads entries count: {current_entry_length}")

        try:
            jsonpatch.apply_patch(current_entries, patches,in_place=False)
        except jsonpatch.JsonPatchException as e:
            raise ValueError(f"Invalid JSON Patch operations: {e}")
    
        
        tool_message = ToolMessage(
            content="Successfully transferred to the pipeline to add the patches in an enhanced manner.",
            name="send_patches",
            tool_call_id=tool_call_id,
        )

        
  
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
        print(f"❌ Error applying por entry patches: {e}")

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





tools = [
    
    reorder_Tool,reorder_responsibilities_tool,
    send_patches,

        #  get_compact_por_entries,
        #  get_por_entry_by_index,
         transfer_to_extra_curricular_agent, transfer_to_main_agent,transfer_to_acads_agent,
         transfer_to_workex_agent, transfer_to_internship_agent
         ,transfer_to_education_agent,transfer_to_scholastic_achievement_agent,transfer_to_certification_assistant_agent]

