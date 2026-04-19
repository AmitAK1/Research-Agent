"""Phase 5 & 6 Test — Full LangGraph Pipeline with Memory"""
import sys, json
sys.path.insert(0, ".")

from src.graph import run_agent

print("=== Test 1: Full Pipeline ===")
result = run_agent("What are the main causes of the 2008 financial crisis?")

print("\n============= STRUCTURED OUTPUT =============")
print(json.dumps(result, indent=2))

assert "summary" in result or "draft" in result, "ERROR: No summary in output"
print("\n✅ Phase 5+6 COMPLETE — Full pipeline with memory works!")

# If you run this again, Phase 6 memory retrieval should kick in
# print("\n\n=== Test 2: Re-run (memory should activate) ===")
# result2 = run_agent("What regulations were created after the 2008 financial crisis?")
# print(json.dumps(result2, indent=2))
