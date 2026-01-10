"""Alternate History API - Manage alternate portfolio realities and future projections."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.services.alt_history import (
    list_histories,
    get_history,
    create_history,
    update_history,
    delete_history,
    compare_histories,
    get_history_events,
    apply_modifications
)
from api.services.future_projection import (
    generate_projection,
    load_projection,
    list_projections,
    delete_projection
)
from reconstruct_state import reconstruct_state

router = APIRouter(prefix="/api/alt-history", tags=["alternate-history"])


class CreateHistoryRequest(BaseModel):
    name: str
    description: str = ""
    modifications: list = []


class ModificationRequest(BaseModel):
    modifications: list


class UpdateHistoryRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


@router.get("")
async def list_alternate_histories():
    """List all alternate histories."""
    histories = list_histories()
    return {
        "histories": histories,
        "count": len(histories)
    }


@router.post("")
async def create_alternate_history(request: CreateHistoryRequest):
    """Create a new alternate history.

    Example modifications:
    - {"type": "remove_ticker", "ticker": "TSLA"}
    - {"type": "add_trade", "ticker": "NVDA", "action": "BUY", "shares": 100, "price": 500, "timestamp": "2024-01-15"}
    - {"type": "scale_position", "ticker": "META", "scale": 2.0}
    - {"type": "change_trade_price", "event_id": 42, "price": 100}
    """
    history = create_history(
        name=request.name,
        description=request.description,
        modifications=request.modifications
    )
    return {"success": True, "history": history}


# ============ Future Projection Endpoints ============
# These must come BEFORE /{history_id} routes to avoid path matching issues

class ProjectionRequest(BaseModel):
    history_id: str = "reality"
    years: int = 3
    use_llm: bool = True


@router.get("/projections")
async def list_future_projections():
    """List all saved future projections."""
    return {
        "projections": list_projections()
    }


@router.post("/projections/generate")
async def create_future_projection(request: ProjectionRequest):
    """Generate a new future projection for a portfolio.

    Args:
        history_id: "reality" or an alternate history ID
        years: 1-5 years to project
        use_llm: Use LLM for analysis (more accurate but slower)

    Returns:
        Projection with analysis and future frames
    """
    if request.years < 1 or request.years > 5:
        raise HTTPException(status_code=400, detail="Years must be between 1 and 5")

    projection = generate_projection(
        history_id=request.history_id,
        years=request.years,
        use_llm=request.use_llm
    )

    if "error" in projection:
        raise HTTPException(status_code=404, detail=projection["error"])

    return projection


@router.get("/projections/{projection_id}")
async def get_future_projection(projection_id: str):
    """Get a saved future projection."""
    projection = load_projection(projection_id)
    if not projection:
        raise HTTPException(status_code=404, detail="Projection not found")
    return projection


@router.delete("/projections/{projection_id}")
async def remove_future_projection(projection_id: str):
    """Delete a future projection."""
    if delete_projection(projection_id):
        return {"success": True, "message": "Projection deleted"}
    raise HTTPException(status_code=404, detail="Projection not found")


# ============ Alternate History Endpoints (with path params) ============

@router.get("/{history_id}")
async def get_alternate_history(history_id: str):
    """Get a specific alternate history with its current state."""
    history = get_history(history_id)
    if not history:
        raise HTTPException(status_code=404, detail="History not found")

    # Get the reconstructed state for this history
    events = get_history_events(history_id)
    if events is not None:
        state = reconstruct_state(events)
        history["state"] = {
            "total_value": state.get('total_value', 0),
            "cash": state.get('cash', 0),
            "portfolio_value": state.get('portfolio_value', 0),
            "ytd_income": state.get('ytd_income', 0),
            "holdings": {k: v for k, v in state.get('holdings', {}).items() if v > 0.01},
            "active_options": len(state.get('active_options', []))
        }

    return history


@router.put("/{history_id}")
async def update_alternate_history(history_id: str, request: UpdateHistoryRequest):
    """Update alternate history metadata."""
    updates = {}
    if request.name is not None:
        updates["name"] = request.name
    if request.description is not None:
        updates["description"] = request.description

    history = update_history(history_id, updates)
    if not history:
        raise HTTPException(status_code=404, detail="History not found")

    return {"success": True, "history": history}


@router.delete("/{history_id}")
async def delete_alternate_history(history_id: str):
    """Delete an alternate history."""
    history = get_history(history_id)
    if not history:
        raise HTTPException(status_code=404, detail="History not found")

    delete_history(history_id)
    return {"success": True, "message": f"Deleted history: {history['name']}"}


@router.post("/{history_id}/modify")
async def modify_alternate_history(history_id: str, request: ModificationRequest):
    """Apply additional modifications to an existing alternate history."""
    history = get_history(history_id)
    if not history:
        raise HTTPException(status_code=404, detail="History not found")

    apply_modifications(history_id, request.modifications)

    # Update the modifications list in metadata
    current_mods = history.get("modifications", [])
    current_mods.extend(request.modifications)
    update_history(history_id, {"modifications": current_mods})

    return {"success": True, "message": "Modifications applied"}


@router.get("/{history_id}/compare/{other_id}")
async def compare_alternate_histories(history_id: str, other_id: str = "reality"):
    """Compare two histories or compare against reality.

    Use "reality" as other_id to compare against the real portfolio.
    """
    comparison = compare_histories(history_id, other_id)

    if "error" in comparison:
        raise HTTPException(status_code=404, detail=comparison["error"])

    return comparison


@router.get("/{history_id}/state")
async def get_history_state(history_id: str):
    """Get full portfolio state for an alternate history."""
    events = get_history_events(history_id)
    if events is None:
        raise HTTPException(status_code=404, detail="History not found")

    state = reconstruct_state(events)

    # Build holdings list like the main state endpoint
    holdings = []
    for ticker, shares in state.get('holdings', {}).items():
        if shares > 0.01:
            price = state.get('latest_prices', {}).get(ticker, 0)
            cost_info = state.get('cost_basis', {}).get(ticker, {})
            market_value = shares * price

            holdings.append({
                "ticker": ticker,
                "shares": shares,
                "current_price": price,
                "market_value": market_value,
                "cost_basis": cost_info.get('total_cost', 0),
                "avg_cost": cost_info.get('avg_price', 0)
            })

    holdings.sort(key=lambda x: x["market_value"], reverse=True)

    return {
        "total_value": state.get('total_value', 0),
        "cash": state.get('cash', 0),
        "portfolio_value": state.get('portfolio_value', 0),
        "holdings": holdings,
        "ytd_income": state.get('ytd_income', 0),
        "ytd_trading_gains": state.get('ytd_trading_gains', 0),
        "ytd_option_income": state.get('ytd_option_income', 0),
        "ytd_dividends": state.get('ytd_dividends', 0),
        "active_options": state.get('active_options', [])
    }


# Quick what-if endpoints for common scenarios
@router.post("/what-if/never-bought")
async def what_if_never_bought(ticker: str, name: str = None):
    """Create alternate history where you never bought a specific ticker."""
    history = create_history(
        name=name or f"Never Bought {ticker}",
        description=f"What if I never invested in {ticker}?",
        modifications=[{"type": "remove_ticker", "ticker": ticker}]
    )

    # Get comparison to reality
    comparison = compare_histories(history["id"], "reality")

    return {
        "history": history,
        "comparison": comparison
    }


@router.post("/what-if/doubled-position")
async def what_if_doubled_position(ticker: str, name: str = None):
    """Create alternate history where you doubled down on a position."""
    history = create_history(
        name=name or f"2x {ticker}",
        description=f"What if I bought twice as much {ticker}?",
        modifications=[{"type": "scale_position", "ticker": ticker, "scale": 2.0}]
    )

    comparison = compare_histories(history["id"], "reality")

    return {
        "history": history,
        "comparison": comparison
    }


@router.get("/{history_id}/project")
async def project_history_future(history_id: str, years: int = 3, use_llm: bool = True):
    """Generate a future projection for a specific history.

    Shortcut endpoint that creates a projection for the given history.
    """
    projection = generate_projection(
        history_id=history_id,
        years=min(max(years, 1), 5),
        use_llm=use_llm
    )

    if "error" in projection:
        raise HTTPException(status_code=404, detail=projection["error"])

    return projection
