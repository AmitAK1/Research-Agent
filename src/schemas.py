"""
Phase 7 — Pydantic Schemas
Structured output models for the research agent.
"""
from typing import List
from pydantic import BaseModel, Field


class ResearchOutput(BaseModel):
    """Structured output from the research agent."""
    query: str = Field(description="The original research query")
    summary: str = Field(description="Concise 2-3 sentence summary of findings")
    key_findings: List[str] = Field(description="3-5 bullet-point key findings")
    calculation_steps: str = Field(default="", description="Step-by-step calculation with formula, inputs, and results. Empty string if no calculations were needed.")
    sources: List[str] = Field(description="Sources or tools used (e.g., 'DuckDuckGo Search', 'Python REPL')")
    confidence: float = Field(description="Confidence score from 0.0 to 1.0")
    needs_further_research: bool = Field(description="Whether the topic needs more investigation")


class QueryRequest(BaseModel):
    """Request schema for the /query API endpoint."""
    query: str = Field(description="The research query to process")
    max_iterations: int = Field(default=2, ge=1, le=5, description="Maximum reflection iterations")
