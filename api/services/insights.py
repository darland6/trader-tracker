"""Insight Generation Service - Generate deep analysis of portfolio events.

This service provides:
1. Event-specific insights (reasoning, future advice, past reflection)
2. Batch insight generation for tickers or date ranges
3. Pattern reflection across trading history
4. Insight caching in memory
"""

import json
import re
from datetime import datetime
from typing import Optional, List
from pathlib import Path

# Insight cache in memory file
MEMORY_DIR = Path(__file__).parent.parent.parent / "data"
INSIGHT_CACHE_FILE = MEMORY_DIR / "insight_cache.json"


def _load_insight_cache() -> dict:
    """Load cached insights."""
    if INSIGHT_CACHE_FILE.exists():
        try:
            return json.loads(INSIGHT_CACHE_FILE.read_text())
        except:
            pass
    return {"events": {}, "reflections": {}}


def _save_insight_cache(cache: dict) -> None:
    """Save insights to cache."""
    INSIGHT_CACHE_FILE.parent.mkdir(exist_ok=True)
    cache["last_updated"] = datetime.now().isoformat()
    INSIGHT_CACHE_FILE.write_text(json.dumps(cache, indent=2))


def get_cached_insight(event_id: int) -> Optional[dict]:
    """Get cached insight for an event."""
    cache = _load_insight_cache()
    return cache.get("events", {}).get(str(event_id))


def cache_insight(event_id: int, insight: dict) -> None:
    """Cache an insight for an event."""
    cache = _load_insight_cache()
    if "events" not in cache:
        cache["events"] = {}
    cache["events"][str(event_id)] = {
        **insight,
        "cached_at": datetime.now().isoformat()
    }
    _save_insight_cache(cache)


def find_event_by_description(description: str, events: list) -> Optional[dict]:
    """Find an event matching a description like 'last TSLA trade'.

    Supports patterns like:
    - 'last TSLA trade'
    - 'recent META put'
    - 'first deposit'
    - 'option on NVDA'
    """
    description = description.lower().strip()

    # Check for event ID
    if description.isdigit():
        event_id = int(description)
        for event in events:
            if event.get('event_id') == event_id:
                return event
        return None

    # Parse the description
    is_last = 'last' in description or 'recent' in description
    is_first = 'first' in description

    # Extract ticker if present (look for uppercase words)
    ticker_match = re.search(r'\b([A-Z]{2,5})\b', description.upper())
    ticker = ticker_match.group(1) if ticker_match else None

    # Determine event type
    event_type = None
    if 'trade' in description or 'buy' in description or 'sell' in description:
        event_type = 'TRADE'
    elif 'option' in description or 'put' in description or 'call' in description:
        event_type = 'OPTION'  # Will match OPTION_OPEN, OPTION_CLOSE, etc.
    elif 'deposit' in description:
        event_type = 'DEPOSIT'
    elif 'withdraw' in description:
        event_type = 'WITHDRAWAL'
    elif 'dividend' in description:
        event_type = 'DIVIDEND'

    # Filter events
    matches = []
    for event in events:
        data = json.loads(event.get('data_json', '{}'))

        # Filter by ticker
        if ticker and data.get('ticker', '').upper() != ticker:
            continue

        # Filter by event type
        if event_type and event_type not in event.get('event_type', ''):
            continue

        matches.append(event)

    if not matches:
        return None

    # Sort by timestamp
    matches.sort(key=lambda x: x.get('timestamp', ''), reverse=not is_first)

    return matches[0]


