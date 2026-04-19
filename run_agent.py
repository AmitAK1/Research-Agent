"""
CLI entry point for the Self-Correcting Research Agent.
Usage: python run_agent.py "your research query here"
"""
import sys
import json

# Ensure src is importable
sys.path.insert(0, ".")

from src.graph import run_agent


def main():
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = input("Enter your research query: ").strip()
        if not query:
            print("No query provided. Exiting.")
            return

    result = run_agent(query)

    print("\n" + "=" * 60)
    print("FINAL RESULT")
    print("=" * 60)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
