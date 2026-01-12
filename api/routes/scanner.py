"""Options Scanner API routes."""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/api/scanner", tags=["scanner"])


class ScanRequest(BaseModel):
    """Request model for options scan."""
    max_dte: int = 45
    min_premium: float = 50
    max_results: int = 10
    use_llm: bool = False


class ScanResponse(BaseModel):
    """Response model for options scan."""
    status: str
    scan_id: Optional[str] = None
    message: str


# Store for background scan results
_scan_results = {}


@router.post("/scan")
async def start_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    """
    Start an options chain scan for income opportunities.

    Scans all holdings for covered call opportunities and
    cash-secured put opportunities based on available capital.
    """
    from core.scanner import get_recommendations

    try:
        # Run synchronously for now (can be made async for large portfolios)
        result = get_recommendations(
            max_dte=request.max_dte,
            min_premium=request.min_premium,
            max_results=request.max_results,
            use_llm=request.use_llm
        )

        return {
            "status": "success",
            "generated_at": result['generated_at'],
            "portfolio_summary": result['portfolio_summary'],
            "recommendations": result['recommendations'],
            "potential_income": result['potential_income'],
            "analysis": result.get('analysis'),
            "scan_errors": result.get('scan_errors')
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")


@router.get("/recommendations")
async def get_quick_recommendations():
    """
    Get quick options recommendations with default settings.
    Useful for the floating action button quick scan.
    """
    from core.scanner import get_recommendations

    try:
        result = get_recommendations(
            max_dte=45,
            min_premium=50,
            max_results=10,
            use_llm=False
        )

        return {
            "status": "success",
            "generated_at": result['generated_at'],
            "portfolio_summary": result['portfolio_summary'],
            "recommendations": result['recommendations'],
            "potential_income": result['potential_income'],
            "scan_errors": result.get('scan_errors')
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")


@router.get("/recommendations/analyze")
async def get_analyzed_recommendations():
    """
    Get options recommendations with LLM analysis.
    Takes longer but provides reasoning and insights.
    """
    from core.scanner import get_recommendations

    try:
        result = get_recommendations(
            max_dte=45,
            min_premium=50,
            max_results=10,
            use_llm=True
        )

        return {
            "status": "success",
            "generated_at": result['generated_at'],
            "portfolio_summary": result['portfolio_summary'],
            "recommendations": result['recommendations'],
            "potential_income": result['potential_income'],
            "analysis": result.get('analysis'),
            "scan_errors": result.get('scan_errors')
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")


@router.get("/recommendations/agent")
async def get_agent_analyzed_recommendations(
    max_dte: int = 45,
    min_premium: float = 50,
    max_results: int = 10
):
    """
    Get AI agent-scored options recommendations using Dexter research.

    This endpoint:
    1. Scans options chains for all holdings
    2. Fetches Dexter financial research for top candidates
    3. Uses an LLM agent to analyze and score opportunities
    4. Returns ranked recommendations with reasoning

    Takes longer than /recommendations but provides intelligent analysis.
    """
    from core.scanner import get_agent_recommendations

    try:
        result = await get_agent_recommendations(
            max_dte=max_dte,
            min_premium=min_premium,
            max_results=max_results
        )

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent scan failed: {str(e)}")


@router.post("/agent/scan")
async def start_agent_scan(request: ScanRequest):
    """
    Start an agent-enhanced options scan.

    Uses Dexter for research and LLM for intelligent scoring.
    """
    from core.scanner import get_agent_recommendations

    try:
        result = await get_agent_recommendations(
            max_dte=request.max_dte,
            min_premium=request.min_premium,
            max_results=request.max_results
        )

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent scan failed: {str(e)}")


@router.get("/ticker/{ticker}")
async def scan_ticker(ticker: str, max_dte: int = 45):
    """
    Scan a specific ticker for options opportunities.
    Returns both puts and calls for the ticker.
    """
    from core.scanner import fetch_options_chain, score_option, get_portfolio_holdings

    try:
        ticker = ticker.upper()
        portfolio = get_portfolio_holdings()

        options = fetch_options_chain(ticker, max_dte)

        if not options:
            return {
                "status": "no_data",
                "ticker": ticker,
                "message": f"No options data available for {ticker}",
                "options": []
            }

        # Score all options
        for opt in options:
            opt['score'] = score_option(opt, portfolio)

        # Sort by score
        options.sort(key=lambda x: x['score'], reverse=True)

        # Separate puts and calls
        puts = [o for o in options if o['type'] == 'PUT'][:5]
        calls = [o for o in options if o['type'] == 'CALL'][:5]

        return {
            "status": "success",
            "ticker": ticker,
            "current_price": options[0]['current_price'] if options else None,
            "top_puts": puts,
            "top_calls": calls,
            "total_contracts_scanned": len(options)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")
