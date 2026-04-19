# Fix Plan — Self-Correcting Research Agent

## Problem Summary

The agent is **architecturally correct** but has 5 critical weaknesses:
1. Python tool runs code but **hides the work** (no formula/steps shown)
2. Planner doesn't tell researcher **which tools to use**
3. Reflection **detects problems but can't fix them** (no actionable instructions)
4. No **validation** — agent can claim CAGR without showing math
5. Schema **lacks `calculation_steps`** field

## Scope & Constraints

- **4 files modified**: `src/agents.py`, `src/schemas.py`, `src/graph.py`, `src/tools.py`
- **0 new files** — all changes are in-place
- **No dependency changes** — no new pip installs needed
- **~30 min of work** — focused, surgical edits

---

## Fix 1: Python REPL Transparency (tools.py + agents.py)

### Problem
`run_python()` returns only the output. The code being executed is invisible in the final answer. The LLM generates a script, runs it, but nobody sees the formula or intermediate steps.

### Fix in `src/tools.py`
**Change `run_python` to return both the code AND the output** so downstream consumers can see the actual calculation.

**Current code (lines 25-31):**
```python
def run_python(code: str) -> str:
    """Execute Python code with error handling."""
    try:
        result = python_tool.run(code)
        return result if result else "Code executed successfully (no output)."
    except Exception as e:
        return f"Python execution error: {str(e)}"
```

**Replace with:**
```python
def run_python(code: str) -> str:
    """Execute Python code and return both the code and its output for transparency."""
    try:
        result = python_tool.run(code)
        output = result if result else "(no printed output)"
        # Return both code and output so calculations are verifiable
        return f"--- Python Code Executed ---\n{code}\n--- Output ---\n{output}"
    except Exception as e:
        return f"--- Python Code Executed ---\n{code}\n--- Error ---\n{str(e)}"
```

### Fix in `src/agents.py` — research_fn (calculation section)
**Change how the LLM generates Python code.** The current prompt is too vague — it says "write a short script". The new prompt must force the LLM to show its work with explicit formulas and labeled print statements.

**Current code (lines 91-100):**
```python
    if needs_calc:
        print("  Running Python calculation...")
        # Let the LLM generate the code
        code_prompt = f"Write a SHORT Python script (just print statements) to calculate/answer: '{query}'. Output ONLY the Python code, no explanation."
        code = llm.invoke(code_prompt).content.strip()
        # Clean code fences if present
        code = code.replace("```python", "").replace("```", "").strip()
        calc_result = run_python(code)
        research_data += f"Calculation Result:\n{calc_result}\n\n"
        sources.append("Python REPL")
```

**Replace with:**
```python
    if needs_calc:
        print("  Running Python calculation...")
        # Force the LLM to write transparent, step-by-step calculation code
        search_data_for_calc = research_data if research_data else "No external data available — use reasonable estimates and cite them."
        code_prompt = f"""Write a Python script to calculate/answer: '{query}'

Available data from research:
{search_data_for_calc}

STRICT RULES for the Python script:
1. Define ALL variables with clear names and comments showing where each number comes from
2. Print EVERY intermediate step with labels
3. Print the FORMULA being used before computing it
4. Print the FINAL result clearly labeled
5. If using CAGR, use: CAGR = ((end_value / start_value) ** (1 / years)) - 1
6. If data is estimated, print "ESTIMATED:" before the value

Example format:
print("Formula: CAGR = ((Final / Initial) ^ (1/n)) - 1")
print(f"Initial (2020): {{initial}}")
print(f"Final (2025): {{final}}")
print(f"CAGR = (( {{final}} / {{initial}} ) ^ (1/5)) - 1 = {{cagr:.2%}}")

Output ONLY the Python code, no markdown fences, no explanation."""
        code = llm.invoke(code_prompt).content.strip()
        # Clean code fences if present
        code = code.replace("```python", "").replace("```", "").strip()
        calc_result = run_python(code)
        research_data += f"Calculation Steps:\n{calc_result}\n\n"
        sources.append("Python REPL")
```

---

## Fix 2: Planner Tool-Tagging (agents.py — planner_fn)

### Problem
Planner creates generic steps like "Collect data on EV market". It doesn't tell the researcher WHICH tool to use for each step. So the researcher independently decides, often incorrectly.

