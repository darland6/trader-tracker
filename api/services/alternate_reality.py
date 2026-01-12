"""
Alternate Reality Engine - User-defined "what if" scenarios.

Creates alternate event histories based on user-defined seeds:
- Different starting cash
- Different stock purchases
- Different timing decisions

Replays these with real historical prices to show how they would have performed.
"""

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import yfinance as yf

SCRIPT_DIR = Path(__file__).parent.parent.parent.resolve()
ALT_REALITIES_FILE = SCRIPT_DIR / 'data' / 'alternate_realities.json'


def load_alternate_realities() -> Dict:
    """Load saved alternate realities from file."""
    if ALT_REALITIES_FILE.exists():
        with open(ALT_REALITIES_FILE, 'r') as f:
            return json.load(f)
    return {'realities': []}


def save_alternate_realities(data: Dict) -> None:
    """Save alternate realities to file."""
    ALT_REALITIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ALT_REALITIES_FILE, 'w') as f:
        json.dump(data, f, indent=2, default=str)


def get_historical_prices(tickers: List[str], start_date: str, end_date: str = None) -> Dict:
    """
    Fetch historical prices for tickers between dates.

    Returns dict of {date_str: {ticker: price}}
    """
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')

    prices_by_date = {}

    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(start=start_date, end=end_date)

            for date, row in hist.iterrows():
                date_str = date.strftime('%Y-%m-%d')
                if date_str not in prices_by_date:
                    prices_by_date[date_str] = {}
                prices_by_date[date_str][ticker] = round(row['Close'], 2)
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")

    return prices_by_date


def create_alternate_reality(
    name: str,
    description: str,
    start_date: str,
    starting_cash: float,
    initial_purchases: List[Dict],  # [{ticker, shares, price (optional)}]
    scenario_type: str = "custom"  # "bull", "bear", "custom"
) -> Dict:
    """
    Create a new alternate reality with user-defined seed.

    Args:
        name: Display name for this reality
        description: What this scenario represents
        start_date: When this alternate timeline begins (YYYY-MM-DD)
        starting_cash: Initial cash amount
        initial_purchases: List of {ticker, shares} to buy at start
        scenario_type: Type of scenario for coloring

    Returns:
        The created reality object with ID
    """
    reality_id = uuid.uuid4().hex[:8]

    # Get tickers for price lookup
    tickers = [p['ticker'].upper() for p in initial_purchases]

    # Fetch historical prices from start date to now
    prices_by_date = get_historical_prices(tickers, start_date)

    if not prices_by_date:
        raise ValueError(f"Could not fetch historical prices for {tickers}")

    # Find first date with prices
    sorted_dates = sorted(prices_by_date.keys())
    first_date = sorted_dates[0] if sorted_dates else start_date

    # Generate initial events
    events = []
    remaining_cash = starting_cash

    # Deposit event
    events.append({
        'event_id': f"{reality_id}-001",
        'timestamp': f"{first_date} 09:30:00",
        'event_type': 'DEPOSIT',
        'data': {
            'amount': starting_cash,
            'source': 'Alternate Reality Seed'
        },
        'cash_delta': starting_cash
    })

    # Purchase events
    event_num = 2
    holdings = {}

    for purchase in initial_purchases:
        ticker = purchase['ticker'].upper()
        shares = purchase['shares']

        # Get price from historical data or use provided price
        if purchase.get('price'):
            price = purchase['price']
        elif first_date in prices_by_date and ticker in prices_by_date[first_date]:
            price = prices_by_date[first_date][ticker]
        else:
            # Find first available price
            for date in sorted_dates:
                if ticker in prices_by_date.get(date, {}):
                    price = prices_by_date[date][ticker]
                    break
            else:
                continue  # Skip if no price found

        total_cost = shares * price

        if total_cost > remaining_cash:
            # Adjust shares to fit budget
            shares = int(remaining_cash / price)
            if shares <= 0:
                continue
            total_cost = shares * price

        events.append({
            'event_id': f"{reality_id}-{event_num:03d}",
            'timestamp': f"{first_date} 09:31:00",
            'event_type': 'TRADE',
            'data': {
                'ticker': ticker,
                'action': 'BUY',
                'shares': shares,
                'price': price,
                'total': total_cost
            },
            'cash_delta': -total_cost
        })

        remaining_cash -= total_cost
        holdings[ticker] = shares
        event_num += 1

    # Generate timeline snapshots with historical prices
    snapshots = generate_timeline_snapshots(
        holdings=holdings,
        cash=remaining_cash,
        prices_by_date=prices_by_date,
        start_date=first_date
    )

    # Calculate final values
    last_snapshot = snapshots[-1] if snapshots else None
    final_value = last_snapshot['total_value'] if last_snapshot else starting_cash

    # Determine sentiment color
    if scenario_type == "bull":
        color = "#22c55e"
    elif scenario_type == "bear":
        color = "#ef4444"
    else:
        # Calculate based on performance
        total_return = (final_value - starting_cash) / starting_cash if starting_cash > 0 else 0
        if total_return > 0.1:
            color = "#22c55e"
        elif total_return < -0.1:
            color = "#ef4444"
        else:
            color = "#06b6d4"

    reality = {
        'id': reality_id,
        'name': name,
        'description': description,
        'created_at': datetime.now().isoformat(),
        'scenario_type': scenario_type,
        'color': color,
        'seed': {
            'start_date': start_date,
            'starting_cash': starting_cash,
            'initial_purchases': initial_purchases
        },
        'events': events,
        'holdings': holdings,
        'current_cash': remaining_cash,
        'snapshots': snapshots,
        'summary': {
            'starting_value': starting_cash,
            'current_value': final_value,
            'total_return': final_value - starting_cash,
            'return_pct': ((final_value - starting_cash) / starting_cash * 100) if starting_cash > 0 else 0
        }
    }

    # Save to file
    data = load_alternate_realities()
    data['realities'].append(reality)
    save_alternate_realities(data)

    return reality


