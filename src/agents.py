"""
Phase 4 — Agent Functions
Planner, Research, and Reflection agents as pure functions.
Each takes AgentState and returns a partial state update.
"""
import time
from typing import TypedDict, List, Dict, Optional
from src.llm import llm, safe_invoke
from src.tools import search_web, run_python
from src.memory import retrieve_memory, format_memory_context


class AgentState(TypedDict):
    query: str
    past_context: str            # Retrieved memory context
    plan: str                    # Planner output
    research_data: str           # Raw search results
    calculation_steps: str       # Python code + output (transparent math)
    draft: str                   # Current answer draft
    feedback: str                # Reflection feedback
    reflection_iterations: int   # Counter for reflection loops
    sources_used: List[str]      # Track which tools were used


def planner_fn(state: AgentState) -> dict:
    """
    Planner Agent — Breaks the query into research steps.
    Considers past context if available.
    """
    print(f"\n{'='*60}")
    print(f"🧠 PLANNER — {time.strftime('%H:%M:%S')}")
    print(f"{'='*60}")

    past = state.get("past_context", "")
    past_section = f"\n\nRelevant past research that may help:\n{past}" if past else ""

    prompt = f"""You are a research planner. Create a clear, numbered step-by-step plan to answer this query.
        
Query: '{state['query']}'
{past_section}

Rules:
- Output ONLY the numbered steps (3-5 steps max)
- Each step MUST end with a tool tag: [TOOL: SEARCH], [TOOL: PYTHON], or [TOOL: LLM]
- Use [TOOL: SEARCH] for steps needing current data, statistics, or real-world facts
- Use [TOOL: PYTHON] for steps needing calculations, formulas, or data processing
- Use [TOOL: LLM] for steps needing analysis, synthesis, or explanation
- If past research is relevant, note which steps can build on it

Example:
1. Find India's EV sales data for 2020 and 2025 from market reports [TOOL: SEARCH]
2. Calculate CAGR using the formula ((Final/Initial)^(1/n))-1 [TOOL: PYTHON]
3. Analyze growth drivers and barriers based on the data [TOOL: LLM]
"""
    response = safe_invoke(prompt)
    plan = response.content
    print(f"Plan:\n{plan}")
    return {"plan": plan, "reflection_iterations": 0, "sources_used": []}


def _validate_calculation(calc_output: str) -> tuple[bool, str]:
    """
    Check Python calculation output for mathematical errors.
    Returns (is_valid, error_description).
    """
    invalid_patterns = {
        "= 0\n": "Initial value is zero — CAGR undefined",
        "= 0 ": "Initial value is zero — CAGR undefined",
        "initial = 0": "Initial value is zero — CAGR undefined",
        "start_value = 0": "Start value is zero — division by zero",
        "calculation_failed:": "Calculation explicitly failed due to missing data",
        "cannot calculate": "Calculation explicitly failed",
        "division by zero": "Division by zero error",
        "zerodivisionerror": "Division by zero exception",
        "nameerror": "Variable not defined (likely missing data)",
        "typeerror": "Type mismatch in calculation",
        "syntaxerror": "Python syntax error",
        "valueerror": "Invalid value for math operation",
        "inf": "Result is infinity — invalid math",
        "nan": "Result is NaN — invalid math",
        "error": "Python execution error",
    }
    calc_lower = calc_output.lower()
    for pattern, reason in invalid_patterns.items():
        if pattern in calc_lower:
            # Extra check: "inf" can appear in "information" — only flag standalone
            if pattern == "inf" and "information" in calc_lower:
                continue
            if pattern == "error" and "--- error ---" not in calc_lower:
                continue
            return False, reason
    return True, ""