### Fix in `src/agents.py` — planner_fn
**Change the planner prompt** to force tool tags on each step.

**Current prompt (lines 36-45):**
```python
    prompt = f"""You are a research planner. Create a clear, numbered step-by-step plan to answer this query.
        
Query: '{state['query']}'
{past_section}

Rules:
- Output ONLY the numbered steps (3-5 steps max)
- Each step should be a specific, actionable research task
- If past research is relevant, note which steps can build on it
"""
```

**Replace with:**
```python
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
```

### Also change research_fn tool decision logic
**Instead of asking 2 separate yes/no questions**, parse the plan for tool tags. This makes the researcher follow the planner's instructions instead of independently (and often wrongly) deciding.

**Current code (lines 64-80):**
```python
    # --- Decision: Does this query need fresh internet data? ---
    decision_prompt = f"""Does this query require up-to-date information from the internet (news, current events, recent data)?
Query: '{query}'
Answer with ONLY 'YES' or 'NO'."""

    decision = llm.invoke(decision_prompt).content.strip().upper()
    needs_search = "YES" in decision
    print(f"  Needs web search: {needs_search}")

    # --- Decision: Does this query involve calculation? ---
    calc_prompt = f"""Does this query require mathematical calculation or data computation?
Query: '{query}'
Answer with ONLY 'YES' or 'NO'."""

    calc_decision = llm.invoke(calc_prompt).content.strip().upper()
    needs_calc = "YES" in calc_decision
    print(f"  Needs calculation: {needs_calc}")
```

**Replace with:**
```python
    # --- Decide tools from planner's tags (saves 2 LLM calls) ---
    plan = state.get("plan", "")
    needs_search = "[TOOL: SEARCH]" in plan.upper()
    needs_calc = "[TOOL: PYTHON]" in plan.upper()
    
    # Fallback: if planner didn't tag tools, ask the LLM (backward compatibility)
    if not needs_search and not needs_calc and "[TOOL:" not in plan.upper():
        decision_prompt = f"""Does this query require: (a) web search for current data, AND/OR (b) mathematical calculations?
Query: '{query}'
Answer ONLY with one of: SEARCH_ONLY, CALC_ONLY, BOTH, NEITHER"""
        decision = llm.invoke(decision_prompt).content.strip().upper()
        needs_search = "SEARCH" in decision or "BOTH" in decision
        needs_calc = "CALC" in decision or "BOTH" in decision

    print(f"  Needs web search: {needs_search}")
    print(f"  Needs calculation: {needs_calc}")
```

---

## Fix 3: Reflection with Actionable Instructions (agents.py — reflect_fn)

### Problem
Current reflector says "missing calculation steps" but doesn't tell the researcher HOW to fix it. The researcher just regenerates a similar bad answer.

### Fix in `src/agents.py` — reflect_fn
**Change the reflection prompt** to force specific, actionable fix instructions.

**Current prompt (lines 146-167):**
```python
    prompt = f"""You are a critical research reviewer. Evaluate this answer for the given query.

Query: '{state['query']}'

Answer to review:
{state['draft']}

Evaluation criteria:
1. Completeness — Does it fully answer the query?
2. Accuracy — Are the facts correct and well-supported?
3. Clarity — Is it well-organized and easy to understand?
4. Depth — Does it provide sufficient detail?

If the answer is excellent on ALL criteria, respond with exactly: PASS

If it needs improvement, respond with:
FAIL
- [specific issue 1]
- [specific issue 2]
- [what information is missing]

Do NOT repeat the answer. Only provide evaluation."""
```

**Replace with:**
```python
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
```

---

## Fix 4: Add `calculation_steps` to State and Schema

### Problem
There's no dedicated field for calculation steps. They get mixed into `research_data` or `draft` and can be lost or summarized away by the LLM.

### Fix in `src/agents.py` — AgentState
**Add `calculation_steps` field.**

**Current (lines 13-21):**
```python
class AgentState(TypedDict):
    query: str
    past_context: str            # Retrieved memory context
    plan: str                    # Planner output
    research_data: str           # Raw search results
    draft: str                   # Current answer draft
    feedback: str                # Reflection feedback
    reflection_iterations: int   # Counter for reflection loops
    sources_used: List[str]      # Track which tools were used
```

**Replace with:**
```python
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
```

