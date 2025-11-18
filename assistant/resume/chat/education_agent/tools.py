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




@tool
def get_compact_education_entries(config: RunnableConfig):
    """
    Get all education entries in a concise, one-line format.
    Returns: list of strings, each representing an education entry.
    """
    try:
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")
        
        entries_raw = r.get(f"resume:{user_id}:{resume_id}")
        resume_data = json.loads(entries_raw) if entries_raw else {}
        entries = resume_data.get("education_entries", [])

        # Filter out invalid entries
        entries = [e for e in entries if e and isinstance(e, dict)]

        compact = []
        for e in entries:
            parts = []
            if e.get("degree"):
                parts.append(e["degree"])
            if e.get("college"):
                parts.append(e["college"])
            if e.get("start_year") or e.get("end_year"):
                years = f"{e.get('start_year','')} - {e.get('end_year','')}".strip(" -")
                parts.append(f"({years})")
            if e.get("cgpa"):
                parts.append(f"CGPA {e['cgpa']}")
            
            # Join all non-empty parts with commas
            line = ", ".join([p for p in parts if p])
            if line:
                compact.append(line)

        print("Compact education entries:", compact)
        return compact

    except Exception as e:
        print(f"Error in get_compact_education_entries: {e}")
        return {"status":"error", "message": str(e)}



# ---- Pydantic input schema ----
class EducationToolInput(BaseModel):
    type: Literal["add", "update", "delete"]  # Default to add
    updates: Optional[Education] = None              # Optional for delete
    index: int               # Optional index

    @field_validator("updates", mode="before")
    @classmethod
    def parse_updates(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("updates must be a dict or JSON string.")
        return v


# ---- Tool function ----
@tool(
    name_or_callable="education_tool",
    description="Add, update, or delete an education entry in the user's resume. "
                "Requires index for update/delete operations.",
    args_schema=EducationToolInput,
    infer_schema=True,
    return_direct=False,
    response_format="content",
    parse_docstring=False
)
async def education_Tool(
    index: int | None,  # Optional index for update/delete operations
    config: RunnableConfig,
    type: Literal["add", "update", "delete"],
    updates: Optional[Education] = None,
) :
    """Add, update, or delete an education entry in the user's resume. 
    Index is required for update/delete operations.
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
            raise ValueError("Index is required for add/update/delete operation.")


        

        # Deep copy for JSON patch
        new_resume = get_resume(user_id, resume_id)
        
        # Ensure key exists
        if "education_entries" not in new_resume:
            new_resume["education_entries"] = []

        # Convert updates to dict safely (ignore unset fields for partial updates)
        updates_data = updates.model_dump(exclude_unset=True) if updates else None

        # ---- Handle operations ----
        if type == "delete":
            if index < len(new_resume['education_entries']):
                del new_resume['education_entries'][index]
            else:
                raise IndexError("Index out of range for education entries.")

        elif type == "add":
            base_entry = Education().model_dump()  # All fields None
            base_entry.update(updates_data or {})
            new_resume['education_entries'].append(base_entry)

        elif type == "update":
            if index < len(new_resume['education_entries']):
                # Merge only the provided fields
                for k, v in updates_data.items():
                    new_resume['education_entries'][index][k] = v
            else:
                raise IndexError("Index out of range for education entries.")
            

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

        print(f"✅ Education section updated for {user_id}")

        return {"status": "success"}

    except Exception as e:
        print(f"❌ Error updating resume for user: {e}")
        return {"status": "error", "err_msg": str(e)}









class MoveOperation(BaseModel):
    old_index: int
    new_index: int


# ---- Tool function ----
@tool(
    name_or_callable="reorder_tool",
    description="Reorder the education entries in the user's resume.",
    infer_schema=True,
    return_direct=False,
    response_format="content",
    parse_docstring=False
)
async def reorder_Tool(
    operations: list[MoveOperation],
    config: RunnableConfig,
) -> None:
    """Reorder the education entries in the user's resume.
    """

    try:
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")
        
        print(operations)

        if not user_id or not resume_id:
            raise ValueError("Missing user_id or resume_id in context.")

        # ✅ Validate operation
        if operations is None or len(operations) is 0:
            raise ValueError("Missing 'operations' for reorder operation.")
        
        
        new_resume = get_resume(user_id, resume_id)
                
        # Ensure key exists
        if "education_entries" not in new_resume:
            raise ValueError("No education entries found in the resume.")

        for op in operations:
            old_index = op.old_index
            new_index = op.new_index
            
            if not isinstance(op, MoveOperation):
                raise ValueError("Invalid operation type. Expected 'MoveOperation'.")
            
            if old_index < 0 or old_index >= len(new_resume['education_entries']):
                raise IndexError(f"Old index {old_index} out of range for education entries.")
            if new_index < 0 or new_index >= len(new_resume['education_entries']):
                raise IndexError(f"New index {new_index} out of range for education entries.")


        # ---- Handle operations ----
        for op in sorted(operations, key=lambda x: x.old_index):
            old_index = op.old_index
            new_index = op.new_index

            # Move the entry
            entry = new_resume['education_entries'].pop(old_index)
            new_resume['education_entries'].insert(new_index, entry)

        # ---- Save & Notify ----
        save_resume(user_id, resume_id, new_resume)
        await send_patch_to_frontend(user_id, new_resume)

        print(f"✅ Education section reordered for {user_id}")

        return {"status": "success"}

    except Exception as e:
        print(f"❌ Error reordering resume for user: {e}")
        return {"status": "error", "err_msg": str(e)}


from ..llm_model import SwarmResumeState
import jsonpatch

@tool
async def send_patches(
    patches: list[dict],   # <-- instead of entry
    state: Annotated[SwarmResumeState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
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


    try:
        print("PATCH:", patches)
        
        
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")

        if not user_id or not resume_id:
            raise ValueError("Missing user_id or resume_id in context.")

        if not patches:
            raise ValueError("Missing 'patches' for state update operation.")
        
        
  
        current_entries = state["resume_schema"].model_dump().get("education_entries", [])   

        try:
            jsonpatch.apply_patch(current_entries, patches,in_place=False)
            print(f"Applied patch list to internships: {patches}")
        except jsonpatch.JsonPatchException as e:
            raise ValueError(f"Invalid JSON Patch operations,: {e}")
        
        # ✅ Apply patches to backend storage
        # result = await apply_patches(f"{user_id}:{resume_id}", patches)
        result = await apply_patches_global(f"{user_id}:{resume_id}", patches,"education_entries")
        
        print("Apply patches result:", result)
        
        if result and result.get("status") == "success":
            return "Education Patches applied successfully.",
                
        elif result and result.get("status") == "error":
            raise ValueError(result.get("message", "Unknown error during patch application."))
        else:
            raise ValueError("Unknown error during patch application.")
    
        

    except Exception as e:
        print(f"❌ Error applying certification entry patches: {e}")


        # ❌ Do not raise ToolException if you want router to handle it
        return f"""The send_patches tool failed due to:\n {e}.\n Please either retry generating valid patches or inform the user 
                that the update could not be applied."""








tools = [send_patches,
        #  get_compact_education_entries,
         transfer_to_main_agent, transfer_to_por_agent,transfer_to_acads_agent,
         transfer_to_workex_agent, transfer_to_internship_agent
         ,transfer_to_scholastic_achievement_agent,transfer_to_extra_curricular_agent,transfer_to_certification_assistant_agent]