def format_event_for_analysis(event: dict) -> str:
    """Format an event for LLM analysis."""
    data = json.loads(event.get('data_json', '{}'))
    reason = json.loads(event.get('reason_json', '{}'))

    lines = [
        f"Event ID: {event.get('event_id')}",
        f"Timestamp: {event.get('timestamp')}",
        f"Type: {event.get('event_type')}",
    ]

    if event['event_type'] == 'TRADE':
        lines.append(f"Action: {data.get('action')} {data.get('shares')} shares of {data.get('ticker')} @ ${data.get('price')}")
        if data.get('gain_loss'):
            lines.append(f"Realized Gain/Loss: ${data.get('gain_loss'):,.2f}")
        if data.get('total'):
            lines.append(f"Total: ${data.get('total'):,.2f}")

    elif 'OPTION' in event['event_type']:
        lines.append(f"Ticker: {data.get('ticker')}")
        lines.append(f"Strategy: {data.get('strategy')} @ ${data.get('strike')}")
        lines.append(f"Expiration: {data.get('expiration')}")
        if data.get('total_premium'):
            lines.append(f"Premium: ${data.get('total_premium'):,.2f}")
        if data.get('profit'):
            lines.append(f"Profit: ${data.get('profit'):,.2f}")

    elif event['event_type'] in ('DEPOSIT', 'WITHDRAWAL'):
        lines.append(f"Amount: ${data.get('amount'):,.2f}")
        if data.get('source'):
            lines.append(f"Source: {data.get('source')}")
        if data.get('purpose'):
            lines.append(f"Purpose: {data.get('purpose')}")

    elif event['event_type'] == 'DIVIDEND':
        lines.append(f"Ticker: {data.get('ticker')}")
        lines.append(f"Amount: ${data.get('amount'):,.2f}")

    if event.get('notes'):
        lines.append(f"Notes: {event.get('notes')}")

    if reason.get('explanation'):
        lines.append(f"User Reason: {reason.get('explanation')}")

    if reason.get('primary'):
        lines.append(f"Reason Category: {reason.get('primary')}")

    return "\n".join(lines)


def generate_insight_prompt(event: dict, portfolio_state: dict, related_events: list) -> str:
    """Generate the prompt for insight generation."""
    event_str = format_event_for_analysis(event)

    # Format portfolio state
    holdings_str = ", ".join([
        f"{t}: {s:.2f} shares"
        for t, s in portfolio_state.get('holdings', {}).items()
        if s > 0.01
    ]) or "None"

    # Format related events
    related_str = ""
    if related_events:
        related_str = "Related Events:\n"
        for e in related_events[:5]:
            data = json.loads(e.get('data_json', '{}'))
            related_str += f"  [{e['event_id']}] {e['timestamp'][:10]} {e['event_type']}: {data.get('ticker', '')} {data.get('action', '')}\n"

    return f"""Analyze this portfolio event and generate insights:

{event_str}

Current Portfolio State:
- Cash: ${portfolio_state.get('cash', 0):,.2f}
- Holdings: {holdings_str}
- YTD Income: ${portfolio_state.get('ytd_income', 0):,.2f} / $30,000 goal

{related_str}

Generate a JSON response with three insights:
{{
  "reasoning": "Why this decision makes sense given the portfolio context and market conditions. Be specific with numbers.",
  "future_advice": "Actionable advice for similar future situations. Include specific price levels or conditions.",
  "past_reflection": "How this connects to previous similar decisions. Note patterns or lessons learned."
}}

Keep each insight to 2-3 sentences. Be specific and quantitative."""


def find_related_events(event: dict, all_events: list, limit: int = 5) -> list:
    """Find events related to this one (same ticker, similar type)."""
    data = json.loads(event.get('data_json', '{}'))
    ticker = data.get('ticker')
    event_type = event.get('event_type')
    event_id = event.get('event_id')

    related = []
    for e in all_events:
        if e.get('event_id') == event_id:
            continue

        e_data = json.loads(e.get('data_json', '{}'))
        e_ticker = e_data.get('ticker')

        # Same ticker or same event type
        if ticker and e_ticker == ticker:
            related.append(e)
        elif e.get('event_type') == event_type:
            related.append(e)

    # Sort by timestamp (most recent first)
    related.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    return related[:limit]


