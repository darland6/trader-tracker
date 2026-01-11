"""Chat endpoint for querying the LLM about portfolio history and strategy."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from llm.config import get_llm_config
from llm.client import LLMClient
from api.routes.state import build_portfolio_state
from api.database import get_all_events
from api.services.memory import (
    get_memory_context,
    parse_and_save_memory_summary,
    get_memory_stats,
    add_learned_pattern,
    get_patterns_by_category,
    get_high_confidence_patterns,
    get_unified_memory_state,
    export_agent_knowledge,
    import_agent_knowledge,
    add_key_insight
)
from api.services.usage import track_usage, get_usage_summary, get_daily_usage
from api.services.langsmith_tracing import (
    trace_llm_call, get_session_stats, start_session,
    get_session_history, get_langsmith_status
)
from api.services.skill_discovery import (
    search_skills, suggest_skill_for_task, install_skill,
    get_installed_skill_content, get_skill_discovery_commands
)
from api.services.insights import (
    find_event_by_description, format_event_for_analysis,
    generate_insight_prompt, find_related_events,
    filter_events_by_criteria, get_reflection_context,
    get_cached_insight, cache_insight
)
import json
import re
import time

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    conversation_history: list[ChatMessage] = []  # Previous messages for context
    include_portfolio_history: bool = True


class ChatResponse(BaseModel):
    response: str
    model: str
    context_events: int
    research_executed: bool = False
    research_query: str | None = None
    search_executed: bool = False
    search_query: str | None = None
    skill_suggestion: dict | None = None  # Suggested skill if relevant
    skill_used: str | None = None  # Skill that was loaded


PORTFOLIO_CHAT_SYSTEM_PROMPT = """You are an AI assistant for a personal financial portfolio management system. Your role is to help the user understand their portfolio, analyze their trading history, and provide insights on their investment strategy.

## Portfolio Goals
- Primary Goal: Generate $30,000/year in income through options premiums, dividends, and trading gains
- Strategy: Sell cash-secured puts on stocks the user is willing to own, collect premiums
- Risk Management: Only trade on conviction positions where assignment would be acceptable

## Your Capabilities
1. **Portfolio Analysis**: Explain current holdings, allocations, and performance
2. **Trade History**: Discuss past trades, options, and their outcomes
3. **Strategy Review**: Analyze if trades align with the income generation goal
4. **Pattern Recognition**: Identify patterns in trading behavior and outcomes
5. **Future Planning**: Help think through potential trades and their implications
6. **Event Log Search**: Search the complete event history for specific events
7. **Deep Financial Research**: Use the Dexter research tool for in-depth financial analysis

## IMPORTANT: Using the Event Log Search Tool
You have access to the FULL event log history beyond what's shown below. When answering questions about:
- Past trades on a specific ticker
- Historical options activity
- Events from a specific time period
- Trading patterns or recurring events
- Any question requiring historical context

You MUST use the search tool first. Include this in your response:

[SEARCH_LOG: your search query]

Search supports these filters:
- `ticker:TSLA` - Find all events for a specific ticker
- `type:TRADE` - Find specific event types (TRADE, OPTION_OPEN, OPTION_CLOSE, OPTION_EXPIRE, DEPOSIT, WITHDRAWAL, DIVIDEND, PRICE_UPDATE)
- `date:2025-01` - Find events from a specific month
- `date:2025-01-15` - Find events from a specific date
- Free text search for notes, reasons, AI analysis

Examples:
- [SEARCH_LOG: ticker:TSLA type:TRADE] - All TSLA trades
- [SEARCH_LOG: ticker:NVDA type:OPTION] - All NVDA options
- [SEARCH_LOG: date:2025-12] - All events in December 2025
- [SEARCH_LOG: income] - Events mentioning "income"

ALWAYS search the log when answering historical questions. Do not guess or assume - verify with the actual data.

## Using the Dexter Research Tool
When you need detailed financial data about a company (revenue, earnings, balance sheets, ratios, etc.), you can request a Dexter research query. To do this, include in your response:

[RESEARCH_QUERY: your research question here]

