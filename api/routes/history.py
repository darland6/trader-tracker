"""History playback API for portfolio timeline visualization."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sys
from pathlib import Path
from datetime import datetime
import json

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.database import get_all_events
from reconstruct_state import load_event_log, reconstruct_state

router = APIRouter(prefix="/api/history", tags=["history"])

SCRIPT_DIR = Path(__file__).parent.parent.parent.resolve()


class TimelineEvent(BaseModel):
    event_id: int
    timestamp: str
    event_type: str
    summary: str
    cash_delta: float
    has_ai_insights: bool


class PortfolioSnapshot(BaseModel):
    timestamp: str
    cash: float
    holdings: dict  # ticker -> shares
    holdings_value: dict  # ticker -> {shares, price, value}
    total_value: float
    active_options: list
    ytd_income: float


class PlaybackData(BaseModel):
    events: list[TimelineEvent]
    start_date: str
    end_date: str
    total_events: int


def summarize_event(event: dict) -> str:
    """Create a short summary of an event."""
    event_type = event.get('event_type', '')
    data = json.loads(event.get('data_json', '{}'))

    if event_type == 'TRADE':
        action = data.get('action', 'TRADE')
        return f"{action} {data.get('shares', 0)} {data.get('ticker', '')} @ ${data.get('price', 0):.2f}"

    elif event_type == 'OPTION_OPEN':
        return f"Sold {data.get('ticker', '')} ${data.get('strike', 0)} {data.get('strategy', '')} put"

    elif event_type == 'OPTION_CLOSE':
        return f"Closed option for ${data.get('profit', 0):.0f}"

    elif event_type == 'OPTION_EXPIRE':
        return f"Option expired (kept ${data.get('original_premium', 0):.0f})"

    elif event_type == 'OPTION_ASSIGN':
        return f"Assigned on {data.get('ticker', '')} option"

    elif event_type == 'DEPOSIT':
        return f"Deposited ${data.get('amount', 0):,.0f}"

    elif event_type == 'WITHDRAWAL':
        return f"Withdrew ${data.get('amount', 0):,.0f}"

    elif event_type == 'PRICE_UPDATE':
        prices = data.get('prices', {})
        return f"Updated {len(prices)} prices"

    elif event_type == 'DIVIDEND':
        return f"{data.get('ticker', '')} dividend ${data.get('amount', 0):.2f}"

    else:
        return event_type


@router.get("/timeline", response_model=PlaybackData)
async def get_timeline(include_price_updates: bool = False):
    """Get all events for timeline playback."""
    events = get_all_events(limit=500)  # Get plenty of history

    timeline = []
    for event in reversed(events):  # Oldest first
        event_type = event.get('event_type', '')

        # Optionally skip price updates for cleaner timeline
        if not include_price_updates and event_type == 'PRICE_UPDATE':
            continue

        reason = json.loads(event.get('reason_json', '{}'))

        timeline.append(TimelineEvent(
            event_id=event['event_id'],
            timestamp=event['timestamp'],
            event_type=event_type,
            summary=summarize_event(event),
            cash_delta=event.get('cash_delta', 0),
            has_ai_insights=bool(reason.get('ai_insights'))
        ))

    if not timeline:
        return PlaybackData(
            events=[],
            start_date="",
            end_date="",
            total_events=0
        )

    return PlaybackData(
        events=timeline,
        start_date=timeline[0].timestamp if timeline else "",
        end_date=timeline[-1].timestamp if timeline else "",
        total_events=len(timeline)
    )


@router.get("/snapshot/{event_id}", response_model=PortfolioSnapshot)
async def get_snapshot_at_event(event_id: int):
    """Get portfolio state after a specific event was applied."""
    try:
        # Load all events up to and including the target event
        events_df = load_event_log(str(SCRIPT_DIR / 'data' / 'event_log_enhanced.csv'))

        # Filter to events up to the target
        events_up_to = events_df[events_df['event_id'] <= event_id]

        if events_up_to.empty:
            raise HTTPException(status_code=404, detail="Event not found")

        # Reconstruct state at this point
        state = reconstruct_state(events_up_to)

        # Get the timestamp of the target event
        target_event = events_up_to[events_up_to['event_id'] == event_id].iloc[0]
        timestamp = str(target_event['timestamp'])

        # Build holdings with values
        holdings = state.get('holdings', {})
        prices = state.get('latest_prices', {})
        holdings_value = {}

        for ticker, shares in holdings.items():
            if shares > 0:
                price = prices.get(ticker, 0)
                holdings_value[ticker] = {
                    "shares": shares,
                    "price": price,
                    "value": shares * price
                }

        total_holdings_value = sum(h["value"] for h in holdings_value.values())

        return PortfolioSnapshot(
            timestamp=timestamp,
            cash=state.get('cash', 0),
            holdings={t: s for t, s in holdings.items() if s > 0},
            holdings_value=holdings_value,
            total_value=state.get('cash', 0) + total_holdings_value,
            active_options=state.get('active_options', []),
            ytd_income=state.get('ytd_income', 0)
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/snapshots")
async def get_all_snapshots(step: int = 1):
    """Get portfolio snapshots at regular intervals for animation.

    Args:
        step: Get every Nth event's snapshot (default 1 = all events)
    """
    try:
        events_df = load_event_log(str(SCRIPT_DIR / 'data' / 'event_log_enhanced.csv'))

        # Skip price updates for cleaner animation
        events_df = events_df[events_df['event_type'] != 'PRICE_UPDATE']

        snapshots = []
        event_ids = events_df['event_id'].tolist()

        for i, event_id in enumerate(event_ids):
            if i % step != 0:
                continue

            # Get state up to this event
            events_up_to = events_df[events_df['event_id'] <= event_id]

            # Reload full df for reconstruction (need price updates for accurate values)
            full_df = load_event_log(str(SCRIPT_DIR / 'data' / 'event_log_enhanced.csv'))
            full_up_to = full_df[full_df['event_id'] <= event_id]

            state = reconstruct_state(full_up_to)

            holdings = state.get('holdings', {})
            prices = state.get('latest_prices', {})

            # Calculate values
            holdings_data = {}
            for ticker, shares in holdings.items():
                if shares > 0:
                    price = prices.get(ticker, 0)
                    holdings_data[ticker] = {
                        "shares": shares,
                        "price": price,
                        "value": shares * price
                    }

            total_value = state.get('cash', 0) + sum(h["value"] for h in holdings_data.values())

            # Get event details
            event_row = events_df[events_df['event_id'] == event_id].iloc[0]

            snapshots.append({
                "event_id": int(event_id),
                "timestamp": str(event_row['timestamp']),
                "event_type": str(event_row['event_type']),
                "summary": summarize_event(dict(event_row)),
                "cash": state.get('cash', 0),
                "holdings": holdings_data,
                "total_value": total_value,
                "ytd_income": state.get('ytd_income', 0)
            })

        return {"snapshots": snapshots, "total": len(snapshots)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/prepared-playback")
async def get_prepared_playback():
    """
    Get fully prepared playback data with historical market prices.

    This endpoint fetches real historical prices from yfinance and generates
    daily frames showing actual portfolio values at each point in time.

    NOTE: This may take 10-30 seconds to load as it fetches historical data.

    Returns:
        frames: Daily portfolio snapshots with real market prices
        events: Original events for reference
        date_range: Start and end dates
        tickers: All tickers involved
        total_frames: Number of daily frames
        total_events: Number of portfolio events
    """
    from api.services.historical_prices import prepare_full_playback

    try:
        # Get all events
        events = get_all_events(limit=500)

        # Format events for the playback service
        formatted_events = []
        for event in reversed(events):  # Oldest first
            event_type = event.get('event_type', '')
            if event_type == 'PRICE_UPDATE':
                continue  # Skip price updates

            data_json = event.get('data_json', '{}')
            if isinstance(data_json, str):
                data = json.loads(data_json)
            else:
                data = data_json

            reason_json = event.get('reason_json', '{}')
            if isinstance(reason_json, str):
                reason = json.loads(reason_json)
            else:
                reason = reason_json

            formatted_events.append({
                'event_id': event['event_id'],
                'timestamp': event['timestamp'],
                'event_type': event_type,
                'data': data,
                'reason': reason,
                'summary': summarize_event(event),
                'cash_delta': event.get('cash_delta', 0),
                'has_ai_insights': bool(reason.get('ai_insights'))
            })

        # Prepare full playback with historical prices
        result = prepare_full_playback(formatted_events)

        # Don't include raw prices_by_date in response (too large)
        if 'prices_by_date' in result:
            del result['prices_by_date']

        return result

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