def filter_events_by_criteria(events: list, ticker: str = None, date_prefix: str = None) -> list:
    """Filter events by ticker or date range."""
    results = []

    for event in events:
        data = json.loads(event.get('data_json', '{}'))

        if ticker and data.get('ticker', '').upper() != ticker.upper():
            continue

        if date_prefix and not event.get('timestamp', '').startswith(date_prefix):
            continue

        # Skip price updates
        if event.get('event_type') == 'PRICE_UPDATE':
            continue

        results.append(event)

    return results


# Reflection templates for common topics
REFLECTION_TOPICS = {
    "options": {
        "description": "Options trading strategy and outcomes",
        "event_types": ["OPTION_OPEN", "OPTION_CLOSE", "OPTION_EXPIRE", "OPTION_ASSIGN"],
        "metrics": ["total_premium", "profit", "strike", "expiration"]
    },
    "risk": {
        "description": "Risk management and position sizing",
        "event_types": ["TRADE", "OPTION_OPEN"],
        "metrics": ["total", "shares", "price"]
    },
    "income": {
        "description": "Income generation progress toward $30K goal",
        "event_types": ["OPTION_CLOSE", "OPTION_EXPIRE", "DIVIDEND", "TRADE"],
        "metrics": ["profit", "amount", "gain_loss"]
    },
    "trading": {
        "description": "Stock trading patterns and decisions",
        "event_types": ["TRADE"],
        "metrics": ["action", "shares", "price", "gain_loss"]
    }
}


def get_reflection_context(topic: str, events: list, portfolio_state: dict) -> str:
    """Build context for a reflection on a topic."""
    topic_lower = topic.lower()

    # Find matching topic template
    template = None
    for key, value in REFLECTION_TOPICS.items():
        if key in topic_lower or topic_lower in value["description"].lower():
            template = value
            break

    if not template:
        template = {
            "description": topic,
            "event_types": [],
            "metrics": []
        }

    # Filter relevant events
    relevant = []
    for event in events:
        if template["event_types"] and event.get("event_type") not in template["event_types"]:
            continue
        if event.get("event_type") == "PRICE_UPDATE":
            continue
        relevant.append(event)

    # Format events
    events_str = ""
    for e in relevant[:20]:
        data = json.loads(e.get('data_json', '{}'))
        reason = json.loads(e.get('reason_json', '{}'))

        event_line = f"[{e['event_id']}] {e['timestamp'][:10]} {e['event_type']}"

        if e['event_type'] == 'TRADE':
            event_line += f": {data.get('action')} {data.get('shares')} {data.get('ticker')} @ ${data.get('price')}"
            if data.get('gain_loss'):
                event_line += f" (P/L: ${data['gain_loss']:,.0f})"
        elif 'OPTION' in e['event_type']:
            event_line += f": {data.get('ticker')} ${data.get('strike')} {data.get('strategy')}"
            if data.get('total_premium'):
                event_line += f" (${ data['total_premium']:,.0f})"
            if data.get('profit'):
                event_line += f" profit: ${data['profit']:,.0f}"
        elif e['event_type'] == 'DIVIDEND':
            event_line += f": {data.get('ticker')} ${data.get('amount'):,.2f}"

        if reason.get('primary'):
            event_line += f" [{reason['primary']}]"

        events_str += event_line + "\n"

    return f"""Generate a reflection on: {topic}

Relevant Events ({len(relevant)} total, showing latest 20):
{events_str}

Current Portfolio State:
- Total Value: ${portfolio_state.get('total_value', 0):,.0f}
- Cash: ${portfolio_state.get('cash', 0):,.0f}
- YTD Income: ${portfolio_state.get('ytd_income', 0):,.0f} / $30,000 goal

Generate a thoughtful reflection covering:
1. Key patterns observed in the data
2. What's working well
3. Areas for improvement
4. Specific recommendations

Be specific and reference actual events when possible."""
