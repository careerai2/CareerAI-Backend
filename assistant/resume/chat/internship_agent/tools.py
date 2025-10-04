from langchain.tools import tool
from pydantic import BaseModel, field_validator
import json
from langgraph.graph import END
from typing import Literal,Union
from models.resume_model import *
from typing import Optional, Literal
from pydantic import BaseModel, field_validator
import json
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from ..utils.common_tools import get_resume, save_resume, send_patch_to_frontend
from ..utils.update_summar_skills import update_summary_and_skills
from ..handoff_tools import *
from redis_config import redis_client as r 
from langgraph.prebuilt import InjectedState
from models.resume_model import Internship
from .functions import update_internship_field 
from ..llm_model import SwarmResumeState,InternshipState
from .handoff_tools import transfer_to_enhancer_pipeline,transfer_to_add_internship_agent,transfer_to_update_internship_agent

@tool
def get_compact_internship_entries(config: RunnableConfig):
    """
    Get all internship entries in a concise format.
    Returns: list of dicts with only non-null fields.
    """
    try:
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")
        
        entries_raw = r.get(f"resume:{user_id}:{resume_id}")
        resume_data = json.loads(entries_raw) if entries_raw else {}
        entries = resume_data.get("internships", [])

        # Filter out None or empty entries
        entries = [e for e in entries if e and isinstance(e, dict)]

        compact = []
        for i, e in enumerate(entries):
            # Build dict with only non-null and non-empty fields
            entry_dict = {
                "index": i,
                **{k: v for k, v in {
                    "company_name": e.get("company_name"),
                    "company_description": e.get("company_description"),
                    "designation": e.get("designation"), 
                    "designation_description": e.get("designation_description"), 
                    "location": e.get("location"),
                    "duration": e.get("duration"),
                }.items() if v not in [None, "", [], {}]}  # remove null/empty values
            }

            compact.append(entry_dict)

        print("Compact entries:", compact)
        return compact

    except Exception as e:
        print(f"Error in get_compact_internship_entries: {e}")
        return []


@tool
def get_full_internship_entries(config: RunnableConfig, tool_call_id: Annotated[str, InjectedToolCallId],):
    """
    Get all internship entries in a full format.
    Returns: list of dicts with all fields.
    """
    try:
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")
        
        entries_raw = r.get(f"resume:{user_id}:{resume_id}")
        resume_data = json.loads(entries_raw) if entries_raw else {}
        entries = resume_data.get("internships", [])

        # Filter out None or empty entries
        entries = [e for e in entries if e and isinstance(e, dict)]
        

        # return entries
        tool_message = ToolMessage(
            content="Successfully transferred to internship_model",
            name="handoff_to_internship_model",
            tool_call_id=tool_call_id,
        )
    
        return Command(
                goto="internship_model",
                update={
                    "messages": [tool_message],
                }
            )

    except Exception as e:
        print(f"Error in get_full_internship_entries: {e}")
        
        return {"error": "Failed to retrieve full internship entries","message":str(e)}


@tool
def get_internship_entry_by_index(index: int, config: RunnableConfig):
    """
    Get a single internship entry by index.
    Returns full entry including all bullets.
    """
    user_id = config["configurable"].get("user_id")
    resume_id = config["configurable"].get("resume_id")
    
    entries_raw = r.get(f"resume:{user_id}:{resume_id}")
    resume_data = json.loads(entries_raw) if entries_raw else {}
    entries = resume_data.get("internships", [])
    
    
    if index is not None and 0 <= index < len(entries):
        return entries[index]
    else:
        return {"error": "Invalid index or entry not found"}


