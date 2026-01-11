"""LangSmith tracing service for LLM observability.

Provides live session token tracking, latency monitoring, and cost estimation.
"""

import os
import time
import uuid
from datetime import datetime
from typing import Optional, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path

# Session storage
_current_session: Optional["TracingSession"] = None
_session_history: list[dict] = []


@dataclass
class LLMTrace:
    """Individual LLM call trace."""
    trace_id: str
    timestamp: str
    model: str
    endpoint: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: int
    success: bool
    error: Optional[str] = None
    cost_estimate: float = 0.0
    metadata: dict = field(default_factory=dict)


@dataclass
class TracingSession:
    """Active tracing session with aggregated stats."""
    session_id: str
    started_at: str
    traces: list[LLMTrace] = field(default_factory=list)
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    total_latency_ms: int = 0
    call_count: int = 0
    error_count: int = 0

    def add_trace(self, trace: LLMTrace):
        """Add a trace to the session and update aggregates."""
        self.traces.append(trace)
        self.total_prompt_tokens += trace.prompt_tokens
        self.total_completion_tokens += trace.completion_tokens
        self.total_tokens += trace.total_tokens
        self.total_cost += trace.cost_estimate
        self.total_latency_ms += trace.latency_ms
        self.call_count += 1
        if not trace.success:
            self.error_count += 1

    def to_dict(self) -> dict:
        """Convert session to dictionary for API response."""
        return {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "duration_seconds": self._get_duration(),
            "call_count": self.call_count,
            "error_count": self.error_count,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "total_cost": round(self.total_cost, 4),
            "avg_latency_ms": self.total_latency_ms // self.call_count if self.call_count > 0 else 0,
            "traces": [asdict(t) for t in self.traces[-20:]],  # Last 20 traces
        }

    def _get_duration(self) -> int:
        """Get session duration in seconds."""
        started = datetime.fromisoformat(self.started_at)
        return int((datetime.now() - started).total_seconds())


# Cost estimates per 1K tokens (approximate, varies by model)
COST_PER_1K_TOKENS = {
    # Claude models
    "claude-3-opus": {"input": 0.015, "output": 0.075},
    "claude-3-sonnet": {"input": 0.003, "output": 0.015},
    "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
    "claude-sonnet-4": {"input": 0.003, "output": 0.015},
    # Local models (no cost)
    "local": {"input": 0.0, "output": 0.0},
}


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate cost for an LLM call."""
    # Find matching cost tier
    costs = COST_PER_1K_TOKENS.get("local")  # Default to local (free)

    for prefix, tier_costs in COST_PER_1K_TOKENS.items():
        if prefix in model.lower():
            costs = tier_costs
            break

    input_cost = (prompt_tokens / 1000) * costs["input"]
    output_cost = (completion_tokens / 1000) * costs["output"]

    return input_cost + output_cost


def start_session() -> TracingSession:
    """Start a new tracing session."""
    global _current_session

    # Save previous session if exists
    if _current_session and _current_session.call_count > 0:
        _session_history.append(_current_session.to_dict())
        # Keep only last 10 sessions
        if len(_session_history) > 10:
            _session_history.pop(0)

    _current_session = TracingSession(
        session_id=str(uuid.uuid4())[:8],
        started_at=datetime.now().isoformat()
    )

    return _current_session


def get_current_session() -> Optional[TracingSession]:
    """Get the current tracing session."""
    global _current_session
    return _current_session


def ensure_session() -> TracingSession:
    """Ensure a session exists, creating one if needed."""
    global _current_session
    if _current_session is None:
        _current_session = start_session()
    return _current_session


def trace_llm_call(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: int,
    endpoint: str = "chat",
    success: bool = True,
    error: Optional[str] = None,
    metadata: Optional[dict] = None
) -> LLMTrace:
    """Record an LLM call trace."""
    session = ensure_session()

    total_tokens = prompt_tokens + completion_tokens
    cost = estimate_cost(model, prompt_tokens, completion_tokens)

    trace = LLMTrace(
        trace_id=str(uuid.uuid4())[:8],
        timestamp=datetime.now().isoformat(),
        model=model,
        endpoint=endpoint,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        latency_ms=latency_ms,
        success=success,
        error=error,
        cost_estimate=cost,
        metadata=metadata or {}
    )

    session.add_trace(trace)

    # Also send to LangSmith if configured
    _send_to_langsmith(trace)

    return trace


def _send_to_langsmith(trace: LLMTrace):
    """Send trace to LangSmith if API key is configured."""
    api_key = os.getenv("LANGSMITH_API_KEY")
    if not api_key:
        return

    try:
        from langsmith import Client

        client = Client(api_key=api_key)

        # Create a run in LangSmith
        client.create_run(
            name=f"{trace.endpoint}/{trace.model}",
            run_type="llm",
            inputs={"endpoint": trace.endpoint},
            outputs={"success": trace.success},
            start_time=datetime.fromisoformat(trace.timestamp),
            end_time=datetime.now(),
            extra={
                "metadata": {
                    "model": trace.model,
                    "prompt_tokens": trace.prompt_tokens,
                    "completion_tokens": trace.completion_tokens,
                    "total_tokens": trace.total_tokens,
                    "latency_ms": trace.latency_ms,
                    "cost_estimate": trace.cost_estimate,
                    **trace.metadata
                }
            },
            error=trace.error if not trace.success else None,
            project_name=os.getenv("LANGSMITH_PROJECT", "trader-tracker")
        )
    except Exception as e:
        # Don't fail the request if LangSmith logging fails
        print(f"[LangSmith] Failed to log trace: {e}")


def get_session_stats() -> dict:
    """Get current session statistics."""
    session = get_current_session()

    if session is None:
        return {
            "active": False,
            "message": "No active session"
        }

    return {
        "active": True,
        **session.to_dict()
    }


def get_session_history() -> list[dict]:
    """Get history of previous sessions."""
    return list(_session_history)


def is_langsmith_configured() -> bool:
    """Check if LangSmith is configured."""
    return bool(os.getenv("LANGSMITH_API_KEY"))


def get_langsmith_status() -> dict:
    """Get LangSmith configuration status."""
    configured = is_langsmith_configured()

    return {
        "configured": configured,
        "project": os.getenv("LANGSMITH_PROJECT", "trader-tracker") if configured else None,
        "api_key_set": configured
    }
