"""
Phase 2 — Tools
DuckDuckGo search and Python REPL tools.
"""
import concurrent.futures
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_experimental.tools import PythonREPLTool

# Initialize tools
search_tool = DuckDuckGoSearchRun()
python_tool = PythonREPLTool()


def search_web(query: str) -> str:
    """Run a DuckDuckGo search with error handling."""
    try:
        result = search_tool.run(query)
        if not result or result.strip() == "":
            return "No search results found."
        return result
    except Exception as e:
        print(f"⚠️ DuckDuckGo search failed: {e}")
        return f"Search failed: {str(e)}"


def run_python(code: str) -> str:
    """Execute Python code and return both the code and its output for transparency."""
    try:
        # Prevent infinite loops or input() hanging the agent
        def execute():
            return python_tool.run(code)
            
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(execute)
            result = future.result(timeout=10) # 10 seconds timeout
            
        output = result if result else "(no printed output)"
        # Return both code and output so calculations are verifiable
        return f"--- Python Code Executed ---\n{code}\n--- Output ---\n{output}"
    except concurrent.futures.TimeoutError:
        print(f"⚠️ Python Execution Timed Out after 10s")
        return f"--- Python Code Executed ---\n{code}\n--- Error ---\nCalculation Timed Out (>10s). You likely wrote an infinite loop or called input(). Do NOT use input()."
    except Exception as e:
        return f"--- Python Code Executed ---\n{code}\n--- Error ---\n{str(e)}"


if __name__ == "__main__":
    print("--- Testing DuckDuckGo Search ---")
    r = search_web("latest AI trends 2026")
    print(r[:300] + "..." if len(r) > 300 else r)

    print("\n--- Testing Python REPL ---")
    r = run_python("print(2 + 2)")
    print(f"Result: {r}")