def research_fn(state: AgentState) -> dict:
    """
    Research Agent — Executes search, extracts data, computes, and drafts.
    Enforces: data extraction before math, math validation, and feedback-driven re-search.
    """
    print(f"\n{'='*60}")
    print(f"🔍 RESEARCHER — {time.strftime('%H:%M:%S')}")
    print(f"{'='*60}")

    query = state["query"]
    sources = list(state.get("sources_used", []))
    calculation_steps = state.get("calculation_steps", "")

    # --- Decide tools from planner's tags ---
    plan = state.get("plan", "")
    needs_search = "[TOOL: SEARCH]" in plan.upper()
    needs_calc = "[TOOL: PYTHON]" in plan.upper()

    # Fallback: if planner didn't tag tools, ask the LLM
    if not needs_search and not needs_calc and "[TOOL:" not in plan.upper():
        decision_prompt = f"""Analyze this query: '{query}'
Does this query explicitly require mathematical calculations, formulas, statistics computation, or quantitative data processing?
Answer ONLY with one of: SEARCH_ONLY, CALC_ONLY, BOTH, NEITHER.
Note: Choose 'SEARCH_ONLY' unless explicit math/computations are needed. General questions (like "how to improve yourself") are SEARCH_ONLY or NEITHER."""
        decision = safe_invoke(decision_prompt).content.strip().upper()
        needs_search = "SEARCH" in decision or "BOTH" in decision
        needs_calc = "CALC" in decision or "BOTH" in decision

    print(f"  Needs web search: {needs_search}")
    print(f"  Needs calculation: {needs_calc}")

    # --- Check if feedback has FIX_INSTRUCTIONS with specific searches ---
    feedback = state.get("feedback", "")
    research_data = ""

    if feedback and "FIX_INSTRUCTIONS" in feedback:
        print("  📌 Executing FIX_INSTRUCTIONS from reflection...")
        # Extract search queries from feedback
        fix_prompt = f"""From the feedback below, extract ONLY the specific search queries mentioned in FIX_INSTRUCTIONS.
Output each search query on its own line, nothing else.

Feedback:
{feedback}"""
        fix_searches = safe_invoke(fix_prompt).content.strip().split("\n")
        for sq in fix_searches:
            sq = sq.strip().strip('"').strip("'").strip("- ")
            if sq and len(sq) > 5 and not sq.upper().startswith("RUN PYTHON"):
                print(f"    → Targeted search: '{sq[:60]}...'")
                result = search_web(sq)
                research_data += f"Targeted Search ({sq[:40]}):\n{result}\n\n"
                if "DuckDuckGo Search" not in sources:
                    sources.append("DuckDuckGo Search")

    # --- Step 1: Web Search (with smart query generation) ---
    if needs_search:
        # Generate a targeted search query with geography + source hints
        search_query_prompt = f"""Generate a highly specific web search query to find data for: '{query}'

Rules:
- Include the country/region if mentioned in the query
- Include specific data source names (e.g., SMEV, Vahan, IEA, Bloomberg, Mordor Intelligence)
- Include years and units (e.g., 'units sold', 'market size USD billion')
- Output ONLY the search query string, nothing else

Example: For 'India EV market growth 2020-2025'
Output: India electric vehicle EV sales market size 2020 2021 2022 2023 2024 2025 SMEV Vahan units billion USD data"""
        smart_query = safe_invoke(search_query_prompt).content.strip().strip('"')
        print(f"  Searching DuckDuckGo: '{smart_query[:60]}...'")
        search_result = search_web(smart_query)
        research_data += f"Web Search Results:\n{search_result}\n\n"
        # Also search with original query for breadth
        if smart_query.lower() != query.lower():
            search_result2 = search_web(query)
            research_data += f"Web Search Results (original query):\n{search_result2}\n\n"
        if "DuckDuckGo Search" not in sources:
            sources.append("DuckDuckGo Search")

    # --- Step 2: Python Calculation (combines extraction and math) ---
    calculation_steps = ""
    if needs_calc:
        print("  Running Python calculation...")
        data_for_calc = research_data if research_data else "No data available."
        code_prompt = f"""Write a Python script to calculate/answer: '{query}'

RAW RESEARCH DATA (extract values directly from this text):
{data_for_calc}

STRICT RULES (Read carefully):
1. Extract the exact numerical values needed for the calculation from the RAW RESEARCH DATA above using python.
2. If the user query does not explicitly require math, trend calculation, or data extraction, just print "No calculation needed for qualitative queries." and call sys.exit(0).
3. If calculation is strictly impossible due to missing numbers, print exactly "CALCULATION_FAILED: Insufficient data to calculate" and call sys.exit(0).
4. Do NOT crash on zero values if calculating percentage differences/growth, handle gracefully or estimate.
5. Always print EVERY intermediate step and the final result clearly labeled.

Output ONLY Python code, no markdown fences, no explanation outside of code comments. Ensure 'import sys' is included if using sys.exit(0)."""
        code = safe_invoke(code_prompt).content.strip()
        code = code.replace("```python", "").replace("```", "").strip()
        calc_result = run_python(code)

        # --- VALIDATE the calculation output ---
        is_valid, error_reason = _validate_calculation(calc_result)
        if is_valid:
            print(f"  ✅ Calculation valid")
            calculation_steps = calc_result
        else:
            print(f"  ❌ INVALID CALCULATION: {error_reason}")
            print(f"  → Marking calculation as failed, will not use in draft")
            calculation_steps = f"CALCULATION_FAILED: {error_reason}\n\n{calc_result}"

        research_data += f"Calculation Steps:\n{calc_result}\n\n"
        if "Python REPL" not in sources:
            sources.append("Python REPL")

    if not needs_search and not needs_calc:
        print("  Answering from LLM knowledge directly.")
        if "LLM Knowledge" not in sources:
            sources.append("LLM Knowledge")

    # --- Build the draft ---
    feedback_section = f"\n\nPrevious feedback to address:\n{feedback}" if feedback else ""
    past = state.get("past_context", "")
    past_section = f"\n\nRelevant past research:\n{past}" if past else ""

    # Only inject calculation steps if they are VALID
    calc_failed = calculation_steps.startswith("CALCULATION_FAILED")
    if calculation_steps and not calc_failed:
        calc_section = f"\n\nCalculation steps (MUST be included verbatim in your answer):\n{calculation_steps}"
    elif calc_failed:
        calc_section = f"\n\nCALCULATION NOTE: The primary calculation failed ({calculation_steps}). If exact calculation is impossible due to fundamentally missing baseline data, state: 'Exact metric cannot be computed due to lack of base data.' Then, provide the closest possible trend analysis based on the available data."
    else:
        calc_section = ""

    draft_prompt = f"""Write a comprehensive, well-structured answer to the query below.

Query: '{query}'

Research Plan: {state.get('plan', 'N/A')}

Research Data: {research_data if research_data else 'No external data gathered — use your knowledge.'}
{past_section}
{feedback_section}
{calc_section}

Rules:
- Be thorough but concise
- Use bullet points for key facts
- Cite sources when available
- If previous feedback was given, specifically address those gaps
- If calculation steps are provided and VALID, you MUST include the exact formula, inputs, and results — do NOT summarize or round differently
- If exact data is missing for some years, provide a PARTIAL answer using available data and clearly state: "Note: This estimate covers [available range] due to data availability"
- ALWAYS provide the best possible answer — never return an empty or purely apologetic response
- If you had to estimate, clearly label it: "Estimated based on [source/method]"
"""
    response = safe_invoke(draft_prompt)
    draft = response.content
    print(f"  Draft generated ({len(draft)} chars)")
    return {"research_data": research_data, "draft": draft, "sources_used": sources, "calculation_steps": calculation_steps}


