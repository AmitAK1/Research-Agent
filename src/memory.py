"""
Phase 3 — Pinecone Vector Memory
Persistent storage & retrieval of past research queries/responses.
"""
import uuid
import time
import numpy as np
from typing import List, Dict
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone, ServerlessSpec

from src.config import (
    PINECONE_API_KEY,
    PINECONE_INDEX_NAME,
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSION,
)

# --- Initialize Embedding Model ---
print(f"Loading embedding model '{EMBEDDING_MODEL}'...")
embedding_model = SentenceTransformer(EMBEDDING_MODEL)

# --- Initialize Pinecone ---
pc = Pinecone(api_key=PINECONE_API_KEY)


def ensure_index_exists():
    """Create the Pinecone index if it does not exist, then wait until ready."""
    existing = [idx.name for idx in pc.list_indexes()]
    if PINECONE_INDEX_NAME not in existing:
        print(f"Creating Pinecone index '{PINECONE_INDEX_NAME}'...")
        pc.create_index(
            name=PINECONE_INDEX_NAME,
            dimension=EMBEDDING_DIMENSION,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        # Wait for index to be ready
        while not pc.describe_index(PINECONE_INDEX_NAME).status.get("ready"):
            print("  Waiting for index to be ready...")
            time.sleep(2)
        print(f"✅ Index '{PINECONE_INDEX_NAME}' created and ready.")
    else:
        print(f"✅ Index '{PINECONE_INDEX_NAME}' already exists.")


# Make sure index exists on import
ensure_index_exists()
index = pc.Index(PINECONE_INDEX_NAME)


def _embed(text: str) -> List[float]:
    """Generate embedding for a single text string."""
    return embedding_model.encode(text).tolist()


def store_memory(query: str, response: str) -> str:
    """Store a query-response pair in Pinecone. Returns the vector ID."""
    vec_id = str(uuid.uuid4())
    embedding = _embed(query)
    metadata = {
        "query": query[:500],       # Pinecone metadata limit
        "response": response[:1000],  # Keep it concise
    }
    index.upsert(vectors=[{"id": vec_id, "values": embedding, "metadata": metadata}])
    print(f"💾 Stored in memory (id={vec_id[:8]}...): '{query[:60]}...'")
    return vec_id


def retrieve_memory(query: str, k: int = 3) -> List[Dict]:
    """
    Retrieve similar past query-response pairs from Pinecone.
    Returns list of dicts with keys: query, response, score.
    """
    embedding = _embed(query)
    try:
        results = index.query(vector=embedding, top_k=k, include_metadata=True)
    except Exception as e:
        print(f"⚠️ Pinecone query failed: {e}")
        return []

    memories = []
    for match in results.get("matches", []):
        score = match.get("score", 0)
        meta = match.get("metadata", {})
        if score > 0.5:  # Only return reasonably similar results
            memories.append({
                "query": meta.get("query", ""),
                "response": meta.get("response", ""),
                "score": round(score, 4),
            })
    return memories


def format_memory_context(memories: List[Dict]) -> str:
    """Format retrieved memories into a string for injection into prompts."""
    if not memories:
        return ""
    lines = ["=== Relevant Past Research ==="]
    for i, m in enumerate(memories, 1):
        lines.append(f"\n[{i}] Previous Query: {m['query']}")
        lines.append(f"    Previous Answer: {m['response'][:300]}...")
        lines.append(f"    Relevance: {m['score']}")
    lines.append("=== End Past Research ===\n")
    return "\n".join(lines)


if __name__ == "__main__":
    print("\n--- Testing Memory Store ---")
    store_memory(
        "What were the early warning signs of the 2008 financial crisis?",
        "Early signs included rising subprime mortgage defaults, declining home prices, and increasing foreclosure rates starting in 2006."
    )
    store_memory(
        "How did the housing market collapse affect Europe?",
        "European banks held significant US mortgage-backed securities. The crisis led to bank bailouts, austerity measures, and the European sovereign debt crisis."
    )

    # Small delay to let Pinecone index
    time.sleep(2)

    print("\n--- Testing Memory Retrieval ---")
    results = retrieve_memory("Tell me about the 2008 financial crisis regulations")
    for r in results:
        print(f"  Score={r['score']} | Query: {r['query'][:80]}")

    print("\n--- Formatted Context ---")
    print(format_memory_context(results))
