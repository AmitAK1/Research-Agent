"""
Phase 5 & 6 — LangGraph Workflow with Memory Integration
Orchestrates: Memory Retrieval → Planner → Research → Reflection (loop) → Memory Store → Format Output
"""
import time
import json
from typing import List
from langgraph.graph import StateGraph, START, END

from src.agents import AgentState, planner_fn, research_fn, reflect_fn
from src.memory import retrieve_memory, store_memory, format_memory_context
from src.schemas import ResearchOutput
from src.llm import llm
from src.config import MAX_REFLECTION_ITERATIONS


# --- Graph Node: Retrieve Memory ---
def retrieve_memory_node(state: AgentState) -> dict:
    """Fetch relevant past research from Pinecone before processing."""
    print(f"\n{'='*60}")
    print(f"📚 MEMORY RETRIEVAL — {time.strftime('%H:%M:%S')}")
    print(f"{'='*60}")

    memories = retrieve_memory(state["query"], k=3)
    context = format_memory_context(memories)

    if context:
        print(f"  Found {len(memories)} relevant past queries.")
    else:
        print("  No relevant past research found.")

    return {"past_context": context}


# --- Graph Node: Store Memory ---
def store_memory_node(state: AgentState) -> dict:
    """Store the query and final answer in Pinecone for future use."""
    print(f"\n{'='*60}")
    print(f"💾 MEMORY STORE — {time.strftime('%H:%M:%S')}")
    print(f"{'='*60}")

    store_memory(state["query"], state["draft"])
    print("  Query + answer stored in Pinecone.")
    return {}


# --- Graph Node: Format Output ---
def format_output_node(state: AgentState) -> dict:
    """Convert the draft into structured Pydantic output."""
    print(f"\n{'='*60}")
    print(f"📋 FORMAT OUTPUT — {time.strftime('%H:%M:%S')}")
    print(f"{'='*60}")

    from src.llm import safe_invoke
    import json

    sources = list(state.get("sources_used", []))
    sources_str = ", ".join(sources) if sources else "LLM Knowledge"

    calc_steps = state.get("calculation_steps", "")
    
    prompt = f"""Convert this research into the required JSON format.

Original Query: {state['query']}

Research Answer:
{state['draft']}

Calculation Steps (include verbatim in calculation_steps field):
{calc_steps if calc_steps else "No calculations performed."}

Sources used: {sources_str}

Output ONLY valid JSON matching this schema exactly:
{{
  "query": "string",
  "summary": "string (Concise 2-3 sentence summary)",
  "key_findings": ["string", "string"],
  "calculation_steps": "string (Exact calculations from the data above)",
  "sources": ["string"],
  "confidence": 0.0 to 1.0,
  "needs_further_research": true or false
}}"""

    try:
        response = safe_invoke(prompt)
        content = response.content.strip()
        
        # Robustly extract JSON block in case LLM added conversational text
        start_idx = content.find('{')
        end_idx = content.rfind('}')
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            content = content[start_idx:end_idx+1]
        
        # Verify it parses before returning
        parsed_json = json.loads(content)
        
        print(f"  ✅ Structured output generated.")
        return {"draft": json.dumps(parsed_json, indent=2)}
    except Exception as e:
        print(f"  ⚠️ Structured output failed ({e}), returning raw draft.")
        # Fallback: place the entire draft in the summary so it displays correctly in UI
        fallback = ResearchOutput(
            query=state["query"],
            summary=state["draft"],
            key_findings=["(Structured output failed, showing full markdown above)"],
            calculation_steps=state.get("calculation_steps", ""),
            sources=sources,
            confidence=0.5,
            needs_further_research=True,
        )
        return {"draft": fallback.model_dump_json(indent=2)}


# --- Conditional Edge: Should Continue Reflecting? ---
def should_continue(state: AgentState) -> str:
    """Decide whether to loop back to research or finish."""
    if "PASS" in state.get("feedback", ""):
        print("  → Routing to: STORE MEMORY (answer passed)")
        return "store_memory"
    if state.get("reflection_iterations", 0) >= MAX_REFLECTION_ITERATIONS:
        print(f"  → Routing to: STORE MEMORY (max iterations reached)")
        return "store_memory"
    print("  → Routing to: RESEARCH (needs improvement)")
    return "research"