def reflect_fn(state: AgentState) -> dict:
    """
    Reflection Agent — Evaluates the draft for completeness and accuracy.
    Either passes (answer is good) or provides specific improvement suggestions.
    """
    print(f"\n{'='*60}")
    print(f"🪞 REFLECTOR — Iteration {state.get('reflection_iterations', 0) + 1} — {time.strftime('%H:%M:%S')}")
    print(f"{'='*60}")

    prompt = f"""You are a critical research reviewer. Evaluate this answer for the given query.

Query: '{state['query']}'

Research data available:
{state.get('research_data', 'None')}

Answer to review:
{state['draft']}

Evaluation criteria:
1. Numerical accuracy — Are all numbers backed by data or calculations? Is every formula shown with inputs and outputs?
2. Completeness — Does it fully answer every part of the query?
3. Verifiability — Are sources specific (not just "IEA" but which report/year)?
4. Calculation transparency — If math was done, are formula + inputs + result all visible?

If the answer is excellent on ALL criteria, respond with exactly: PASS

If it needs improvement, respond with:
FAIL

MISSING_DATA:
- [exact data point needed, e.g., "India EV sales volume for 2020"]

MISSING_CALCULATIONS:
- [exact calculation needed, e.g., "CAGR formula with actual numbers plugged in"]

MISSING_SOURCES:
- [what source would fix this, e.g., "SMEV or Vahan dashboard data for 2023"]

FIX_INSTRUCTIONS:
- [specific action: "Search for 'India EV sales 2020 2021 2022 2023 2024 2025 Vahan'"]
- [specific action: "Run Python: CAGR = ((final/initial)**(1/5))-1 with the actual sales numbers"]

Do NOT repeat the answer. Only provide evaluation and fix instructions."""

    response = safe_invoke(prompt)
    feedback = response.content
    iterations = state.get("reflection_iterations", 0) + 1

    if "PASS" in feedback:
        print(f"  ✅ Answer PASSED reflection.")
    else:
        print(f"  ❌ Answer needs improvement. Feedback:\n{feedback[:300]}")

    return {"feedback": feedback, "reflection_iterations": iterations}


if __name__ == "__main__":
    # Test each agent independently
    print("\n" + "="*60)
    print("TESTING AGENTS INDEPENDENTLY")
    print("="*60)

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

    # Test planner
    result = planner_fn(test_state)
    test_state.update(result)

    # Test researcher
    result = research_fn(test_state)
    test_state.update(result)

    # Test reflector
    result = reflect_fn(test_state)
    test_state.update(result)

    print(f"\nFinal state keys: {list(test_state.keys())}")
    print(f"Sources used: {test_state['sources_used']}")
