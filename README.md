# Self-Correcting Research Agent

A production-ready research agent built with **LangGraph**, **Groq** (LLM), **Pinecone** (vector memory), **DuckDuckGo** (search), and **FastAPI** (API deployment).

## Architecture

```
START → Memory Retrieval → Planner → Research → Reflection → [loops if needed] → Memory Store → Format Output → END
```

**Key Features:**
- **Smart Tool Routing** — Agent decides if query needs web search, calculation, or direct LLM knowledge
- **Self-Correction** — Reflection agent evaluates and improves answers (max 2 iterations)
- **Persistent Memory** — Pinecone stores past queries/responses, injects context into future research
- **Structured Output** — Pydantic-enforced JSON schema via Groq function calling

## Quick Start

### 1. Setup
```bash
# Install dependencies (into existing agents venv)
agents\Scripts\pip.exe install -r requirements.txt

# Create .env with your API keys
# GROQ_API_KEY=gsk_...
# PINECONE_API_KEY=pcsk_...
# PINECONE_INDEX_NAME=research-agent
```

### 2. Run Tests (Phase by Phase)
```bash
# Set encoding for Windows
$env:PYTHONIOENCODING='utf-8'

python tests/test_phase1_llm.py        # LLM check
python tests/test_phase2_tools.py      # Tools check
python tests/test_phase3_memory.py     # Pinecone check
python tests/test_phase4_agents.py     # Agent functions
python tests/test_phase5_graph.py      # Full pipeline
python tests/test_phase7_schema.py     # Structured output
```

### 3. Run Agent (CLI)
```bash
python run_agent.py "What caused the 2008 financial crisis?"
```

### 4. Run API Server
```bash
python -m uvicorn src.api:app --host 127.0.0.1 --port 8000
```

Then visit:
- **Swagger UI**: http://localhost:8000/docs
- **Health**: http://localhost:8000/health
- **Query**:
```bash
curl -X POST http://localhost:8000/query -H "Content-Type: application/json" -d '{"query": "What are the latest AI trends?"}'
```

## Project Structure

```
LumiqAI/
├── src/
│   ├── config.py      # Environment variables & constants
│   ├── llm.py         # Groq LLM initialization
│   ├── tools.py       # DuckDuckGo + Python REPL
│   ├── memory.py      # Pinecone vector memory
│   ├── agents.py      # Planner, Research, Reflection agents
│   ├── graph.py       # LangGraph workflow orchestration
│   ├── schemas.py     # Pydantic output models
│   └── api.py         # FastAPI endpoints
├── tests/             # Phase-by-phase test scripts
├── .env               # API keys (gitignored)
├── requirements.txt   # Dependencies
├── run_agent.py       # CLI entry point
├── Procfile           # Render deployment
└── README.md
```

## Output Schema

```json
{
  "query": "string",
  "summary": "string",
  "key_findings": ["string"],
  "sources": ["string"],
  "confidence": 0.0-1.0,
  "needs_further_research": true/false
}
```

## Deployment (Render)

1. Push to GitHub
2. Connect repo on [render.com](https://render.com)
3. Set environment variables: `GROQ_API_KEY`, `PINECONE_API_KEY`, `PINECONE_INDEX_NAME`
4. Build command: `pip install -r requirements.txt`
5. Start command: `uvicorn src.api:app --host 0.0.0.0 --port $PORT`