Example: [RESEARCH_QUERY: What was TSLA's revenue growth over the last 4 quarters?]

The system will execute the research and provide results. Use this for:
- Analyzing companies before recommending trades
- Getting current financial metrics
- Comparing stocks to their competitors
- Deep-diving into specific financial aspects

## Skill Discovery System
You have access to specialized skills from Anthropic's skills library that can enhance your capabilities.
When encountering tasks that might benefit from specialized skills, use these commands:

### [SKILL_SEARCH: query]
Search for relevant skills. Example: [SKILL_SEARCH: frontend design]

### [SKILL_INSTALL: skill_id]
Install a skill from Anthropic's repo. Example: [SKILL_INSTALL: frontend-design]

### [SKILL_USE: skill_id]
Load an installed skill's instructions for the current task.

## Insight Generation Commands
Generate deep analysis and insights about events in the portfolio:

### [ANALYZE_EVENT: event_id or description]
Generate comprehensive analysis of a specific event or recent event matching description.
Example: [ANALYZE_EVENT: 45] or [ANALYZE_EVENT: last TSLA trade]

This generates:
- **Reasoning**: Why this decision makes sense given portfolio context
- **Future Advice**: Actionable advice for similar future situations
- **Past Reflection**: Connection to previous similar events

### [GENERATE_INSIGHTS: ticker or date range]
Batch generate insights for multiple events.
Example: [GENERATE_INSIGHTS: TSLA] or [GENERATE_INSIGHTS: 2026-01]

### [REFLECT: topic]
Generate reflection on patterns and learnings around a topic.
Example: [REFLECT: options strategy] or [REFLECT: risk management]

## Pattern Learning Commands
Learn and remember patterns about the user's trading behavior and preferences:

### [LEARN_PATTERN: category] pattern description
Save a learned pattern with confidence tracking.
Categories: trading_style, risk_tolerance, position_sizing, timing_preference, ticker_affinity, strategy_preference, goal_alignment

Examples:
- [LEARN_PATTERN: strategy_preference] Only sells puts on stocks acceptable for long-term ownership
- [LEARN_PATTERN: risk_tolerance] Prefers strikes >10% OTM for put selling
- [LEARN_PATTERN: ticker_affinity] Frequently trades TSLA and tech stocks

Patterns are automatically consolidated - similar patterns increase confidence rather than duplicating.
Use this when:
1. User explicitly states a preference
2. You observe a recurring behavior in their trading history
3. You infer a pattern from multiple events

Available skills include:
- **frontend-design**: Create distinctive, production-grade web interfaces
- **webapp-testing**: Automated browser testing for web applications
- **mcp-builder**: Build Model Context Protocol servers and tools
- **pdf/docx/pptx/xlsx**: Document processing capabilities
- **canvas-design**: Visual designs using HTML canvas
- **theme-factory**: Generate design themes and color palettes

When to use skills:
- Frontend/UI work: Use "frontend-design" for web interfaces
- Testing: Use "webapp-testing" for browser automation
- Documents: Use document skills for processing files
- Building tools: Use "mcp-builder" for MCP development

## Guidelines
- **ALWAYS search the event log** when answering questions about history, specific tickers, or past decisions
- Be specific and reference actual events from the history when relevant
- Use exact numbers from the portfolio data
- Connect insights to the $30K income goal
- Be honest about risks and uncertainties
- Keep responses concise but informative
- Suggest using Dexter research when you need current financial data beyond the portfolio

## Current Portfolio State
{portfolio_state}

## Recent Event History (last {event_count} events - use SEARCH_LOG for full history)
{event_history}

{memory_context}

Now respond to the user's question based on this context. Remember: Use [SEARCH_LOG: ...] for historical questions!

After your response, ALWAYS generate a memory summary on a new line starting with [MEMORY_SUMMARY]:
The summary should be a JSON object with: summary, intent, key_facts (array), learned_patterns (array), tags (array).
Keep it concise - this helps you remember this conversation in future sessions."""


def search_event_log(query: str, limit: int = 100) -> list[dict]:
    """Search the event log for events matching the query.

    Searches by ticker, event type, date range, notes, and reasons.
    """
    query = query.lower().strip()
    events = get_all_events(limit=500)  # Get more events for searching

    matches = []

    # Parse query for special filters
    ticker_filter = None
    type_filter = None
    date_filter = None

    # Check for ticker: prefix
    ticker_match = re.search(r'ticker:(\w+)', query)
    if ticker_match:
        ticker_filter = ticker_match.group(1).upper()
        query = re.sub(r'ticker:\w+', '', query).strip()

    # Check for type: prefix
    type_match = re.search(r'type:(\w+)', query)
    if type_match:
        type_filter = type_match.group(1).upper()
        query = re.sub(r'type:\w+', '', query).strip()

    # Check for date: prefix (YYYY-MM-DD or YYYY-MM)
    date_match = re.search(r'date:(\d{4}-\d{2}(?:-\d{2})?)', query)
    if date_match:
        date_filter = date_match.group(1)
        query = re.sub(r'date:\d{4}-\d{2}(?:-\d{2})?', '', query).strip()

    for event in events:
        data = json.loads(event.get('data_json', '{}'))
        reason = json.loads(event.get('reason_json', '{}'))

        # Apply filters
        if ticker_filter:
            event_ticker = data.get('ticker', '').upper()
            if event_ticker != ticker_filter:
                continue

        if type_filter:
            if type_filter not in event.get('event_type', '').upper():
                continue

        if date_filter:
            if not event.get('timestamp', '').startswith(date_filter):
                continue

        # Free text search
        if query:
            searchable = ' '.join([
                event.get('event_type', ''),
                data.get('ticker', ''),
                data.get('action', ''),
                str(data.get('strike', '')),
                str(data.get('strategy', '')),
                event.get('notes', ''),
                reason.get('explanation', ''),
                str(reason.get('ai_insights', {}).get('reasoning', '')),
            ]).lower()

            if query not in searchable:
                continue

        matches.append(event)

        if len(matches) >= limit:
            break

    return matches


def format_search_results(events: list[dict]) -> str:
    """Format search results for LLM context."""
    if not events:
        return "(No matching events found)"

    lines = [f"Found {len(events)} matching events:\n"]

    for event in events:
        data = json.loads(event.get('data_json', '{}'))
        reason = json.loads(event.get('reason_json', '{}'))

        line = f"[Event #{event['event_id']}] [{event['timestamp'][:10]}] {event['event_type']}"

        if event['event_type'] == 'TRADE':
            line += f": {data.get('action')} {data.get('shares')} {data.get('ticker')} @ ${data.get('price')}"
            if data.get('gain_loss'):
                line += f" (gain/loss: ${data['gain_loss']:,.2f})"
        elif event['event_type'] == 'OPTION_OPEN':
            line += f": Sold {data.get('ticker')} ${data.get('strike')} {data.get('strategy')} exp {data.get('expiration')} for ${data.get('total_premium')}"
        elif event['event_type'] in ('OPTION_CLOSE', 'OPTION_EXPIRE', 'OPTION_ASSIGN'):
            line += f": {data.get('ticker')} ${data.get('strike')} - profit: ${data.get('profit', 0):,.2f}"
        elif event['event_type'] in ('DEPOSIT', 'WITHDRAWAL'):
            line += f": ${data.get('amount'):,.2f}"
        elif event['event_type'] == 'DIVIDEND':
            line += f": {data.get('ticker')} ${data.get('amount'):,.2f}"
        elif event['event_type'] == 'PRICE_UPDATE':
            prices = data.get('prices', {})
            line += f": Updated {len(prices)} prices"

        if reason.get('explanation'):
            line += f"\n    Reason: {reason['explanation'][:150]}"

        ai = reason.get('ai_insights', {})
        if ai.get('reasoning'):
            line += f"\n    AI Analysis: {ai['reasoning'][:150]}"

        lines.append(line + "\n")

    return "\n".join(lines)


def format_event_for_context(event: dict) -> str:
    """Format an event for the LLM context."""
    data = json.loads(event.get('data_json', '{}'))
    reason = json.loads(event.get('reason_json', '{}'))

    event_str = f"[{event['timestamp'][:10]}] {event['event_type']}"

    if event['event_type'] == 'TRADE':
        event_str += f": {data.get('action')} {data.get('shares')} {data.get('ticker')} @ ${data.get('price')}"
    elif event['event_type'] == 'OPTION_OPEN':
        event_str += f": Sold {data.get('ticker')} ${data.get('strike')} {data.get('strategy')} exp {data.get('expiration')} for ${data.get('premium')}"
    elif event['event_type'] in ('OPTION_CLOSE', 'OPTION_EXPIRE', 'OPTION_ASSIGN'):
        event_str += f": {data.get('ticker', 'Option')} - {event['event_type'].replace('OPTION_', '')}"
    elif event['event_type'] in ('DEPOSIT', 'WITHDRAWAL'):
        event_str += f": ${data.get('amount')}"
    elif event['event_type'] == 'PRICE_UPDATE':
        return ""  # Skip price updates in chat context

    if reason.get('explanation'):
        event_str += f" | Reason: {reason['explanation'][:100]}"

    return event_str


# Company descriptions for ticker context
TICKER_DESCRIPTIONS = {
    "BMNR": "Bitdeer Technologies - Bitcoin/crypto mining infrastructure",
    "TSLA": "Tesla - EVs, energy, AI/robotics",
    "META": "Meta Platforms - Social media, VR/metaverse",
    "PLTR": "Palantir - AI/data analytics, government & enterprise",
    "RKLB": "Rocket Lab - Space launch, satellite services",
    "SPOT": "Spotify - Music/audio streaming",
    "NBIS": "Nebius - AI cloud infrastructure (Yandex spinoff)",
    "COIN": "Coinbase - Crypto exchange",
    "MSTR": "MicroStrategy - Bitcoin treasury company",
    "NVDA": "NVIDIA - AI chips, GPUs",
    "AMD": "AMD - Semiconductors, CPUs/GPUs",
    "AAPL": "Apple - Consumer tech, services",
    "MSFT": "Microsoft - Cloud, AI, enterprise software",
    "GOOGL": "Alphabet/Google - Search, cloud, AI",
    "AMZN": "Amazon - E-commerce, AWS cloud",
}


def format_portfolio_state(state: dict) -> str:
    """Format portfolio state for LLM context."""
    lines = [
        f"Total Value: ${state.get('total_value', 0):,.0f}",
        f"Cash: ${state.get('cash', 0):,.0f}",
        f"Holdings Value: ${state.get('portfolio_value', 0):,.0f}",
        "",
        "Holdings:"
    ]

    for h in state.get('holdings', []):
        ticker = h['ticker']
        company_desc = TICKER_DESCRIPTIONS.get(ticker, "")
        gain_str = f"+{h['unrealized_gain_pct']:.1f}%" if h['unrealized_gain_pct'] >= 0 else f"{h['unrealized_gain_pct']:.1f}%"
        if company_desc:
            lines.append(f"  - {ticker} ({company_desc}): {h['shares']} shares @ ${h['current_price']:.2f} = ${h['market_value']:,.0f} ({gain_str})")
        else:
            lines.append(f"  - {ticker}: {h['shares']} shares @ ${h['current_price']:.2f} = ${h['market_value']:,.0f} ({gain_str})")

    lines.append("")
    lines.append("Active Options:")
    for opt in state.get('active_options', []):
        lines.append(f"  - {opt['ticker']} ${opt['strike']} {opt['strategy']} exp {opt['expiration']} (${opt['premium']} premium)")

    if not state.get('active_options'):
        lines.append("  (none)")

    lines.append("")
    lines.append("YTD Income:")
    income = state.get('income', {})
    lines.append(f"  - Trading Gains: ${income.get('trading_gains', 0):,.0f}")
    lines.append(f"  - Option Income: ${income.get('option_income', 0):,.0f}")
    lines.append(f"  - Dividends: ${income.get('dividends', 0):,.0f}")
    lines.append(f"  - Total: ${income.get('total', 0):,.0f} ({income.get('progress_pct', 0):.1f}% of $30K goal)")

    return "\n".join(lines)


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat with the LLM about your portfolio."""
    config = get_llm_config()

    if not config.enabled:
        raise HTTPException(status_code=400, detail="LLM is disabled. Enable it in settings.")

    try:
        # Build portfolio context
        state = build_portfolio_state()

        # Build template state similar to web dashboard
        template_state = {
            "cash": state.get('cash', 0),
            "portfolio_value": sum(
                shares * state.get('latest_prices', {}).get(ticker, 0)
                for ticker, shares in state.get('holdings', {}).items()
                if shares > 0
            ),
            "total_value": 0,
            "holdings": [],
            "active_options": [],
            "income": {
                "trading_gains": state.get('ytd_trading_gains', 0),
                "option_income": state.get('ytd_option_income', 0),
                "dividends": state.get('ytd_dividends', 0),
                "total": state.get('ytd_income', 0),
                "progress_pct": (state.get('ytd_income', 0) / 30000) * 100 if state.get('ytd_income', 0) else 0
            }
        }

        # Build holdings
        for ticker, shares in state.get('holdings', {}).items():
            if shares > 0:
                price = state.get('latest_prices', {}).get(ticker, 0)
                cost_info = state.get('cost_basis', {}).get(ticker, {})
                market_value = shares * price
                total_cost = cost_info.get('total_cost', 0)
                unrealized_gain = market_value - total_cost
                gain_pct = ((market_value - total_cost) / total_cost * 100) if total_cost > 0 else 0

                template_state["holdings"].append({
                    "ticker": ticker,
                    "shares": shares,
                    "current_price": price,
                    "market_value": market_value,
                    "unrealized_gain": unrealized_gain,
                    "unrealized_gain_pct": gain_pct
                })

        template_state["holdings"].sort(key=lambda x: x["market_value"], reverse=True)
        template_state["portfolio_value"] = sum(h["market_value"] for h in template_state["holdings"])
        template_state["total_value"] = template_state["portfolio_value"] + template_state["cash"]

        # Get active options
        for opt in state.get('active_options', []):
            template_state["active_options"].append({
                "ticker": opt.get('ticker', ''),
                "strategy": opt.get('strategy', ''),
                "strike": opt.get('strike', 0),
                "expiration": opt.get('expiration', ''),
                "premium": opt.get('total_premium', opt.get('premium', 0))
            })

        # Get event history
        events = get_all_events(limit=50) if request.include_portfolio_history else []
        event_lines = []
        for e in reversed(events):  # Oldest first
            line = format_event_for_context(e)
            if line:
                event_lines.append(line)

        # Get memory context from previous sessions
        memory_context = get_memory_context(max_entries=15)

        # Build system prompt
        system_prompt = PORTFOLIO_CHAT_SYSTEM_PROMPT.format(
            portfolio_state=format_portfolio_state(template_state),
            event_count=len(event_lines),
            event_history="\n".join(event_lines) if event_lines else "(No recent events)",
            memory_context=memory_context if memory_context else ""
        )

        # Build messages array with conversation history
        messages = []
        for msg in request.conversation_history:
            messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": request.message})

        # Call LLM
        client = LLMClient(config)
        start_time = time.time()

        if config.provider == "claude":
            import anthropic
            api_client = anthropic.Anthropic(api_key=config.anthropic_api_key)

            response = api_client.messages.create(
                model=config.claude_model,
                max_tokens=1024,
                system=system_prompt,
                messages=messages
            )

            response_text = response.content[0].text
            model_used = config.claude_model

            # Track Claude usage
            duration_ms = int((time.time() - start_time) * 1000)
            track_usage(
                model=model_used,
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                endpoint="chat",
                duration_ms=duration_ms
            )
            # Live session tracing
            trace_llm_call(
                model=model_used,
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                latency_ms=duration_ms,
                endpoint="chat"
            )

        else:  # local
            import httpx

            # For local LLM, prepend system message
            local_messages = [{"role": "system", "content": system_prompt}] + messages

            api_response = httpx.post(
                f"{config.local_url}/chat/completions",
                json={
                    "model": config.local_model,
                    "messages": local_messages,
                    "max_tokens": 1024,
                    "temperature": 0.7
                },
                timeout=config.timeout
            )
            api_response.raise_for_status()
            result = api_response.json()

            response_text = result["choices"][0]["message"]["content"]
            model_used = config.local_model

            # Track local LLM usage
            duration_ms = int((time.time() - start_time) * 1000)
            usage_data = result.get("usage", {})
            prompt_tokens = usage_data.get("prompt_tokens", 0)
            completion_tokens = usage_data.get("completion_tokens", 0)
            track_usage(
                model=model_used,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                endpoint="chat",
                duration_ms=duration_ms
            )
            # Live session tracing
            trace_llm_call(
                model=model_used,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=duration_ms,
                endpoint="chat"
            )

        # Check if the response contains a search log query
        search_executed = False
        search_query = None
        search_match = re.search(r'\[SEARCH_LOG:\s*(.+?)\]', response_text)

        if search_match:
            search_query = search_match.group(1).strip()

            # Execute the search
            search_results = search_event_log(search_query)
            formatted_results = format_search_results(search_results)
            search_executed = True

            # Add search results to conversation and get follow-up
            search_context = f"\n\n[SEARCH RESULTS for '{search_query}']\n{formatted_results}\n[END SEARCH RESULTS]"

            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user", "content": f"Here are the event log search results you requested:{search_context}\n\nPlease analyze these results and provide your insights."})

            # Get follow-up response with search results
            follow_start = time.time()
            if config.provider == "claude":
                follow_up = api_client.messages.create(
                    model=config.claude_model,
                    max_tokens=1024,
                    system=system_prompt,
                    messages=messages
                )
                response_text = response_text + search_context + "\n\n" + follow_up.content[0].text
                # Track follow-up usage
                track_usage(
                    model=config.claude_model,
                    prompt_tokens=follow_up.usage.input_tokens,
                    completion_tokens=follow_up.usage.output_tokens,
                    endpoint="chat-search",
                    duration_ms=int((time.time() - follow_start) * 1000)
                )
            else:
                local_messages = [{"role": "system", "content": system_prompt}] + messages
                follow_up_response = httpx.post(
                    f"{config.local_url}/chat/completions",
                    json={
                        "model": config.local_model,
                        "messages": local_messages,
                        "max_tokens": 1024,
                        "temperature": 0.7
                    },
                    timeout=config.timeout
                )
                follow_up_response.raise_for_status()
                follow_up_result = follow_up_response.json()
                response_text = response_text + search_context + "\n\n" + follow_up_result["choices"][0]["message"]["content"]
                # Track follow-up usage
                usage_data = follow_up_result.get("usage", {})
                track_usage(
                    model=config.local_model,
                    prompt_tokens=usage_data.get("prompt_tokens", 0),
                    completion_tokens=usage_data.get("completion_tokens", 0),
                    endpoint="chat-search",
                    duration_ms=int((time.time() - follow_start) * 1000)
                )

        # Check if the response contains a research query
        research_executed = False
        research_query = None
        research_match = re.search(r'\[RESEARCH_QUERY:\s*(.+?)\]', response_text)

        if research_match:
            research_query = research_match.group(1).strip()

            # Try to execute the research
            try:
                from integrations.dexter import query_dexter, is_dexter_available

                if is_dexter_available():
                    result = await query_dexter(research_query, timeout=120)

                    if result.success:
                        research_executed = True

                        # Append research results and get a follow-up response
                        research_context = f"\n\n[RESEARCH RESULTS for '{research_query}']\n{result.answer}\n[END RESEARCH RESULTS]"

                        # Add research results to conversation and get follow-up
                        messages.append({"role": "assistant", "content": response_text})
                        messages.append({"role": "user", "content": f"Here are the research results you requested:{research_context}\n\nPlease continue your analysis with this data."})

                        # Get follow-up response
                        research_start = time.time()
                        if config.provider == "claude":
                            follow_up = api_client.messages.create(
                                model=config.claude_model,
                                max_tokens=1024,
                                system=system_prompt,
                                messages=messages
                            )
                            response_text = response_text + research_context + "\n\n" + follow_up.content[0].text
                            # Track research follow-up usage
                            track_usage(
                                model=config.claude_model,
                                prompt_tokens=follow_up.usage.input_tokens,
                                completion_tokens=follow_up.usage.output_tokens,
                                endpoint="chat-research",
                                duration_ms=int((time.time() - research_start) * 1000)
                            )
                        else:
                            local_messages = [{"role": "system", "content": system_prompt}] + messages
                            follow_up_response = httpx.post(
                                f"{config.local_url}/chat/completions",
                                json={
                                    "model": config.local_model,
                                    "messages": local_messages,
                                    "max_tokens": 1024,
                                    "temperature": 0.7
                                },
                                timeout=config.timeout
                            )
                            follow_up_response.raise_for_status()
                            follow_up_result = follow_up_response.json()
                            response_text = response_text + research_context + "\n\n" + follow_up_result["choices"][0]["message"]["content"]
                            # Track research follow-up usage
                            usage_data = follow_up_result.get("usage", {})
                            track_usage(
                                model=config.local_model,
                                prompt_tokens=usage_data.get("prompt_tokens", 0),
                                completion_tokens=usage_data.get("completion_tokens", 0),
                                endpoint="chat-research",
                                duration_ms=int((time.time() - research_start) * 1000)
                            )
                    else:
                        # Research failed, note it in response
                        response_text += f"\n\n(Note: Research query failed: {result.error})"
                else:
                    response_text += "\n\n(Note: Dexter research agent is not available. Install it for deep financial research.)"

            except Exception as research_error:
                response_text += f"\n\n(Note: Could not execute research: {str(research_error)})"

        # Check for skill commands
        skill_search_executed = False
        skill_install_executed = False
        skill_used = None

        # SKILL_SEARCH: query - search for relevant skills
        skill_search_match = re.search(r'\[SKILL_SEARCH:\s*(.+?)\]', response_text, re.IGNORECASE)
        if skill_search_match:
            search_query = skill_search_match.group(1).strip()
            search_results = search_skills(search_query)
            skill_search_executed = True

            # Format results
            if search_results:
                results_text = f"\n\n[SKILL SEARCH RESULTS for '{search_query}']\n"
                for skill in search_results[:5]:
                    installed = "✓ installed" if skill.get("installed") else "available"
                    results_text += f"- **{skill['id']}** ({installed}): {skill['description']}\n"
                results_text += "\nUse [SKILL_INSTALL: skill_id] to install, or [SKILL_USE: skill_id] if already installed.\n[END SKILL SEARCH]"
                response_text += results_text
            else:
                response_text += f"\n\n(No skills found matching '{search_query}')"

        # SKILL_INSTALL: skill_id - install a skill from Anthropic repo
        skill_install_match = re.search(r'\[SKILL_INSTALL:\s*(.+?)\]', response_text, re.IGNORECASE)
        if skill_install_match:
            skill_id = skill_install_match.group(1).strip().lower()
            install_result = await install_skill(skill_id)
            skill_install_executed = True

            if install_result["success"]:
                if install_result.get("already_installed"):
                    response_text += f"\n\n(Skill '{skill_id}' is already installed and ready to use)"
                else:
                    response_text += f"\n\n(Skill '{skill_id}' installed successfully! Use [SKILL_USE: {skill_id}] to load it.)"
            else:
                response_text += f"\n\n(Failed to install skill '{skill_id}': {install_result['message']})"

        # SKILL_USE: skill_id - load and use an installed skill
        skill_use_match = re.search(r'\[SKILL_USE:\s*(.+?)\]', response_text, re.IGNORECASE)
        if skill_use_match:
            skill_id = skill_use_match.group(1).strip().lower()
            skill_content = get_installed_skill_content(skill_id)

            if skill_content:
                skill_used = skill_id
                # Add skill instructions to the conversation for follow-up
                skill_context = f"\n\n[SKILL LOADED: {skill_id}]\nFollow these specialized instructions:\n\n{skill_content[:3000]}\n[END SKILL]"
                response_text += skill_context
            else:
                # Try to auto-install if not found
                install_result = await install_skill(skill_id)
                if install_result["success"]:
                    skill_content = get_installed_skill_content(skill_id)
                    if skill_content:
                        skill_used = skill_id
                        skill_context = f"\n\n[SKILL LOADED: {skill_id}]\nFollow these specialized instructions:\n\n{skill_content[:3000]}\n[END SKILL]"
                        response_text += skill_context
                    else:
                        response_text += f"\n\n(Skill '{skill_id}' installed but could not be loaded)"
                else:
                    response_text += f"\n\n(Skill '{skill_id}' not found. Use [SKILL_SEARCH: keyword] to find available skills.)"

        # Check for insight generation commands
        insight_generated = False

        # ANALYZE_EVENT: event_id or description
        analyze_match = re.search(r'\[ANALYZE_EVENT:\s*(.+?)\]', response_text, re.IGNORECASE)
        if analyze_match:
            event_query = analyze_match.group(1).strip()
            all_events = get_all_events(limit=500)

            # Find the event
            if event_query.isdigit():
                target_event = None
                for e in all_events:
                    if e.get('event_id') == int(event_query):
                        target_event = e
                        break
            else:
                target_event = find_event_by_description(event_query, all_events)

            if target_event:
                # Check cache first
                cached = get_cached_insight(target_event['event_id'])
                if cached:
                    insight_str = f"\n\n[CACHED INSIGHT for Event #{target_event['event_id']}]\n"
                    insight_str += f"**Reasoning**: {cached.get('reasoning', 'N/A')}\n\n"
                    insight_str += f"**Future Advice**: {cached.get('future_advice', 'N/A')}\n\n"
                    insight_str += f"**Past Reflection**: {cached.get('past_reflection', 'N/A')}\n"
                    insight_str += f"(Generated: {cached.get('cached_at', 'unknown')[:10]})\n[END INSIGHT]"
                    response_text += insight_str
                    insight_generated = True
                else:
                    # Format event for context
                    event_context = format_event_for_analysis(target_event)
                    related = find_related_events(target_event, all_events)
                    insight_prompt = generate_insight_prompt(target_event, template_state, related)

                    response_text += f"\n\n[ANALYZING Event #{target_event['event_id']}]\n"
                    response_text += f"```\n{event_context}\n```\n"
                    response_text += f"Use this context to generate insights. Related events: {len(related)}\n"
                    response_text += f"[END ANALYSIS CONTEXT]"
                    insight_generated = True
            else:
                response_text += f"\n\n(Could not find event matching '{event_query}'. Try [SEARCH_LOG: ...] first.)"

        # GENERATE_INSIGHTS: ticker or date range
        batch_match = re.search(r'\[GENERATE_INSIGHTS:\s*(.+?)\]', response_text, re.IGNORECASE)
        if batch_match:
            query = batch_match.group(1).strip()
            all_events = get_all_events(limit=500)

            # Determine if ticker or date
            if re.match(r'\d{4}-\d{2}', query):
                # Date prefix
                filtered = filter_events_by_criteria(all_events, date_prefix=query)
                filter_type = f"date: {query}"
            else:
                # Ticker
                filtered = filter_events_by_criteria(all_events, ticker=query.upper())
                filter_type = f"ticker: {query.upper()}"

            if filtered:
                response_text += f"\n\n[BATCH INSIGHT CONTEXT: {filter_type}]\n"
                response_text += f"Found {len(filtered)} events. Analyze these for patterns:\n\n"

                for e in filtered[:10]:  # Limit to 10 events
                    response_text += format_event_for_analysis(e) + "\n---\n"

                response_text += f"\nGenerate insights covering patterns, what worked, and lessons learned.\n"
                response_text += f"[END BATCH CONTEXT]"
            else:
                response_text += f"\n\n(No events found for {filter_type})"

        # REFLECT: topic
        reflect_match = re.search(r'\[REFLECT:\s*(.+?)\]', response_text, re.IGNORECASE)
        if reflect_match:
            topic = reflect_match.group(1).strip()
            all_events = get_all_events(limit=500)
            reflection_context = get_reflection_context(topic, all_events, template_state)

            response_text += f"\n\n[REFLECTION CONTEXT: {topic}]\n"
            response_text += reflection_context
            response_text += f"\n[END REFLECTION CONTEXT]"

        # LEARN_PATTERN: category] pattern description
        # Pattern: [LEARN_PATTERN: category] description text
        pattern_matches = re.findall(
            r'\[LEARN_PATTERN:\s*(\w+)\]\s*([^\[\n]+)',
            response_text,
            re.IGNORECASE
        )

        patterns_learned = []
        for category, pattern_text in pattern_matches:
            category = category.lower().strip()
            pattern_text = pattern_text.strip()

            if pattern_text and len(pattern_text) > 5:
                # Determine source based on context
                # If user explicitly stated something, it's "stated"
                source = "stated" if "I " in request.message or "i " in request.message else "observed"

                result = add_learned_pattern(
                    pattern=pattern_text,
                    category=category,
                    source=source,
                    confidence=0.7 if source == "stated" else 0.5,
                    evidence=request.message[:200]
                )

                patterns_learned.append({
                    "category": category,
                    "pattern": pattern_text,
                    "confidence": result.get("confidence", 0.5),
                    "is_new": result.get("evidence_count", 1) == 1
                })

        # Add acknowledgment for learned patterns
        if patterns_learned:
            ack_str = "\n\n**Patterns Learned:**\n"
            for p in patterns_learned:
                status = "NEW" if p["is_new"] else f"UPDATED (conf: {p['confidence']:.0%})"
                ack_str += f"- [{p['category']}] {p['pattern']} ({status})\n"
            response_text += ack_str

        # Extract and save memory summary from response
        user_visible_response = response_text

        # Strip any thinking/reasoning blocks from local LLM responses
        if '</think>' in user_visible_response:
            user_visible_response = re.sub(r'<think>[\s\S]*?</think>\s*', '', user_visible_response)
        # Also strip any text before </think> if opening tag is missing
        if '</think>' in user_visible_response:
            user_visible_response = user_visible_response.split('</think>')[-1].strip()

        # Look for memory summary - handles various formats from different models
        # Pattern matches [MEMORY_SUMMARY]: {json} or [MEMORY_SUMMARY: {json}] etc.
        memory_match = re.search(r'\[MEMORY_SUMMARY\][:\s]*(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})', user_visible_response, re.DOTALL)
        if not memory_match:
            # Try alternate format with colon inside brackets
            memory_match = re.search(r'\[MEMORY_SUMMARY:\s*(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})\s*\]?', user_visible_response, re.DOTALL)
        if memory_match:
            memory_json = memory_match.group(1)
            # Remove memory summary from user-visible response
            user_visible_response = re.sub(r'\s*\[MEMORY_SUMMARY\]?[:\s]*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}\s*\]?', '', user_visible_response, flags=re.DOTALL).strip()
            # Save to persistent memory
            try:
                parse_and_save_memory_summary(request.message, user_visible_response, memory_json)
            except Exception as mem_error:
                pass  # Don't fail the request if memory save fails

        # Proactively suggest skills if relevant to user's message
        # This helps when LLM doesn't output the command format (especially local LLMs)
        skill_suggestion = None
        if not skill_used and not skill_search_executed:
            suggested = suggest_skill_for_task(request.message)
            if suggested:
                skill_suggestion = {
                    "id": suggested["id"],
                    "name": suggested["name"],
                    "description": suggested["description"],
                    "relevance_score": suggested["relevance_score"]
                }

        return ChatResponse(
            response=user_visible_response,
            model=model_used,
            context_events=len(event_lines),
            research_executed=research_executed,
            research_query=research_query,
            search_executed=search_executed,
            search_query=search_query,
            skill_suggestion=skill_suggestion,
            skill_used=skill_used
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@router.get("/memory/stats")
async def get_memory_statistics():
    """Get statistics about the LLM memory file."""
    return get_memory_stats()


@router.get("/memory/context")
async def get_memory_context_preview():
    """Preview the memory context that would be injected into prompts."""
    context = get_memory_context(max_entries=20)
    return {
        "context": context,
        "stats": get_memory_stats()
    }


@router.get("/usage")
async def get_token_usage():
    """Get token usage summary."""
    return get_usage_summary()


@router.get("/usage/daily")
async def get_daily_token_usage(days: int = 30):
    """Get daily token usage for the last N days."""
    return get_daily_usage(days)


@router.get("/session")
async def get_live_session():
    """Get live session token usage and traces."""
    return get_session_stats()


@router.post("/session/new")
async def start_new_session():
    """Start a new tracing session."""
    session = start_session()
    return {
        "success": True,
        "session_id": session.session_id,
        "message": "New session started"
    }


@router.get("/session/history")
async def get_sessions_history():
    """Get history of previous sessions."""
    return {
        "sessions": get_session_history(),
        "current": get_session_stats()
    }


@router.get("/langsmith/status")
async def langsmith_status():
    """Get LangSmith configuration status."""
    return get_langsmith_status()


@router.get("/patterns")
async def get_learned_patterns(category: str = None, min_confidence: float = None):
    """Get learned patterns, optionally filtered.

    Args:
        category: Filter by category (trading_style, risk_tolerance, etc.)
        min_confidence: Filter by minimum confidence (0.0-1.0)
    """
    if min_confidence is not None:
        patterns = get_high_confidence_patterns(min_confidence)
        if category:
            patterns = [p for p in patterns if p.get("category") == category]
    else:
        patterns = get_patterns_by_category(category)

    return {
        "patterns": patterns,
        "count": len(patterns),
        "categories": list(set(p.get("category") for p in patterns))
    }


# ============ Unified Agent Memory Endpoints ============

@router.get("/memory/unified")
async def get_agent_memory():
    """Get the complete unified view of agent memory.

    Returns all memory components:
    - Patterns by category
    - High confidence patterns
    - User preferences
    - Project context
    - Recent conversations
    - Statistics
    """
    return get_unified_memory_state()


@router.get("/memory/export")
async def export_memory():
    """Export agent knowledge for backup or transfer to another project."""
    return export_agent_knowledge()


@router.post("/memory/import")
async def import_memory(knowledge: dict):
    """Import agent knowledge from an export.

    Merges with existing knowledge, increasing confidence for matching patterns.
    """
    return import_agent_knowledge(knowledge)


@router.post("/memory/insight")
async def add_insight(insight: str):
    """Add a key insight about the project."""
    add_key_insight(insight)
    return {"success": True, "message": f"Added insight: {insight[:50]}..."}
