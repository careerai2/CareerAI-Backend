from models.resume_model import *
# from ...handoff_tools import *
from config.chroma_config import chroma_client, embeddings

from config.log_config import get_logger

logger = get_logger("query_vector_db")

# new version with more filters
# chroma cloud not support async yet, so keep it sync for now
def new_query_pdf_knowledge_base(
    query_text: str,
    collection_name: str,
    role: list[str] = None,
    section: str = None,
    subsection: str = None,
    field: str = None,
    n_results: int = 10,
    debug: bool = True,
):
    """
    Query stored PDF chunks in Chroma and return the closest match.
    Supports filtering by role, Section, Subsection, and Field metadata.
    """

    # Default role handling
    if role is None:
        role = []

    # 1️⃣ Embed query
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
        filters.append({"Field": {"$eq": field}})

    if not filters:
        where_filter = {}
    elif len(filters) == 1:
        where_filter = filters[0]
    else:
        where_filter = {"$and": filters}

    if debug:
        logger.debug(f"🔹 Query: {query_text}")
        logger.debug(f"🔹 Filter: {where_filter}")

    # 3️⃣ Load collection
    collection = chroma_client.get_or_create_collection(name=collection_name)

    # Query Chroma
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where=where_filter,
        include=["documents", "distances", "metadatas"],
    )

    if not results["documents"] or not results["documents"][0]:
        logger.warn("❌ No matching documents found.")
        return ""

    # 4️⃣ Select best match
    best_idx = min(
        range(len(results["distances"][0])),
        key=lambda i: results["distances"][0][i],
    )

    best_doc = results["documents"][0][best_idx]
    best_meta = results["metadatas"][0][best_idx]

    # Clean text
    clean_doc = " ".join(best_doc.split())

    return f"{clean_doc}\n"