def generate_timeline_snapshots(
    holdings: Dict[str, int],
    cash: float,
    prices_by_date: Dict[str, Dict[str, float]],
    start_date: str
) -> List[Dict]:
    """Generate value snapshots for each date in the price history."""
    snapshots = []
    sorted_dates = sorted(prices_by_date.keys())

    prev_value = None

    for date_str in sorted_dates:
        prices = prices_by_date[date_str]

        # Calculate holdings value
        holdings_value = 0
        holdings_breakdown = {}

        for ticker, shares in holdings.items():
            if ticker in prices:
                value = shares * prices[ticker]
                holdings_value += value
                holdings_breakdown[ticker] = {
                    'shares': shares,
                    'price': prices[ticker],
                    'value': value
                }

        total_value = cash + holdings_value

        # Calculate sentiment based on change
        if prev_value is not None:
            change = (total_value - prev_value) / prev_value if prev_value > 0 else 0
            if change > 0.02:
                sentiment = 'bullish'
                sentiment_score = min(1.0, change * 10)
            elif change < -0.02:
                sentiment = 'bearish'
                sentiment_score = max(-1.0, change * 10)
            else:
                sentiment = 'neutral'
                sentiment_score = change * 10
        else:
            sentiment = 'neutral'
            sentiment_score = 0

        snapshots.append({
            'date': date_str,
            'cash': cash,
            'holdings_value': holdings_value,
            'total_value': total_value,
            'holdings': holdings_breakdown,
            'sentiment': sentiment,
            'sentiment_score': round(sentiment_score, 3)
        })

        prev_value = total_value

    return snapshots


def get_alternate_reality(reality_id: str) -> Optional[Dict]:
    """Get a specific alternate reality by ID."""
    data = load_alternate_realities()
    for reality in data['realities']:
        if reality['id'] == reality_id:
            return reality
    return None