class InternshipToolInput(BaseModel):
    type: Literal["add", "update", "delete"]  # Default operation
    updates: Optional[Internship] = None
    index: Optional[int] = None  # Required for update/delete

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
    name_or_callable="internship_tool",
    description="Add, update, or delete an internship entry in the user's resume. "
                "Requires index for update/delete operations.",
    args_schema=InternshipToolInput,
    infer_schema=True,
    return_direct=False,
    response_format="content",
    parse_docstring=False
)
async def internship_Tool(
    index: int,
    config: RunnableConfig,
    type: Literal["add", "update", "delete"],
    updates: Optional[Internship] = None,
):
    """Add, update, or delete an internship entry in the user's resume. 
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
            raise ValueError("Index is required for update/delete operation.")


        # Deep copy for JSON patch
        new_resume = get_resume(user_id, resume_id)
        if not new_resume:
            raise ValueError("Resume not found.")


        # Convert updates to dict safely (ignore unset fields for partial updates)
        updates_data = updates.model_dump(exclude_unset=True) if updates else None

        # ---- Handle operations ----
        if type == "delete":
            if index < len(new_resume['internships']):
                del new_resume['internships'][index]
            else:
                raise IndexError("Index out of range for internship entries.")

        elif type == "add":
            base_entry = Internship().model_dump()  # All fields None
            base_entry.update(updates_data or {})
            new_resume['internships'].append(base_entry)

        elif type == "update":
            if index < len(new_resume['internships']):
                for k, v in updates_data.items():
                    new_resume['internships'][index][k] = v
            else:
                raise IndexError("Index out of range for internship entries.")
        
    
        
        if new_resume.get("total_updates") > 5:
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

        print(f"✅ Internship section updated for {user_id}")

        return {"status": "success"}

    except Exception as e:
        print(f"❌ Error updating internship for user {user_id}: {e}")
        return {"status": "error", "message": str(e)}



@tool(
    name_or_callable="internship_bullet_tool",
    description="Add, update, or delete a bullet point inside a specific internship entry in the resume. "
                "Requires internship_index for identifying the internship entry and bullet_index for update/delete.",
    args_schema=None,  # you can define a Pydantic schema like InternshipBulletInput
    infer_schema=True,
    return_direct=False,
    response_format="content",
    parse_docstring=False
)
async def internship_bullet_tool(
    internship_index: int,
    config: RunnableConfig,
    type: Literal["add", "update", "delete"],
    bullet_index: Optional[int] = None,
    bullet_entry: Optional[str] = None,
):
    """Add, update, or delete a bullet point in a specific internship entry."""
    try:
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")
        if not user_id or not resume_id:
            raise ValueError("Missing user_id or resume_id in context.")

        # Load resume
        new_resume = get_resume(user_id, resume_id)
        if not new_resume:
            raise ValueError("Resume not found.")

        # Validate internship index
        if internship_index >= len(new_resume['internships']):
            raise IndexError("Internship index out of range.")

        internship_entry = new_resume['internships'][internship_index]

        # Ensure internship_work_description_bullets field exists
        if "internship_work_description_bullets" not in internship_entry or internship_entry["internship_work_description_bullets"] is None:
            internship_entry["internship_work_description_bullets"] = []

        # ---- Handle operations ----
        if type == "add":
            if not bullet_entry:
                raise ValueError("Missing 'bullet_entry' for add operation.")
            internship_entry["internship_work_description_bullets"].append(bullet_entry)

        elif type == "update":
            if bullet_index is None or bullet_index >= len(internship_entry["internship_work_description_bullets"]):
                raise IndexError("Bullet index out of range.")
            if not bullet_entry:
                raise ValueError("Missing 'bullet_entry' for update operation.")
            internship_entry["internship_work_description_bullets"][bullet_index] = bullet_entry

        elif type == "delete":
            if bullet_index is None or bullet_index >= len(internship_entry["internship_work_description_bullets"]):
                raise IndexError("Bullet index out of range.")
            del internship_entry["internship_work_description_bullets"][bullet_index]

        # Save updates
        save_resume(user_id, resume_id, new_resume)
        await send_patch_to_frontend(user_id, new_resume)

        print(f"✅ Bullet point {type}d for internship {internship_index}, user {user_id}")
        return {"status": "success"}

    except Exception as e:
        print(f"❌ Error updating bullet point for user {user_id}: {e}")
        return {"status": "error", "message": str(e)}


class MoveOperation(BaseModel):
    old_index: int
    new_index: int

# ---- Pydantic input schema ----
class ReorderToolInput(BaseModel):
    operations: list[MoveOperation]


# ---- Tool function ----
@tool(
    name_or_callable="reorder_tool",
    description="Reorder the internship entries in the user's resume.",
    args_schema=ReorderToolInput,
    infer_schema=True,
    return_direct=False,
    response_format="content",
    parse_docstring=False
)
async def reorder_Tool(
    operations: ReorderToolInput,
    config: RunnableConfig,
) -> None:
    """Reorder the internship entries in the user's resume.
    """

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
        if "internships" not in new_resume:
            raise ValueError("No internship entries found in the resume.")

        total_entry = len(new_resume['internships'])

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
            entry = new_resume['internships'].pop(old_index)
            new_resume['internships'].insert(new_index, entry)

        # ---- Save & Notify ----
        save_resume(user_id, resume_id, new_resume)
        await send_patch_to_frontend(user_id, new_resume)

        print(f"✅ Internship section reordered for {user_id}")

        return {"status": "success"}

    except Exception as e:
        print(f"❌ Error reordering Internships for user: {e}")
        return {"status": "error", "message": str(e)}




# ---- Tool function ----
@tool(
    name_or_callable="reorder_internship_work_description_bullets_tool",
    description="Reorder the internship_work_description_bullets in a particular internships entry of the user's resume.",
    infer_schema=True,
    return_direct=False,
    response_format="content",
    parse_docstring=False
)
async def reorder_bullet_points_tool(
    operations: list[MoveOperation],
    entry_at: int,
    config: RunnableConfig,
) -> None:
    """Reorder the internship_work_description_bullets in a particular Internship entry of the user's resume."""

    try:
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")

        if not user_id or not resume_id:
            raise ValueError("Missing user_id or resume_id in context.")

        if not operations or len(operations) == 0:
            raise ValueError("Missing 'operations' for reorder operation.")

        new_resume = get_resume(user_id, resume_id)

        if "internships" not in new_resume:
            raise ValueError("No internships entries found in the resume.")

        total_entry = len(new_resume['internships'])
        if entry_at < 0 or entry_at >= total_entry:
            raise IndexError(f"Entry index {entry_at} out of range.")

        bullets = new_resume['internships'][entry_at].get('internship_work_description_bullets', [])
        total_bullet_points = len(bullets)

        if total_bullet_points == 0:
            raise ValueError("No bullet points found in the specified entry.")

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
            item = bullets.pop(op.old_index)
            bullets.insert(op.new_index, item)

        # ✅ Save changes
        save_resume(user_id, resume_id, new_resume)
        await send_patch_to_frontend(user_id, new_resume)

        print(f"✅ Reordered responsibilities for user {user_id}")
        return {"status": "success"}

    except Exception as e:
        print(f"❌ Error reordering responsibilities: {e}")
        return {"status": "error", "message": str(e)}






