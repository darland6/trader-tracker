"""Prompts for LLM-generated event insights."""

INSIGHT_SYSTEM_PROMPT = """You are a financial analysis assistant helping track investment decisions for a portfolio focused on generating $30,000/year income through options trading and strategic stock positions.

Given an event and recent portfolio history, generate three structured insights in JSON format:

1. **reasoning**: Analyze why this decision makes sense given the current portfolio, market conditions, and income goals. Reference specific numbers and positions.

2. **future_advice**: Provide actionable advice for similar future situations. Include specific price levels, timeframes, or conditions to watch for.

3. **past_reflection**: Connect this decision to previous similar events if any exist. Note patterns in decision-making and lessons that apply.

IMPORTANT:
- Keep each insight to 2-3 sentences maximum
- Be specific and quantitative when possible
- Reference the reason taxonomy (INCOME_GENERATION, PROFIT_TAKING, etc.)
- Consider the $30k/year income goal context
- If no relevant past events exist, acknowledge this briefly

Respond ONLY with valid JSON in this exact format:
{
  "reasoning": "Your analysis here...",
  "future_advice": "Your advice here...",
  "past_reflection": "Your reflection here..."
}"""


def build_event_context(event_type: str, event_data: dict, user_reason: str,
                        notes: str, portfolio_state: dict, recent_events: list) -> str:
    """Build the context prompt for the LLM."""

    # Format the current event
    event_section = f"""CURRENT EVENT:
Type: {event_type}
Data: {format_event_data(event_data)}
User's Reason: {user_reason or 'Not provided'}
Notes: {notes or 'None'}"""

    # Format portfolio state
    holdings_str = ", ".join([f"{t}: {s} shares" for t, s in portfolio_state.get('holdings', {}).items() if s > 0])
    options_str = format_active_options(portfolio_state.get('active_options', []))

    portfolio_section = f"""CURRENT PORTFOLIO STATE:
Cash: ${portfolio_state.get('cash', 0):,.2f}
Holdings: {holdings_str or 'None'}
Active Options: {options_str or 'None'}
YTD Income: ${portfolio_state.get('ytd_income', 0):,.2f} / $30,000 goal ({portfolio_state.get('ytd_income', 0) / 300:.1f}% progress)"""

    # Format recent events
    if recent_events:
        events_str = format_recent_events(recent_events)
        history_section = f"""RECENT HISTORY (last {len(recent_events)} events):
{events_str}"""
    else:
        history_section = "RECENT HISTORY: No previous events"

    return f"""{event_section}

{portfolio_section}

{history_section}

Based on this context, generate insights about this decision."""


def format_event_data(data: dict) -> str:
    """Format event data for display."""
    if not data:
        return "No data"

    parts = []
    if 'action' in data:
        parts.append(f"{data['action']} {data.get('ticker', '')} {data.get('shares', '')} shares @ ${data.get('price', 0):.2f}")
    elif 'ticker' in data and 'strategy' in data:
        parts.append(f"{data.get('strategy')} on {data['ticker']} @ ${data.get('strike', 0)} exp {data.get('expiration', '')}")
        if 'total_premium' in data:
            parts.append(f"Premium: ${data['total_premium']:,.0f}")
    elif 'amount' in data:
        parts.append(f"${data['amount']:,.2f}")
        if 'source' in data:
            parts.append(f"Source: {data['source']}")
        if 'purpose' in data:
            parts.append(f"Purpose: {data['purpose']}")
    else:
        parts.append(str(data))

    return " | ".join(parts)


def format_active_options(options: list) -> str:
    """Format active options for display."""
    if not options:
        return "None"

    parts = []
    for opt in options[:5]:  # Limit to 5
        parts.append(f"{opt.get('ticker', '')} {opt.get('strategy', '')} ${opt.get('strike', 0)} exp {opt.get('expiration', '')}")

    result = "; ".join(parts)
    if len(options) > 5:
        result += f" (+{len(options) - 5} more)"
    return result


def format_recent_events(events: list) -> str:
    """Format recent events for context."""
    lines = []
    for event in events[-10:]:  # Last 10
        event_id = event.get('event_id', '?')
        event_type = event.get('event_type', 'UNKNOWN')
        timestamp = str(event.get('timestamp', ''))[:10]

        data = event.get('data', {})
        if isinstance(data, str):
            import json
            try:
                data = json.loads(data)
            except:
                data = {}

        reason = event.get('reason', {})
        if isinstance(reason, str):
            import json
            try:
                reason = json.loads(reason)
            except:
                reason = {}

        primary_reason = reason.get('primary', '')
        notes = event.get('notes', '')[:50] + ('...' if len(event.get('notes', '')) > 50 else '')

        # Format based on type
        if event_type == 'TRADE':
            action = data.get('action', '')
            ticker = data.get('ticker', '')
            shares = data.get('shares', 0)
            lines.append(f"  [{event_id}] {timestamp} {event_type}: {action} {shares} {ticker} - {primary_reason}")
        elif event_type.startswith('OPTION'):
            ticker = data.get('ticker', '')
            strategy = data.get('strategy', '')
            strike = data.get('strike', 0)
            lines.append(f"  [{event_id}] {timestamp} {event_type}: {ticker} {strategy} ${strike} - {primary_reason}")
        else:
            lines.append(f"  [{event_id}] {timestamp} {event_type}: {primary_reason} {notes}")

    return "\n".join(lines)
