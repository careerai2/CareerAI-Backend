from models.resume_model import *
import json
from ...handoff_tools import *
from config.chroma_config import chroma_client, embeddings

import jsonpatch

# def query_tech_handbook(
#     query_text: str,
#     role: list = ["tech"],
#     section: str = None,
#     subsection: str = None,
#     field: str = None,
#     n_results: int = 5,
#     debug: bool = True
# ) -> str:
#     """
#     Query the tech internship handbook stored in ChromaDB.

#     Parameters:
#     - query_text: User query.
#     - role: Filter by role (default "tech").
#     - section/subsection/field: Optional metadata filters.
#     - n_results: Number of top chunks to return.
#     - debug: Print debug info.

#     Returns:
#     - Formatted top N matching chunks with metadata and distance scores.
#     """

#     # 1️⃣ Embed query
#     query_embedding = embeddings.embed_query(query_text)

#     # 2️⃣ Build metadata filter
#     filters = []
#     if role:
#         filters.append({"role": {"$in": role}})
#     if section:
#         filters.append({"Section": {"$eq": section}})
#     if subsection:
#         filters.append({"Subsection": {"$eq": subsection}})
#     if field:
#         filters.append({"Field": {"$eq": field}})

#     if not filters:
#         where_filter = {}
#     elif len(filters) == 1:
#         where_filter = filters[0]
#     else:
#         where_filter = {"$and": filters}

#     if debug:
#         print(f"🔹 Query: {query_text}")
#         print(f"🔹 Filter: {where_filter}")
        
#     collection = chroma_client.get_or_create_collection(name="internship_knowledge")


#     # 3️⃣ Query Chroma
#     results = collection.query(
#         query_embeddings=[query_embedding],
#         n_results=n_results,
#         where=where_filter,
#         include=["documents", "distances", "metadatas"]
#     )

#     if not results["documents"] or not results["documents"][0]:
#         return "❌ No matching documents found."

#     # 4️⃣ Sort top chunks by distance
#     sorted_chunks = sorted(
#         zip(results["documents"][0], results["metadatas"][0], results["distances"][0]),
#         key=lambda x: x[2]
#     )

#     # 5️⃣ Format results
#     formatted_chunks = []
#     for doc, meta, dist in sorted_chunks[:n_results]:
#         clean_doc = " ".join(doc.split())
#         header_path = " > ".join(filter(None, [meta.get("Section", ""), meta.get("Subsection", ""), meta.get("Field", "")]))
#         formatted_chunks.append(f"### {header_path}\n{clean_doc}\n")

#     return "\n\n".join(formatted_chunks)



# new version with more filters
async def new_query_pdf_knowledge_base(
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
    results = await collection.query(
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