# # ------ Retrival Tool -------------
# @tool(
#     description=(
#         "Retrieves the most relevant and exact information for a given role, section, "
#         "and field from the knowledge base. Returns action verbs, skills, guidelines, "
#         "good to have - must have or examples.")
# )
# async def use_knowledge_base(
#     query_text: str,
#     config: RunnableConfig,
#     section: Literal["Internship","Skills"],
#     field: Literal["ActionVerbs","GoodTOHave","MustHave","Guidelines"],
#     n_results: int = 5,
#     similarity_threshold: float = 0.45,  # good for cosine distance
# ):
#     """
#     Use it for if you need to fetch exact action verbs, must-haves, good-to-haves, or guidelines for a specific resume section.
#     Always use before creating or editing an entry.
#     Precise retrieval tool for LLMs.
#     Uses semantic search + metadata filters.
#     """
#     try:
#         query_embedding = embeddings.embed_query(query_text)
#         role = config["configurable"].get("tailoring_keys")

#         # ---- Build dynamic filters ----
#         conditions = []
#         if role:
#             if isinstance(role, list) and len(role) > 1:
#                 conditions.append({"$or": [{"role": r} for r in role]})
#             else:
#                 conditions.append({"role": role[0] if isinstance(role, list) else role})
#         if section:
#             conditions.append({"section": section})
#         if field:
#             conditions.append({"field": field})

#         where_filter = {"$and": conditions} if conditions else {}

#         # ---- Query Chroma ----
#         results = collection.query(
#             query_embeddings=[query_embedding],
#             n_results=n_results,
#             where=where_filter,
#             include=["documents", "distances", "metadatas"],
#         )

#         retrieved_texts = []
#         for doc_list, dist_list in zip(results["documents"], results["distances"]):
#             for doc, dist in zip(doc_list, dist_list):
#                 # keep only close (similar) results
#                 if dist > similarity_threshold:
#                     continue
#                 # parse JSON arrays if present
#                 if isinstance(doc, str) and doc.startswith("["):
#                     try:
#                         parsed = json.loads(doc)
#                         if isinstance(parsed, list):
#                             retrieved_texts.extend(parsed)
#                         else:
#                             retrieved_texts.append(parsed)
#                     except Exception:
#                         retrieved_texts.append(doc)
#                 else:
#                     retrieved_texts.append(doc)

