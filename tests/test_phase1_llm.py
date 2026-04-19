"""Phase 1 Test — LLM Sanity Check"""
import sys, time
sys.path.insert(0, ".")

from src.llm import llm
from src.config import GROQ_MODEL

print(f"Testing LLM: {GROQ_MODEL}")
print("-" * 40)

start = time.time()
response = llm.invoke("Explain AI in 2 lines.")
elapsed = time.time() - start

print(f"Response ({elapsed:.2f}s):")
print(response.content)
print("-" * 40)

if elapsed < 5:
    print(f"✅ PASS — Response received in {elapsed:.2f}s (under 5s)")
else:
    print(f"⚠️ SLOW — Response took {elapsed:.2f}s. Consider switching to llama-3.1-8b-instant")

assert response.content, "ERROR: Empty response from LLM"
print("✅ Phase 1 COMPLETE")
