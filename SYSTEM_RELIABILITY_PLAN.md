# System Reliability & Execution Plan

## Objective
The agent currently generates sound logic but fails under real-world constraints (API rate limits, missing data, rigid validation). This plan outlines the exact changes needed to move the system from a "Self-Correcting Agent" to a "Reliable Production System."

---

## 1. Robust Fallback & Circuit Breaker (Fixing the 429 Crash)
**Problem:** When the primary Groq model hits a 429 Rate Limit, the system falls back to a smaller Groq model (`llama-3.1-8b-instant`), which hits the exact same quota pool and crashes the system.
**Solution:** Implement a cross-provider fallback using OpenRouter (Gemma 4 26B Free).

**Files to Change:**
*   `src/config.py`:
    *   Add `OPENROUTER_API_KEY` to the environment variables validation.
*   `src/llm.py`:
    *   Initialize a new ChatOpenAI client pointed at the OpenRouter base URL (`https://openrouter.ai/api/v1`).
    *   Update `safe_invoke` to try: 
        1. Groq Primary -> 
        2. Wait 3s -> Groq Primary (retry) -> 
        3. OpenRouter Fallback (Gemma 4 26B) -> 
        4. Circuit Breaker (Return graceful "System Overloaded" response instead of a Python exception).

---

## 2. Intelligent Data Estimation (Analyst Mode)
**Problem:** If the agent finds data for 2022, 2023, and 2024, but misses 2020, it returns `MISSING`, the calculation fails, and the pipeline stalls. Real analysts extrapolate.
**Solution:** Embed estimation logic into the Python REPL code generation.

**Files to Change:**
*   `src/agents.py` (`research_fn`):
    *   Update the `code_prompt` for the Python REPL.
    *   Instruct the LLM: *"If exact historical data (e.g., 2020) is missing but recent trend data (e.g., 2022, 2023, 2024) is available, write Python code to perform a simple linear extrapolation backwards to estimate the missing year."*
    *   Require the script to print `"ESTIMATED: [Reasoning]"` before using the extrapolated number.

---

## 3. Data-Grounded Validation
**Problem:** The current `_validate_calculation` function evaluates syntax. If the output is `= 0` or throws an error, it fails. But it completely ignores if the inputs themselves are fake or literally the string `"MISSING"`.
**Solution:** Upgrade the validator to parse for realistic inputs.

**Files to Change:**
*   `src/agents.py` (`_validate_calculation`):
    *   Add checks for the string `"MISSING"` in the python output.
    *   Add checks for unrealistic ranges (e.g., negative market sizes, calculations resulting in NaN).
    *   When the validator catches these, it feeds the specific data failure back to the reflection loop, forcing the agent to attempt Estimation Mode.

---

## 4. Partial Answer Mode & Graceful Degradation
**Problem:** If the agent absolutely cannot calculate the CAGR (e.g., no data exists to even extrapolate), it breaks the prompt boundaries or loops indefinitely until it exhausts iterations.
**Solution:** Accept partial completion. Provide whatever data *was* found.

**Files to Change:**
*   `src/agents.py` (`research_fn` draft generation):
    *   Update the drafting prompt: *"If the exact calculation is impossible due to fundamentally missing baseline data, state: 'Exact [Metric] cannot be computed due to lack of base data.' Then, provide the closest possible trend analysis based on the available data."*
*   `src/schemas.py`:
    *   Ensure the `calculation_steps` can handle a "calculation aborted but here is the trend" string without failing Pydantic validation.

---

## 5. Reducing Redundant LLM Calls (Performance Optimization)
**Problem:** Excessive LLM calls for structured extraction block the pipeline and burn tokens.
**Solution:** Merge operations. 

**Files to Change:**
*   `src/agents.py`:
    *   Remove or bypass the standalone `_extract_numbers_from_research` LLM call. 
    *   Instead, pipe the raw `research_data` directly into the Python REPL prompt and instruct the LLM to write the extraction regex/parsing directly within the Python script. Python is better at data extraction than an LLM anyway.

---
*Document created to track the architectural shifts for the System Reliability update (April 2026).*