"""
Phase 0 — Configuration
Loads environment variables and validates they exist.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "research-agent")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# --- Validation ---
_missing = []
if not GROQ_API_KEY:
    _missing.append("GROQ_API_KEY")
if not PINECONE_API_KEY:
    _missing.append("PINECONE_API_KEY")
if not OPENROUTER_API_KEY:
    _missing.append("OPENROUTER_API_KEY")

if _missing:
    raise EnvironmentError(
        f"Missing required environment variables: {', '.join(_missing)}.\n"
        f"Create a .env file at: {_env_path}\n"
        f"With:\n  GROQ_API_KEY=gsk_...\n  PINECONE_API_KEY=pcsk_..."
    )

# Groq model — 8b-instant for high volume/stability, 32b/70b for reasoning
GROQ_MODEL = "llama-3.1-8b-instant"

# Embedding model for Pinecone
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384

# Agent config
MAX_REFLECTION_ITERATIONS = 3

if __name__ == "__main__":
    print(f"✅ Config loaded successfully!")
    print(f"   GROQ_API_KEY: {GROQ_API_KEY[:12]}...")
    print(f"   PINECONE_API_KEY: {PINECONE_API_KEY[:12]}...")
    print(f"   PINECONE_INDEX_NAME: {PINECONE_INDEX_NAME}")
    print(f"   GROQ_MODEL: {GROQ_MODEL}")
