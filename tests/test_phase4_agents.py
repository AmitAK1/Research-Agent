"""Phase 4 Test — Individual Agent Functions"""
import sys
sys.path.insert(0, ".")

from src.agents import AgentState, planner_fn, research_fn, reflect_fn

test_state: AgentState = {
    "query": "What are the main causes of the 2008 financial crisis?",
    "past_context": "",
    "plan": "",
    "research_data": "",
    "draft": "",
    "feedback": "",
    "reflection_iterations": 0,
    "sources_used": [],
}

print("=== Test 1: Planner ===")
result = planner_fn(test_state)
assert "plan" in result, "ERROR: Planner didn't return 'plan'"
test_state.update(result)
print("✅ Planner works\n")

print("=== Test 2: Research ===")
result = research_fn(test_state)
assert "draft" in result, "ERROR: Researcher didn't return 'draft'"
test_state.update(result)
print(f"Draft length: {len(test_state['draft'])} chars")
print("✅ Researcher works\n")

print("=== Test 3: Reflection ===")
result = reflect_fn(test_state)
assert "feedback" in result, "ERROR: Reflector didn't return 'feedback'"
test_state.update(result)
print(f"Iterations: {test_state['reflection_iterations']}")
print("✅ Reflector works\n")

print(f"Sources used: {test_state['sources_used']}")
print("✅ Phase 4 COMPLETE")
