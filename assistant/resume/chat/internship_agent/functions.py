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
from models.resume_model import Internship
# from .state import InternshipState
from ..llm_model import SwarmResumeState,InternshipState

import jsonpatch



# to update any field in internship state like index,retrieved_info of internship agent
def update_internship_field(thread_id: str, field: Literal["index", "retrieved_info"], value):
    """
    Update any field in the internship state for a given thread_id in Redis (plain JSON string storage).
    
    Args:
        thread_id (str): The unique thread/session ID.
        field (str): The field name to update (e.g., 'index', 'retrieved_info').
        value: The new value to set.
    """
    key = f"state:{thread_id}:internship"

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
    
    



# # CAN BE MORE OPTIMIZED WILL DO LATER
# async def apply_patches(thread_id: str, patches: list[dict]):
#     """
#     Adds or updates an internship in the resume and syncs with Redis + frontend.
#     """
#     try:
#         internship_state_raw = r.get(f"state:{thread_id}:internship")
#         if internship_state_raw:
#             internship_state = json.loads(internship_state_raw)
#             print("Internship State from Redis:", internship_state)
#             index = int(internship_state.get("index")) if internship_state.get("index") is not None else None
#         else:
#             internship_state = {}
#             index = None


#         if not patches or len(patches) == 0:
#             print("No patches to apply, skipping save.")
#             return {"status": "success", "message": "No patches to apply."}

#         # Load resume from Redis
#         current_resume_raw = r.get(f"resume:{thread_id}")
#         if not current_resume_raw:
#             raise ValueError("Resume not found for the given thread_id.")
#         current_resume = json.loads(current_resume_raw)

#         # Get internships list
#         current_internships = current_resume.get("internships", [])

#         current_company_names = [internship.get("company_name", "").lower().strip() for internship in current_internships if internship.get("company_name")]

#         print("Current Company Names:",current_company_names)
        
#         is_company_name_patch = any(
#     patch.get("path") == "/company_name" and patch.get("op") in ("add","replace") and patch.get("value", "").lower().strip() not in current_company_names
#     for patch in patches
# )
#         if is_company_name_patch:
#             index = None  # Force adding a new internship

#         # Ensure index is integer if provided
#         if index is not None:
#             try:
#                 index = int(index)
#             except ValueError:
#                 print(f"Invalid index provided: {index}, will create new entry.")
#                 index = None

#         # Update existing or add new internship
#         if index is not None and 0 <= index < len(current_internships):
#             print(f"Updating internship at index {index}")
#             jsonpatch.apply_patch(current_internships[index], patches, in_place=True)
#         else:
#             print(f"Adding new internship (index={index})")
#             new_internship = Internship().model_dump()
#             jsonpatch.apply_patch(new_internship, patches, in_place=True)
#             current_internships.append(new_internship)
#             update_internship_field(thread_id, "index", len(current_internships) - 1)
#             index = len(current_internships) - 1

#         # Save back to Redis
#         current_resume["internships"] = current_internships
#         r.set(f"resume:{thread_id}", json.dumps(current_resume))

#         # Notify frontend
#         user_id = thread_id.split(":")[0]
#         print(f"User ID: {user_id}, Applied patches: {patches}")
#         await send_patch_to_frontend(user_id, current_resume)

#         return {"status": "success", "message": "Internship updated successfully.","index": index}

#     except ValidationError as ve:
#         return {"status": "error", "message": f"Validation error: {ve.errors()}"}
#     except Exception as e:
#         return {"status": "error", "message": str(e)}




