"""
Agent-Enhanced Options Scanner - Uses Dexter + LLM for intelligent option analysis.

This scanner combines:
1. yfinance options chain data (prices, greeks)
2. Dexter MCP financial research (fundamentals, news, metrics)
3. LLM agent reasoning to score and recommend options

The agent considers:
- Quantitative metrics (premium, delta, theta)
- Fundamental analysis (revenue growth, margins, debt)
- News sentiment and catalysts
- Position sizing based on risk and goals
"""

import asyncio
import json
from datetime import datetime
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from api.services.options_scanner import (
    get_portfolio_holdings,
    fetch_options_chain,
    score_option,
    calculate_break_even,
    calculate_contract_recommendation,
    MAX_WORKERS
)


async def get_dexter_research(ticker: str) -> Dict:
    """
    Fetch Dexter research for a ticker via MCP.

    Returns fundamental data, metrics, and recent news.
    """
    from integrations.dexter import is_mcp_available, query_dexter_mcp, query_dexter_auto

    if not is_mcp_available():
        return {
            'ticker': ticker,
            'available': False,
            'error': 'Dexter MCP not available'
        }

    try:
        # Query Dexter for comprehensive analysis
        question = f"Get financial metrics, valuation ratios, and recent news for {ticker}"
        result = await query_dexter_auto(question, timeout=30)

        if result.success:
            return {
                'ticker': ticker,
                'available': True,
                'research': result.answer,
                'raw': result.raw_output
            }
        else:
            return {
                'ticker': ticker,
                'available': False,
                'error': result.error
            }

    except Exception as e:
        return {
            'ticker': ticker,
            'available': False,
            'error': str(e)
        }


def get_research_sync(ticker: str) -> Dict:
    """Synchronous wrapper for get_dexter_research."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(get_dexter_research(ticker))
        loop.close()
        return result
    except Exception as e:
        return {
            'ticker': ticker,
            'available': False,
            'error': str(e)
        }


def build_agent_prompt(options: List[Dict], research: Dict[str, Dict], portfolio: Dict) -> str:
    """
    Build a comprehensive prompt for the LLM agent to analyze options.
    Uses self-reflective questioning approach for deeper analysis.
    """
    prompt = f"""You are an expert options income strategist using self-reflective questioning to analyze opportunities.

## Your Approach: Self-Questioning Before Recommendations

Before recommending anything, ask yourself these questions and answer them:

1. "What's the current market sentiment and how does it affect option premiums?"
2. "Which of these stocks would I actually want to own at the put strike prices?"
3. "Am I recommending high-premium options because they're good or because they look attractive?"
4. "What's the realistic probability of assignment and am I okay with that outcome?"
5. "Is this portfolio overexposed to any sector or correlation risk?"
6. "How close is this portfolio to its income goal and what's the appropriate risk level?"
7. "What information am I missing that would change my recommendations?"

## Portfolio Context
- Cash Available: ${portfolio['cash']:,.0f}
- YTD Income: ${portfolio['ytd_income']:,.0f} of ${portfolio['income_goal']:,.0f} goal ({portfolio['ytd_income']/portfolio['income_goal']*100:.1f}%)
- Remaining Goal: ${portfolio['remaining_goal']:,.0f}
- Holdings: {list(portfolio['holdings'].keys())}
- Holdings Value by Ticker: {json.dumps({k: f"${v['value']:,.0f}" for k, v in portfolio['holdings'].items()}, indent=2) if isinstance(list(portfolio['holdings'].values())[0] if portfolio['holdings'] else {}, dict) else 'See below'}

## Fundamental Research (from Dexter)
"""

    for ticker, data in research.items():
        if data.get('available') and data.get('research'):
            prompt += f"\n### {ticker}\n{data['research'][:1500]}\n"
        else:
            prompt += f"\n### {ticker}\nNo research available: {data.get('error', 'Unknown')}\n"

    prompt += "\n## Options Opportunities\n"

    # Group by ticker
    by_ticker = {}
    for opt in options:
        ticker = opt['ticker']
        if ticker not in by_ticker:
            by_ticker[ticker] = []
        by_ticker[ticker].append(opt)

    for ticker, opts in by_ticker.items():
        prompt += f"\n### {ticker} (Current: ${opts[0]['current_price']:.2f})\n"

        puts = [o for o in opts if o['type'] == 'PUT'][:3]
        calls = [o for o in opts if o['type'] == 'CALL'][:3]

        if puts:
            prompt += "**Cash-Secured Puts:**\n"
            for p in puts:
                prompt += f"- ${p['strike']:.2f} put, {p['expiration']} ({p['dte']}d): ${p['premium_per_contract']:.0f} premium, {p['annualized_yield_pct']:.1f}% ann yield, {p['otm_pct']:.1f}% OTM, delta {p['delta']:.2f}\n"

        if calls:
            prompt += "**Covered Calls:**\n"
            for c in calls:
                prompt += f"- ${c['strike']:.2f} call, {c['expiration']} ({c['dte']}d): ${c['premium_per_contract']:.0f} premium, {c['annualized_yield_pct']:.1f}% ann yield, {c['otm_pct']:.1f}% OTM, delta {c['delta']:.2f}\n"

    prompt += """
