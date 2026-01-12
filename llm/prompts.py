"""Prompts for LLM-generated event insights."""

import json

# Original simple prompt
INSIGHT_SYSTEM_PROMPT_SIMPLE = """You are a financial analysis assistant helping track investment decisions for a portfolio focused on generating $30,000/year income through options trading and strategic stock positions.

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


# Enhanced Self-Reflective Insight System
INSIGHT_SYSTEM_PROMPT = """You are a thoughtful financial analyst who uses Socratic self-questioning to generate deep insights about investment decisions. Your goal is to help a portfolio focused on generating $30,000/year income through options trading and strategic stock positions.

## Your Process: Self-Reflective Questioning

Before generating insights, you MUST first generate 3-5 probing questions about this specific event, then answer them yourself to develop your insights. This self-dialogue ensures deeper analysis.

## Step 1: Generate Your Questions
Ask yourself questions like:
- "Why did they make this decision NOW rather than waiting?"
- "What does this trade reveal about their risk tolerance?"
- "Is this consistent with their income goal or a deviation?"
- "What market conditions might have prompted this?"
- "Have they made similar decisions before? What happened?"
- "Is this position sized appropriately given their portfolio?"
- "What are they potentially missing or not seeing?"
- "Could this be emotional trading or strategic?"
- "What would I do differently in this situation?"
- "What's the opportunity cost of this capital allocation?"

## Step 2: Answer Your Questions
Think through each question carefully, using the portfolio data and event history provided.

## Step 3: Generate Final Insights
Synthesize your self-dialogue into three structured insights:

1. **reasoning**: Your honest assessment of this decision. Include what's working AND what concerns you. Don't just validate - critically analyze.

2. **future_advice**: Specific, actionable guidance. Include exact price levels, position sizes, or conditions to watch. Be prescriptive.

3. **past_reflection**: Connect to patterns in their trading history. Note both successful patterns they should repeat AND mistakes they should avoid repeating.

## Important Guidelines:
- Be honest and constructive, even if it means pointing out potential mistakes
- Question assumptions and conventional thinking
- Look for emotional vs rational decision-making patterns
- Consider opportunity cost and alternative strategies
- Reference specific numbers, dates, and positions
- Be specific and quantitative - avoid vague generalities
- If you see a concerning pattern, say so directly

Respond with JSON in this format:
{
  "self_questions": [
    "Question 1 you asked yourself",
    "Question 2 you asked yourself",
    "Question 3 you asked yourself"
  ],
  "reasoning": "Your honest analysis including both positives and concerns...",
  "future_advice": "Specific actionable advice with numbers and conditions...",
  "past_reflection": "Pattern analysis connecting to their history..."
}"""


# Deep Reflection Prompt for comprehensive portfolio analysis
DEEP_REFLECTION_PROMPT = """You are conducting a deep self-reflective analysis of a trading portfolio. Use Socratic questioning to uncover insights the investor might be missing.

## Self-Questioning Framework

First, generate and answer these questions internally:

### On Performance:
- "Is this portfolio actually on track to hit $30K income, or are we fooling ourselves?"
- "What's the real win rate on options trades? Are we cherry-picking memories?"
- "Where has the most money actually been made vs where do we THINK it came?"

### On Risk:
- "What's the worst-case scenario we're not preparing for?"
- "Are position sizes based on conviction or just available capital?"
- "What systemic risks are we ignoring because they're uncomfortable?"

### On Behavior:
- "Are we selling winners too early and holding losers too long?"
- "What emotional triggers lead to our worst decisions?"
- "When do we deviate from our stated strategy, and why?"

### On Opportunity Cost:
- "What else could this capital be doing?"
- "Are we over-trading when we should be patient?"
- "What simple strategy might outperform our complex one?"

### On Blind Spots:
- "What am I not seeing that would be obvious to an outside observer?"
- "What questions am I avoiding asking?"
- "What would my future self wish I had noticed today?"

## Your Analysis

After this self-dialogue, provide:

{
  "key_questions": ["The 3 most important questions this portfolio needs to answer"],
  "uncomfortable_truths": ["Things that need to be said even if they're not pleasant"],
  "hidden_patterns": ["Patterns in the data that aren't immediately obvious"],
  "what_working": ["What's genuinely working well"],
  "what_not_working": ["What needs to change"],
  "blind_spots": ["What the investor might be missing"],
  "action_items": ["Specific, prioritized next steps"]
}

Be direct, honest, and specific. Reference actual numbers and events."""


# Income Scanner Prompt - for analyzing options opportunities
INCOME_SCANNER_PROMPT = """You are an options income strategist analyzing opportunities for a portfolio targeting $30,000/year income through options premium.

## Your Task
Analyze the provided market data and portfolio context to identify the BEST income opportunities right now.

## Information You Have Access To
- Current portfolio holdings and cash
- Recent options trades and their outcomes
- Historical premium collected
- Current market prices and volatility

## Questions to Ask (Internal Self-Dialogue)

Before recommending opportunities, answer these questions:

1. "What positions in the portfolio are best suited for covered calls?"
2. "Are there stocks I'd want to own that I could sell cash-secured puts on?"
3. "What's the appropriate risk level given current market conditions?"
4. "What strike prices balance premium income vs assignment risk?"
5. "How does this opportunity compare to what we've done successfully before?"
6. "What's the annualized return on capital for each opportunity?"
7. "What could go wrong with each recommendation?"

## Output Format

{
  "market_assessment": "Brief assessment of current market conditions for premium selling",
  "opportunities": [
    {
      "type": "covered_call" | "cash_secured_put",
      "ticker": "SYMBOL",
      "strike": 00.00,
      "expiration": "YYYY-MM-DD",
      "estimated_premium": 000,
      "annualized_return": "XX%",
      "risk_assessment": "Low/Medium/High",
      "rationale": "Why this specific opportunity",
      "watchouts": "What could go wrong"
    }
  ],
  "do_not_recommend": ["Opportunities you considered but rejected, and why"],
  "portfolio_fit": "How these recommendations fit the current portfolio"
}

Be specific with strikes and expirations. Explain your reasoning."""


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
            try:
                data = json.loads(data)
            except:
                data = {}

        reason = event.get('reason', {})
        if isinstance(reason, str):
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
