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
from models.resume_model import WorkExperience
# from .state import InternshipState
from ..llm_model import SwarmResumeState,InternshipState,WorkexState

import jsonpatch



# to update any field in internship state like index,retrieved_info of internship agent
def update_workex_field(thread_id: str, field: Literal["index", "retrieved_info"], value):
    """
    Update any field in the internship state for a given thread_id in Redis (plain JSON string storage).
    
    Args:
        thread_id (str): The unique thread/session ID.
        field (str): The field name to update (e.g., 'index', 'retrieved_info').
        value: The new value to set.
    """
    key = f"state:{thread_id}:workex"

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
    Applies JSON patches to the entire internship section of the resume.
    Handles creation, replacement, or removal of work_experiences at any index.
    Syncs updated resume to Redis and frontend.
    """
    try:

        # Early exit if no patches
        if not patches:
            return {"status": "success", "message": "No patches to apply."}

        # Load current resume from Redis
        current_resume_raw = r.get(f"resume:{thread_id}")
        if not current_resume_raw:
            return {"status": "error", "message": "Resume not found in Redis."}

        try:
            current_resume = json.loads(current_resume_raw)
        except json.JSONDecodeError:
            return {"status": "error", "message": "Corrupted resume data in Redis."}

        # Ensure work_experiences section exists
        current_workex = current_resume.get("work_experiences", [])
        if not isinstance(current_workex, list):
            current_workex = []

        # ✅ Apply patches to entire work_experiences list
        try:
            jsonpatch.apply_patch(current_workex, patches, in_place=True)
            print(f"Applied patch list to work_experiences: {patches}")
        except jsonpatch.JsonPatchException as e:
            return {"status": "error", "message": f"Failed to apply patch list: {e}"}

        # Save updated work_experiences back to resume
        current_resume["work_experiences"] = current_workex

        # Save updated resume to Redis
        try:
            r.set(f"resume:{thread_id}", json.dumps(current_resume))
        except TypeError as e:
            return {"status": "error", "message": f"Failed to serialize updated resume: {e}"}

        # Identify user safely
        try:
            user_id = thread_id.split(":", 1)[0]
        except IndexError:
            user_id = thread_id

        # Notify frontend
        await send_patch_to_frontend(user_id, current_resume)

        # Push to undo stack for revert functionality
        undo_stack_key = f"undo_stack:{thread_id}"
        r.lpush(undo_stack_key, json.dumps({
            "section": "work_experiences",
            "patches": patches
        }))

        print(f"User {user_id}: Applied patches to internship section successfully.")

        return {"status": "success", "message": "Internships section updated successfully."}

    except ValidationError as ve:
        return {"status": "error", "message": f"Validation error: {ve.errors()}"}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}





# new version with more filters
def new_query_pdf_knowledge_base(
    query_text,
    role=["workex"],
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

    collection = chroma_client.get_or_create_collection(name="workex_guide_doc")
    
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
