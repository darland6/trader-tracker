"""Options routes."""

from fastapi import APIRouter, HTTPException
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.models import OptionOpenRequest, OptionCloseRequest, ApiResponse
from cli.events import create_option_event, create_option_close_event, get_active_options, auto_expire_options
from api.database import sync_csv_to_db

router = APIRouter(prefix="/api/options", tags=["options"])


@router.get("/active")
async def get_active():
    """Get all active options."""
    options = get_active_options()
    return {"options": options}


@router.post("/open", response_model=ApiResponse)
async def open_option(option: OptionOpenRequest):
    """Open a new option position."""
    try:
        ticker = option.ticker.upper()
        action = option.action.upper()

        event_id, position_id = create_option_event(
            ticker=ticker,
            action=action,
            strategy=option.strategy,
            strike=option.strike,
            expiration=option.expiration,
            contracts=option.contracts,
            premium=option.premium,
            reason_text=option.reason
        )

        sync_csv_to_db()

        return ApiResponse(
            success=True,
            message=f"{action} {option.contracts} {ticker} {option.strategy} @ ${option.strike} exp {option.expiration}",
            event_id=event_id,
            position_id=position_id,
            data={
                "ticker": ticker,
                "action": action,
                "strategy": option.strategy,
                "strike": option.strike,
                "expiration": option.expiration,
                "contracts": option.contracts,
                "premium": option.premium,
                "position_id": position_id
            }
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/close", response_model=ApiResponse)
async def close_option(request: OptionCloseRequest):
    """Close an existing option position."""
    try:
        if not request.event_id and not request.position_id:
            raise HTTPException(status_code=400, detail="Either event_id or position_id is required")

        event_type = f"OPTION_{request.close_type.upper()}"

        event_id = create_option_close_event(
            option_id=request.event_id,
            position_id=request.position_id,
            close_cost=request.close_cost,
            event_type=event_type,
            reason_text=request.reason
        )

        sync_csv_to_db()

        identifier = request.position_id or str(request.event_id)
        return ApiResponse(
            success=True,
            message=f"Option {identifier} {request.close_type.lower()}d",
            event_id=event_id,
            data={
                "original_option_id": request.event_id,
                "position_id": request.position_id,
                "close_type": request.close_type,
                "close_cost": request.close_cost
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/auto-expire", response_model=ApiResponse)
async def run_auto_expire():
    """Check for and auto-expire any options past their expiration date."""
    try:
        expired = auto_expire_options()
        sync_csv_to_db()

        if expired:
            return ApiResponse(
                success=True,
                message=f"Expired {len(expired)} option(s)",
                data={"expired": expired}
            )
        else:
            return ApiResponse(
                success=True,
                message="No expired options found",
                data={"expired": []}
            )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
