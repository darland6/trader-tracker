"""Price update routes."""

from fastapi import APIRouter, HTTPException
import sys
from pathlib import Path
from datetime import datetime
import pytz

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import yfinance as yf
from api.models import ApiResponse
from cli.events import create_price_update_event
from api.database import sync_csv_to_db, update_price_cache, get_cached_prices
from reconstruct_state import load_event_log, reconstruct_state

router = APIRouter(prefix="/api", tags=["prices"])

SCRIPT_DIR = Path(__file__).parent.parent.parent.resolve()


def is_market_hours() -> tuple[bool, str]:
    """Check if US stock market is currently open.
    Returns (is_open, session_type) where session_type is 'regular', 'pre', 'post', or 'closed'.
    """
    try:
        eastern = pytz.timezone('US/Eastern')
        now = datetime.now(eastern)
        weekday = now.weekday()

        # Closed on weekends
        if weekday >= 5:
            return False, 'closed'

        hour = now.hour
        minute = now.minute
        current_time = hour * 60 + minute

        # Pre-market: 4:00 AM - 9:30 AM ET
        pre_market_start = 4 * 60  # 4:00 AM
        market_open = 9 * 60 + 30  # 9:30 AM

        # Regular hours: 9:30 AM - 4:00 PM ET
        market_close = 16 * 60  # 4:00 PM

        # Post-market: 4:00 PM - 8:00 PM ET
        post_market_end = 20 * 60  # 8:00 PM

        if pre_market_start <= current_time < market_open:
            return True, 'pre'
        elif market_open <= current_time < market_close:
            return True, 'regular'
        elif market_close <= current_time < post_market_end:
            return True, 'post'
        else:
            return False, 'closed'
    except Exception:
        return False, 'unknown'


def fetch_live_prices(tickers: list, include_extended: bool = True) -> dict:
    """Fetch current prices from yfinance, including extended hours if available.

    Returns dict with ticker -> {price, session} where session is 'regular', 'pre', 'post', or 'closed'.
    """
    prices = {}
    is_open, session = is_market_hours()

    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)

            # Get basic price info
            price = None
            price_session = session

            # Try to get the most current price
            if include_extended and session in ('pre', 'post'):
                # During extended hours, try to get pre/post market price
                try:
                    # Get recent history with prepost=True to include extended hours
                    hist = t.history(period='1d', prepost=True)
                    if not hist.empty:
                        price = round(hist['Close'].iloc[-1], 2)
                except Exception:
                    pass

            # Fallback to regular price
            if price is None:
                price = t.fast_info.get('lastPrice')
                if price:
                    price = round(price, 2)
                    # If market is closed, this is the last regular session price
                    if session == 'closed':
                        price_session = 'closed'

            if price:
                prices[ticker] = {
                    'price': price,
                    'session': price_session
                }
        except Exception:
            pass

    return prices


@router.get("/prices")
async def get_prices():
    """Get current cached prices with session info."""
    cached = get_cached_prices()
    is_open, current_session = is_market_hours()

    return {
        "prices": {ticker: data['price'] for ticker, data in cached.items()},
        "cache_info": cached,
        "market_session": current_session,
        "market_open": is_open
    }


@router.post("/prices/update", response_model=ApiResponse)
async def update_prices(save_to_log: bool = True):
    """Fetch live prices and optionally save to event log."""
    try:
        # Get current holdings
        events_df = load_event_log(str(SCRIPT_DIR / 'event_log_enhanced.csv'))
        state = reconstruct_state(events_df)
        tickers = list(state.get('holdings', {}).keys())

        # Fetch live prices with extended hours support
        price_data = fetch_live_prices(tickers, include_extended=True)

        if not price_data:
            raise HTTPException(status_code=500, detail="Failed to fetch prices")

        # Extract just prices for cache and event log
        prices = {ticker: data['price'] for ticker, data in price_data.items()}

        # Update cache with session info
        update_price_cache(price_data)

        # Save to event log if requested
        event_id = None
        if save_to_log:
            event_id = create_price_update_event(prices)
            sync_csv_to_db()

        # Get current market session
        is_open, current_session = is_market_hours()

        return ApiResponse(
            success=True,
            message=f"Updated prices for {len(prices)} tickers",
            event_id=event_id,
            data={
                "prices": price_data,
                "market_session": current_session,
                "market_open": is_open
            }
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
