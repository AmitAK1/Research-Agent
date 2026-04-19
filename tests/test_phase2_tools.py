"""Phase 2 Test — Tools (DuckDuckGo + Python REPL)"""
import sys
sys.path.insert(0, ".")

from src.tools import search_web, run_python

print("=== Test 1: DuckDuckGo Search ===")
result = search_web("latest AI trends 2026")
print(result[:300] + "..." if len(result) > 300 else result)
assert len(result) > 50, "ERROR: Search result too short"
print("✅ DuckDuckGo search works\n")

print("=== Test 2: Python REPL ===")
result = run_python("print(2 + 2)")
print(f"Result: '{result}'")
assert "4" in result, f"ERROR: Expected '4' in result, got '{result}'"
print("✅ Python REPL works\n")

print("✅ Phase 2 COMPLETE")
