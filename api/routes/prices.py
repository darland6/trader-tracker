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
from api.database import sync_csv_to_db, update_price_cache, get_cached_prices, compact_price_events
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
    """Fetch live prices and optionally save to event log with gain/loss tracking."""
    try:
        # Get current state BEFORE price update to calculate changes
        events_df = load_event_log(str(SCRIPT_DIR / 'data' / 'event_log_enhanced.csv'))
        state = reconstruct_state(events_df)

        # Get old prices from state (reconstructed from events)
        old_prices = state.get('latest_prices', {})
        holdings_dict = state.get('holdings', {})  # ticker -> shares
        tickers = [t for t, s in holdings_dict.items() if s > 0]

        # Fetch live prices with extended hours support
        price_data = fetch_live_prices(tickers, include_extended=True)

        if not price_data:
            raise HTTPException(status_code=500, detail="Failed to fetch prices")

        # Extract just prices for cache and event log
        prices = {ticker: data['price'] for ticker, data in price_data.items()}

        # Calculate portfolio gain/loss from this price update
        portfolio_before = state.get('portfolio_value', 0)
        portfolio_after = 0
        price_changes = {}

        for ticker, new_price in prices.items():
            old_price = old_prices.get(ticker, new_price)
            shares = holdings_dict.get(ticker, 0)
            if shares > 0:
                portfolio_after += shares * new_price
                change_pct = ((new_price - old_price) / old_price * 100) if old_price > 0 else 0
                change_value = shares * (new_price - old_price)
                price_changes[ticker] = {
                    'old_price': old_price,
                    'new_price': new_price,
                    'change_pct': round(change_pct, 2),
                    'change_value': round(change_value, 2),
                    'shares': shares
                }

        portfolio_change = portfolio_after - portfolio_before
        portfolio_change_pct = (portfolio_change / portfolio_before * 100) if portfolio_before > 0 else 0

        # Update cache with session info
        update_price_cache(price_data)

        # Save to event log if requested
        event_id = None
        if save_to_log:
            event_id = create_price_update_event_with_changes(
                prices,
                price_changes,
                portfolio_before,
                portfolio_after,
                portfolio_change,
                portfolio_change_pct
            )
            sync_csv_to_db()

            # Compact price events - keep only first and last of each day
            compacted = compact_price_events()

        # Get current market session
        is_open, current_session = is_market_hours()

        return ApiResponse(
            success=True,
            message=f"Updated prices for {len(prices)} tickers (portfolio {'+' if portfolio_change >= 0 else ''}{portfolio_change:,.0f})",
            event_id=event_id,
            data={
                "prices": price_data,
                "market_session": current_session,
                "market_open": is_open,
                "portfolio_change": round(portfolio_change, 2),
                "portfolio_change_pct": round(portfolio_change_pct, 2),
                "price_changes": price_changes
            }
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def create_price_update_event_with_changes(prices, price_changes, portfolio_before, portfolio_after, portfolio_change, portfolio_change_pct):
    """Create a PRICE_UPDATE event with gain/loss information."""
    from cli.events import append_event

    data = {
        "prices": prices,
        "source": "yfinance",
        "price_changes": price_changes,
        "portfolio_before": round(portfolio_before, 2),
        "portfolio_after": round(portfolio_after, 2),
        "portfolio_change": round(portfolio_change, 2),
        "portfolio_change_pct": round(portfolio_change_pct, 2)
    }

    reason = {
        "primary": "PRICE_UPDATE",
        "analysis": f"Portfolio {'gained' if portfolio_change >= 0 else 'lost'} ${abs(portfolio_change):,.0f} ({portfolio_change_pct:+.1f}%)"
    }

    change_str = f"{'+' if portfolio_change >= 0 else ''}{portfolio_change:,.0f}"
    notes = f"Price update: Portfolio {change_str} ({portfolio_change_pct:+.1f}%)"

    return append_event("PRICE_UPDATE", data, reason, notes, ["prices", "market_data"], False, 0, skip_ai=True)
