"""Historical price fetching for accurate playback interpolation."""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.parent.parent.resolve()


def fetch_historical_prices(
    tickers: List[str],
    start_date: str,
    end_date: str
) -> Dict[str, Dict[str, float]]:
    """
    Fetch historical daily closing prices for multiple tickers.

    Args:
        tickers: List of stock symbols
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        Dict mapping date strings to {ticker: price} dicts
        Example: {"2026-01-05": {"TSLA": 445.0, "PLTR": 177.0}, ...}
    """
    if not tickers:
        return {}

    # Add buffer days to ensure we have data for start/end
    start = datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=5)
    end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)

    prices_by_date = {}

    try:
        # Fetch all tickers at once for efficiency
        data = yf.download(
            tickers,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            progress=False,
            auto_adjust=True
        )

        if data.empty:
            return {}

        # Handle single ticker case (different DataFrame structure)
        if len(tickers) == 1:
            ticker = tickers[0]
            for date_idx in data.index:
                date_str = date_idx.strftime("%Y-%m-%d")
                price = data.loc[date_idx, 'Close']
                if pd.notna(price):
                    prices_by_date[date_str] = {ticker: round(float(price), 2)}
        else:
            # Multiple tickers - 'Close' is a DataFrame with ticker columns
            close_prices = data['Close']
            for date_idx in close_prices.index:
                date_str = date_idx.strftime("%Y-%m-%d")
                prices_by_date[date_str] = {}
                for ticker in tickers:
                    if ticker in close_prices.columns:
                        price = close_prices.loc[date_idx, ticker]
                        if pd.notna(price):
                            prices_by_date[date_str][ticker] = round(float(price), 2)

    except Exception as e:
        print(f"[Historical Prices] Error fetching data: {e}")
        return {}

    return prices_by_date


def get_price_at_date(
    prices_by_date: Dict[str, Dict[str, float]],
    target_date: str,
    ticker: str
) -> float:
    """
    Get price for a ticker at a specific date, with fallback to nearest date.
    """
    # Try exact date
    if target_date in prices_by_date:
        if ticker in prices_by_date[target_date]:
            return prices_by_date[target_date][ticker]

    # Find nearest earlier date
    sorted_dates = sorted(prices_by_date.keys())
    for date in reversed(sorted_dates):
        if date <= target_date and ticker in prices_by_date.get(date, {}):
            return prices_by_date[date][ticker]

    # Find nearest later date as last resort
    for date in sorted_dates:
        if date > target_date and ticker in prices_by_date.get(date, {}):
            return prices_by_date[date][ticker]

    return 0.0


