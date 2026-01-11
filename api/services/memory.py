"""Persistent memory service for LLM context across sessions.

This service maintains a knowledge file that accumulates insights and context
from LLM interactions, allowing the assistant to "remember" past conversations.

File is capped at MAX_FILE_SIZE_MB to prevent unbounded growth. When the limit
is reached, older entries are automatically pruned to make room for new ones.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional

# Memory file location
MEMORY_DIR = Path(__file__).parent.parent.parent / "data"
MEMORY_FILE = MEMORY_DIR / "llm_memory.json"

# File size limit (1GB)
MAX_FILE_SIZE_MB = 1024
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# Entry limits
MAX_MEMORY_ENTRIES = 10000  # Absolute max entries
MAX_PATTERNS = 500  # Max learned patterns
PRUNE_PERCENTAGE = 0.25  # Remove 25% of oldest entries when pruning


def _ensure_memory_file():
    """Ensure the memory file exists."""
    MEMORY_DIR.mkdir(exist_ok=True)
    if not MEMORY_FILE.exists():
        MEMORY_FILE.write_text(json.dumps({
            "created": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "project_context": {
                "name": "Portfolio Tracker",
                "goal": "$30,000/year income through options and trading",
                "key_insights": []
            },
            "conversation_memories": [],
            "learned_patterns": [],
            "user_preferences": {}
        }, indent=2))


def load_memory() -> dict:
    """Load the memory file."""
    _ensure_memory_file()
    try:
        return json.loads(MEMORY_FILE.read_text())
    except (json.JSONDecodeError, IOError):
        return {
            "project_context": {},
            "conversation_memories": [],
            "learned_patterns": [],
            "user_preferences": {}
        }


def _check_file_size_and_prune(memory: dict) -> dict:
    """Check if memory would exceed size limit and prune if needed."""
    # Serialize to check size
    content = json.dumps(memory, indent=2)
    size_bytes = len(content.encode('utf-8'))

    if size_bytes <= MAX_FILE_SIZE_BYTES:
        return memory  # Under limit, no pruning needed

    # Calculate how many entries to remove
    conversations = memory.get("conversation_memories", [])
    patterns = memory.get("learned_patterns", [])

    if conversations:
        # Remove oldest 25% of conversations
        prune_count = max(1, int(len(conversations) * PRUNE_PERCENTAGE))
        memory["conversation_memories"] = conversations[prune_count:]
        memory.setdefault("stats", {})
        memory["stats"]["last_prune"] = datetime.now().isoformat()
        memory["stats"]["entries_pruned"] = memory["stats"].get("entries_pruned", 0) + prune_count

    if len(patterns) > MAX_PATTERNS:
        # Keep most recent patterns
        memory["learned_patterns"] = patterns[-MAX_PATTERNS:]

    # Recursively check if still too large
    content = json.dumps(memory, indent=2)
    if len(content.encode('utf-8')) > MAX_FILE_SIZE_BYTES:
        return _check_file_size_and_prune(memory)

    return memory


def save_memory(memory: dict) -> None:
    """Save the memory file, pruning if size limit exceeded."""
    _ensure_memory_file()
    memory["last_updated"] = datetime.now().isoformat()

    # Check size and prune if needed
    memory = _check_file_size_and_prune(memory)

    MEMORY_FILE.write_text(json.dumps(memory, indent=2))


def get_memory_stats() -> dict:
    """Get statistics about the memory file."""
    if not MEMORY_FILE.exists():
        return {"exists": False}

    memory = load_memory()
    file_size = MEMORY_FILE.stat().st_size

    return {
        "exists": True,
        "file_size_bytes": file_size,
        "file_size_mb": round(file_size / (1024 * 1024), 2),
        "max_size_mb": MAX_FILE_SIZE_MB,
        "usage_percent": round((file_size / MAX_FILE_SIZE_BYTES) * 100, 2),
        "conversation_count": len(memory.get("conversation_memories", [])),
        "pattern_count": len(memory.get("learned_patterns", [])),
        "preference_count": len(memory.get("user_preferences", {})),
        "created": memory.get("created"),
        "last_updated": memory.get("last_updated"),
        "entries_pruned": memory.get("stats", {}).get("entries_pruned", 0)
    }


def add_memory_entry(
    user_query: str,
    assistant_response: str,
    summary: str,
    intent: str,
    key_facts: list[str] = None,
    tags: list[str] = None
) -> None:
    """Add a new memory entry from an LLM interaction.

    Args:
        user_query: What the user asked
        assistant_response: What the assistant said (truncated)
        summary: Brief summary of the interaction
        intent: The user's apparent intent
        key_facts: Important facts learned
        tags: Categories for this interaction
    """
    memory = load_memory()

    entry = {
        "timestamp": datetime.now().isoformat(),
        "user_query": user_query[:200] + "..." if len(user_query) > 200 else user_query,
        "summary": summary,
        "intent": intent,
        "key_facts": key_facts or [],
        "tags": tags or []
    }

    memory["conversation_memories"].append(entry)

    # Trim to max entries (file size is also checked in save_memory)
    if len(memory["conversation_memories"]) > MAX_MEMORY_ENTRIES:
        memory["conversation_memories"] = memory["conversation_memories"][-MAX_MEMORY_ENTRIES:]

    # Save will also check file size and prune if needed
    save_memory(memory)


def add_learned_pattern(
    pattern: str,
    category: str = "general",
    source: str = "observed",  # "observed" | "stated" | "inferred"
    confidence: float = 0.5,
    evidence: str = None
) -> dict:
    """Add or update a learned pattern about the user or their portfolio.

    If a similar pattern exists in the same category, increases its confidence
    and adds new evidence. Otherwise creates a new pattern.

    Args:
        pattern: The pattern description
        category: Category (trading_style, risk_tolerance, position_sizing, timing_preference, ticker_affinity, strategy_preference, goal_alignment)
        source: How the pattern was learned (observed, stated, inferred)
        confidence: Initial confidence (0.0-1.0), stated patterns start higher
        evidence: Evidence for this pattern (event ID, quote, etc.)

    Returns:
        The pattern entry (new or updated)
    """
    memory = load_memory()

    # Normalize pattern for comparison
    pattern_lower = pattern.lower().strip()

    # Look for existing similar pattern in same category
    existing_idx = None
    for idx, p in enumerate(memory.get("learned_patterns", [])):
        if p.get("category") == category:
            existing_lower = p.get("pattern", "").lower()
            # Check for similarity (contains key words or very similar)
            if (pattern_lower in existing_lower or
                existing_lower in pattern_lower or
                _patterns_similar(pattern_lower, existing_lower)):
                existing_idx = idx
                break

    if existing_idx is not None:
        # Update existing pattern
        existing = memory["learned_patterns"][existing_idx]
        existing["evidence_count"] = existing.get("evidence_count", 1) + 1
        existing["confidence"] = min(1.0, existing.get("confidence", 0.5) + 0.1)
        existing["last_confirmed"] = datetime.now().isoformat()

        if evidence:
            existing.setdefault("evidence", []).append({
                "text": evidence,
                "timestamp": datetime.now().isoformat()
            })
            # Keep only last 10 evidence items
            existing["evidence"] = existing["evidence"][-10:]

        # Update pattern text if source is "stated" (user explicitly said it)
        if source == "stated":
            existing["pattern"] = pattern
            existing["confidence"] = max(existing["confidence"], 0.8)

        save_memory(memory)
        return existing
    else:
        # Create new pattern
        pattern_entry = {
            "timestamp": datetime.now().isoformat(),
            "pattern": pattern,
            "category": category,
            "source": source,
            "confidence": confidence if source != "stated" else max(confidence, 0.8),
            "evidence_count": 1,
            "last_confirmed": datetime.now().isoformat(),
            "evidence": [{"text": evidence, "timestamp": datetime.now().isoformat()}] if evidence else []
        }

        memory.setdefault("learned_patterns", []).append(pattern_entry)

        # Keep last 50 patterns
        if len(memory["learned_patterns"]) > MAX_PATTERNS:
            memory["learned_patterns"] = memory["learned_patterns"][-MAX_PATTERNS:]

        save_memory(memory)
        return pattern_entry


def _patterns_similar(p1: str, p2: str) -> bool:
    """Check if two patterns are similar enough to merge."""
    # Simple word overlap check
    words1 = set(p1.split())
    words2 = set(p2.split())
    if len(words1) < 3 or len(words2) < 3:
        return False
    overlap = len(words1 & words2)
    return overlap >= min(len(words1), len(words2)) * 0.6


def get_patterns_by_category(category: str = None) -> list:
    """Get learned patterns, optionally filtered by category."""
    memory = load_memory()
    patterns = memory.get("learned_patterns", [])

    if category:
        patterns = [p for p in patterns if p.get("category") == category]

    # Sort by confidence
    patterns.sort(key=lambda x: x.get("confidence", 0), reverse=True)
    return patterns


def get_high_confidence_patterns(min_confidence: float = 0.7) -> list:
    """Get patterns above a confidence threshold."""
    memory = load_memory()
    patterns = memory.get("learned_patterns", [])
    return [p for p in patterns if p.get("confidence", 0) >= min_confidence]


def update_user_preference(key: str, value: str) -> None:
    """Update a user preference."""
    memory = load_memory()
    memory["user_preferences"][key] = {
        "value": value,
        "updated": datetime.now().isoformat()
    }
    save_memory(memory)


def get_memory_context(max_entries: int = 20) -> str:
    """Get formatted memory context for injection into LLM prompts.

    Returns a formatted string summarizing past interactions and learned knowledge.
    """
    memory = load_memory()

    lines = []
    lines.append("## PERSISTENT MEMORY (from previous sessions)")
    lines.append("")

    # Project context
    ctx = memory.get("project_context", {})
    if ctx.get("key_insights"):
        lines.append("### Key Project Insights")
        for insight in ctx.get("key_insights", [])[-5:]:
            lines.append(f"- {insight}")
        lines.append("")

    # Learned patterns
    patterns = memory.get("learned_patterns", [])
    if patterns:
        lines.append("### Learned Patterns")
        for p in patterns[-10:]:
            lines.append(f"- [{p.get('category', 'general')}] {p.get('pattern', '')}")
        lines.append("")

    # Recent conversation summaries
    conversations = memory.get("conversation_memories", [])
    if conversations:
        lines.append("### Recent Interactions Summary")
        for conv in conversations[-max_entries:]:
            date = conv.get("timestamp", "")[:10]
            lines.append(f"- [{date}] {conv.get('intent', 'query')}: {conv.get('summary', '')}")
            if conv.get("key_facts"):
                for fact in conv.get("key_facts", []):
                    lines.append(f"  • {fact}")
        lines.append("")

    # User preferences
    prefs = memory.get("user_preferences", {})
    if prefs:
        lines.append("### User Preferences")
        for key, val in prefs.items():
            lines.append(f"- {key}: {val.get('value', '')}")
        lines.append("")

    if len(lines) <= 3:
        return ""  # No meaningful memory to share

    return "\n".join(lines)


def get_memory_summary_prompt() -> str:
    """Get the prompt to generate a memory summary after an interaction."""
    return """After responding to the user, generate a brief memory summary in JSON format:

