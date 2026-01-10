"""Research endpoint for financial analysis via Dexter."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from integrations.dexter import (
    query_dexter,
    is_dexter_available,
    get_dexter_status,
    EXAMPLE_QUERIES
)

router = APIRouter(prefix="/api/research", tags=["research"])


class ResearchRequest(BaseModel):
    query: str
    timeout: int = 120


class ResearchResponse(BaseModel):
    success: bool
    query: str
    answer: str
    error: str | None = None


@router.get("/status")
async def research_status():
    """Check if Dexter research agent is available."""
    status = get_dexter_status()
    return {
        "available": status["ready"],
        "status": status,
        "example_queries": EXAMPLE_QUERIES[:3]
    }


@router.post("/query", response_model=ResearchResponse)
async def research_query(request: ResearchRequest):
    """
    Query Dexter for financial research.

    Dexter is an autonomous agent that can analyze:
    - Income statements
    - Balance sheets
    - Cash flow statements
    - Financial ratios
    - Revenue trends
    - And more

    Example queries:
    - "What was AAPL's revenue growth over the last 4 quarters?"
    - "Analyze TSLA's profit margins"
    - "Compare META's P/E ratio to competitors"
    """
    if not is_dexter_available():
        status = get_dexter_status()
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Dexter research agent is not available",
                "status": status,
                "setup_instructions": [
                    "1. Clone dexter: git clone https://github.com/virattt/dexter.git",
                    "2. Install bun: https://bun.sh",
                    "3. cd dexter && bun install",
                    "4. Configure dexter/.env with API keys",
                    "5. Set DEXTER_PATH in your .env"
                ]
            }
        )

    result = await query_dexter(request.query, timeout=request.timeout)

    return ResearchResponse(
        success=result.success,
        query=result.query,
        answer=result.answer,
        error=result.error
    )


@router.get("/examples")
async def research_examples():
    """Get example research queries."""
    return {
        "examples": EXAMPLE_QUERIES,
        "tickers_in_portfolio": []  # Could populate from portfolio state
    }


@router.get("/insights")
async def get_portfolio_insights(llm_calculate: bool = False):
    """
    Generate portfolio insights for the dashboard.
    Uses Dexter if available, falls back to local LLM.

    Args:
        llm_calculate: If True, pass raw events to LLM to calculate values
                      instead of using pre-computed state.
    """
    from api.routes.state import build_portfolio_state
    from llm.config import get_llm_config

    state = build_portfolio_state()
    config = get_llm_config()

    # Build portfolio context
    holdings_summary = []
    for ticker, shares in state.get('holdings', {}).items():
        if shares > 0:
            price = state.get('latest_prices', {}).get(ticker, 0)
            cost_info = state.get('cost_basis', {}).get(ticker, {})
            value = shares * price
            gain_pct = 0
            if cost_info.get('total_cost', 0) > 0:
                gain_pct = ((value - cost_info['total_cost']) / cost_info['total_cost']) * 100
            holdings_summary.append({
                'ticker': ticker,
                'shares': shares,
                'value': value,
                'gain_pct': round(gain_pct, 1)
            })

    # Sort by value
    holdings_summary.sort(key=lambda x: x['value'], reverse=True)
    top_holdings = holdings_summary[:5]

    # Get active options
    active_options = state.get('active_options', [])

    # Calculate secured collateral for active options
    secured_collateral = 0
    for opt in active_options:
        strategy = opt.get('strategy', '').lower()
        if 'put' in strategy or 'secured' in strategy:
            secured_collateral += opt.get('strike', 0) * 100 * opt.get('contracts', 1)

    # Tax reserve estimate (25% of realized gains)
    ytd_realized = state.get('ytd_trading_gains', 0) + state.get('ytd_option_income', 0)
    tax_reserve = max(0, ytd_realized * 0.25)

    # Available cash (deployable)
    cash = state.get('cash', 0)
    available_cash = max(0, cash - secured_collateral - tax_reserve)

    # Build context string with clear cash breakdown
    portfolio_context = f"""Portfolio Overview:
- Total Value: ${state.get('total_value', 0):,.0f}
- Holdings Value: ${state.get('portfolio_value', 0):,.0f}

Cash Breakdown (IMPORTANT - all trades and options affect cash):
- Total Cash: ${cash:,.0f}
- Secured Put Collateral: ${secured_collateral:,.0f} (reserved for {len(active_options)} active options)
- Tax Reserve (25%): ${tax_reserve:,.0f} (estimated on ${ytd_realized:,.0f} realized gains)
- Available/Deployable: ${available_cash:,.0f}

