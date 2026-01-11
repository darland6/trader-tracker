"""Token usage tracking for LLM calls.

Tracks prompt tokens, completion tokens, and costs over time.
Aggregates usage by day, model, and endpoint.
"""

import json
from pathlib import Path
from datetime import datetime, date
from typing import Optional

# Usage file location
DATA_DIR = Path(__file__).parent.parent.parent / "data"
USAGE_FILE = DATA_DIR / "llm_usage.json"


def _ensure_usage_file():
    """Ensure the usage file exists."""
    DATA_DIR.mkdir(exist_ok=True)
    if not USAGE_FILE.exists():
        USAGE_FILE.write_text(json.dumps({
            "created": datetime.now().isoformat(),
            "total": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "requests": 0
            },
            "by_day": {},
            "by_model": {},
            "by_endpoint": {},
            "recent_calls": []
        }, indent=2))


def load_usage() -> dict:
    """Load the usage file."""
    _ensure_usage_file()
    try:
        return json.loads(USAGE_FILE.read_text())
    except (json.JSONDecodeError, IOError):
        return {
            "total": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "requests": 0},
            "by_day": {},
            "by_model": {},
            "by_endpoint": {},
            "recent_calls": []
        }


def save_usage(usage: dict) -> None:
    """Save the usage file."""
    _ensure_usage_file()
    usage["last_updated"] = datetime.now().isoformat()
    USAGE_FILE.write_text(json.dumps(usage, indent=2))


def track_usage(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    endpoint: str = "chat",
    duration_ms: Optional[int] = None
) -> None:
    """Track a single LLM usage event.

    Args:
        model: Model name (e.g., "meta/llama-3.3-70b")
        prompt_tokens: Number of input tokens
        completion_tokens: Number of output tokens
        endpoint: Which endpoint made the call (chat, insights, research)
        duration_ms: How long the request took in milliseconds
    """
    usage = load_usage()
    total_tokens = prompt_tokens + completion_tokens
    today = date.today().isoformat()

    # Update totals
    usage["total"]["prompt_tokens"] += prompt_tokens
    usage["total"]["completion_tokens"] += completion_tokens
    usage["total"]["total_tokens"] += total_tokens
    usage["total"]["requests"] += 1

    # Update by day
    if today not in usage["by_day"]:
        usage["by_day"][today] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "requests": 0
        }
    usage["by_day"][today]["prompt_tokens"] += prompt_tokens
    usage["by_day"][today]["completion_tokens"] += completion_tokens
    usage["by_day"][today]["total_tokens"] += total_tokens
    usage["by_day"][today]["requests"] += 1

    # Update by model
    if model not in usage["by_model"]:
        usage["by_model"][model] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "requests": 0
        }
    usage["by_model"][model]["prompt_tokens"] += prompt_tokens
    usage["by_model"][model]["completion_tokens"] += completion_tokens
    usage["by_model"][model]["total_tokens"] += total_tokens
    usage["by_model"][model]["requests"] += 1

    # Update by endpoint
    if endpoint not in usage["by_endpoint"]:
        usage["by_endpoint"][endpoint] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "requests": 0
        }
    usage["by_endpoint"][endpoint]["prompt_tokens"] += prompt_tokens
    usage["by_endpoint"][endpoint]["completion_tokens"] += completion_tokens
    usage["by_endpoint"][endpoint]["total_tokens"] += total_tokens
    usage["by_endpoint"][endpoint]["requests"] += 1

    # Add to recent calls (keep last 100)
    call_record = {
        "timestamp": datetime.now().isoformat(),
        "model": model,
        "endpoint": endpoint,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens
    }
    if duration_ms:
        call_record["duration_ms"] = duration_ms
        call_record["tokens_per_sec"] = round(completion_tokens / (duration_ms / 1000), 1) if duration_ms > 0 else 0

    usage["recent_calls"].append(call_record)
    usage["recent_calls"] = usage["recent_calls"][-100:]  # Keep last 100

    save_usage(usage)


def get_usage_summary() -> dict:
    """Get a summary of token usage."""
    usage = load_usage()
    today = date.today().isoformat()

    # Calculate today's usage
    today_usage = usage.get("by_day", {}).get(today, {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "requests": 0
    })

    # Get recent calls stats
    recent = usage.get("recent_calls", [])[-10:]
    avg_tokens_per_sec = 0
    if recent:
        speeds = [c.get("tokens_per_sec", 0) for c in recent if c.get("tokens_per_sec")]
        if speeds:
            avg_tokens_per_sec = round(sum(speeds) / len(speeds), 1)

    return {
        "total": usage.get("total", {}),
        "today": today_usage,
        "by_model": usage.get("by_model", {}),
        "by_endpoint": usage.get("by_endpoint", {}),
        "recent_calls": recent,
        "avg_tokens_per_sec": avg_tokens_per_sec,
        "last_updated": usage.get("last_updated")
    }


def get_daily_usage(days: int = 30) -> list:
    """Get daily usage for the last N days."""
    usage = load_usage()
    by_day = usage.get("by_day", {})

    # Sort by date descending and take last N days
    sorted_days = sorted(by_day.items(), key=lambda x: x[0], reverse=True)[:days]

    return [{"date": d, **stats} for d, stats in sorted_days]
