"""
Phase 1 — LLM Initialization
Provides the Groq-backed LLM instance used across the project.
Includes retry + fallback logic for rate limits.
"""
import time as _time
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage
from src.config import GROQ_API_KEY, GROQ_MODEL, OPENROUTER_API_KEY

llm = ChatGroq(
    model=GROQ_MODEL,
    api_key=GROQ_API_KEY,
    temperature=0,
    max_retries=2,
)

# Fallback model hosted on OpenRouter
_fallback_llm = ChatOpenAI(
    model="openrouter/elephant-alpha",
    openai_api_key=OPENROUTER_API_KEY,
    openai_api_base="https://openrouter.ai/api/v1",
    temperature=0,
    max_retries=2,
)


def safe_invoke(prompt, use_llm=None):
    """
    Invoke LLM with automatic retry + fallback to OpenRouter.
    Returns the response object (same as llm.invoke).
    """
    target = use_llm or llm
    try:
        return target.invoke(prompt)
    except Exception as e:
        err_str = str(e).lower()
        if "rate_limit" in err_str or "429" in err_str or "too many" in err_str:
            print(f"  ⏳ Rate limited — waiting 3s then retrying...")
            _time.sleep(3)
            try:
                return target.invoke(prompt)
            except Exception:
                print(f"  ⚠️ Groq retries exhausted — falling back to OpenRouter...")
                try:
                    return _fallback_llm.invoke(prompt)
                except Exception as fallback_e:
                    print(f"  🚨 Fallback also failed: {fallback_e}")
                    return AIMessage(content="[SYSTEM OVERLOAD] Exact response cannot be generated due to system capacity limits.")
        raise  # Re-raise non-rate-limit errors


if __name__ == "__main__":
    print(f"Testing LLM ({GROQ_MODEL})...")
    start = _time.time()
    response = llm.invoke("Explain AI in 2 lines.")
    elapsed = _time.time() - start
    print(f"Response ({elapsed:.2f}s):\n{response.content}")