### Fix in `src/agents.py` — research_fn
**Store calculation output separately** in `calculation_steps` AND in `research_data`.

In the `needs_calc` block (the new version from Fix 1), after `calc_result = run_python(code)`, the return statement at the end of research_fn should also include `calculation_steps`:

**Current return (line 134):**
```python
    return {"research_data": research_data, "draft": draft, "sources_used": sources}
```

**Replace with:**
```python
    return {"research_data": research_data, "draft": draft, "sources_used": sources, "calculation_steps": calculation_steps}
```

AND add this line at the top of `research_fn` (after `sources = ...` on line 62):
```python
    calculation_steps = state.get("calculation_steps", "")
```

AND in the `needs_calc` block, after `calc_result = run_python(code)`:
```python
        calculation_steps = calc_result  # Store the full code + output
```

### Fix in `src/agents.py` — research_fn draft prompt
**Inject calculation_steps into the draft prompt** so the LLM MUST incorporate them into its answer.

In the draft_prompt (the big f-string), add after `{feedback_section}`:
```python
    # --- Calculation steps ---
    calc_section = f"\n\nCalculation steps (MUST be included verbatim in your answer):\n{calculation_steps}" if calculation_steps else ""
```

And add `{calc_section}` into the draft_prompt. Also add this to the Rules:
```
- If calculation steps are provided, you MUST include the exact formula, inputs, and results in your answer — do NOT summarize or round differently
```

### Fix in `src/schemas.py` — ResearchOutput
**Add the field.**

**Current (lines 9-16):**
```python
class ResearchOutput(BaseModel):
    """Structured output from the research agent."""
    query: str = Field(description="The original research query")
    summary: str = Field(description="Concise 2-3 sentence summary of findings")
    key_findings: List[str] = Field(description="3-5 bullet-point key findings")
    sources: List[str] = Field(description="Sources or tools used (e.g., 'DuckDuckGo Search', 'Python REPL')")
    confidence: float = Field(description="Confidence score from 0.0 to 1.0")
    needs_further_research: bool = Field(description="Whether the topic needs more investigation")
```

**Replace with:**
```python
class ResearchOutput(BaseModel):
    """Structured output from the research agent."""
    query: str = Field(description="The original research query")
    summary: str = Field(description="Concise 2-3 sentence summary of findings")
    key_findings: List[str] = Field(description="3-5 bullet-point key findings")
    calculation_steps: str = Field(default="", description="Step-by-step calculation with formula, inputs, and results. Empty string if no calculations were needed.")
    sources: List[str] = Field(description="Sources or tools used (e.g., 'DuckDuckGo Search', 'Python REPL')")
    confidence: float = Field(description="Confidence score from 0.0 to 1.0")
    needs_further_research: bool = Field(description="Whether the topic needs more investigation")
```

### Fix in `src/graph.py` — format_output_node
**Pass calculation_steps to the formatter** so it appears in the final JSON.

**Current prompt in format_output_node (lines 60-69):**
```python
    prompt = f"""Convert this research into the required JSON format.

Original Query: {state['query']}

Research Answer:
{state['draft']}

Sources used: {sources_str}

Fill in ALL fields accurately. For confidence, rate 0.0-1.0 based on the quality and completeness of the answer."""
```

**Replace with:**
```python
    calc_steps = state.get("calculation_steps", "")
    
    prompt = f"""Convert this research into the required JSON format.

Original Query: {state['query']}

Research Answer:
{state['draft']}

Calculation Steps (include verbatim in calculation_steps field):
{calc_steps if calc_steps else "No calculations performed."}

Sources used: {sources_str}

Fill in ALL fields accurately. For confidence, rate 0.0-1.0 based on the quality and completeness of the answer.
If calculation_steps data is provided above, copy it exactly into the calculation_steps field."""
```

### Fix in `src/graph.py` — initial_state in run_agent
**Add `calculation_steps` to initial state.**

**Current (lines 149-158):**
```python
    initial_state: AgentState = {
        "query": query,
        "past_context": "",
        "plan": "",
        "research_data": "",
        "draft": "",
        "feedback": "",
        "reflection_iterations": 0,
        "sources_used": [],
    }
```

**Replace with:**
```python
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
```

---

## Fix 5: Validation Layer (graph.py)