## Your Analysis Task

After your self-questioning, provide your analysis. Include:
- Your honest assessment of the market conditions
- Which opportunities you considered but rejected (and WHY - this is important!)
- Your top recommendations with specific reasoning

**Be honest**: If none of these opportunities are compelling, say so. Don't recommend trades just to recommend something.

Respond with a JSON object containing:
{
    "self_reflection": {
        "key_question_answered": "The most important question you asked yourself and your answer",
        "rejected_opportunities": ["Ticker/strike you considered but rejected and why"],
        "risk_concerns": ["Concerns you have about any recommendations"]
    },
    "ranked_recommendations": [
        {
            "rank": 1,
            "ticker": "XYZ",
            "type": "PUT" or "CALL",
            "strike": 100.00,
            "expiration": "2026-02-14",
            "agent_score": 85,
            "reasoning": "Honest explanation including both positives AND concerns",
            "risk_factors": ["Specific risks to watch"],
            "suggested_contracts": 2,
            "confidence": "HIGH" or "MEDIUM" or "LOW",
            "would_i_own_at_strike": true or false (for puts)
        }
    ],
    "market_outlook": "Your honest assessment - don't just be bullish by default",
    "strategy_notes": "What this portfolio should actually do (including doing nothing if appropriate)",
    "contrarian_view": "What could go wrong with these recommendations?"
}

Focus on quality over quantity. If only 2-3 opportunities are genuinely good, that's fine.
Be specific about why each is recommended AND what could go wrong.
"""

    return prompt


def parse_agent_response(response: str) -> Dict:
    """Parse the LLM agent's JSON response."""
    try:
        # Try to extract JSON from response
        import re

        # Look for JSON block
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            return json.loads(json_match.group())

        # Fallback: return as analysis text
        return {
            'ranked_recommendations': [],
            'market_outlook': response[:500],
            'strategy_notes': 'Could not parse structured response',
            'raw_response': response
        }

    except json.JSONDecodeError:
        return {
            'ranked_recommendations': [],
            'market_outlook': 'Parse error',
            'strategy_notes': response[:500] if response else 'No response',
            'raw_response': response
        }


