from config.chroma_config import chroma_client, embeddings
from logging import Logger



# new version with more filters
def new_query_pdf_knowledge_base(
    query_text,
    logger: Logger ,
    role=["por"],
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
        logger.debug(f"🔹 Query: {query_text}")
        logger.debug(f"🔹 Filter: {where_filter}")

    collection = chroma_client.get_or_create_collection(name="por_guide_doc")
    
    # 3️⃣ Query Chroma
    results = collection.query(
        query_embeddings=[query_embedding],  # OR query_texts=[query_text]
        n_results=n_results,
        where=where_filter,
        include=["documents", "distances", "metadatas"],
    )

    if not results["documents"] or not results["documents"][0]:
        logger.warning("❌ No matching documents found.")
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
