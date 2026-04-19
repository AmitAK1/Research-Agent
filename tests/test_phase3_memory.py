"""Phase 3 Test — Pinecone Memory"""
import sys, time
sys.path.insert(0, ".")

from src.memory import store_memory, retrieve_memory, format_memory_context

print("=== Test 1: Store Memory ===")
store_memory(
    "What were the early warning signs of the 2008 financial crisis?",
    "Rising subprime defaults, declining home prices, increasing foreclosures from 2006."
)
store_memory(
    "How did the housing market collapse affect Europe?",
    "European banks held US mortgage-backed securities, leading to bank bailouts and austerity."
)
print("✅ Memory stored\n")

# Pinecone needs a moment to index
print("Waiting 3s for Pinecone to index...")
time.sleep(3)

print("\n=== Test 2: Retrieve Memory ===")
results = retrieve_memory("Tell me about the 2008 financial crisis regulations")
print(f"Found {len(results)} similar results:")
for r in results:
    print(f"  Score={r['score']} | Query: {r['query'][:80]}")

print("\n=== Test 3: Formatted Context ===")
context = format_memory_context(results)
print(context if context else "(empty — no results above threshold)")

if results:
    print("\n✅ Phase 3 COMPLETE — Memory working!")
else:
    print("\n⚠️ No results retrieved. This could be timing — try running again after a few seconds.")