### Problem
Agent can claim "CAGR is 101%" with no proof. There's no gate between reflection and output that checks if required calculations actually exist.

### Fix in `src/graph.py` — add validate_output_node

**Add this new node function** (add after `format_output_node` function, before `should_continue`):

```python
def validate_output_node(state: AgentState) -> dict:
    """Validation gate: ensure calculations exist when the query requires them."""
    print(f"\n{'='*60}")
    print(f"✅ VALIDATOR — {time.strftime('%H:%M:%S')}")
    print(f"{'='*60}")
    
    query_lower = state["query"].lower()
    calc_keywords = ["calculate", "cagr", "growth rate", "percentage", "compute", "estimate", "how much", "how many", "forecast", "predict"]
    needs_math = any(kw in query_lower for kw in calc_keywords)
    
    calc_steps = state.get("calculation_steps", "")
    has_calculations = bool(calc_steps and len(calc_steps) > 20)
    
    if needs_math and not has_calculations:
        print("  ⚠️ VALIDATION FAILED: Query requires calculations but none found.")
        print("  → Forcing calculation step...")
        # Return feedback that forces a recalculation
        return {
            "feedback": "FAIL\n\nMISSING_CALCULATIONS:\n- This query explicitly requires numerical calculations but NONE were performed.\n- You MUST use the Python tool to compute the answer with real numbers.\n\nFIX_INSTRUCTIONS:\n- Run Python with the actual formula and numbers to produce verifiable results.",
            "reflection_iterations": max(0, state.get("reflection_iterations", 0) - 1)  # Give it another chance
        }
    
    if needs_math and has_calculations:
        print(f"  ✅ Calculations present ({len(calc_steps)} chars)")
    else:
        print("  ✅ No calculations required for this query")
    
    return {}
```

### Wire it into the graph

**Current graph edges (lines 116-128):**
```python
    # Define edges: START → retrieve_memory → planner → research → reflect → [conditional]
    builder.add_edge(START, "retrieve_memory")
    builder.add_edge("retrieve_memory", "planner")
    builder.add_edge("planner", "research")
    builder.add_edge("research", "reflect")

    # Conditional: either loop back to research or proceed to store + format
    builder.add_conditional_edges("reflect", should_continue, {
        "research": "research",
        "store_memory": "store_memory",
    })
    builder.add_edge("store_memory", "format_output")
    builder.add_edge("format_output", END)
```

**Replace with:**
```python
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
```

And add the node:
```python
    builder.add_node("validate", validate_output_node)
```

---

## Summary of All File Changes

| File | What Changes |
|---|---|
| `src/tools.py` | `run_python()` returns code + output (Fix 1) |
| `src/agents.py` | AgentState gets `calculation_steps` (Fix 4), planner prompt gets tool tags (Fix 2), research_fn reads plan tags instead of asking LLM (Fix 2), research_fn calc prompt forces transparency (Fix 1), research_fn draft prompt includes calc_steps (Fix 4), reflect_fn prompt gives actionable fix instructions (Fix 3) |
| `src/schemas.py` | `ResearchOutput` gets `calculation_steps` field (Fix 4) |
| `src/graph.py` | `validate_output_node` added (Fix 5), `format_output_node` prompt includes calc_steps (Fix 4), initial_state gets `calculation_steps` (Fix 4), graph wiring includes validate node (Fix 5) |

## Test After Changes

```bash
$env:PYTHONIOENCODING='utf-8'
agents\Scripts\python.exe run_agent.py "Analyze India's EV market growth from 2020-2025 and estimate future CAGR. Show calculations."
```

**Expected improvements:**
1. Output should show: `Formula: CAGR = ((Final / Initial) ^ (1/n)) - 1` with actual numbers
2. `calculation_steps` field in JSON should have the full Python code + output
3. If CAGR is claimed, the numbers should be traceable
4. Reflection should give specific fix instructions if math is missing
5. Validator should catch missing calculations and force a retry

## What NOT To Change (Out of Scope)

- **URLs in sources**: DuckDuckGo's LangChain tool doesn't return URLs — fixing this requires switching to a different search API (e.g., Tavily, SerpAPI). Not worth the complexity.
- **Deployment config** — no changes needed
- **Memory/Pinecone** — working fine, no changes
- **FastAPI endpoints** — `ResearchOutput` schema change auto-propagates to API