async def get_agent_recommendations(
    max_dte: int = 45,
    min_premium: float = 50,
    max_results: int = 10
) -> Dict:
    """
    Get LLM agent-scored options recommendations using Dexter research.

    This is the main entry point for agent-enhanced scanning.
    """
    from llm.client import get_llm_response
    from llm.config import get_llm_config

    portfolio = get_portfolio_holdings()
    holdings = portfolio['holdings']
    cash = portfolio['cash']

    # Check if LLM is enabled
    config = get_llm_config()
    if not config.enabled:
        return {
            'status': 'error',
            'error': 'LLM is not enabled. Enable it in settings to use agent scanner.',
            'generated_at': datetime.now().isoformat()
        }

    all_options = []
    scan_errors = []
    research_data = {}

    # 1. Fetch options chains in parallel
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(fetch_options_chain, ticker, max_dte): ticker
            for ticker in holdings.keys()
        }

        for future in as_completed(futures):
            ticker = futures[future]
            try:
                options = future.result()
                if options:
                    # Pre-score and filter options
                    for opt in options:
                        opt['score'] = score_option(opt, portfolio)

                        # Filter by premium threshold
                        if opt['premium_per_contract'] >= min_premium:
                            # For puts, check collateral
                            if opt['type'] == 'PUT':
                                if opt['collateral_required'] > cash * 0.5:
                                    continue

                            # Add enhanced metrics
                            opt['break_even'] = calculate_break_even(opt)
                            contract_rec = calculate_contract_recommendation(opt, portfolio)
                            opt['suggested_contracts'] = contract_rec['suggested_contracts']
                            opt['max_contracts'] = contract_rec['max_by_capital']

                            all_options.append(opt)
                else:
                    scan_errors.append(f"{ticker}: No options data")

            except Exception as e:
                scan_errors.append(f"{ticker}: {str(e)}")

    if not all_options:
        return {
            'status': 'no_data',
            'error': 'No options opportunities found matching criteria',
            'scan_errors': scan_errors,
            'generated_at': datetime.now().isoformat()
        }

    # Sort by score to get best candidates
    all_options.sort(key=lambda x: x['score'], reverse=True)
    top_options = all_options[:20]  # Top 20 for agent analysis

    # 2. Fetch Dexter research for tickers in top options
    unique_tickers = list(set(opt['ticker'] for opt in top_options))

    # Parallel research fetch
    with ThreadPoolExecutor(max_workers=3) as executor:
        research_futures = {
            executor.submit(get_research_sync, ticker): ticker
            for ticker in unique_tickers[:5]  # Limit to top 5 tickers for speed
        }

        for future in as_completed(research_futures):
            ticker = research_futures[future]
            try:
                research_data[ticker] = future.result()
            except Exception as e:
                research_data[ticker] = {
                    'ticker': ticker,
                    'available': False,
                    'error': str(e)
                }

    # 3. Build prompt and get agent analysis
    prompt = build_agent_prompt(top_options, research_data, portfolio)

    try:
        agent_response = get_llm_response(prompt, max_tokens=2000)
        agent_analysis = parse_agent_response(agent_response)
    except Exception as e:
        agent_analysis = {
            'ranked_recommendations': [],
            'market_outlook': f'Agent analysis failed: {str(e)}',
            'strategy_notes': 'Falling back to algorithmic scoring'
        }

    # 4. Merge agent rankings with option details
    recommendations = []

    if agent_analysis.get('ranked_recommendations'):
        for agent_rec in agent_analysis['ranked_recommendations'][:max_results]:
            # Find matching option
            matching = [
                o for o in all_options
                if o['ticker'] == agent_rec.get('ticker')
                and o['type'] == agent_rec.get('type')
                and abs(o['strike'] - agent_rec.get('strike', 0)) < 0.01
            ]

            if matching:
                opt = matching[0].copy()
                opt['agent_score'] = agent_rec.get('agent_score', opt['score'])
                opt['agent_reasoning'] = agent_rec.get('reasoning', '')
                opt['agent_risk_factors'] = agent_rec.get('risk_factors', [])
                opt['agent_confidence'] = agent_rec.get('confidence', 'MEDIUM')
                opt['agent_suggested_contracts'] = agent_rec.get('suggested_contracts', opt.get('suggested_contracts', 1))
                recommendations.append(opt)
            else:
                # Agent recommended something not in our filtered list
                recommendations.append({
                    'ticker': agent_rec.get('ticker'),
                    'type': agent_rec.get('type'),
                    'strike': agent_rec.get('strike'),
                    'expiration': agent_rec.get('expiration'),
                    'agent_score': agent_rec.get('agent_score', 0),
                    'agent_reasoning': agent_rec.get('reasoning', ''),
                    'agent_risk_factors': agent_rec.get('risk_factors', []),
                    'agent_confidence': agent_rec.get('confidence', 'LOW'),
                    'note': 'Agent recommendation - verify details'
                })

    # If agent didn't return recommendations, use algorithmic ones
    if not recommendations:
        recommendations = all_options[:max_results]
        for opt in recommendations:
            opt['agent_score'] = opt['score']
            opt['agent_reasoning'] = 'Algorithmic scoring (agent unavailable)'
            opt['agent_confidence'] = 'MEDIUM'

    # Calculate potential income
    potential_income = sum(
        r.get('premium_per_contract', 0) * r.get('agent_suggested_contracts', r.get('suggested_contracts', 1))
        for r in recommendations[:5]
    )

    return {
        'status': 'success',
        'generated_at': datetime.now().isoformat(),
        'agent_model': config.local_model if config.provider == 'local' else config.claude_model,
        'dexter_available': any(r.get('available') for r in research_data.values()),
        'portfolio_summary': {
            'holdings_scanned': len(holdings),
            'cash_available': cash,
            'ytd_income': portfolio['ytd_income'],
            'income_goal': portfolio['income_goal'],
            'remaining_goal': portfolio['remaining_goal']
        },
        'recommendations': recommendations,
        'potential_income': potential_income,
        'market_outlook': agent_analysis.get('market_outlook', ''),
        'strategy_notes': agent_analysis.get('strategy_notes', ''),
        'research_summary': {
            ticker: {
                'available': data.get('available'),
                'preview': data.get('research', '')[:200] if data.get('research') else None
            }
            for ticker, data in research_data.items()
        },
        'scan_errors': scan_errors if scan_errors else None
    }


def get_agent_recommendations_sync(
    max_dte: int = 45,
    min_premium: float = 50,
    max_results: int = 10
) -> Dict:
    """Synchronous wrapper for get_agent_recommendations."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            get_agent_recommendations(max_dte, min_premium, max_results)
        )
        loop.close()
        return result
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'generated_at': datetime.now().isoformat()
        }