#         # ---- Deduplicate & return ----
#         retrieved_texts = list(dict.fromkeys(map(str, retrieved_texts)))
#         result = "\n".join(retrieved_texts)

#         return result if result else "No relevant information found."

#     except Exception as e:
#         return {"status": "error", "message": str(e)}

@tool(
    description="Retrieve internship-related knowledge (ActionVerbs, Requirements, Guidelines, or field-specific guideline). Supports multiple fields."
)
def fetch_internship_info(fields: Union[str, list[str]], config: RunnableConfig) -> dict:
    """
    Fetch internship information for one or multiple fields.

    Args:
        fields: str or list of str. Can include "ActionVerbs", "Requirements",
                "Guidelines", or specific fields like "company_name", "duration".
    """
    try:
        print(f"[fetch_internship_info] Called with fields: {fields}")
        if isinstance(fields, str):
            fields = [fields]

        role = config["configurable"].get("tailoring_keys")
        print(f"[fetch_internship_info] Role: {role}")
        INTERNSHIP_KB = "Nothing"
        print(f"[fetch_internship_info] Loaded KB keys: {list(INTERNSHIP_KB.keys())}")

        results = {}
        for field in fields:
            field_norm = field.strip().lower()
            print(f"[fetch_internship_info] Processing field: {field} (normalized: {field_norm})")

            if field_norm == "actionverbs":
                results["ActionVerbs"] = INTERNSHIP_KB.get("ActionVerbs", [])
                print(f"[fetch_internship_info] ActionVerbs: {results['ActionVerbs']}")

            elif field_norm == "requirements":
                results["Requirements"] = INTERNSHIP_KB.get("Requirements", [])
                print(f"[fetch_internship_info] Requirements: {results['Requirements']}")

            elif field_norm == "guidelines":
                results["Guidelines"] = INTERNSHIP_KB.get("Guidelines", [])
                print(f"[fetch_internship_info] Guidelines: {results['Guidelines']}")

            else:
                # Look inside Guidelines
                match = next(
                    (g for g in INTERNSHIP_KB.get("Guidelines", []) if g.get("field", "").lower() == field_norm),
                    None
                )
                if match:
                    results[match["field"]] = match.get("instruction", "")
                    print(f"[fetch_internship_info] Found guideline for {field}: {match.get('instruction', '')}")
                else:
                    results[field] = f"No information found for '{field}'"
                    print(f"[fetch_internship_info] No information found for {field}")

        print(f"[fetch_internship_info] Final results: {results}")
        return results
    except Exception as e:
        print(f"[fetch_internship_info] Error: {e}")
        return {"status": "error", "message": str(e)}



class entryStateInput(BaseModel):
    field: Literal[
        "company_name",
        "company_description",
        "location",
        "designation",
        "designation_description",
        "duration",
        "internship_work_description_bullets"
    ]
    value: str | list[str]

# @tool
# async def update_entry_state(
#     entry: list[entryStateInput],
#     state: Annotated[SwarmResumeState, InjectedState],
#     config: RunnableConfig
# ):
#     """Update the internship sub-state within SwarmResumeState."""
#     try:
#         user_id = config["configurable"].get("user_id")
#         resume_id = config["configurable"].get("resume_id")

#         if not user_id or not resume_id:
#             raise ValueError("Missing user_id or resume_id in context.")

#         print("STATE BEFORE UPDATE:", state["internship"].entry)
#         print(f"🔄 Updating internship entry state with: {entry}")

#         if not entry:
#             raise ValueError("Missing 'entry' for state update operation.")

#         # Ensure the internship sub-state exists
#         if state["internship"] is None:
#             raise ValueError("Internship state not initialized.")

#         # Ensure the entry object exists
#         if state["internship"].entry is None:
#             state["internship"].entry = Internship()

#         failed_fields = []

#         for e in entry:
#             if e.field == "internship_work_description_bullets":
#                 if not isinstance(e.value, list):
#                     failed_fields.append({
#                         "field": e.field,
#                         "message": "Value must be a list of strings."
#                     })
#                     continue
#                 if state["internship"].entry.internship_work_description_bullets is None:
#                     state["internship"].entry.internship_work_description_bullets = []
#                 state["internship"].entry.internship_work_description_bullets.extend(e.value)
#             else:
#                 if isinstance(e.value, list):
#                     if len(e.value) == 1:
#                         setattr(state["internship"].entry, e.field, e.value[0])
#                     else:
#                         failed_fields.append({
#                             "field": e.field,
#                             "message": "Value must be a single string."
#                         })
#                 else:
#                     setattr(state["internship"].entry, e.field, e.value)

