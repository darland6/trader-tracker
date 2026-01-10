"""Trade routes."""

from fastapi import APIRouter, HTTPException
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.models import TradeRequest, ApiResponse
from cli.events import create_trade_event
from api.database import sync_csv_to_db

router = APIRouter(prefix="/api", tags=["trades"])


@router.post("/trade", response_model=ApiResponse)
async def execute_trade(trade: TradeRequest):
    """Execute a trade (buy or sell)."""
    try:
        action = trade.action.upper()
        ticker = trade.ticker.upper()
        total = trade.shares * trade.price

        event_id = create_trade_event(
            action=action,
            ticker=ticker,
            shares=trade.shares,
            price=trade.price,
            total=total,
            gain_loss=trade.gain_loss,
            reason_text=trade.reason,
            notes=trade.notes
        )

        # Sync to database after CSV update
        sync_csv_to_db()

        return ApiResponse(
            success=True,
            message=f"{action} {trade.shares} shares of {ticker} @ ${trade.price:.2f}",
            event_id=event_id,
            data={
                "action": action,
                "ticker": ticker,
                "shares": trade.shares,
                "price": trade.price,
                "total": total
            }
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
