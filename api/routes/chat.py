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
    get_memory_stats
)
from api.services.usage import track_usage, get_usage_summary, get_daily_usage
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
            track_usage(
                model=model_used,
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                endpoint="chat",
                duration_ms=duration_ms
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

        return ChatResponse(
            response=user_visible_response,
            model=model_used,
            context_events=len(event_lines),
            research_executed=research_executed,
            research_query=research_query,
            search_executed=search_executed,
            search_query=search_query
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