{
    "summary": "One sentence summarizing what was discussed",
    "intent": "The user's goal (e.g., 'analyze trade', 'understand options', 'plan strategy')",
    "key_facts": ["Important fact 1", "Important fact 2"],
    "learned_patterns": ["Any pattern noticed about user's trading style or preferences"],
    "tags": ["category1", "category2"]
}

Keep the summary concise. Only include key_facts and learned_patterns if there's something genuinely new and important. Return ONLY the JSON, no other text."""


def parse_and_save_memory_summary(
    user_query: str,
    assistant_response: str,
    summary_json: str
) -> bool:
    """Parse the LLM's memory summary and save it.

    Returns True if successfully saved.
    """
    try:
        # Try to extract JSON from the response
        if "```json" in summary_json:
            summary_json = summary_json.split("```json")[1].split("```")[0]
        elif "```" in summary_json:
            summary_json = summary_json.split("```")[1].split("```")[0]

        data = json.loads(summary_json.strip())

        add_memory_entry(
            user_query=user_query,
            assistant_response=assistant_response[:500],
            summary=data.get("summary", ""),
            intent=data.get("intent", "general query"),
            key_facts=data.get("key_facts", []),
            tags=data.get("tags", [])
        )

        # Save any learned patterns
        for pattern in data.get("learned_patterns", []):
            if pattern:
                add_learned_pattern(pattern)

        return True

    except (json.JSONDecodeError, KeyError) as e:
        # If we can't parse, save a basic entry
        add_memory_entry(
            user_query=user_query,
            assistant_response=assistant_response[:500],
            summary="Interaction recorded (auto-generated)",
            intent="general",
            key_facts=[],
            tags=[]
        )
        return False


