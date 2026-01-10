"""Cash transaction routes."""

from fastapi import APIRouter, HTTPException
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.models import CashRequest, ApiResponse
from cli.events import create_cash_event
from api.database import sync_csv_to_db

router = APIRouter(prefix="/api/cash", tags=["cash"])


@router.post("/deposit", response_model=ApiResponse)
async def deposit(amount: float, source: str = "", reason: str = ""):
    """Deposit cash into the portfolio."""
    try:
        event_id = create_cash_event(
            event_type="DEPOSIT",
            amount=amount,
            reason_text=reason,
            description=source
        )

        sync_csv_to_db()

        return ApiResponse(
            success=True,
            message=f"Deposited ${amount:,.2f}",
            event_id=event_id,
            data={"amount": amount, "source": source}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/withdraw", response_model=ApiResponse)
async def withdraw(amount: float, purpose: str = "", reason: str = ""):
    """Withdraw cash from the portfolio."""
    try:
        event_id = create_cash_event(
            event_type="WITHDRAWAL",
            amount=amount,
            reason_text=reason,
            description=purpose
        )

        sync_csv_to_db()

        return ApiResponse(
            success=True,
            message=f"Withdrew ${amount:,.2f}",
            event_id=event_id,
            data={"amount": amount, "purpose": purpose}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/transaction", response_model=ApiResponse)
async def transaction(request: CashRequest):
    """Generic cash transaction (deposit or withdrawal)."""
    action = request.action.upper()

    if action == "DEPOSIT":
        return await deposit(request.amount, request.description, request.reason)
    else:
        return await withdraw(request.amount, request.description, request.reason)
