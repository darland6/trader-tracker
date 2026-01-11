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
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
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
        from api.services.future_projection import generate_projection

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


def build_historical_timeline(events1: pd.DataFrame, events2: pd.DataFrame,
                             name1: str, name2: str) -> list:
    """Build a timeline showing how portfolio values evolved differently.

    Reconstructs state at key points to show divergence over time.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
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
