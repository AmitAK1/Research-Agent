"""Phase 7 Test — Structured Output"""
import sys, json
sys.path.insert(0, ".")

from src.llm import llm
from src.schemas import ResearchOutput

print("=== Test: Structured Output via with_structured_output ===")

structured_llm = llm.with_structured_output(ResearchOutput)

response = structured_llm.invoke("""Convert this research into the required JSON format.

Original Query: What caused the 2008 financial crisis?

Research Answer:
The 2008 financial crisis was primarily caused by the housing market bubble fueled by subprime lending, 
lack of financial regulation, excessive risk-taking by banks, and the proliferation of complex mortgage-backed securities.
Key factors include the Community Reinvestment Act pressures, credit rating agency failures, and the collapse of Lehman Brothers.

Sources used: DuckDuckGo Search, LLM Knowledge

Fill in ALL fields accurately.""")

print(f"\nType: {type(response)}")
print(f"\nStructured Output:")
print(json.dumps(response.model_dump(), indent=2))

# Validate
assert response.query, "ERROR: Missing query"
assert response.summary, "ERROR: Missing summary"
assert len(response.key_findings) > 0, "ERROR: No key findings"
assert 0.0 <= response.confidence <= 1.0, "ERROR: Invalid confidence"

print("\n✅ Phase 7 COMPLETE — Structured output works!")
