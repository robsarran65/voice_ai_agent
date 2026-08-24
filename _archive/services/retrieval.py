# ============================================================
# Retrieval Pipeline (pgvector)
# Voice AI Agent (Low/No-Cost Edition)
# ============================================================

import json
from typing import List, Dict

from api.services.postgres_client import query
from api.services.litellm_router import run_llm


# ------------------------------------------------------------
# Embedding Generator (placeholder)
# Later: replace with LiteLLM embedding model
# ------------------------------------------------------------
def generate_embedding(text: str) -> List[float]:
    """
    Placeholder embedding generator.
    Replace with LiteLLM embeddings when ready.
    """
    # Temporary fake embedding (length 10)
    return [float(len(text))] * 10


# ------------------------------------------------------------
# Store Document in pgvector Table
# ------------------------------------------------------------
def store_document(doc_id: str, text: str, metadata: Dict = None):
    embedding = generate_embedding(text)
    metadata_json = json.dumps(metadata or {})

    sql = """
        INSERT INTO documents (doc_id, content, metadata, embedding)
        VALUES (%s, %s, %s, %s)
    """

    params = (doc_id, text, metadata_json, embedding)
    return query(sql, params)


# ------------------------------------------------------------
# Vector Similarity Search
# ------------------------------------------------------------
def retrieve_similar(user_text: str, top_k: int = 3) -> List[Dict]:
    """
    Perform pgvector similarity search.
    """
    embedding = generate_embedding(user_text)

    sql = """
        SELECT doc_id, content, metadata,
               embedding <-> %s AS distance
        FROM documents
        ORDER BY embedding <-> %s
        LIMIT %s
    """

    params = (embedding, embedding, top_k)
    results = query(sql, params)

    return results or []


# ------------------------------------------------------------
# Retrieval Wrapper for LangGraph
# ------------------------------------------------------------
def retrieve_context(user_text: str) -> str:
    """
    High-level retrieval function used by LangGraph.
    Returns a concatenated context string.
    """

    docs = retrieve_similar(user_text, top_k=3)

    if not docs:
        return "(no relevant documents found)"

    combined = "\n\n".join([doc["content"] for doc in docs])
    return combined