def list_alternate_realities() -> List[Dict]:
    """List all alternate realities (summary only)."""
    data = load_alternate_realities()
    return [{
        'id': r['id'],
        'name': r['name'],
        'description': r['description'],
        'created_at': r['created_at'],
        'scenario_type': r['scenario_type'],
        'color': r['color'],
        'summary': r['summary']
    } for r in data['realities']]


def delete_alternate_reality(reality_id: str) -> bool:
    """Delete an alternate reality."""
    data = load_alternate_realities()
    original_count = len(data['realities'])
    data['realities'] = [r for r in data['realities'] if r['id'] != reality_id]

    if len(data['realities']) < original_count:
        save_alternate_realities(data)
        return True
    return False


def refresh_alternate_reality(reality_id: str) -> Optional[Dict]:
    """
    Refresh an alternate reality with updated prices.

    Fetches latest prices and regenerates snapshots.
    """
    data = load_alternate_realities()

    for i, reality in enumerate(data['realities']):
        if reality['id'] == reality_id:
            seed = reality['seed']

            # Get tickers
            tickers = [p['ticker'].upper() for p in seed['initial_purchases']]

            # Fetch fresh prices
            prices_by_date = get_historical_prices(tickers, seed['start_date'])

            if prices_by_date:
                # Regenerate snapshots
                snapshots = generate_timeline_snapshots(
                    holdings=reality['holdings'],
                    cash=reality['current_cash'],
                    prices_by_date=prices_by_date,
                    start_date=seed['start_date']
                )

                reality['snapshots'] = snapshots

                # Update summary
                if snapshots:
                    final_value = snapshots[-1]['total_value']
                    starting_value = seed['starting_cash']
                    reality['summary'] = {
                        'starting_value': starting_value,
                        'current_value': final_value,
                        'total_return': final_value - starting_value,
                        'return_pct': ((final_value - starting_value) / starting_value * 100) if starting_value > 0 else 0
                    }

                data['realities'][i] = reality
                save_alternate_realities(data)

            return reality

    return None


def get_combined_timeline_data() -> Dict:
    """
    Get combined timeline data for all realities including main.

    Returns data structured for the multiverse visualization.
    """
    from reconstruct_state import load_event_log, reconstruct_state

    # Load main portfolio state
    events_df = load_event_log(str(SCRIPT_DIR / 'data' / 'event_log_enhanced.csv'))
    main_state = reconstruct_state(events_df)

    # Get alternate realities
    alt_realities = load_alternate_realities()['realities']

    # Build main reality data
    main_reality = {
        'id': 'main',
        'name': 'Current Reality',
        'description': 'Your actual portfolio',
        'is_main': True,
        'color': '#06b6d4',
        'summary': {
            'starting_value': None,  # Unknown original investment
            'current_value': main_state.get('total_value', 0),
            'total_return': main_state.get('ytd_income', 0),
            'return_pct': None
        },
        'holdings': main_state.get('holdings', {}),
        'cash': main_state.get('cash', 0),
        'snapshots': []  # Would need historical playback for this
    }

    # Combine all realities
    all_realities = [main_reality] + alt_realities

    # Find date range across all realities
    all_dates = set()
    for reality in alt_realities:
        for snapshot in reality.get('snapshots', []):
            all_dates.add(snapshot['date'])

    sorted_dates = sorted(all_dates) if all_dates else [datetime.now().strftime('%Y-%m-%d')]

    return {
        'generated_at': datetime.now().isoformat(),
        'timeline': {
            'start_date': sorted_dates[0] if sorted_dates else None,
            'end_date': sorted_dates[-1] if sorted_dates else None,
            'present_date': datetime.now().strftime('%Y-%m-%d')
        },
        'realities': all_realities,
        'total_realities': len(all_realities)
    }
