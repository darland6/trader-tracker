"""
Consolidated Realities Module - Alternate histories, reality engine, and projections.

This module combines functionality from:
- api/services/alt_history.py - Alternate history creation and modification
- api/services/alternate_reality.py - Reality engine and comparison
- api/services/reality_projections.py - Future projections and LLM analysis

Key Features:
1. Alternate History Management (from alt_history.py)
   - Create alternate portfolio histories based on modifications
   - Compare histories against reality or each other
   - LLM-powered modification generation

2. Simple Reality Engine (from alternate_reality.py)
   - User-defined "what if" scenarios with specific starting conditions
   - Historical price replay for alternate portfolios
   - Predefined scenario templates

3. Future Projections (from reality_projections.py)
   - LLM-powered timeline generation
   - Bull/bear/base case scenarios
   - Macro event simulation
"""

import json
import uuid
import shutil
import re
import math
import hashlib
import asyncio
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd
import yfinance as yf

# =============================================================================
# Storage Configuration
# =============================================================================

SCRIPT_DIR = Path(__file__).parent.parent.resolve()
DATA_DIR = SCRIPT_DIR / "data"
ALT_HISTORIES_DIR = DATA_DIR / "alt_histories"
ALT_HISTORIES_INDEX = ALT_HISTORIES_DIR / "index.json"
ALT_REALITIES_FILE = DATA_DIR / "alternate_realities.json"
PROJECTIONS_DIR = DATA_DIR / "projections"


def ensure_storage():
    """Ensure storage directories exist."""
    ALT_HISTORIES_DIR.mkdir(parents=True, exist_ok=True)
    PROJECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    if not ALT_HISTORIES_INDEX.exists():
        with open(ALT_HISTORIES_INDEX, 'w') as f:
            json.dump({"histories": []}, f)


# =============================================================================
# Part 1: Alternate History Management (from alt_history.py)
# =============================================================================

def load_index() -> dict:
    """Load the alternate histories index."""
    ensure_storage()
    with open(ALT_HISTORIES_INDEX) as f:
        return json.load(f)


def save_index(index: dict):
    """Save the alternate histories index."""
    ensure_storage()
    with open(ALT_HISTORIES_INDEX, 'w') as f:
        json.dump(index, f, indent=2, default=str)


def list_histories() -> list:
    """List all alternate histories."""
    index = load_index()
    return index.get("histories", [])


def get_history(history_id: str) -> Optional[dict]:
    """Get a specific alternate history metadata."""
    histories = list_histories()
    for h in histories:
        if h["id"] == history_id:
            return h
    return None


def get_history_events(history_id: str) -> Optional[pd.DataFrame]:
    """Load the event log for an alternate history."""
    history = get_history(history_id)
    if not history:
        return None

    event_file = ALT_HISTORIES_DIR / f"{history_id}.csv"
    if not event_file.exists():
        return None

    df = pd.read_csv(event_file)
    df['data'] = df['data_json'].apply(json.loads)
    df = df.drop('data_json', axis=1)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df.sort_values('timestamp')


def create_history(name: str, description: str = "", modifications: list = None, use_llm: bool = True) -> dict:
    """Create a new alternate history.

    Args:
        name: Display name for this reality
        description: What-if scenario description
        modifications: List of modification rules to apply
        use_llm: Whether to use LLM to interpret description and generate modifications

    Returns:
        The created history metadata with processing status
    """
    ensure_storage()

    history_id = str(uuid.uuid4())[:8]

    # Copy the real event log as base
    real_events = DATA_DIR / "event_log_enhanced.csv"
    alt_events = ALT_HISTORIES_DIR / f"{history_id}.csv"
    shutil.copy(real_events, alt_events)

    # If description provided but no modifications, use LLM to generate them
    llm_generated = False
    llm_analysis = None
    if description and not modifications and use_llm:
        result = generate_modifications_from_description(description, history_id)
        if result:
            modifications = result.get("modifications", [])
            llm_analysis = result.get("analysis", {})
            llm_generated = True

    # Apply modifications if provided
    if modifications:
        apply_modifications(history_id, modifications)

    # Create metadata
    history = {
        "id": history_id,
        "name": name,
        "description": description,
        "created_at": datetime.now().isoformat(),
        "modified_at": datetime.now().isoformat(),
        "modifications": modifications or [],
        "event_count": len(pd.read_csv(alt_events)),
        "llm_generated": llm_generated,
        "llm_analysis": llm_analysis,
        "status": "ready"
    }

    # Add to index
    index = load_index()
    index["histories"].append(history)
    save_index(index)

    return history