def clear_memory() -> None:
    """Clear all memory (for testing or reset)."""
    if MEMORY_FILE.exists():
        MEMORY_FILE.unlink()
    _ensure_memory_file()


# ============ Unified Agent Memory Interface ============

def get_unified_memory_state() -> dict:
    """Get the complete state of agent memory across all components.

    Returns a comprehensive view of:
    - Conversation memories
    - Learned patterns (by category)
    - User preferences
    - Project context
    - Statistics

    This is the primary interface for understanding what the agent "knows".
    """
    memory = load_memory()

    # Group patterns by category
    patterns_by_category = {}
    for p in memory.get("learned_patterns", []):
        cat = p.get("category", "general")
        if cat not in patterns_by_category:
            patterns_by_category[cat] = []
        patterns_by_category[cat].append(p)

    # Sort each category by confidence
    for cat in patterns_by_category:
        patterns_by_category[cat].sort(
            key=lambda x: x.get("confidence", 0),
            reverse=True
        )

    # Get high confidence patterns
    high_confidence = [
        p for p in memory.get("learned_patterns", [])
        if p.get("confidence", 0) >= 0.7
    ]

    # Calculate memory health metrics
    conversations = memory.get("conversation_memories", [])
    patterns = memory.get("learned_patterns", [])

    return {
        "summary": {
            "conversation_count": len(conversations),
            "pattern_count": len(patterns),
            "high_confidence_patterns": len(high_confidence),
            "preference_count": len(memory.get("user_preferences", {})),
            "created": memory.get("created"),
            "last_updated": memory.get("last_updated")
        },
        "patterns_by_category": patterns_by_category,
        "high_confidence_patterns": high_confidence,
        "user_preferences": memory.get("user_preferences", {}),
        "project_context": memory.get("project_context", {}),
        "recent_conversations": conversations[-10:] if conversations else [],
        "stats": get_memory_stats()
    }


