"""Alternate History Service - Create and manage alternate portfolio realities."""

import json
import uuid
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional
import pandas as pd

# Storage location
DATA_DIR = Path(__file__).parent.parent.parent / "data"
ALT_HISTORIES_DIR = DATA_DIR / "alt_histories"
ALT_HISTORIES_INDEX = ALT_HISTORIES_DIR / "index.json"


def ensure_storage():
    """Ensure storage directory exists."""
    ALT_HISTORIES_DIR.mkdir(parents=True, exist_ok=True)
    if not ALT_HISTORIES_INDEX.exists():
        with open(ALT_HISTORIES_INDEX, 'w') as f:
            json.dump({"histories": []}, f)


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


def create_history(name: str, description: str = "", modifications: list = None) -> dict:
    """Create a new alternate history.

    Args:
        name: Display name for this reality
        description: What-if scenario description
        modifications: List of modification rules to apply

    Returns:
        The created history metadata
    """
    ensure_storage()

    history_id = str(uuid.uuid4())[:8]

    # Copy the real event log as base
    real_events = DATA_DIR / "event_log_enhanced.csv"
    alt_events = ALT_HISTORIES_DIR / f"{history_id}.csv"
    shutil.copy(real_events, alt_events)

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
        "event_count": len(pd.read_csv(alt_events))
    }

    # Add to index
    index = load_index()
    index["histories"].append(history)
    save_index(index)

    return history


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


def compare_histories(history_id_1: str, history_id_2: str = "reality") -> dict:
    """Compare two histories (or one against reality).

    Args:
        history_id_1: First history ID
        history_id_2: Second history ID or "reality" for the real event log

    Returns:
        Comparison data including portfolio values, holdings differences, etc.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from reconstruct_state import reconstruct_state, load_event_log

    # Load first history
    if history_id_1 == "reality":
        events1 = load_event_log(str(DATA_DIR / "event_log_enhanced.csv"))
        name1 = "Reality"
    else:
        events1 = get_history_events(history_id_1)
        h1 = get_history(history_id_1)
        name1 = h1["name"] if h1 else history_id_1

    # Load second history
    if history_id_2 == "reality":
        events2 = load_event_log(str(DATA_DIR / "event_log_enhanced.csv"))
        name2 = "Reality"
    else:
        events2 = get_history_events(history_id_2)
        h2 = get_history(history_id_2)
        name2 = h2["name"] if h2 else history_id_2

    if events1 is None or events2 is None:
        return {"error": "History not found"}

    # Reconstruct states
    state1 = reconstruct_state(events1)
    state2 = reconstruct_state(events2)

    # Calculate differences
    holdings_diff = {}
    all_tickers = set(state1.get('holdings', {}).keys()) | set(state2.get('holdings', {}).keys())

    for ticker in all_tickers:
        shares1 = state1.get('holdings', {}).get(ticker, 0)
        shares2 = state2.get('holdings', {}).get(ticker, 0)
        price = state1.get('latest_prices', {}).get(ticker, 0)

        if shares1 > 0.01 or shares2 > 0.01:
            holdings_diff[ticker] = {
                "shares_1": shares1,
                "shares_2": shares2,
                "diff": shares2 - shares1,
                "value_1": shares1 * price,
                "value_2": shares2 * price,
                "value_diff": (shares2 - shares1) * price
            }

    return {
        "history_1": {
            "id": history_id_1,
            "name": name1,
            "total_value": state1.get('total_value', 0),
            "cash": state1.get('cash', 0),
            "portfolio_value": state1.get('portfolio_value', 0),
            "ytd_income": state1.get('ytd_income', 0),
            "holdings_count": len([s for s in state1.get('holdings', {}).values() if s > 0.01])
        },
        "history_2": {
            "id": history_id_2,
            "name": name2,
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
        }
    }