def validate_output_node(state: AgentState) -> dict:
    """Validation gate: ensure calculations exist AND are mathematically valid."""
    print(f"\n{'='*60}")
    print(f"✅ VALIDATOR — {time.strftime('%H:%M:%S')}")
    print(f"{'='*60}")
    
    query_lower = state["query"].lower()
    calc_keywords = ["calculate", "cagr", "growth rate", "percentage", "compute", "estimate", "how much", "how many", "forecast", "predict"]
    needs_math = any(kw in query_lower for kw in calc_keywords)
    
    calc_steps = state.get("calculation_steps", "")
    has_calculations = bool(calc_steps and len(calc_steps) > 20)
    
    # --- Check 1: Calculations must exist ---
    if needs_math and not has_calculations:
        print("  ⚠️ VALIDATION FAILED: Query requires calculations but none found.")
        return {
            "feedback": "FAIL\n\nMISSING_CALCULATIONS:\n- This query explicitly requires numerical calculations but NONE were performed.\n\nFIX_INSTRUCTIONS:\n- Search for the specific numerical data needed\n- Run Python with the actual formula and numbers to produce verifiable results."
        }
    
    # --- Check 2: Calculations must be VALID (not just present) ---
    if needs_math and has_calculations:
        if calc_steps.startswith("CALCULATION_FAILED"):
            print("  ⚠️ VALIDATION FAILED: Calculation was invalid (caught by researcher).")
            return {
                "feedback": "FAIL\n\nMISSING_DATA:\n- The Python calculation failed because required numerical data was missing or invalid (e.g., initial value = 0).\n\nFIX_INSTRUCTIONS:\n- Search for specific numerical data points with exact years and values\n- Ensure all initial/start values are > 0 before computing growth rates"
            }
        
        # Additional content-level checks
        calc_lower = calc_steps.lower()
        invalid_signals = [
            ("initial = 0", "initial value is zero"),
            ("start_value = 0", "start value is zero"),
            ("= 0\n", "a value is zero that shouldn't be"),
            ("cannot calculate", "calculation could not be completed"),
            ("error:", "calculation error occurred"),
        ]
        for pattern, reason in invalid_signals:
            if pattern in calc_lower:
                # Skip false positives
                if pattern == "= 0\n" and "= 0." in calc_lower:
                    continue  # "= 0.5" is valid
                print(f"  ⚠️ VALIDATION FAILED: {reason}")
                return {
                    "feedback": f"FAIL\n\nMISSING_DATA:\n- Calculation contains invalid data: {reason}\n\nFIX_INSTRUCTIONS:\n- Search for the correct numerical values with specific years\n- Re-run calculation with valid, non-zero initial values"
                }
        
        print(f"  ✅ Calculations present AND valid ({len(calc_steps)} chars)")
    else:
        print("  ✅ No calculations required for this query")
    
    return {}


# --- Build the Graph ---
def build_graph() -> StateGraph:
    """Construct and compile the LangGraph workflow."""
    builder = StateGraph(AgentState)

    # Add nodes
    builder.add_node("retrieve_memory", retrieve_memory_node)
    builder.add_node("planner", planner_fn)
    builder.add_node("research", research_fn)
    builder.add_node("reflect", reflect_fn)
    builder.add_node("validate", validate_output_node)
    builder.add_node("store_memory", store_memory_node)
    builder.add_node("format_output", format_output_node)

    # Define edges: START → retrieve_memory → planner → research → reflect → [conditional]
    builder.add_edge(START, "retrieve_memory")
    builder.add_edge("retrieve_memory", "planner")
    builder.add_edge("planner", "research")
    builder.add_edge("research", "reflect")

    # Conditional: either loop back to research or proceed to validate + store + format
    builder.add_conditional_edges("reflect", should_continue, {
        "research": "research",
        "store_memory": "validate",
    })
    
    # Validation gate before storing
    builder.add_conditional_edges("validate", should_continue, {
        "research": "research",
        "store_memory": "store_memory",
    })
    builder.add_edge("store_memory", "format_output")
    builder.add_edge("format_output", END)

    return builder.compile()


# Compile the graph
agent_graph = build_graph()


def run_agent(query: str, max_iterations: int = 2) -> dict:
    """
    Main entry point: run the full research agent pipeline.
    Returns parsed JSON result.
    """
    print(f"\n{'#'*60}")
    print(f"# RESEARCH AGENT — Query: '{query[:50]}...'")
    print(f"# Max iterations: {max_iterations}")
    print(f"{'#'*60}")

    start_time = time.time()

    initial_state: AgentState = {
        "query": query,
        "past_context": "",
        "plan": "",
        "research_data": "",
        "calculation_steps": "",
        "draft": "",
        "feedback": "",
        "reflection_iterations": 0,
        "sources_used": [],
    }

    final_state = agent_graph.invoke(initial_state)

    elapsed = time.time() - start_time
    print(f"\n{'#'*60}")
    print(f"# COMPLETED in {elapsed:.2f}s")
    print(f"{'#'*60}")

    # Parse the structured JSON from draft
    try:
        result = json.loads(final_state["draft"])
    except (json.JSONDecodeError, TypeError):
        result = {"query": query, "summary": final_state["draft"], "raw": True}

    return result


if __name__ == "__main__":
    result = run_agent("What are the main causes of the 2008 financial crisis?")
    print("\n\n============= FINAL STRUCTURED OUTPUT =============")
    print(json.dumps(result, indent=2))