def export_agent_knowledge() -> dict:
    """Export all agent knowledge for backup or transfer.

    Returns a portable format that can be imported into another instance.
    """
    memory = load_memory()

    return {
        "export_version": "1.0",
        "exported_at": datetime.now().isoformat(),
        "data": {
            "learned_patterns": memory.get("learned_patterns", []),
            "user_preferences": memory.get("user_preferences", {}),
            "project_context": memory.get("project_context", {}),
            "key_insights": memory.get("project_context", {}).get("key_insights", [])
        }
    }


def import_agent_knowledge(knowledge: dict) -> dict:
    """Import agent knowledge from an export.

    Merges with existing knowledge, increasing confidence for matching patterns.

    Args:
        knowledge: Export dict from export_agent_knowledge()

    Returns:
        Summary of what was imported
    """
    if knowledge.get("export_version") != "1.0":
        return {"success": False, "error": "Incompatible export version"}

    data = knowledge.get("data", {})
    imported = {"patterns": 0, "preferences": 0, "insights": 0}

    # Import patterns
    for p in data.get("learned_patterns", []):
        add_learned_pattern(
            pattern=p.get("pattern", ""),
            category=p.get("category", "general"),
            source=p.get("source", "imported"),
            confidence=p.get("confidence", 0.5),
            evidence=f"Imported from export {knowledge.get('exported_at', 'unknown')}"
        )
        imported["patterns"] += 1

    # Import preferences
    for key, value in data.get("user_preferences", {}).items():
        update_user_preference(key, value.get("value", str(value)))
        imported["preferences"] += 1

    # Import key insights
    memory = load_memory()
    existing_insights = memory.get("project_context", {}).get("key_insights", [])
    new_insights = data.get("key_insights", [])
    for insight in new_insights:
        if insight not in existing_insights:
            existing_insights.append(insight)
            imported["insights"] += 1
    memory.setdefault("project_context", {})["key_insights"] = existing_insights[-20:]
    save_memory(memory)

    return {
        "success": True,
        "imported": imported,
        "message": f"Imported {imported['patterns']} patterns, {imported['preferences']} preferences, {imported['insights']} insights"
    }


def add_key_insight(insight: str) -> None:
    """Add a key insight about the project.

    Key insights are high-value observations that should persist.
    """
    memory = load_memory()
    insights = memory.get("project_context", {}).get("key_insights", [])

    if insight not in insights:
        insights.append(insight)
        # Keep last 20 key insights
        memory.setdefault("project_context", {})["key_insights"] = insights[-20:]
        save_memory(memory)


def get_agent_context_summary() -> str:
    """Get a concise summary of agent knowledge for LLM context.

    Returns a formatted string suitable for injection into prompts.
    Focuses on high-confidence patterns and recent context.
    """
    state = get_unified_memory_state()

    lines = ["## Agent Memory Summary"]

    # High confidence patterns
    if state["high_confidence_patterns"]:
        lines.append("\n### Key Patterns (High Confidence)")
        for p in state["high_confidence_patterns"][:5]:
            lines.append(f"- [{p.get('category')}] {p.get('pattern')} ({p.get('confidence', 0):.0%})")

    # User preferences
    if state["user_preferences"]:
        lines.append("\n### User Preferences")
        for key, val in list(state["user_preferences"].items())[:5]:
            lines.append(f"- {key}: {val.get('value', val)}")

    # Key project insights
    insights = state.get("project_context", {}).get("key_insights", [])
    if insights:
        lines.append("\n### Key Insights")
        for insight in insights[-5:]:
            lines.append(f"- {insight}")

    return "\n".join(lines) if len(lines) > 1 else ""