YTD Income Sources:
- Trading Gains (stock buys/sells): ${state.get('ytd_trading_gains', 0):,.0f}
- Option Income (premiums minus close costs): ${state.get('ytd_option_income', 0):,.0f}
- Dividends: ${state.get('ytd_dividends', 0):,.0f}
- Total YTD Income: ${state.get('ytd_income', 0):,.0f}

Top Holdings:
"""
    for h in top_holdings:
        portfolio_context += f"- {h['ticker']}: ${h['value']:,.0f} ({h['gain_pct']:+.1f}%)\n"

    # Try Dexter first for one holding
    dexter_insight = None
    if is_dexter_available() and top_holdings:
        top_ticker = top_holdings[0]['ticker']
        try:
            result = await query_dexter(
                f"What are the key financial metrics and outlook for {top_ticker}? Be concise.",
                timeout=60
            )
            if result.success:
                dexter_insight = {
                    'ticker': top_ticker,
                    'analysis': result.answer[:500]  # Truncate for UI
                }
        except Exception:
            pass

    # Generate insights using LLM
    insights = []

    if config.enabled:
        prompt = f"""You are a portfolio analyst. Based on this portfolio data, provide 3 brief, actionable insights.
Each insight should be 1-2 sentences max. Focus on:
1. Risk/concentration observations
2. Income generation opportunities
3. Market positioning

{portfolio_context}

Format as JSON array: [{{"title": "...", "insight": "...", "type": "risk|opportunity|info"}}]
Return ONLY the JSON array, no other text."""

        try:
            if config.provider == "claude":
                import anthropic
                client = anthropic.Anthropic(api_key=config.anthropic_api_key)
                response = client.messages.create(
                    model=config.claude_model,
                    max_tokens=500,
                    messages=[{"role": "user", "content": prompt}]
                )
                import json
                insights = json.loads(response.content[0].text)
            else:
                import httpx
                response = httpx.post(
                    f"{config.local_url}/chat/completions",
                    json={
                        "model": config.local_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 500,
                        "temperature": 0.7
                    },
                    timeout=30.0
                )
                response.raise_for_status()
                import json
                result = response.json()
                insights = json.loads(result["choices"][0]["message"]["content"])
        except Exception as e:
            # Fallback static insights based on data
            insights = generate_static_insights(state, holdings_summary)
    else:
        insights = generate_static_insights(state, holdings_summary)

    return {
        "generated_at": state.get('as_of'),
        "insights": insights,
        "dexter_analysis": dexter_insight,
        "portfolio_summary": {
            "total_value": state.get('total_value', 0),
            "cash": state.get('cash', 0),
            "ytd_income": state.get('ytd_income', 0),
            "holdings_count": len(holdings_summary),
            "options_count": len(active_options)
        }
    }


def generate_static_insights(state, holdings):
    """Generate basic insights without LLM."""
    insights = []

    # Concentration check
    if holdings:
        top = holdings[0]
        total = sum(h['value'] for h in holdings)
        if total > 0:
            concentration = (top['value'] / total) * 100
            if concentration > 30:
                insights.append({
                    "title": "Concentration Risk",
                    "insight": f"{top['ticker']} represents {concentration:.0f}% of your portfolio. Consider diversifying.",
                    "type": "risk"
                })

    # Cash position
    cash = state.get('cash', 0)
    total = state.get('total_value', 1)
    cash_pct = (cash / total) * 100
    if cash_pct > 15:
        insights.append({
            "title": "High Cash Position",
            "insight": f"You have {cash_pct:.0f}% in cash. Consider deploying via covered calls or CSPs.",
            "type": "opportunity"
        })
    elif cash_pct < 5:
        insights.append({
            "title": "Low Cash Reserve",
            "insight": f"Only {cash_pct:.1f}% cash. Consider maintaining reserves for opportunities.",
            "type": "risk"
        })

    # Income progress
    ytd_income = state.get('ytd_income', 0)
    goal = 30000
    progress = (ytd_income / goal) * 100
    import datetime
    month = datetime.datetime.now().month
    expected = (month / 12) * 100

    if progress > expected + 10:
        insights.append({
            "title": "Ahead of Income Goal",
            "insight": f"YTD income at {progress:.0f}% of goal vs {expected:.0f}% expected. Great progress!",
            "type": "info"
        })
    elif progress < expected - 10:
        insights.append({
            "title": "Behind Income Goal",
            "insight": f"YTD income at {progress:.0f}% vs {expected:.0f}% expected. Consider more premium selling.",
            "type": "opportunity"
        })

    # Big winners/losers
    for h in holdings:
        if h['gain_pct'] > 50:
            insights.append({
                "title": f"{h['ticker']} Big Winner",
                "insight": f"Up {h['gain_pct']:.0f}%. Consider taking profits or selling covered calls.",
                "type": "opportunity"
            })
            break
        elif h['gain_pct'] < -30:
            insights.append({
                "title": f"{h['ticker']} Down Significantly",
                "insight": f"Down {abs(h['gain_pct']):.0f}%. Review thesis - average down or cut losses?",
                "type": "risk"
            })
            break

    return insights[:3]  # Max 3 insights


@router.get("/calculate")
async def llm_calculate_portfolio():
    """
    Let LLM calculate portfolio values from raw events.

    Instead of pre-computing values, this passes raw event data to the LLM
    and asks it to calculate cash breakdown, collateral, income, etc.
    Useful for verification and getting explanations.
    """
    from llm.config import get_llm_config
    from api.database import get_all_events, sync_csv_to_db
    import json as json_module

    config = get_llm_config()
    if not config.enabled:
        return {"error": "LLM is disabled", "suggestion": "Enable LLM in settings"}

    # Get raw events
    sync_csv_to_db()
    events = get_all_events(limit=50)

    # Format events for LLM
    events_summary = []
    for e in reversed(events):  # Chronological order
        data = json_module.loads(e.get('data_json', '{}'))
        events_summary.append({
            "id": e['event_id'],
            "type": e['event_type'],
            "ticker": data.get('ticker', ''),
            "cash_delta": e.get('cash_delta', 0),
            "data": data
        })

    # Get starting state
    from pathlib import Path
    starting_file = Path(__file__).parent.parent.parent / "data" / "starting_state.json"
    with open(starting_file) as f:
        starting = json_module.load(f)

    prompt = f"""You are a portfolio accountant. Calculate the current portfolio state from these events.

