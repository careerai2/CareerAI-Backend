from langchain.tools import tool
from pydantic import BaseModel, field_validator,ValidationError
import json
from typing import Literal,Union
from models.resume_model import *
from typing import Optional, Literal
from pydantic import BaseModel, field_validator
import json
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from ..utils.common_tools import get_resume, save_resume, send_patch_to_frontend
from ..handoff_tools import *
from redis_config import redis_client as r , chroma_client, embeddings
from assistant.resume.chat.utils.common_tools import send_patch_to_frontend
from langgraph.prebuilt import InjectedState
from models.resume_model import AcademicProject
# from .state import InternshipState
from ..llm_model import SwarmResumeState,InternshipState,WorkexState

import jsonpatch



# to update any field in internship state like index,retrieved_info of internship agent
def update_acads_field(thread_id: str, field: Literal["index", "retrieved_info"], value):
    """
    Update any field in the Por state for a given thread_id in Redis (plain JSON string storage).
    
    Args:
        thread_id (str): The unique thread/session ID.
        field (str): The field name to update (e.g., 'index', 'retrieved_info').
        value: The new value to set.
    """
    key = f"state:{thread_id}:por"

    # Fetch current JSON
    current_resume_json = r.get(key)
    if current_resume_json:
        current_resume = json.loads(current_resume_json)
    else:
        # Default structure if key doesn't exist
        current_resume = {"retrieved_info": "None", "index": None, "pathches": []}

    # Update the desired field
    current_resume[str(field)] = value

    # Save it back
    r.set(key, json.dumps(current_resume))
    print(f"Updated field '{field}' to '{value}' for thread {thread_id}.")
    
    



async def apply_patches(thread_id: str, patches: list[dict]):
    """
    Adds or updates an Academic Project in the resume and syncs with Redis + frontend.
    Robust version with edge case handling, consistent with internship/por logic.
    """
    try:
        # Load academic projects state from Redis
        acads_state_raw = r.get(f"state:{thread_id}:acads")
        index = None
        if acads_state_raw:
            try:
                acads_state = json.loads(acads_state_raw)
                index = acads_state.get("index")
                if index is not None:
                    index = int(index)
            except json.JSONDecodeError:
                print("Corrupted Academic Projects state in Redis. Resetting.")
                acads_state = {}
                index = None
        else:
            acads_state = {}

        # Early exit if no patches
        if not patches:
            return {"status": "success", "message": "No patches to apply."}

        # Load resume from Redis
        current_resume_raw = r.get(f"resume:{thread_id}")
        if not current_resume_raw:
            return {"status": "error", "message": "Resume not found."}

        try:
            current_resume = json.loads(current_resume_raw)
        except json.JSONDecodeError:
            return {"status": "error", "message": "Corrupted resume data in Redis."}

        # Get existing academic projects list
        current_projects = current_resume.get("academic_projects", [])
        current_project_names = [
            proj.get("project_name", "").lower().strip()
            for proj in current_projects if proj.get("project_name")
        ]

        # Check if any patch adds/replaces a new project
        is_new_project_patch = any(
            patch.get("path") == "/project_name"
            and patch.get("op") in ("add", "replace")
            and patch.get("value", "").lower().strip() not in current_project_names
            for patch in patches
        )
        if is_new_project_patch:
            index = None  # Force new project creation

        # Apply patches to existing or new project
        if index is not None and 0 <= index < len(current_projects):
            try:
                jsonpatch.apply_patch(current_projects[index], patches, in_place=True)
                print(f"Updated Academic Project at index {index}")
            except jsonpatch.JsonPatchException as e:
                return {"status": "error", "message": f"Failed to apply patch: {e}"}
        else:
            # Add new Academic Project entry
            new_project = AcademicProject().model_dump()
            try:
                jsonpatch.apply_patch(new_project, patches, in_place=True)
            except jsonpatch.JsonPatchException as e:
                return {"status": "error", "message": f"Failed to apply patch to new Academic Project: {e}"}
            current_projects.append(new_project)
            index = len(current_projects) - 1
            update_acads_field(thread_id, "index", index)
            print(f"Added new Academic Project at index {index}")

        # Save back to Redis
        current_resume["academic_projects"] = current_projects
        try:
            r.set(f"resume:{thread_id}", json.dumps(current_resume))
        except TypeError as e:
            return {"status": "error", "message": f"Failed to serialize resume: {e}"}

        # Notify frontend safely
        try:
            user_id = thread_id.split(":", 1)[0]
        except IndexError:
            user_id = thread_id
        await send_patch_to_frontend(user_id, current_resume)

        # Save undo stack
        undo_stack_key = f"undo_stack:{thread_id}"
        r.lpush(undo_stack_key, json.dumps({
            "section": "academic_projects",
            "index": index,
            "patches": patches
        }))

        print(f"User ID: {user_id}, patches applied: {patches}")

        return {
            "status": "success",
            "message": "Academic Project updated successfully.",
            "index": index
        }

    except ValidationError as ve:
        return {"status": "error", "message": f"Validation error: {ve.errors()}"}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}


# new version with more filters
def new_query_pdf_knowledge_base(
    query_text,
    role=["acads"],
    section=None,
    subsection=None,
    field=None,
    n_results=10,
    debug=True,
):
    """
    Query stored PDF chunks in Chroma and return the closest match.
    Supports filtering by role, Section, Subsection, and Field metadata.
    """

    # 1️⃣ Embed query (if you added documents directly, use query_texts instead)
    query_embedding = embeddings.embed_query(query_text)

    # 2️⃣ Build metadata filter
    filters = []
    if role:
        filters.append({"role": {"$in": role}})
    if section:
        filters.append({"Section": {"$eq": section}})
    if subsection:
        filters.append({"Subsection": {"$eq": subsection}})
    if field:
        filters.append({"Field": {"$eq": field}})  # only if you used "Field" in splitter

    if not filters:
        where_filter = {}
    elif len(filters) == 1:
        where_filter = filters[0]
    else:
        where_filter = {"$and": filters}

    if debug:
        print(f"🔹 Query: {query_text}")
        print(f"🔹 Filter: {where_filter}")

    collection = chroma_client.get_or_create_collection(name="acads_guide_doc")
    
    # 3️⃣ Query Chroma
    results = collection.query(
        query_embeddings=[query_embedding],  # OR query_texts=[query_text]
        n_results=n_results,
        where=where_filter,
        include=["documents", "distances", "metadatas"],
    )

    if not results["documents"] or not results["documents"][0]:
        print("❌ No matching documents found.")
        return ""

    # 4️⃣ Select best match
    best_idx = min(
        range(len(results["distances"][0])),
        key=lambda i: results["distances"][0][i],
    )
    best_doc = results["documents"][0][best_idx]
    best_meta = results["metadatas"][0][best_idx]
    best_dist = results["distances"][0][best_idx]

    # Clean text
    clean_doc = " ".join(best_doc.split())
    header_path = " > ".join(
        filter(
            None,
            [
                best_meta.get("Section", ""),
                best_meta.get("Subsection", ""),
                best_meta.get("Field", ""),
            ],
        )
    )

    return f"{clean_doc}\n"