def generate_playback_frames(
    events: List[dict],
    prices_by_date: Dict[str, Dict[str, float]],
    frames_per_day: int = 1
) -> List[dict]:
    """
    Generate playback frames with interpolated portfolio values.

    Args:
        events: List of portfolio events in chronological order
        prices_by_date: Historical prices from fetch_historical_prices
        frames_per_day: How many frames to generate per day (1 = daily)

    Returns:
        List of frame objects with portfolio state at each point
    """
    from reconstruct_state import load_event_log, reconstruct_state
    import pandas as pd

    if not events:
        return []

    frames = []

    # Get all unique dates from events
    event_dates = sorted(set(
        e['timestamp'].split(' ')[0] if isinstance(e.get('timestamp'), str)
        else e['timestamp'].strftime('%Y-%m-%d')
        for e in events
    ))

    if not event_dates:
        return []

    start_date = datetime.strptime(event_dates[0], "%Y-%m-%d")
    end_date = datetime.strptime(event_dates[-1], "%Y-%m-%d")

    # Load events from CSV (proper format for reconstruct_state)
    csv_path = SCRIPT_DIR / 'data' / 'event_log_enhanced.csv'
    full_events_df = load_event_log(str(csv_path))

    # Generate frames for each day in range
    current_date = start_date

    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")

        # Find all events on or before this date
        events_up_to_date = []
        for e in events:
            event_date = e['timestamp'].split(' ')[0] if isinstance(e.get('timestamp'), str) else e['timestamp'].strftime('%Y-%m-%d')
            if event_date <= date_str:
                events_up_to_date.append(e)

        if not events_up_to_date:
            current_date += timedelta(days=1)
            continue

        # Get the last event ID up to this date
        last_event_id = events_up_to_date[-1]['event_id']

        # Filter DataFrame to events up to this point
        filtered_df = full_events_df[full_events_df['event_id'] <= last_event_id]

        # Reconstruct state at this point
        state = reconstruct_state(filtered_df)

        # Apply historical prices for this date
        holdings = state.get('holdings', {})
        holdings_value = {}
        total_holdings_value = 0

        for ticker, shares in holdings.items():
            if shares > 0:
                # Use historical price if available, otherwise latest from state
                price = get_price_at_date(prices_by_date, date_str, ticker)
                if price == 0:
                    price = state.get('latest_prices', {}).get(ticker, 0)

                value = shares * price
                holdings_value[ticker] = {
                    'shares': shares,
                    'price': price,
                    'value': round(value, 2)
                }
                total_holdings_value += value

        cash = state.get('cash', 0)

        # Find which event applies at this date
        current_event = events_up_to_date[-1] if events_up_to_date else None

        frame = {
            'date': date_str,
            'timestamp': f"{date_str} 16:00:00",  # Market close
            'event_id': last_event_id,
            'event_type': current_event.get('event_type', 'N/A') if current_event else 'N/A',
            'event_summary': current_event.get('summary', '') if current_event else '',
            'is_event_day': date_str in event_dates,
            'cash': round(cash, 2),
            'holdings_value': holdings_value,
            'total_holdings': round(total_holdings_value, 2),
            'total_value': round(cash + total_holdings_value, 2),
            'active_options': state.get('active_options', []),
            'ytd_income': round(
                state.get('ytd_option_income', 0) + state.get('ytd_trading_gains', 0), 2
            )
        }

        frames.append(frame)
        current_date += timedelta(days=1)

    return frames


def prepare_full_playback(events: List[dict]) -> dict:
    """
    Prepare complete playback data with historical prices.

    This may take a while as it fetches historical data from yfinance.

    Returns:
        {
            'frames': [...],  # Daily frames with real prices
            'events': [...],  # Original events
            'date_range': {'start': '...', 'end': '...'},
            'tickers': [...],
            'total_frames': N,
            'total_events': N
        }
    """
    if not events:
        return {'frames': [], 'events': [], 'date_range': {}, 'tickers': [], 'total_frames': 0, 'total_events': 0}

    # Get date range
    dates = [
        e['timestamp'].split(' ')[0] if isinstance(e.get('timestamp'), str)
        else e['timestamp'].strftime('%Y-%m-%d')
        for e in events
    ]
    start_date = min(dates)
    end_date = max(dates)

    # Get all tickers from events
    tickers = set()
    for e in events:
        data = e.get('data', {})
        if isinstance(data, str):
            import json
            try:
                data = json.loads(data)
            except:
                data = {}
        if 'ticker' in data:
            tickers.add(data['ticker'].upper())

    # Also get tickers from starting state
    starting_state_path = SCRIPT_DIR / 'data' / 'starting_state.json'
    if starting_state_path.exists():
        import json
        with open(starting_state_path) as f:
            starting_state = json.load(f)
            for ticker in starting_state.get('holdings', {}).keys():
                tickers.add(ticker.upper())

    tickers = list(tickers)

    print(f"[Playback] Fetching historical prices for {len(tickers)} tickers from {start_date} to {end_date}...")

    # Fetch historical prices
    prices_by_date = fetch_historical_prices(tickers, start_date, end_date)

    print(f"[Playback] Got prices for {len(prices_by_date)} trading days")

    # Generate frames
    frames = generate_playback_frames(events, prices_by_date)

    print(f"[Playback] Generated {len(frames)} playback frames")

    return {
        'frames': frames,
        'events': events,
        'date_range': {'start': start_date, 'end': end_date},
        'tickers': tickers,
        'total_frames': len(frames),
        'total_events': len(events),
        'prices_by_date': prices_by_date  # Include raw price data
    }