async def apply_patches(thread_id: str, patches: list[dict]):
    """
    Adds or updates an internship in the resume and syncs with Redis + frontend.
    Robust version with edge case handling.
    """
    try:
        # Load internship state from Redis
        internship_state_raw = r.get(f"state:{thread_id}:internship")
        index = None
        if internship_state_raw:
            try:
                internship_state = json.loads(internship_state_raw)
                index = internship_state.get("index")
                if index is not None:
                    index = int(index)
            except json.JSONDecodeError:
                print("Corrupted internship state in Redis. Resetting.")
                internship_state = {}
                index = None
        else:
            internship_state = {}

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

        current_internships = current_resume.get("internships", [])
        current_company_names = [
            internship.get("company_name", "").lower().strip()
            for internship in current_internships if internship.get("company_name")
        ]

        # Check if any patch adds/replaces a new company name
        is_new_company_patch = any(
            patch.get("path") == "/company_name"
            and patch.get("op") in ("add", "replace")
            and patch.get("value", "").lower().strip() not in current_company_names
            for patch in patches
        )
        if is_new_company_patch:
            index = None  # Force adding a new internship

        # Apply patches
        if index is not None and 0 <= index < len(current_internships):
            try:
                jsonpatch.apply_patch(current_internships[index], patches, in_place=True)
                print(f"Updated internship at index {index}")
            except jsonpatch.JsonPatchException as e:
                return {"status": "error", "message": f"Failed to apply patch: {e}"}
        else:
            # Add new internship
            new_internship = Internship().model_dump()
            try:
                jsonpatch.apply_patch(new_internship, patches, in_place=True)
            except jsonpatch.JsonPatchException as e:
                return {"status": "error", "message": f"Failed to apply patch to new entry: {e}"}
            current_internships.append(new_internship)
            index = len(current_internships) - 1
            # Save new index to internship state
            update_internship_field(thread_id, "index", index)
            print(f"Added new internship at index {index}")

        # Save back to Redis
        current_resume["internships"] = current_internships
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
        
        # Maintain undo stack
        # undo_stack_key = f"undo_stack:{thread_id}"
        # r.lpush(undo_stack_key, json.dumps(patches))

        # # Clear redo stack on new action
        # redo_stack_key = f"redo_stack:{thread_id}"
        # r.delete(redo_stack_key)
        
        
        print(f"User ID: {user_id}, patches applied: {patches}")

        return {"status": "success", "message": "Internship updated successfully.", "index": index}

    except ValidationError as ve:
        return {"status": "error", "message": f"Validation error: {ve.errors()}"}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}



# For retriever
def query_pdf_knowledge_base(query_text, role=["internship"], n_results=5, similarity_threshold= 1, debug=True):
    """
    Query stored PDF chunks in Chroma with strict filtering for high specificity.
    """
    # 1️⃣ Embed the query
    query_embedding = embeddings.embed_query(query_text)
    if debug:
        print(f"🔹 Query Text: {query_text}")
        print(f"🔹 Query Embedding Length: {len(query_embedding)}")
        
    collection = chroma_client.get_or_create_collection(name="internship_guide")

    # 2️⃣ Build filter
    where_filter = {"role": {"$in": role}} if role else {}

    # 3️⃣ Query Chroma
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where=where_filter,
        include=["documents", "distances", "metadatas"],
    )

    if debug:
        print(f"🔹 Total chunks retrieved: {len(results['documents'][0])}")

    # 4️⃣ Filter by similarity
    retrieved_texts = []
    for doc, dist, meta in zip(results["documents"][0], results["distances"][0], results["metadatas"][0]):
        clean_doc = " ".join(doc.split())  # collapse spaces
        # if debug:
        #     print(f"Distance={dist:.3f} | Role={meta.get('role')} | Text Snippet={clean_doc[:80]}...")
        #     # continue
        if dist < similarity_threshold:
            retrieved_texts.append({"text": clean_doc, "distance": dist, "metadata": meta})
        elif debug:
            print(f"❌ Chunk excluded due to threshold (distance={dist:.3f})")

    # 5️⃣ Sort and limit
    retrieved_texts = sorted(retrieved_texts, key=lambda x: x["distance"])
    retrieved_texts = retrieved_texts[:n_results]

    if not retrieved_texts:
        if debug:
            print("⚠️ No relevant chunks passed the similarity threshold.")
        return "No relevant information found."

    return "\n\n".join([d['text'] for d in retrieved_texts])



# new version with more filters
def new_query_pdf_knowledge_base(
    query_text,
    role=["internship"],
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

    collection = chroma_client.get_or_create_collection(name="internship_guide_doc")
    
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