def generate_modifications_from_description(description: str, history_id: str) -> Optional[dict]:
    """Use LLM to interpret a scenario description and generate modifications.

    Args:
        description: Natural language description of the what-if scenario
        history_id: The history ID to analyze

    Returns:
        Dictionary with modifications and analysis, or None if LLM unavailable
    """
    try:
        from llm.config import get_llm_config
        from llm.client import get_llm_response

        config = get_llm_config()
        if not config.enabled:
            return None

        # Load current holdings to understand the portfolio
        from reconstruct_state import load_event_log, reconstruct_state
        events = load_event_log(str(DATA_DIR / "event_log_enhanced.csv"))
        state = reconstruct_state(events)

        holdings_summary = "\n".join([
            f"- {ticker}: {shares:.0f} shares"
            for ticker, shares in state.get('holdings', {}).items()
            if shares > 0.01
        ])

        prompt = f"""You are analyzing a portfolio to create an alternate reality scenario.

CURRENT HOLDINGS:
{holdings_summary}

USER'S SCENARIO DESCRIPTION:
"{description}"

Based on this description, generate modifications to transform this portfolio into the alternate reality.

Available modification types:
1. remove_ticker - Remove all trades for a ticker: {{"type": "remove_ticker", "ticker": "TSLA"}}
2. scale_position - Scale shares up/down: {{"type": "scale_position", "ticker": "TSLA", "scale": 2.0}}
3. add_trade - Add a hypothetical trade: {{"type": "add_trade", "ticker": "NVDA", "action": "BUY", "shares": 100, "price": 500, "timestamp": "2024-01-15"}}

Interpret the user's intent and generate appropriate modifications.

Respond ONLY in JSON format (no explanation text before or after):
{{
    "analysis": {{
        "interpretation": "What the user wants to explore",
        "key_changes": ["List of main changes being made"],
        "expected_impact": "How this will affect the portfolio"
    }},
    "modifications": [
        {{"type": "...", ...}},
        ...
    ]
}}

If the scenario is about market conditions (bull/bear) rather than specific trades, respond with empty modifications but explain in analysis that projections will reflect this."""

        response = get_llm_response(prompt, max_tokens=1500)
        if not response:
            return None

        # Parse JSON from response - handle <think> tags and other prefixes
        try:
            # Remove <think>...</think> tags if present
            clean_response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)

            # Find JSON object
            json_start = clean_response.find('{')
            json_end = clean_response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = clean_response[json_start:json_end]
                result = json.loads(json_str)
                return result
        except json.JSONDecodeError as e:
            print(f"LLM response JSON parse failed: {e}")
            print(f"Response was: {response[:500]}")
            pass

        return None

    except Exception as e:
        print(f"LLM modification generation failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def apply_modifications(history_id: str, modifications: list):
    """Apply modification rules to an alternate history.

    Modification types:
    - remove_events: Remove events matching criteria
    - add_event: Add a new event
    - modify_event: Change an existing event
    - what_if_price: Change price at a point in time
    - what_if_trade: Add/remove a hypothetical trade
    """
    event_file = ALT_HISTORIES_DIR / f"{history_id}.csv"
    df = pd.read_csv(event_file)

    for mod in modifications:
        mod_type = mod.get("type")

        if mod_type == "remove_ticker":
            # Remove all events for a ticker
            ticker = mod.get("ticker")
            df = df[~df['data_json'].str.contains(f'"ticker": "{ticker}"', na=False)]

        elif mod_type == "remove_event":
            # Remove specific event by ID
            event_id = mod.get("event_id")
            df = df[df['event_id'] != event_id]

        elif mod_type == "add_trade":
            # Add a hypothetical trade
            new_event = {
                "event_id": df['event_id'].max() + 1,
                "timestamp": mod.get("timestamp", datetime.now().isoformat()),
                "event_type": "TRADE",
                "data_json": json.dumps({
                    "action": mod.get("action", "BUY"),
                    "ticker": mod.get("ticker"),
                    "shares": mod.get("shares"),
                    "price": mod.get("price"),
                    "total": mod.get("shares", 0) * mod.get("price", 0),
                    "source": "ALTERNATE_REALITY"
                }),
                "reason_json": json.dumps({"primary": "WHAT_IF_SCENARIO"}),
                "notes": mod.get("notes", "Alternate reality trade"),
                "tags_json": '["alternate", "what-if"]',
                "affects_cash": True,
                "cash_delta": -mod.get("shares", 0) * mod.get("price", 0) if mod.get("action") == "BUY" else mod.get("shares", 0) * mod.get("price", 0)
            }
            df = pd.concat([df, pd.DataFrame([new_event])], ignore_index=True)

        elif mod_type == "change_trade_price":
            # What if I bought at a different price?
            event_id = mod.get("event_id")
            new_price = mod.get("price")

            idx = df[df['event_id'] == event_id].index
            if len(idx) > 0:
                row = df.loc[idx[0]]
                data = json.loads(row['data_json'])
                old_total = data.get('total', 0)
                data['price'] = new_price
                data['total'] = data.get('shares', 0) * new_price
                df.loc[idx[0], 'data_json'] = json.dumps(data)
                # Update cash delta
                if data.get('action') == 'BUY':
                    df.loc[idx[0], 'cash_delta'] = -data['total']
                else:
                    df.loc[idx[0], 'cash_delta'] = data['total']

        elif mod_type == "scale_position":
            # What if I bought more/less shares?
            ticker = mod.get("ticker")
            scale = mod.get("scale", 1.0)  # 2.0 = double, 0.5 = half

            for idx, row in df.iterrows():
                if f'"ticker": "{ticker}"' in row['data_json']:
                    data = json.loads(row['data_json'])
                    if 'shares' in data:
                        data['shares'] = data['shares'] * scale
                        data['total'] = data.get('total', 0) * scale
                        df.loc[idx, 'data_json'] = json.dumps(data)
                        df.loc[idx, 'cash_delta'] = row['cash_delta'] * scale

    # Re-sort and re-index
    df = df.sort_values('timestamp')
    df['event_id'] = range(1, len(df) + 1)

    # Save
    df.to_csv(event_file, index=False)


def update_history(history_id: str, updates: dict) -> Optional[dict]:
    """Update history metadata."""
    index = load_index()

    for i, h in enumerate(index["histories"]):
        if h["id"] == history_id:
            h.update(updates)
            h["modified_at"] = datetime.now().isoformat()
            index["histories"][i] = h
            save_index(index)
            return h

    return None


def delete_history(history_id: str) -> bool:
    """Delete an alternate history."""
    index = load_index()

    # Remove from index
    index["histories"] = [h for h in index["histories"] if h["id"] != history_id]
    save_index(index)

    # Delete event file
    event_file = ALT_HISTORIES_DIR / f"{history_id}.csv"
    if event_file.exists():
        event_file.unlink()

    return True


def compare_histories(history_id_1: str, history_id_2: str = "reality", include_projections: bool = True) -> dict:
    """Compare two histories (or one against reality).

    Args:
        history_id_1: First history ID
        history_id_2: Second history ID or "reality" for the real event log
        include_projections: Whether to generate and compare future projections

    Returns:
        Comparison data including portfolio values, holdings differences,
        historical divergence points, and future projections.
    """
    import sys
    sys.path.insert(0, str(SCRIPT_DIR))
    from reconstruct_state import reconstruct_state, load_event_log

    # Load first history
    if history_id_1 == "reality":
        events1 = load_event_log(str(DATA_DIR / "event_log_enhanced.csv"))
        name1 = "Reality"
        desc1 = "Actual portfolio history"
    else:
        events1 = get_history_events(history_id_1)
        h1 = get_history(history_id_1)
        name1 = h1["name"] if h1 else history_id_1
        desc1 = h1.get("description", "") if h1 else ""

    # Load second history
    if history_id_2 == "reality":
        events2 = load_event_log(str(DATA_DIR / "event_log_enhanced.csv"))
        name2 = "Reality"
        desc2 = "Actual portfolio history"
    else:
        events2 = get_history_events(history_id_2)
        h2 = get_history(history_id_2)
        name2 = h2["name"] if h2 else history_id_2
        desc2 = h2.get("description", "") if h2 else ""

    if events1 is None or events2 is None:
        return {"error": "History not found"}

    # Reconstruct states
    state1 = reconstruct_state(events1)
    state2 = reconstruct_state(events2)

    # Calculate current holdings differences
    holdings_diff = {}
    all_tickers = set(state1.get('holdings', {}).keys()) | set(state2.get('holdings', {}).keys())

    for ticker in all_tickers:
        shares1 = state1.get('holdings', {}).get(ticker, 0)
        shares2 = state2.get('holdings', {}).get(ticker, 0)
        price = state1.get('latest_prices', {}).get(ticker, 0)
        if price == 0:
            price = state2.get('latest_prices', {}).get(ticker, 0)

        if shares1 > 0.01 or shares2 > 0.01:
            holdings_diff[ticker] = {
                "shares_1": shares1,
                "shares_2": shares2,
                "diff": shares2 - shares1,
                "value_1": shares1 * price,
                "value_2": shares2 * price,
                "value_diff": (shares2 - shares1) * price
            }

    # Find historical divergence points
    divergence_points = find_divergence_points(events1, events2)

    # Build historical timeline showing how values diverged over time
    historical_timeline = build_historical_timeline(events1, events2, name1, name2)

    result = {
        "history_1": {
            "id": history_id_1,
            "name": name1,
            "description": desc1,
            "total_value": state1.get('total_value', 0),
            "cash": state1.get('cash', 0),
            "portfolio_value": state1.get('portfolio_value', 0),
            "ytd_income": state1.get('ytd_income', 0),
            "holdings_count": len([s for s in state1.get('holdings', {}).values() if s > 0.01])
        },
        "history_2": {
            "id": history_id_2,
            "name": name2,
            "description": desc2,
            "total_value": state2.get('total_value', 0),
            "cash": state2.get('cash', 0),
            "portfolio_value": state2.get('portfolio_value', 0),
            "ytd_income": state2.get('ytd_income', 0),
            "holdings_count": len([s for s in state2.get('holdings', {}).values() if s > 0.01])
        },
        "comparison": {
            "total_value_diff": state2.get('total_value', 0) - state1.get('total_value', 0),
            "cash_diff": state2.get('cash', 0) - state1.get('cash', 0),
            "portfolio_diff": state2.get('portfolio_value', 0) - state1.get('portfolio_value', 0),
            "income_diff": state2.get('ytd_income', 0) - state1.get('ytd_income', 0),
            "holdings_diff": holdings_diff
        },
        "divergence": {
            "points": divergence_points,
            "first_divergence": divergence_points[0] if divergence_points else None,
            "total_divergent_events": len(divergence_points)
        },
        "historical_timeline": historical_timeline
    }

    # Generate and compare future projections
    if include_projections:
        # Generate projections for both histories (use statistical for speed)
        proj1 = generate_projection(history_id_1, years=3, use_llm=False)
        proj2 = generate_projection(history_id_2, years=3, use_llm=False)

        if "error" not in proj1 and "error" not in proj2:
            # Extract key projection data
            frames1 = proj1.get("frames", [])
            frames2 = proj2.get("frames", [])

            # Build projection comparison timeline
            projection_timeline = []
            for i in range(min(len(frames1), len(frames2))):
                f1 = frames1[i]
                f2 = frames2[i]
                projection_timeline.append({
                    "date": f1.get("date"),
                    "month": f1.get("month"),
                    "year": f1.get("year"),
                    "value_1": f1.get("total_value", 0),
                    "value_2": f2.get("total_value", 0),
                    "diff": f2.get("total_value", 0) - f1.get("total_value", 0),
                    "diff_pct": ((f2.get("total_value", 0) - f1.get("total_value", 0)) /
                                f1.get("total_value", 1) * 100) if f1.get("total_value", 0) > 0 else 0
                })

            # Get end state projections
            end_state_1 = frames1[-1] if frames1 else {}
            end_state_2 = frames2[-1] if frames2 else {}

            result["projections"] = {
                "years": 3,
                "history_1_projection": {
                    "end_date": end_state_1.get("date"),
                    "projected_value": end_state_1.get("total_value", 0),
                    "growth_from_current": ((end_state_1.get("total_value", 0) - state1.get('total_value', 0)) /
                                           state1.get('total_value', 1) * 100) if state1.get('total_value', 0) > 0 else 0
                },
                "history_2_projection": {
                    "end_date": end_state_2.get("date"),
                    "projected_value": end_state_2.get("total_value", 0),
                    "growth_from_current": ((end_state_2.get("total_value", 0) - state2.get('total_value', 0)) /
                                           state2.get('total_value', 1) * 100) if state2.get('total_value', 0) > 0 else 0
                },
                "projected_diff": end_state_2.get("total_value", 0) - end_state_1.get("total_value", 0),
                "timeline": projection_timeline
            }

    return result


def find_divergence_points(events1: pd.DataFrame, events2: pd.DataFrame) -> list:
    """Find events that differ between two histories.

    Returns list of divergence points showing what's different.
    """
    divergences = []

    # Get event IDs from both
    ids1 = set(events1['event_id'].tolist()) if 'event_id' in events1.columns else set()
    ids2 = set(events2['event_id'].tolist()) if 'event_id' in events2.columns else set()

    # Events only in history 1
    only_in_1 = ids1 - ids2
    # Events only in history 2
    only_in_2 = ids2 - ids1

    # Process events only in history 1 (removed in history 2)
    for event_id in sorted(only_in_1):
        event_row = events1[events1['event_id'] == event_id]
        if len(event_row) > 0:
            row = event_row.iloc[0]
            data = row.get('data', {}) if 'data' in row else {}
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except:
                    data = {}

            divergences.append({
                "event_id": event_id,
                "timestamp": str(row.get('timestamp', '')),
                "type": row.get('event_type', ''),
                "in_history": "history_1_only",
                "description": f"Event #{event_id}: {row.get('event_type', '')} - {data.get('ticker', data.get('action', ''))}",
                "data": data
            })

    # Process events only in history 2 (added in history 2)
    for event_id in sorted(only_in_2):
        event_row = events2[events2['event_id'] == event_id]
        if len(event_row) > 0:
            row = event_row.iloc[0]
            data = row.get('data', {}) if 'data' in row else {}
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except:
                    data = {}

            divergences.append({
                "event_id": event_id,
                "timestamp": str(row.get('timestamp', '')),
                "type": row.get('event_type', ''),
                "in_history": "history_2_only",
                "description": f"Event #{event_id}: {row.get('event_type', '')} - {data.get('ticker', data.get('action', ''))}",
                "data": data
            })

    # Check for events with same ID but different data
    common_ids = ids1 & ids2
    for event_id in sorted(common_ids):
        row1 = events1[events1['event_id'] == event_id].iloc[0]
        row2 = events2[events2['event_id'] == event_id].iloc[0]

        # Compare data_json if it exists
        data1 = row1.get('data', {})
        data2 = row2.get('data', {})

        if isinstance(data1, str):
            try:
                data1 = json.loads(data1)
            except:
                data1 = {}
        if isinstance(data2, str):
            try:
                data2 = json.loads(data2)
            except:
                data2 = {}

        # Check for differences
        if data1 != data2:
            divergences.append({
                "event_id": event_id,
                "timestamp": str(row1.get('timestamp', '')),
                "type": row1.get('event_type', ''),
                "in_history": "modified",
                "description": f"Event #{event_id} modified: {row1.get('event_type', '')}",
                "data_1": data1,
                "data_2": data2,
                "changes": {k: {"from": data1.get(k), "to": data2.get(k)}
                           for k in set(data1.keys()) | set(data2.keys())
                           if data1.get(k) != data2.get(k)}
            })

    # Sort by timestamp
    divergences.sort(key=lambda x: x.get('timestamp', ''))

    return divergences


def create_seeded_reality(
    name: str,
    description: str,
    start_date: str,
    starting_cash: float,
    tickers: list,
    scenario_type: str = "custom",
    trading_style: str = "moderate",
    use_llm: bool = True
) -> dict:
    """Create a new alternate reality with generated trading history.

    This creates a complete event log with trades (buys AND sells) throughout
    the timeline, using real historical prices.

    Args:
        name: Display name for this reality
        description: What-if scenario description
        start_date: When the alternate timeline begins (YYYY-MM-DD)
        starting_cash: Initial cash to invest
        tickers: List of tickers to trade
        scenario_type: "bull", "bear", "dca", "swing", "custom"
        trading_style: "conservative", "moderate", "aggressive"
        use_llm: Whether to use LLM to generate intelligent trade decisions

    Returns:
        The created history with full trading timeline
    """
    ensure_storage()
    history_id = str(uuid.uuid4())[:8]

    # Fetch historical prices for all tickers
    end_date = datetime.now().strftime('%Y-%m-%d')
    price_data = {}

    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(start=start_date, end=end_date)
            if not hist.empty:
                price_data[ticker] = {
                    date.strftime('%Y-%m-%d'): row['Close']
                    for date, row in hist.iterrows()
                }
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")

    if not price_data:
        return {"error": "Could not fetch historical prices for any ticker"}

    # Get all trading dates
    all_dates = set()
    for ticker_prices in price_data.values():
        all_dates.update(ticker_prices.keys())
    sorted_dates = sorted(all_dates)

    if not sorted_dates:
        return {"error": "No price data available"}

    # Generate trades based on scenario and style
    if use_llm:
        trades = generate_llm_trading_history(
            price_data, sorted_dates, starting_cash, tickers,
            scenario_type, trading_style, description
        )
    else:
        trades = generate_algorithmic_trades(
            price_data, sorted_dates, starting_cash, tickers,
            scenario_type, trading_style
        )

    # Build event log
    events = []
    event_id = 1

    # Initial deposit
    events.append({
        "event_id": event_id,
        "timestamp": f"{sorted_dates[0]} 09:30:00",
        "event_type": "DEPOSIT",
        "data_json": json.dumps({
            "amount": starting_cash,
            "source": f"Alternate Reality: {name}"
        }),
        "reason_json": json.dumps({"primary": "ALTERNATE_REALITY_SEED"}),
        "notes": f"Initial deposit for {name}",
        "tags_json": '["alternate", "deposit"]',
        "affects_cash": True,
        "cash_delta": starting_cash
    })
    event_id += 1

    # Add trades
    for trade in trades:
        action = trade['action']
        total = trade['shares'] * trade['price']
        cash_delta = total if action == 'SELL' else -total

        events.append({
            "event_id": event_id,
            "timestamp": f"{trade['date']} 10:00:00",
            "event_type": "TRADE",
            "data_json": json.dumps({
                "action": action,
                "ticker": trade['ticker'],
                "shares": trade['shares'],
                "price": round(trade['price'], 2),
                "total": round(total, 2),
                "reason": trade.get('reason', ''),
                "source": "ALTERNATE_REALITY"
            }),
            "reason_json": json.dumps({
                "primary": trade.get('reason_code', 'WHAT_IF_TRADE'),
                "explanation": trade.get('reason', '')
            }),
            "notes": trade.get('reason', f"{action} {trade['ticker']}"),
            "tags_json": '["alternate", "trade"]',
            "affects_cash": True,
            "cash_delta": cash_delta
        })
        event_id += 1

    # Save event log
    df = pd.DataFrame(events)
    event_file = ALT_HISTORIES_DIR / f"{history_id}.csv"
    df.to_csv(event_file, index=False)

    # Calculate final stats
    from reconstruct_state import reconstruct_state
    df['data'] = df['data_json'].apply(json.loads)
    final_state = reconstruct_state(df)

    # Create metadata
    history = {
        "id": history_id,
        "name": name,
        "description": description,
        "created_at": datetime.now().isoformat(),
        "modified_at": datetime.now().isoformat(),
        "seed_config": {
            "start_date": start_date,
            "starting_cash": starting_cash,
            "tickers": tickers,
            "scenario_type": scenario_type,
            "trading_style": trading_style
        },
        "trade_count": len(trades),
        "event_count": len(events),
        "final_state": {
            "total_value": final_state.get('total_value', 0),
            "cash": final_state.get('cash', 0),
            "portfolio_value": final_state.get('portfolio_value', 0),
            "holdings": {k: v for k, v in final_state.get('holdings', {}).items() if v > 0}
        },
        "performance": {
            "starting_value": starting_cash,
            "ending_value": final_state.get('total_value', 0),
            "total_return": final_state.get('total_value', 0) - starting_cash,
            "return_pct": ((final_state.get('total_value', 0) - starting_cash) / starting_cash * 100) if starting_cash > 0 else 0
        },
        "llm_generated": use_llm,
        "status": "ready"
    }

    # Add to index
    index = load_index()
    index["histories"].append(history)
    save_index(index)

    return history


def generate_algorithmic_trades(
    price_data: dict,
    sorted_dates: list,
    starting_cash: float,
    tickers: list,
    scenario_type: str,
    trading_style: str
) -> list:
    """Generate trades using algorithmic rules.

    Strategies:
    - bull: Buy dips, hold long, sell at peaks
    - bear: Frequent profit-taking, tight stops
    - dca: Dollar cost average on schedule
    - swing: Trade momentum swings
    """
    trades = []
    cash = starting_cash
    holdings = {t: 0 for t in tickers}

    # Trading parameters based on style
    style_params = {
        "conservative": {"position_pct": 0.15, "profit_target": 0.20, "stop_loss": 0.10},
        "moderate": {"position_pct": 0.25, "profit_target": 0.15, "stop_loss": 0.08},
        "aggressive": {"position_pct": 0.40, "profit_target": 0.10, "stop_loss": 0.05}
    }
    params = style_params.get(trading_style, style_params["moderate"])

    # Track cost basis for P&L
    cost_basis = {t: 0 for t in tickers}

    if scenario_type == "dca":
        # Dollar cost averaging - buy regularly
        buy_interval = max(5, len(sorted_dates) // (len(tickers) * 12))  # ~monthly per ticker
        ticker_idx = 0

        for i, date in enumerate(sorted_dates):
            if i % buy_interval == 0 and cash > 1000:
                ticker = tickers[ticker_idx % len(tickers)]
                if ticker in price_data and date in price_data[ticker]:
                    price = price_data[ticker][date]
                    amount_to_invest = cash * params["position_pct"]
                    shares = int(amount_to_invest / price)

                    if shares > 0 and shares * price <= cash:
                        trades.append({
                            "date": date,
                            "ticker": ticker,
                            "action": "BUY",
                            "shares": shares,
                            "price": price,
                            "reason": f"DCA buy #{len([t for t in trades if t['ticker'] == ticker and t['action'] == 'BUY']) + 1}",
                            "reason_code": "DCA_SCHEDULE"
                        })
                        cash -= shares * price
                        holdings[ticker] += shares
                        cost_basis[ticker] += shares * price

                ticker_idx += 1

    elif scenario_type == "swing":
        # Swing trading - buy low, sell high based on moving averages
        for ticker in tickers:
            if ticker not in price_data:
                continue

            prices = [(d, price_data[ticker].get(d)) for d in sorted_dates if price_data[ticker].get(d)]
            if len(prices) < 20:
                continue

            # Calculate simple moving average
            for i in range(20, len(prices)):
                date, price = prices[i]
                ma20 = sum(p[1] for p in prices[i-20:i]) / 20
                ma5 = sum(p[1] for p in prices[i-5:i]) / 5

                # Buy signal: price crosses above MA20, short MA above long MA
                if holdings[ticker] == 0 and price > ma20 and ma5 > ma20 and cash > 1000:
                    amount = cash * params["position_pct"]
                    shares = int(amount / price)
                    if shares > 0:
                        trades.append({
                            "date": date,
                            "ticker": ticker,
                            "action": "BUY",
                            "shares": shares,
                            "price": price,
                            "reason": f"Swing buy: price {price:.2f} > MA20 {ma20:.2f}",
                            "reason_code": "SWING_BUY"
                        })
                        cash -= shares * price
                        holdings[ticker] += shares
                        cost_basis[ticker] = shares * price

                # Sell signal: price crosses below MA20 or profit target hit
                elif holdings[ticker] > 0:
                    avg_cost = cost_basis[ticker] / holdings[ticker] if holdings[ticker] > 0 else price
                    gain_pct = (price - avg_cost) / avg_cost

                    if price < ma20 or gain_pct >= params["profit_target"] or gain_pct <= -params["stop_loss"]:
                        reason = "profit target" if gain_pct >= params["profit_target"] else (
                            "stop loss" if gain_pct <= -params["stop_loss"] else "MA crossover"
                        )
                        trades.append({
                            "date": date,
                            "ticker": ticker,
                            "action": "SELL",
                            "shares": holdings[ticker],
                            "price": price,
                            "reason": f"Swing sell: {reason} ({gain_pct*100:.1f}%)",
                            "reason_code": "SWING_SELL"
                        })
                        cash += holdings[ticker] * price
                        holdings[ticker] = 0
                        cost_basis[ticker] = 0

    elif scenario_type in ["bull", "bear"]:
        # Bull: Aggressive buying, patient selling
        # Bear: Quick profits, tight stops
        buy_threshold = 0.95 if scenario_type == "bull" else 0.98  # Buy when price is X% of recent high
        sell_threshold = params["profit_target"] if scenario_type == "bull" else params["profit_target"] * 0.5

        for ticker in tickers:
            if ticker not in price_data:
                continue

            prices = [(d, price_data[ticker].get(d)) for d in sorted_dates if price_data[ticker].get(d)]
            if len(prices) < 10:
                continue

            recent_high = max(p[1] for p in prices[:10])

            for i in range(10, len(prices)):
                date, price = prices[i]
                recent_high = max(recent_high, price)
                recent_low = min(p[1] for p in prices[max(0, i-10):i])

                # Buy on dips
                if holdings[ticker] == 0 and price <= recent_high * buy_threshold and cash > 1000:
                    amount = cash * params["position_pct"]
                    shares = int(amount / price)
                    if shares > 0:
                        trades.append({
                            "date": date,
                            "ticker": ticker,
                            "action": "BUY",
                            "shares": shares,
                            "price": price,
                            "reason": f"{scenario_type.title()} buy: dip to {price:.2f}",
                            "reason_code": f"{scenario_type.upper()}_BUY"
                        })
                        cash -= shares * price
                        holdings[ticker] += shares
                        cost_basis[ticker] = shares * price
                        recent_high = price  # Reset after buy

                # Sell on target or stop
                elif holdings[ticker] > 0:
                    avg_cost = cost_basis[ticker] / holdings[ticker]
                    gain_pct = (price - avg_cost) / avg_cost

                    should_sell = (
                        gain_pct >= sell_threshold or
                        gain_pct <= -params["stop_loss"] or
                        (scenario_type == "bear" and price < recent_low * 1.02)  # Quick exit in bear
                    )

                    if should_sell:
                        reason = "profit target" if gain_pct >= sell_threshold else "stop loss"
                        trades.append({
                            "date": date,
                            "ticker": ticker,
                            "action": "SELL",
                            "shares": holdings[ticker],
                            "price": price,
                            "reason": f"{scenario_type.title()} sell: {reason} ({gain_pct*100:.1f}%)",
                            "reason_code": f"{scenario_type.upper()}_SELL"
                        })
                        cash += holdings[ticker] * price
                        holdings[ticker] = 0
                        cost_basis[ticker] = 0

    else:  # custom - do initial buys then occasional rebalancing
        # Initial allocation
        allocation_per_ticker = starting_cash / len(tickers) * params["position_pct"]

        for ticker in tickers:
            if ticker in price_data and sorted_dates[0] in price_data[ticker]:
                price = price_data[ticker][sorted_dates[0]]
                shares = int(allocation_per_ticker / price)
                if shares > 0 and shares * price <= cash:
                    trades.append({
                        "date": sorted_dates[0],
                        "ticker": ticker,
                        "action": "BUY",
                        "shares": shares,
                        "price": price,
                        "reason": "Initial allocation",
                        "reason_code": "INITIAL_BUY"
                    })
                    cash -= shares * price
                    holdings[ticker] += shares
                    cost_basis[ticker] = shares * price

        # Periodic rebalancing every ~quarter
        rebalance_interval = max(60, len(sorted_dates) // 4)
        for i in range(rebalance_interval, len(sorted_dates), rebalance_interval):
            date = sorted_dates[i]

            # Calculate current values
            total_value = cash
            for ticker in tickers:
                if ticker in price_data and date in price_data[ticker]:
                    total_value += holdings[ticker] * price_data[ticker][date]

            target_per_ticker = total_value / len(tickers) * 0.8  # 80% in stocks

            for ticker in tickers:
                if ticker not in price_data or date not in price_data[ticker]:
                    continue

                price = price_data[ticker][date]
                current_value = holdings[ticker] * price
                diff = target_per_ticker - current_value

                if abs(diff) > target_per_ticker * 0.1:  # >10% off target
                    if diff > 0 and cash > diff:  # Need to buy
                        shares = int(diff / price)
                        if shares > 0:
                            trades.append({
                                "date": date,
                                "ticker": ticker,
                                "action": "BUY",
                                "shares": shares,
                                "price": price,
                                "reason": "Rebalance buy",
                                "reason_code": "REBALANCE"
                            })
                            cash -= shares * price
                            holdings[ticker] += shares
                            cost_basis[ticker] += shares * price
                    elif diff < 0 and holdings[ticker] > 0:  # Need to sell
                        shares = min(holdings[ticker], int(-diff / price))
                        if shares > 0:
                            trades.append({
                                "date": date,
                                "ticker": ticker,
                                "action": "SELL",
                                "shares": shares,
                                "price": price,
                                "reason": "Rebalance sell",
                                "reason_code": "REBALANCE"
                            })
                            cash += shares * price
                            holdings[ticker] -= shares
                            if holdings[ticker] > 0:
                                cost_basis[ticker] *= (holdings[ticker] / (holdings[ticker] + shares))
                            else:
                                cost_basis[ticker] = 0

    return trades


def generate_llm_trading_history(
    price_data: dict,
    sorted_dates: list,
    starting_cash: float,
    tickers: list,
    scenario_type: str,
    trading_style: str,
    description: str
) -> list:
    """Use LLM to generate intelligent trading decisions."""
    try:
        from llm.config import get_llm_config
        from llm.client import get_llm_response

        config = get_llm_config()
        if not config.enabled:
            return generate_algorithmic_trades(price_data, sorted_dates, starting_cash, tickers, scenario_type, trading_style)

        # Build price summary for LLM
        price_summary = []
        sample_dates = sorted_dates[::max(1, len(sorted_dates) // 20)]  # ~20 sample points

        for date in sample_dates:
            prices_on_date = {t: price_data[t].get(date) for t in tickers if t in price_data and date in price_data[t]}
            if prices_on_date:
                price_summary.append(f"{date}: " + ", ".join(f"{t}=${p:.2f}" for t, p in prices_on_date.items()))

        prompt = f"""You are a portfolio manager creating a trading history for an alternate reality simulation.

SCENARIO: {description}
TYPE: {scenario_type}
STYLE: {trading_style}
STARTING CASH: ${starting_cash:,.0f}
TICKERS TO TRADE: {', '.join(tickers)}

HISTORICAL PRICES (sample dates):
{chr(10).join(price_summary[:15])}
...
{chr(10).join(price_summary[-5:])}

Generate a realistic trading history with 10-30 trades spread throughout the timeline.
Include both BUY and SELL trades with realistic reasoning.

Respond ONLY in JSON format:
{{
    "trades": [
        {{
            "date": "YYYY-MM-DD",
            "ticker": "TICK",
            "action": "BUY" or "SELL",
            "shares": 100,
            "reason": "Brief explanation"
        }},
        ...
    ]
}}

Rules:
1. First trades should be BUYs to establish positions
2. Don't sell more shares than owned
3. Space trades realistically (not all on same day)
4. Match the scenario type ({scenario_type}) and style ({trading_style})
5. Use realistic share quantities based on price and available cash
6. Include profit-taking sells and loss-cutting sells
"""

        response = get_llm_response(prompt, max_tokens=2000)
        if not response:
            return generate_algorithmic_trades(price_data, sorted_dates, starting_cash, tickers, scenario_type, trading_style)

        # Parse response
        clean_response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
        json_start = clean_response.find('{')
        json_end = clean_response.rfind('}') + 1

        if json_start >= 0 and json_end > json_start:
            result = json.loads(clean_response[json_start:json_end])
            llm_trades = result.get("trades", [])

            # Validate and enrich trades with actual prices
            validated_trades = []
            for trade in llm_trades:
                ticker = trade.get("ticker")
                date = trade.get("date")

                if ticker in price_data and date in price_data[ticker]:
                    trade["price"] = price_data[ticker][date]
                    trade["reason_code"] = "LLM_GENERATED"
                    validated_trades.append(trade)

            if validated_trades:
                return validated_trades

        return generate_algorithmic_trades(price_data, sorted_dates, starting_cash, tickers, scenario_type, trading_style)

    except Exception as e:
        print(f"LLM trade generation failed: {e}")
        return generate_algorithmic_trades(price_data, sorted_dates, starting_cash, tickers, scenario_type, trading_style)


def build_historical_timeline(events1: pd.DataFrame, events2: pd.DataFrame,
                             name1: str, name2: str) -> list:
    """Build a timeline showing how portfolio values evolved differently.

    Reconstructs state at key points to show divergence over time.
    """
    import sys
    sys.path.insert(0, str(SCRIPT_DIR))
    from reconstruct_state import reconstruct_state

    timeline = []

    # Get all unique dates from both event logs
    dates1 = pd.to_datetime(events1['timestamp']).dt.date.unique()
    dates2 = pd.to_datetime(events2['timestamp']).dt.date.unique()
    all_dates = sorted(set(dates1) | set(dates2))

    # Sample dates (monthly or every N events to avoid too many points)
    if len(all_dates) > 24:
        # Sample monthly
        sampled_dates = all_dates[::max(1, len(all_dates) // 24)]
        # Always include first and last
        if all_dates[0] not in sampled_dates:
            sampled_dates = [all_dates[0]] + list(sampled_dates)
        if all_dates[-1] not in sampled_dates:
            sampled_dates = list(sampled_dates) + [all_dates[-1]]
    else:
        sampled_dates = all_dates

    for date in sampled_dates:
        # Filter events up to this date
        mask1 = pd.to_datetime(events1['timestamp']).dt.date <= date
        mask2 = pd.to_datetime(events2['timestamp']).dt.date <= date

        events1_to_date = events1[mask1]
        events2_to_date = events2[mask2]

        if len(events1_to_date) == 0 and len(events2_to_date) == 0:
            continue

        # Reconstruct states
        state1 = reconstruct_state(events1_to_date) if len(events1_to_date) > 0 else {'total_value': 0, 'cash': 0}
        state2 = reconstruct_state(events2_to_date) if len(events2_to_date) > 0 else {'total_value': 0, 'cash': 0}

        timeline.append({
            "date": str(date),
            "history_1": {
                "name": name1,
                "total_value": state1.get('total_value', 0),
                "cash": state1.get('cash', 0),
                "event_count": len(events1_to_date)
            },
            "history_2": {
                "name": name2,
                "total_value": state2.get('total_value', 0),
                "cash": state2.get('cash', 0),
                "event_count": len(events2_to_date)
            },
            "diff": state2.get('total_value', 0) - state1.get('total_value', 0)
        })

    return timeline


# =============================================================================
# Part 2: Simple Reality Engine (from alternate_reality.py)
# =============================================================================

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
    events_df = load_event_log(str(DATA_DIR / 'event_log_enhanced.csv'))
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


# =============================================================================
# Part 3: Future Projections (from reality_projections.py)
# =============================================================================

def get_portfolio_context() -> Dict:
    """Get current portfolio state for LLM context."""
    from reconstruct_state import load_event_log, reconstruct_state

    events_df = load_event_log(str(DATA_DIR / 'event_log_enhanced.csv'))
    state = reconstruct_state(events_df)

    holdings_summary = []
    for ticker, shares in state.get('holdings', {}).items():
        if shares > 0:
            price = state.get('latest_prices', {}).get(ticker, 0)
            cost_basis = state.get('cost_basis', {}).get(ticker, {})
            holdings_summary.append({
                'ticker': ticker,
                'shares': shares,
                'price': price,
                'value': shares * price,
                'cost_basis': cost_basis.get('avg_price', 0),
                'gain_pct': ((price - cost_basis.get('avg_price', 1)) / cost_basis.get('avg_price', 1) * 100) if cost_basis.get('avg_price', 0) > 0 else 0
            })

    return {
        'total_value': state.get('total_value', 0),
        'cash': state.get('cash', 0),
        'portfolio_value': state.get('portfolio_value', 0),
        'holdings': sorted(holdings_summary, key=lambda x: x['value'], reverse=True),
        'ytd_income': state.get('ytd_income', 0),
        'active_options': len(state.get('active_options', []))
    }


def build_projection_prompt(portfolio: Dict, years_forward: int = 3, years_back: int = 1) -> str:
    """Build the LLM prompt for generating projections."""

    holdings_text = "\n".join([
        f"- {h['ticker']}: {h['shares']:.0f} shares @ ${h['price']:.2f} = ${h['value']:,.0f} ({h['gain_pct']:+.1f}%)"
        for h in portfolio['holdings'][:8]
    ])

    prompt = f"""You are a financial analyst creating scenario projections for a portfolio visualization.

## Current Portfolio (as of {datetime.now().strftime('%Y-%m-%d')})
Total Value: ${portfolio['total_value']:,.0f}
Cash: ${portfolio['cash']:,.0f}
Holdings Value: ${portfolio['portfolio_value']:,.0f}

Top Holdings:
{holdings_text}

## Task
Generate a structured JSON response with timeline projections for this portfolio. Create realistic scenarios based on:
1. The specific stocks held (tech-heavy, growth stocks, etc.)
2. Current market conditions and trends
3. Macro economic factors

## Output Format
Return ONLY valid JSON (no markdown, no explanation) with this exact structure:

{{
    "generated_at": "{datetime.now().isoformat()}",
    "timeline": {{
        "start_date": "{(datetime.now() - timedelta(days=365*years_back)).strftime('%Y-%m-%d')}",
        "end_date": "{(datetime.now() + timedelta(days=365*years_forward)).strftime('%Y-%m-%d')}",
        "present_date": "{datetime.now().strftime('%Y-%m-%d')}"
    }},
    "realities": [
        {{
            "id": "base",
            "name": "Base Case",
            "description": "Most likely scenario based on current trends",
            "probability": 0.5,
            "color": "#06b6d4",
            "sentiment": "neutral",
            "snapshots": [
                {{
                    "date": "YYYY-MM-DD",
                    "total_value": 000000,
                    "change_from_present_pct": 0.0,
                    "sentiment": "bullish|bearish|neutral",
                    "sentiment_score": 0.0
                }}
            ],
            "macro_events": [
                {{
                    "date": "YYYY-MM-DD",
                    "title": "Event Title",
                    "description": "What happened and market impact",
                    "impact": "positive|negative|neutral",
                    "magnitude": "minor|moderate|major",
                    "affected_holdings": ["TICKER1", "TICKER2"]
                }}
            ]
        }},
        {{
            "id": "bull",
            "name": "Bull Scenario",
            "description": "Optimistic case - favorable conditions",
            "probability": 0.25,
            "color": "#22c55e",
            "sentiment": "bullish",
            "snapshots": [...],
            "macro_events": [...]
        }},
        {{
            "id": "bear",
            "name": "Bear Scenario",
            "description": "Pessimistic case - adverse conditions",
            "probability": 0.25,
            "color": "#ef4444",
            "sentiment": "bearish",
            "snapshots": [...],
            "macro_events": [...]
        }}
    ]
}}

## Requirements for snapshots:
- Include monthly snapshots from {years_back} year ago to {years_forward} years in future
- Past snapshots should reflect actual market history (approximate)
- Future snapshots should project realistic growth/decline based on scenario
- sentiment_score: -1.0 (very bearish) to +1.0 (very bullish)

## Requirements for macro_events:
- 4-6 events per reality (mix of past and future)
- Past events: Real events that impacted these holdings
- Future events: Plausible events that could occur
- Be specific to the holdings in this portfolio
- Include dates spread across the timeline

Generate realistic, thoughtful projections. For past events, reference real market events. For future events, create plausible scenarios based on each company's sector and business model."""

    return prompt


def parse_llm_response(response: str) -> Optional[Dict]:
    """Parse LLM response, handling various formats."""
    # Try to extract JSON from response
    # First try: direct JSON parse
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # Second try: find JSON block
    json_match = re.search(r'\{[\s\S]*\}', response)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # Third try: find JSON in code blocks
    code_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', response)
    if code_match:
        try:
            return json.loads(code_match.group(1))
        except json.JSONDecodeError:
            pass

    return None


def generate_fallback_projections(portfolio: Dict, years_forward: int = 3, years_back: int = 1) -> Dict:
    """Generate basic projections without LLM."""

    now = datetime.now()
    start_date = now - timedelta(days=365 * years_back)
    end_date = now + timedelta(days=365 * years_forward)

    base_value = portfolio['total_value']

    def generate_snapshots(growth_rate: float, volatility: float) -> List[Dict]:
        snapshots = []
        current = start_date
        months = 0

        while current <= end_date:
            # Calculate value at this point
            years_from_present = (current - now).days / 365

            if years_from_present < 0:
                # Past: use lower volatility
                value = base_value * (1 + growth_rate * years_from_present * 0.8)
            else:
                # Future: project with growth rate
                value = base_value * (1 + growth_rate) ** years_from_present

            # Add some variation
            variation = math.sin(months * 0.5) * volatility * base_value
            value += variation

            sentiment_score = growth_rate + (variation / base_value)

            snapshots.append({
                'date': current.strftime('%Y-%m-%d'),
                'total_value': round(value, 0),
                'change_from_present_pct': round((value - base_value) / base_value * 100, 1),
                'sentiment': 'bullish' if sentiment_score > 0.05 else ('bearish' if sentiment_score < -0.05 else 'neutral'),
                'sentiment_score': round(max(-1, min(1, sentiment_score * 5)), 2)
            })

            current += timedelta(days=30)
            months += 1

        return snapshots

    # Generate macro events
    def generate_events(scenario: str) -> List[Dict]:
        events = []

        # Past event
        past_date = (now - timedelta(days=180)).strftime('%Y-%m-%d')
        events.append({
            'date': past_date,
            'title': 'Market Volatility' if scenario != 'bull' else 'Tech Rally',
            'description': 'Market experienced significant movement affecting growth stocks',
            'impact': 'neutral' if scenario == 'base' else ('positive' if scenario == 'bull' else 'negative'),
            'magnitude': 'moderate',
            'affected_holdings': [h['ticker'] for h in portfolio['holdings'][:3]]
        })

        # Future events
        future_dates = [
            (now + timedelta(days=90)).strftime('%Y-%m-%d'),
            (now + timedelta(days=365)).strftime('%Y-%m-%d'),
            (now + timedelta(days=730)).strftime('%Y-%m-%d')
        ]

        if scenario == 'bull':
            events.extend([
                {'date': future_dates[0], 'title': 'AI Boom Accelerates', 'description': 'Major AI breakthroughs drive tech valuations higher', 'impact': 'positive', 'magnitude': 'major', 'affected_holdings': [h['ticker'] for h in portfolio['holdings'][:2]]},
                {'date': future_dates[1], 'title': 'Fed Cuts Rates', 'description': 'Interest rate cuts boost growth stocks', 'impact': 'positive', 'magnitude': 'moderate', 'affected_holdings': [h['ticker'] for h in portfolio['holdings']]},
                {'date': future_dates[2], 'title': 'Space Economy Expansion', 'description': 'Commercial space industry reaches new milestones', 'impact': 'positive', 'magnitude': 'major', 'affected_holdings': ['RKLB'] if any(h['ticker'] == 'RKLB' for h in portfolio['holdings']) else []}
            ])
        elif scenario == 'bear':
            events.extend([
                {'date': future_dates[0], 'title': 'Recession Fears', 'description': 'Economic indicators point to slowdown', 'impact': 'negative', 'magnitude': 'major', 'affected_holdings': [h['ticker'] for h in portfolio['holdings']]},
                {'date': future_dates[1], 'title': 'Tech Regulation', 'description': 'New regulations impact tech sector', 'impact': 'negative', 'magnitude': 'moderate', 'affected_holdings': [h['ticker'] for h in portfolio['holdings'][:3]]},
                {'date': future_dates[2], 'title': 'Market Correction', 'description': 'Valuations normalize after prolonged rally', 'impact': 'negative', 'magnitude': 'moderate', 'affected_holdings': [h['ticker'] for h in portfolio['holdings']]}
            ])
        else:
            events.extend([
                {'date': future_dates[0], 'title': 'Mixed Earnings Season', 'description': 'Companies report varied results', 'impact': 'neutral', 'magnitude': 'minor', 'affected_holdings': [h['ticker'] for h in portfolio['holdings'][:2]]},
                {'date': future_dates[1], 'title': 'Sector Rotation', 'description': 'Investors shift between growth and value', 'impact': 'neutral', 'magnitude': 'moderate', 'affected_holdings': [h['ticker'] for h in portfolio['holdings']]},
                {'date': future_dates[2], 'title': 'Steady Growth', 'description': 'Markets continue gradual appreciation', 'impact': 'positive', 'magnitude': 'minor', 'affected_holdings': [h['ticker'] for h in portfolio['holdings']]}
            ])

        return events

    return {
        'generated_at': now.isoformat(),
        'source': 'fallback',
        'timeline': {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'present_date': now.strftime('%Y-%m-%d')
        },
        'realities': [
            {
                'id': 'base',
                'name': 'Base Case',
                'description': 'Most likely scenario - moderate growth continues',
                'probability': 0.50,
                'color': '#06b6d4',
                'sentiment': 'neutral',
                'snapshots': generate_snapshots(0.08, 0.03),
                'macro_events': generate_events('base')
            },
            {
                'id': 'bull',
                'name': 'Bull Scenario',
                'description': 'Optimistic - strong growth driven by favorable conditions',
                'probability': 0.25,
                'color': '#22c55e',
                'sentiment': 'bullish',
                'snapshots': generate_snapshots(0.25, 0.05),
                'macro_events': generate_events('bull')
            },
            {
                'id': 'bear',
                'name': 'Bear Scenario',
                'description': 'Pessimistic - downturn from adverse conditions',
                'probability': 0.25,
                'color': '#ef4444',
                'sentiment': 'bearish',
                'snapshots': generate_snapshots(-0.15, 0.06),
                'macro_events': generate_events('bear')
            }
        ],
        'portfolio_context': {
            'total_value': portfolio['total_value'],
            'holdings': [h['ticker'] for h in portfolio['holdings']]
        }
    }


async def generate_projections(
    years_forward: int = 3,
    years_back: int = 1,
    use_llm: bool = True
) -> Dict:
    """
    Generate timeline projections for the multiverse visualization.

    Args:
        years_forward: Years to project into future
        years_back: Years of history to include
        use_llm: Whether to use LLM for intelligent projections

    Returns:
        Structured projection data for visualization
    """
    from llm.config import get_llm_config

    portfolio = get_portfolio_context()

    if not use_llm:
        return generate_fallback_projections(portfolio, years_forward, years_back)

    config = get_llm_config()
    if not config.enabled:
        return generate_fallback_projections(portfolio, years_forward, years_back)

    try:
        from llm.client import get_llm_response

        prompt = build_projection_prompt(portfolio, years_forward, years_back)
        response = get_llm_response(prompt, max_tokens=4000)

        parsed = parse_llm_response(response)

        if parsed and 'realities' in parsed:
            parsed['source'] = 'llm'
            parsed['model'] = config.local_model if config.provider == 'local' else config.claude_model
            parsed['portfolio_context'] = {
                'total_value': portfolio['total_value'],
                'holdings': [h['ticker'] for h in portfolio['holdings']]
            }
            return parsed
        else:
            # LLM response wasn't parseable, use fallback
            result = generate_fallback_projections(portfolio, years_forward, years_back)
            result['llm_error'] = 'Response not parseable'
            return result

    except Exception as e:
        result = generate_fallback_projections(portfolio, years_forward, years_back)
        result['llm_error'] = str(e)
        return result


def generate_projections_sync(
    years_forward: int = 3,
    years_back: int = 1,
    use_llm: bool = True
) -> Dict:
    """Synchronous wrapper for generate_projections."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            generate_projections(years_forward, years_back, use_llm)
        )
        loop.close()
        return result
    except Exception as e:
        portfolio = get_portfolio_context()
        result = generate_fallback_projections(portfolio, years_forward, years_back)
        result['error'] = str(e)
        return result


# ============================================================================
# Projection Management Functions (from future_projection.py)
# ============================================================================

def generate_projection(
    history_id: str = "reality",
    years: int = 3,
    use_llm: bool = True,
    idea_ids: list = None
) -> dict:
    """Generate a future projection for a portfolio.

    Args:
        history_id: The history to project from ("reality" or alt history ID)
        years: Number of years to project (1-5)
        use_llm: Whether to use LLM for analysis (falls back to statistical if False)
        idea_ids: List of idea IDs to apply as modifications to the projection

    Returns:
        Projection data with future frames
    """
    import sys
    sys.path.insert(0, str(SCRIPT_DIR))

    from reconstruct_state import load_event_log, reconstruct_state

    # Get alternate history metadata if not reality
    history_context = None
    if history_id != "reality":
        history_metadata = get_history(history_id)
        if history_metadata:
            history_context = {
                "name": history_metadata.get("name", ""),
                "description": history_metadata.get("description", ""),
                "modifications": history_metadata.get("modifications", [])
            }

    # Load ideas if specified
    applied_ideas = []
    idea_context = None
    if idea_ids:
        try:
            from api.routes.ideas import get_idea_by_id

            for idea_id in idea_ids:
                idea = get_idea_by_id(idea_id)
                if idea:
                    applied_ideas.append({
                        "id": idea_id,
                        "title": idea.get("title", ""),
                        "category": idea.get("category", ""),
                        "tags": idea.get("tags", []),
                        "actions": idea.get("actions", [])
                    })

            if applied_ideas:
                idea_context = {
                    "ideas": applied_ideas,
                    "idea_count": len(applied_ideas),
                    "idea_tags": list(set(t for i in applied_ideas for t in i.get("tags", [])))
                }
        except:
            pass  # Ideas module might not be available

    # Load current state
    if history_id == "reality":
        events = load_event_log(str(DATA_DIR / "event_log_enhanced.csv"))
    else:
        events = get_history_events(history_id)

    if events is None:
        return {"error": "History not found"}

    current_state = reconstruct_state(events)

    # Always load reality's prices as fallback for alternates
    reality_prices = current_state.get('latest_prices', {})
    if history_id != "reality":
        # Load reality prices to use as fallback
        reality_events = load_event_log(str(DATA_DIR / "event_log_enhanced.csv"))
        reality_state = reconstruct_state(reality_events)
        reality_prices = reality_state.get('latest_prices', {})

    # Get holdings for analysis
    holdings = []
    for ticker, shares in current_state.get('holdings', {}).items():
        if shares > 0.01:
            # Use reality prices as fallback if alternate doesn't have prices
            price = current_state.get('latest_prices', {}).get(ticker, 0)
            if price == 0:
                price = reality_prices.get(ticker, 0)
            cost_info = current_state.get('cost_basis', {}).get(ticker, {})
            holdings.append({
                "ticker": ticker,
                "shares": shares,
                "current_price": price,
                "market_value": shares * price,
                "avg_cost": cost_info.get('avg_price', 0),
                "unrealized_gain_pct": ((price - cost_info.get('avg_price', 1)) / cost_info.get('avg_price', 1) * 100) if cost_info.get('avg_price', 0) > 0 else 0
            })

    # Generate analysis and projections
    if use_llm:
        analysis = get_llm_analysis_for_projection(holdings, years, history_context, idea_context)
    else:
        analysis = get_statistical_analysis_for_projection(holdings, years, history_context, idea_context)

    # Generate future price frames
    projection_id = str(uuid.uuid4())[:8]
    start_date = datetime.now()
    frames = generate_future_frames_for_projection(
        holdings,
        analysis,
        start_date,
        years,
        idea_context
    )

    projection = {
        "id": projection_id,
        "history_id": history_id,
        "created_at": datetime.now().isoformat(),
        "years": years,
        "start_date": start_date.isoformat(),
        "end_date": (start_date + timedelta(days=years * 365)).isoformat(),
        "current_state": {
            "total_value": current_state.get('total_value', 0),
            "cash": current_state.get('cash', 0),
            "portfolio_value": current_state.get('portfolio_value', 0),
            "holdings_count": len(holdings)
        },
        "analysis": analysis,
        "frames": frames,
        "projected_state": frames[-1] if frames else None,
        "applied_ideas": applied_ideas if applied_ideas else None
    }

    # Save projection
    save_projection(projection)

    return projection


def get_llm_analysis_for_projection(holdings: list, years: int, history_context: dict = None, idea_context: dict = None) -> dict:
    """Get LLM-powered analysis of holdings and market trends for projections."""
    try:
        from llm.config import get_llm_config
        from llm.client import get_llm_client

        config = get_llm_config()
        if not config.enabled:
            return get_statistical_analysis_for_projection(holdings, years, history_context, idea_context)

        # Build analysis prompt (simplified version)
        holdings_summary = "\n".join([
            f"- {h['ticker']}: {h['shares']:.0f} shares @ ${h['current_price']:.2f}"
            for h in holdings
        ])

        prompt = f"""Analyze these portfolio holdings for a {years}-year projection:

CURRENT HOLDINGS:
{holdings_summary}

Provide JSON with ticker_analysis and portfolio_projection."""

        client = get_llm_client()
        if client is None:
            return get_statistical_analysis_for_projection(holdings, years, history_context, idea_context)

        response = client.generate(prompt, max_tokens=2000)

        # Parse JSON from response
        try:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                analysis = json.loads(response[json_start:json_end])
                analysis["source"] = "llm"
                return analysis
        except json.JSONDecodeError:
            pass

        return get_statistical_analysis_for_projection(holdings, years, history_context, idea_context)

    except Exception as e:
        print(f"LLM analysis failed: {e}")
        return get_statistical_analysis_for_projection(holdings, years, history_context, idea_context)


def get_statistical_analysis_for_projection(holdings: list, years: int, history_context: dict = None, idea_context: dict = None) -> dict:
    """Generate statistical analysis for projections without LLM."""
    growth_multiplier = 1.0

    # Default sector characteristics
    sector_profiles = {
        "TSLA": {"growth": 20, "volatility": 45},
        "META": {"growth": 15, "volatility": 30},
        "DEFAULT": {"growth": 10, "volatility": 25}
    }

    ticker_analysis = {}
    for h in holdings:
        ticker = h['ticker']
        profile = sector_profiles.get(ticker, sector_profiles["DEFAULT"])
        base_growth = profile["growth"] * growth_multiplier

        ticker_analysis[ticker] = {
            "annual_growth_rates": {
                "pessimistic": base_growth - profile["volatility"] * 0.5,
                "base": base_growth,
                "optimistic": base_growth + profile["volatility"] * 0.5
            }
        }

    return {
        "source": "statistical",
        "growth_multiplier": growth_multiplier,
        "ticker_analysis": ticker_analysis,
        "portfolio_projection": {}
    }


def generate_future_frames_for_projection(
    holdings: list,
    analysis: dict,
    start_date: datetime,
    years: int,
    idea_context: dict = None
) -> list:
    """Generate monthly frames for the projected future."""
    frames = []
    ticker_analysis = analysis.get("ticker_analysis", {})
    months = years * 12

    for month in range(months + 1):
        frame_date = start_date + timedelta(days=month * 30)
        frame_holdings = []
        total_value = 0

        for h in holdings:
            ticker = h["ticker"]
            current_price = h.get("current_price", 0)

            if current_price <= 0:
                continue

            ta = ticker_analysis.get(ticker, {})
            growth_rates = ta.get("annual_growth_rates", {"base": 10})
            base_growth = growth_rates.get("base", 10)
            annual_growth = base_growth / 100
            noise = random.gauss(0, 0.015)

            growth_factor = (1 + annual_growth / 12 + noise) ** month
            projected_price = current_price * growth_factor
            holding_value = h["shares"] * projected_price
            total_value += holding_value

            frame_holdings.append({
                "ticker": ticker,
                "shares": h["shares"],
                "price": round(projected_price, 2),
                "value": round(holding_value, 2),
                "change_from_start": round((projected_price / current_price - 1) * 100, 1)
            })

        frames.append({
            "date": frame_date.isoformat()[:10],
            "month": month,
            "year": round(month / 12, 2),
            "total_value": round(total_value, 2),
            "holdings": frame_holdings,
            "is_projection": True
        })

    return frames


def save_projection(projection: dict):
    """Save a projection to disk."""
    ensure_storage()
    filepath = PROJECTIONS_DIR / f"{projection['id']}.json"
    with open(filepath, 'w') as f:
        json.dump(projection, f, indent=2, default=str)


def load_projection(projection_id: str) -> Optional[dict]:
    """Load a projection from disk."""
    filepath = PROJECTIONS_DIR / f"{projection_id}.json"
    if not filepath.exists():
        return None
    with open(filepath) as f:
        return json.load(f)


def list_projections() -> list:
    """List all saved projections."""
    ensure_storage()
    projections = []
    for f in PROJECTIONS_DIR.glob("*.json"):
        try:
            with open(f) as file:
                p = json.load(file)
                projections.append({
                    "id": p.get("id"),
                    "history_id": p.get("history_id"),
                    "created_at": p.get("created_at"),
                    "years": p.get("years"),
                    "end_date": p.get("end_date")
                })
        except:
            pass
    return sorted(projections, key=lambda x: x.get("created_at", ""), reverse=True)


def delete_projection(projection_id: str) -> bool:
    """Delete a projection."""
    filepath = PROJECTIONS_DIR / f"{projection_id}.json"
    if filepath.exists():
        filepath.unlink()
        return True
    return False