#         print(f"✅ Internship entry state updated.", state["internship"].entry)

#         key = f"state:{user_id}:{resume_id}:internship"

#         # Load existing state from Redis if present
#         saved_state = r.get(key)
#         if saved_state:
#             if isinstance(saved_state, bytes):   # handle redis-py default
#                 saved_state = saved_state.decode("utf-8")
#             saved_state = json.loads(saved_state)
#         else:
#             saved_state = {"entry": {}, "retrived_info": "None"}

#         # Update entry while preserving retrived_info
#         saved_state["entry"] = state["internship"].entry.model_dump()

#         # Save back to Redis
#         status = r.set(key, json.dumps(saved_state))

#         return {
#             "status": "success" if status else "failed",
#             "failed_fields": failed_fields
#         }

#     except Exception as e:
#         print(f"❌ Error updating internship entry state: {e}")
#         return {"status": "error", "message": str(e)}


import jsonpatch

@tool
async def send_patches(
    patches: list[dict],   # <-- instead of entry
    state: Annotated[SwarmResumeState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    config: RunnableConfig
):
    """Apply JSON Patch ops (RFC 6902) to the internship actual internship entry in the resume."""
    try:
        
        print("PATCH:", patches)
        
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")

        if not user_id or not resume_id:
            raise ValueError("Missing user_id or resume_id in context.")

        if not patches:
            raise ValueError("Missing 'patches' for state update operation.")
        
        index = getattr(state["internship"], "index", None)
        
        
        tool_message = ToolMessage(
            content="Successfully transferred to internship_model",
            name="handoff_to_internship_model",
            tool_call_id=tool_call_id,
        )

        
  
        return Command(
            goto="query_generator_model",
            update={
                "messages": [tool_message],
                "internship": {
                    "retrived_info": "",
                    "patches": patches,
                    "index": index,
                },
            },
        )

    except Exception as e:
        print(f"❌ Error applying internship entry patches: {e}")
        fallback_msg = ToolMessage(
            content=f"Error applying patches internally: {e}",
            name="error_message",
            tool_call_id=tool_call_id,
        )
        return {"messages": [fallback_msg]}



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



@tool
async def update_index_and_focus(
    index: int,
    state: Annotated[SwarmResumeState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    config: RunnableConfig
):
    """Update the index and fetch the corresponding internship entry on which focus is needed."""
    try:
        user_id = config["configurable"].get("user_id")
        resume_id = config["configurable"].get("resume_id")

        if not user_id or not resume_id:
            raise ValueError("Missing user_id or resume_id in context.")

        resume= state.get("resume_schema", {})
        current_entries = getattr(resume, "internships", [])

        if len(current_entries) == 0:
            raise ValueError("No internship entries found in the resume.Add an entry first.")
        if index < 0 or index >= len(current_entries):
            raise IndexError("Index out of range for internship entries.")
        entry = current_entries[index]
            
        update_internship_field(f"""{user_id}:{resume_id}""", "index", index)
        
        tool_message = ToolMessage(
            content="Successfully updated the focus to the specified internship entry.",
            name="update_index_and_focus",
            tool_call_id=tool_call_id,
        )
        

        return Command(
            goto="internship_model",
            update={
                "messages": state["messages"] + [tool_message]
            },
        )
    except Exception as e:
        print(f"❌ Error getting entry by company name: {e}")
        return {"status": "error", "message": str(e)}




tools = [
    # internship_Tool, 
    send_patches,
    update_index_and_focus,
    # transfer_to_enhancer_pipeline,
    # transfer_to_update_internship_agent,
         reorder_bullet_points_tool,
         reorder_Tool,
        # internship_bullet_tool,
        # human_assistance,
        # use_knowledge_base,
        # get_compact_internship_entries,
        # get_internship_entry_by_index,
        get_full_internship_entries,
        ]


transfer_tools = [transfer_to_main_agent, transfer_to_por_agent,
         transfer_to_workex_agent, transfer_to_education_agent,
         transfer_to_scholastic_achievement_agent, transfer_to_extra_curricular_agent]
    