STARTING STATE:
- Cash: ${starting['cash']:,.2f}
- Holdings: {json_module.dumps(starting['initial_holdings'], indent=2)}

EVENTS (chronological order):
{json_module.dumps(events_summary, indent=2)}

CALCULATE AND RETURN AS JSON:
{{
    "current_cash": <total cash after all events>,
    "cash_breakdown": {{
        "total": <same as current_cash>,
        "secured_put_collateral": <strike * 100 * contracts for each ACTIVE put option>,
        "tax_reserve_25pct": <25% of realized gains from trades + options>,
        "available": <total - collateral - tax_reserve>
    }},
    "active_options": [<list any OPTION_OPEN without matching CLOSE/EXPIRE/ASSIGN>],
    "ytd_income": {{
        "trading_gains": <sum of gain_loss from SELL trades>,
        "option_income": <premiums received minus close costs>,
        "total": <sum of above>
    }},
    "explanation": "<brief explanation of your calculations>"
}}

RULES:
- BUY reduces cash by total amount
- SELL increases cash by total amount (gain_loss is tracked separately for income)
- OPTION_OPEN increases cash by premium
- OPTION_CLOSE reduces cash by close_cost
- OPTION_EXPIRE has no cash effect (premium already received)
- An option is ACTIVE if OPTION_OPEN has no matching CLOSE/EXPIRE/ASSIGN (match by option_id or position_id)
- Secured put collateral = strike * 100 shares * contracts

Return ONLY valid JSON, no other text."""

    try:
        if config.provider == "claude":
            import anthropic
            client = anthropic.Anthropic(api_key=config.anthropic_api_key)
            response = client.messages.create(
                model=config.claude_model,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )
            result_text = response.content[0].text
        else:
            import httpx
            response = httpx.post(
                f"{config.local_url}/chat/completions",
                json={
                    "model": config.local_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1500,
                    "temperature": 0
                },
                timeout=60.0
            )
            response.raise_for_status()
            result_text = response.json()["choices"][0]["message"]["content"]

        # Parse LLM response
        # Try to extract JSON from response
        import re
        json_match = re.search(r'\{[\s\S]*\}', result_text)
        if json_match:
            llm_result = json_module.loads(json_match.group())
        else:
            llm_result = {"raw_response": result_text, "parse_error": "Could not extract JSON"}

        return {
            "source": "llm",
            "provider": config.provider,
            "model": config.claude_model if config.provider == "claude" else config.local_model,
            "calculation": llm_result,
            "events_processed": len(events_summary)
        }

    except Exception as e:
        return {
            "error": str(e),
            "suggestion": "Check LLM configuration in settings"
        }
