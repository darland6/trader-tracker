"""Historical price fetching for accurate playback interpolation.

Data sources (in priority order):
1. yfinance - Real historical market data
2. Agent/Dexter - Research tool for missing data
3. Interpolation - Smart fill between known data points
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import json

SCRIPT_DIR = Path(__file__).parent.parent.parent.resolve()

# Cache for prices fetched via agent
AGENT_PRICE_CACHE_FILE = SCRIPT_DIR / "data" / "agent_price_cache.json"


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


def load_agent_price_cache() -> Dict[str, Dict[str, float]]:
    """Load cached prices from agent research."""
    if AGENT_PRICE_CACHE_FILE.exists():
        try:
            with open(AGENT_PRICE_CACHE_FILE) as f:
                return json.load(f)
        except:
            pass
    return {}


def save_agent_price_cache(cache: Dict[str, Dict[str, float]]):
    """Save agent-researched prices to cache."""
    AGENT_PRICE_CACHE_FILE.parent.mkdir(exist_ok=True)
    with open(AGENT_PRICE_CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)


def fetch_price_via_agent(ticker: str, date: str) -> Optional[float]:
    """
    Use the agent/Dexter to research a historical price.

    This is a fallback when yfinance doesn't have data.
    """
    try:
        from integrations.dexter import DexterClient

        client = DexterClient()
        if not client.is_available():
            return None

        # Query Dexter for historical price
        query = f"What was the closing price of {ticker} on {date}? Just the number."
        response = client.research(query, max_tokens=100)

        if response and response.get('answer'):
            # Try to extract price from response
            import re
            answer = response['answer']
            # Look for dollar amounts or plain numbers
            matches = re.findall(r'\$?([\d,]+\.?\d*)', answer)
            if matches:
                price_str = matches[0].replace(',', '')
                price = float(price_str)
                if 0.01 < price < 100000:  # Sanity check
                    return price

    except Exception as e:
        print(f"[Agent Price] Error fetching {ticker} for {date}: {e}")

    return None


def interpolate_missing_prices(
    prices_by_date: Dict[str, Dict[str, float]],
    tickers: List[str],
    start_date: str,
    end_date: str
) -> Dict[str, Dict[str, float]]:
    """
    Fill in missing prices using linear interpolation.

    For each ticker, finds gaps in the data and interpolates between
    known price points. This ensures smooth animations even when
    market data is unavailable (weekends, holidays, data gaps).
    """
    if not prices_by_date or not tickers:
        return prices_by_date

    # Generate all dates in range
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    all_dates = []
    current = start
    while current <= end:
        all_dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)

    # For each ticker, interpolate missing values
    for ticker in tickers:
        # Collect known prices for this ticker
        known_prices = []
        for date in sorted(prices_by_date.keys()):
            if ticker in prices_by_date.get(date, {}):
                known_prices.append((date, prices_by_date[date][ticker]))

        if len(known_prices) < 2:
            continue  # Can't interpolate with less than 2 points

        # Create interpolation function
        known_dates = [datetime.strptime(d, "%Y-%m-%d").timestamp() for d, _ in known_prices]
        known_values = [p for _, p in known_prices]

        # Fill in missing dates
        for date in all_dates:
            if date not in prices_by_date:
                prices_by_date[date] = {}

            if ticker not in prices_by_date[date]:
                date_ts = datetime.strptime(date, "%Y-%m-%d").timestamp()

                # Check if date is within our known range
                if known_dates[0] <= date_ts <= known_dates[-1]:
                    # Linear interpolation
                    interpolated = np.interp(date_ts, known_dates, known_values)
                    prices_by_date[date][ticker] = round(float(interpolated), 2)

    return prices_by_date


def fetch_prices_with_fallback(
    tickers: List[str],
    start_date: str,
    end_date: str,
    use_agent: bool = True,
    use_interpolation: bool = True
) -> Tuple[Dict[str, Dict[str, float]], Dict[str, str]]:
    """
    Fetch historical prices with multi-layer fallback.

    Priority:
    1. yfinance (real market data)
    2. Agent/Dexter (research missing data)
    3. Interpolation (fill gaps)

    Args:
        tickers: List of stock symbols
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        use_agent: Whether to use agent for missing data
        use_interpolation: Whether to interpolate remaining gaps

    Returns:
        Tuple of (prices_by_date, data_sources)
        data_sources maps "ticker:date" to source ("yfinance", "agent", "interpolated")
    """
    data_sources = {}

    # Step 1: Fetch from yfinance
    print(f"[Prices] Fetching {len(tickers)} tickers from yfinance...")
    prices_by_date = fetch_historical_prices(tickers, start_date, end_date)

    # Track yfinance sources
    for date, ticker_prices in prices_by_date.items():
        for ticker in ticker_prices:
            data_sources[f"{ticker}:{date}"] = "yfinance"

    print(f"[Prices] Got {len(prices_by_date)} days from yfinance")

    # Step 2: Check agent cache and fetch missing via agent
    if use_agent:
        agent_cache = load_agent_price_cache()
        agent_fetched = 0

        # Generate all dates in range
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        current = start

        while current <= end:
            date_str = current.strftime("%Y-%m-%d")

            for ticker in tickers:
                # Check if we already have this price
                if date_str in prices_by_date and ticker in prices_by_date[date_str]:
                    current += timedelta(days=1)
                    continue

                # Check agent cache
                cache_key = f"{ticker}:{date_str}"
                if cache_key in agent_cache:
                    if date_str not in prices_by_date:
                        prices_by_date[date_str] = {}
                    prices_by_date[date_str][ticker] = agent_cache[cache_key]
                    data_sources[cache_key] = "agent_cached"
                    continue

                # Skip weekends (agent won't have data either)
                if current.weekday() >= 5:
                    current += timedelta(days=1)
                    continue

                # Try fetching via agent (limit to avoid too many calls)
                if agent_fetched < 10:  # Limit agent calls per request
                    price = fetch_price_via_agent(ticker, date_str)
                    if price:
                        if date_str not in prices_by_date:
                            prices_by_date[date_str] = {}
                        prices_by_date[date_str][ticker] = price
                        agent_cache[cache_key] = price
                        data_sources[cache_key] = "agent"
                        agent_fetched += 1

            current += timedelta(days=1)

        # Save agent cache
        if agent_fetched > 0:
            save_agent_price_cache(agent_cache)
            print(f"[Prices] Fetched {agent_fetched} prices via agent")

    # Step 3: Interpolate remaining gaps
    if use_interpolation:
        before_count = sum(len(p) for p in prices_by_date.values())
        prices_by_date = interpolate_missing_prices(prices_by_date, tickers, start_date, end_date)
        after_count = sum(len(p) for p in prices_by_date.values())

        interpolated_count = after_count - before_count
        if interpolated_count > 0:
            print(f"[Prices] Interpolated {interpolated_count} price points")

        # Track interpolated sources
        for date, ticker_prices in prices_by_date.items():
            for ticker in ticker_prices:
                key = f"{ticker}:{date}"
                if key not in data_sources:
                    data_sources[key] = "interpolated"

    return prices_by_date, data_sources


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


def prepare_full_playback(
    events: List[dict],
    use_agent: bool = True,
    use_interpolation: bool = True,
    history_id: str = "reality"
) -> dict:
    """
    Prepare complete playback data with historical prices.

    Uses multi-layer fallback:
    1. yfinance for market data
    2. Agent/Dexter for missing data
    3. Interpolation for remaining gaps

    Args:
        events: List of portfolio events
        use_agent: Whether to use agent for missing prices
        use_interpolation: Whether to interpolate gaps
        history_id: "reality" or an alternate history ID

    Returns:
        {
            'frames': [...],  # Daily frames with real/interpolated prices
            'events': [...],  # Original events
            'date_range': {'start': '...', 'end': '...'},
            'tickers': [...],
            'total_frames': N,
            'total_events': N,
            'data_quality': {...}  # Stats about data sources
        }
    """
    if not events:
        return {
            'frames': [], 'events': [], 'date_range': {},
            'tickers': [], 'total_frames': 0, 'total_events': 0,
            'history_id': history_id
        }

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
            try:
                data = json.loads(data)
            except:
                data = {}
        if 'ticker' in data:
            tickers.add(data['ticker'].upper())

    # Also get tickers from starting state
    starting_state_path = SCRIPT_DIR / 'data' / 'starting_state.json'
    if starting_state_path.exists():
        with open(starting_state_path) as f:
            starting_state = json.load(f)
            for ticker in starting_state.get('holdings', {}).keys():
                tickers.add(ticker.upper())

    tickers = list(tickers)

    print(f"[Playback] Preparing {history_id} timeline with {len(tickers)} tickers from {start_date} to {end_date}...")

    # Fetch historical prices with fallback
    prices_by_date, data_sources = fetch_prices_with_fallback(
        tickers, start_date, end_date,
        use_agent=use_agent,
        use_interpolation=use_interpolation
    )

    # Calculate data quality stats
    source_counts = {}
    for source in data_sources.values():
        source_counts[source] = source_counts.get(source, 0) + 1

    total_points = len(data_sources)
    data_quality = {
        "total_data_points": total_points,
        "sources": source_counts,
        "yfinance_pct": round(source_counts.get("yfinance", 0) / total_points * 100, 1) if total_points > 0 else 0,
        "interpolated_pct": round(source_counts.get("interpolated", 0) / total_points * 100, 1) if total_points > 0 else 0,
        "agent_pct": round((source_counts.get("agent", 0) + source_counts.get("agent_cached", 0)) / total_points * 100, 1) if total_points > 0 else 0
    }

    print(f"[Playback] Data quality: {data_quality['yfinance_pct']}% yfinance, {data_quality['interpolated_pct']}% interpolated")

    # Generate frames
    frames = generate_playback_frames(events, prices_by_date)

    print(f"[Playback] Generated {len(frames)} daily frames")

    return {
        'frames': frames,
        'events': events,
        'date_range': {'start': start_date, 'end': end_date},
        'tickers': tickers,
        'total_frames': len(frames),
        'total_events': len(events),
        'history_id': history_id,
        'data_quality': data_quality,
        'prices_by_date': prices_by_date  # Include raw price data
    }


def prepare_alt_history_playback(
    history_id: str,
    use_agent: bool = True,
    use_interpolation: bool = True
) -> dict:
    """
    Prepare playback data for an alternate history timeline.

    Args:
        history_id: The alternate history ID
        use_agent: Whether to use agent for missing prices
        use_interpolation: Whether to interpolate gaps

    Returns:
        Same structure as prepare_full_playback
    """
    from api.services.alt_history import get_history_events, get_history

    # Load alternate history events
    events_df = get_history_events(history_id)
    if events_df is None:
        return {"error": f"History {history_id} not found"}

    history_meta = get_history(history_id)

    # Convert DataFrame to list of dicts
    events = []
    for _, row in events_df.iterrows():
        data = row.get('data', {})
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except:
                data = {}

        events.append({
            'event_id': row['event_id'],
            'timestamp': str(row['timestamp']),
            'event_type': row['event_type'],
            'data': data,
            'summary': f"{row['event_type']}: {data.get('ticker', data.get('action', ''))}",
            'cash_delta': row.get('cash_delta', 0)
        })

    result = prepare_full_playback(
        events,
        use_agent=use_agent,
        use_interpolation=use_interpolation,
        history_id=history_id
    )

    # Add history metadata
    if history_meta:
        result['history_name'] = history_meta.get('name', history_id)
        result['history_description'] = history_meta.get('description', '')

    return result
