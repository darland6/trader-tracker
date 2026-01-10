"""Research endpoint for financial analysis via Dexter."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from integrations.dexter import (
    query_dexter,
    is_dexter_available,
    get_dexter_status,
    EXAMPLE_QUERIES
)

router = APIRouter(prefix="/api/research", tags=["research"])


class ResearchRequest(BaseModel):
    query: str
    timeout: int = 120


class ResearchResponse(BaseModel):
    success: bool
    query: str
    answer: str
    error: str | None = None


@router.get("/status")
async def research_status():
    """Check if Dexter research agent is available."""
    status = get_dexter_status()
    return {
        "available": status["ready"],
        "status": status,
        "example_queries": EXAMPLE_QUERIES[:3]
    }


@router.post("/query", response_model=ResearchResponse)
async def research_query(request: ResearchRequest):
    """
    Query Dexter for financial research.

    Dexter is an autonomous agent that can analyze:
    - Income statements
    - Balance sheets
    - Cash flow statements
    - Financial ratios
    - Revenue trends
    - And more

    Example queries:
    - "What was AAPL's revenue growth over the last 4 quarters?"
    - "Analyze TSLA's profit margins"
    - "Compare META's P/E ratio to competitors"
    """
    if not is_dexter_available():
        status = get_dexter_status()
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Dexter research agent is not available",
                "status": status,
                "setup_instructions": [
                    "1. Clone dexter: git clone https://github.com/virattt/dexter.git",
                    "2. Install bun: https://bun.sh",
                    "3. cd dexter && bun install",
                    "4. Configure dexter/.env with API keys",
                    "5. Set DEXTER_PATH in your .env"
                ]
            }
        )

    result = await query_dexter(request.query, timeout=request.timeout)

    return ResearchResponse(
        success=result.success,
        query=result.query,
        answer=result.answer,
        error=result.error
    )


@router.get("/examples")
async def research_examples():
    """Get example research queries."""
    return {
        "examples": EXAMPLE_QUERIES,
        "tickers_in_portfolio": []  # Could populate from portfolio state
    }
