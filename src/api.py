"""
Phase 8 — FastAPI Application
REST API for the research agent.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import time

from src.schemas import QueryRequest, ResearchOutput
from src.graph import run_agent

app = FastAPI(
    title="Self-Correcting Research Agent",
    description="A research agent with planning, search, reflection, and persistent memory.",
    version="1.0.0",
)

# CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "timestamp": time.time()}


@app.post("/query", response_model=ResearchOutput)
async def research_query(request: QueryRequest):
    """
    Run the research agent on a query.
    Returns structured JSON with summary, key findings, sources, and confidence.
    """
    try:
        result = run_agent(request.query, max_iterations=request.max_iterations)

        # If result is already a valid ResearchOutput dict, return it
        if isinstance(result, dict) and "summary" in result:
            return result
        else:
            raise ValueError("Agent returned unexpected format")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
