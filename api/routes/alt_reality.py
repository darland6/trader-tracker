"""
Alternate Reality API - User-defined "what if" scenarios.

Endpoints for creating, viewing, and managing alternate portfolio timelines.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/api/alt-reality", tags=["alternate-reality"])


class PurchaseInput(BaseModel):
    ticker: str
    shares: int
    price: Optional[float] = None  # If not provided, uses historical price


class CreateRealityRequest(BaseModel):
    name: str
    description: str
    start_date: str  # YYYY-MM-DD
    starting_cash: float
    initial_purchases: List[PurchaseInput]
    scenario_type: Optional[str] = "custom"  # "bull", "bear", "custom"


class CreateRealityResponse(BaseModel):
    id: str
    name: str
    message: str


@router.get("/")
async def list_realities():
    """List all alternate realities."""
    from core.realities import list_alternate_realities

    realities = list_alternate_realities()
    return {
        "realities": realities,
        "count": len(realities)
    }


@router.post("/create")
async def create_reality(request: CreateRealityRequest):
    """
    Create a new alternate reality with user-defined seed.

    Example:
    {
        "name": "Tech Heavy 2024",
        "description": "What if I had gone all-in on tech in Jan 2024",
        "start_date": "2024-01-02",
        "starting_cash": 100000,
        "initial_purchases": [
            {"ticker": "NVDA", "shares": 100},
            {"ticker": "TSLA", "shares": 50},
            {"ticker": "META", "shares": 30}
        ],
        "scenario_type": "bull"
    }
    """
    from core.realities import create_alternate_reality

    try:
        purchases = [
            {
                'ticker': p.ticker,
                'shares': p.shares,
                'price': p.price
            }
            for p in request.initial_purchases
        ]

        reality = create_alternate_reality(
            name=request.name,
            description=request.description,
            start_date=request.start_date,
            starting_cash=request.starting_cash,
            initial_purchases=purchases,
            scenario_type=request.scenario_type or "custom"
        )

        return {
            "id": reality['id'],
            "name": reality['name'],
            "message": f"Created alternate reality '{reality['name']}' with ${reality['summary']['current_value']:,.0f} current value",
            "summary": reality['summary']
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{reality_id}")
async def get_reality(reality_id: str):
    """Get full details of an alternate reality including timeline snapshots."""
    from core.realities import get_alternate_reality

    reality = get_alternate_reality(reality_id)

    if not reality:
        raise HTTPException(status_code=404, detail=f"Reality '{reality_id}' not found")

    return reality


@router.delete("/{reality_id}")
async def delete_reality(reality_id: str):
    """Delete an alternate reality."""
    from core.realities import delete_alternate_reality

    if delete_alternate_reality(reality_id):
        return {"message": f"Reality '{reality_id}' deleted"}
    else:
        raise HTTPException(status_code=404, detail=f"Reality '{reality_id}' not found")


@router.post("/{reality_id}/refresh")
async def refresh_reality(reality_id: str):
    """Refresh an alternate reality with latest prices."""
    from core.realities import refresh_alternate_reality

    reality = refresh_alternate_reality(reality_id)

    if not reality:
        raise HTTPException(status_code=404, detail=f"Reality '{reality_id}' not found")

    return {
        "id": reality['id'],
        "name": reality['name'],
        "message": "Reality refreshed with latest prices",
        "summary": reality['summary']
    }


@router.get("/combined/timeline")
async def get_combined_timeline():
    """
    Get combined timeline data for multiverse visualization.

    Returns main reality + all alternate realities with their snapshots.
    """
    from core.realities import get_combined_timeline_data

    return get_combined_timeline_data()


@router.post("/quick-create/{scenario}")
async def quick_create_scenario(
    scenario: str,
    starting_cash: float = 100000,
    start_date: str = "2024-01-02"
):
    """
    Quick-create predefined scenarios.

    Scenarios:
    - tech-bull: Heavy tech allocation
    - dividend: Dividend-focused portfolio
    - index: Simple index fund approach
    - space: Space/aerospace focused
    - ai-play: AI/ML companies
    """
    from core.realities import create_alternate_reality

    scenarios = {
        "tech-bull": {
            "name": "Tech Bull Run",
            "description": "Heavy allocation to high-growth tech",
            "purchases": [
                {"ticker": "NVDA", "shares": 50},
                {"ticker": "META", "shares": 30},
                {"ticker": "TSLA", "shares": 40},
                {"ticker": "PLTR", "shares": 200}
            ],
            "type": "bull"
        },
        "dividend": {
            "name": "Dividend Income",
            "description": "Focus on dividend-paying stocks",
            "purchases": [
                {"ticker": "VYM", "shares": 200},
                {"ticker": "SCHD", "shares": 200},
                {"ticker": "O", "shares": 100},
                {"ticker": "JNJ", "shares": 50}
            ],
            "type": "custom"
        },
        "index": {
            "name": "Index Investor",
            "description": "Simple index fund approach",
            "purchases": [
                {"ticker": "SPY", "shares": 100},
                {"ticker": "QQQ", "shares": 100}
            ],
            "type": "custom"
        },
        "space": {
            "name": "Space Economy",
            "description": "Bet on commercial space",
            "purchases": [
                {"ticker": "RKLB", "shares": 500},
                {"ticker": "LMT", "shares": 20},
                {"ticker": "BA", "shares": 30}
            ],
            "type": "bull"
        },
        "ai-play": {
            "name": "AI Revolution",
            "description": "All-in on AI infrastructure",
            "purchases": [
                {"ticker": "NVDA", "shares": 80},
                {"ticker": "AMD", "shares": 100},
                {"ticker": "MSFT", "shares": 30},
                {"ticker": "GOOGL", "shares": 20}
            ],
            "type": "bull"
        }
    }

    if scenario not in scenarios:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scenario '{scenario}'. Available: {list(scenarios.keys())}"
        )

    config = scenarios[scenario]

    try:
        reality = create_alternate_reality(
            name=config["name"],
            description=config["description"],
            start_date=start_date,
            starting_cash=starting_cash,
            initial_purchases=config["purchases"],
            scenario_type=config["type"]
        )

        return {
            "id": reality['id'],
            "name": reality['name'],
            "message": f"Created '{config['name']}' scenario",
            "summary": reality['summary']
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
