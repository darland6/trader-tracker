"""
Reality Projections Service - LLM-powered timeline generation.

Generates past analysis and future projections for the multiverse visualization.
Uses LLM to create realistic macro events, market scenarios, and portfolio projections.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import hashlib


def get_portfolio_context() -> Dict:
    """Get current portfolio state for LLM context."""
    from reconstruct_state import load_event_log, reconstruct_state
    from pathlib import Path

    SCRIPT_DIR = Path(__file__).parent.parent.parent.resolve()
    events_df = load_event_log(str(SCRIPT_DIR / 'data' / 'event_log_enhanced.csv'))
    state = reconstruct_state(events_df)

    holdings_summary = []
    for ticker, shares in state.get('holdings', {}).items():
        if shares > 0:
            price = state.get('latest_prices', {}).get(ticker, 0)
            cost_basis = state.get('cost_basis', {}).get(ticker, {})
            holdings_summary.append({
                'ticker': ticker,
                'shares': shares,
                'price': price,
                'value': shares * price,
                'cost_basis': cost_basis.get('avg_price', 0),
                'gain_pct': ((price - cost_basis.get('avg_price', 1)) / cost_basis.get('avg_price', 1) * 100) if cost_basis.get('avg_price', 0) > 0 else 0
            })

    return {
        'total_value': state.get('total_value', 0),
        'cash': state.get('cash', 0),
        'portfolio_value': state.get('portfolio_value', 0),
        'holdings': sorted(holdings_summary, key=lambda x: x['value'], reverse=True),
        'ytd_income': state.get('ytd_income', 0),
        'active_options': len(state.get('active_options', []))
    }


def build_projection_prompt(portfolio: Dict, years_forward: int = 3, years_back: int = 1) -> str:
    """Build the LLM prompt for generating projections."""

    holdings_text = "\n".join([
        f"- {h['ticker']}: {h['shares']:.0f} shares @ ${h['price']:.2f} = ${h['value']:,.0f} ({h['gain_pct']:+.1f}%)"
        for h in portfolio['holdings'][:8]
    ])

    prompt = f"""You are a financial analyst creating scenario projections for a portfolio visualization.

## Current Portfolio (as of {datetime.now().strftime('%Y-%m-%d')})
Total Value: ${portfolio['total_value']:,.0f}
Cash: ${portfolio['cash']:,.0f}
Holdings Value: ${portfolio['portfolio_value']:,.0f}

Top Holdings:
{holdings_text}

## Task
Generate a structured JSON response with timeline projections for this portfolio. Create realistic scenarios based on:
1. The specific stocks held (tech-heavy, growth stocks, etc.)
2. Current market conditions and trends
3. Macro economic factors

## Output Format
Return ONLY valid JSON (no markdown, no explanation) with this exact structure:

{{
    "generated_at": "{datetime.now().isoformat()}",
    "timeline": {{
        "start_date": "{(datetime.now() - timedelta(days=365*years_back)).strftime('%Y-%m-%d')}",
        "end_date": "{(datetime.now() + timedelta(days=365*years_forward)).strftime('%Y-%m-%d')}",
        "present_date": "{datetime.now().strftime('%Y-%m-%d')}"
    }},
    "realities": [
        {{
            "id": "base",
            "name": "Base Case",
            "description": "Most likely scenario based on current trends",
            "probability": 0.5,
            "color": "#06b6d4",
            "sentiment": "neutral",
            "snapshots": [
                {{
                    "date": "YYYY-MM-DD",
                    "total_value": 000000,
                    "change_from_present_pct": 0.0,
                    "sentiment": "bullish|bearish|neutral",
                    "sentiment_score": 0.0
                }}
            ],
            "macro_events": [
                {{
                    "date": "YYYY-MM-DD",
                    "title": "Event Title",
                    "description": "What happened and market impact",
                    "impact": "positive|negative|neutral",
                    "magnitude": "minor|moderate|major",
                    "affected_holdings": ["TICKER1", "TICKER2"]
                }}
            ]
        }},
        {{
            "id": "bull",
            "name": "Bull Scenario",
            "description": "Optimistic case - favorable conditions",
            "probability": 0.25,
            "color": "#22c55e",
            "sentiment": "bullish",
            "snapshots": [...],
            "macro_events": [...]
        }},
        {{
            "id": "bear",
            "name": "Bear Scenario",
            "description": "Pessimistic case - adverse conditions",
            "probability": 0.25,
            "color": "#ef4444",
            "sentiment": "bearish",
            "snapshots": [...],
            "macro_events": [...]
        }}
    ]
}}

## Requirements for snapshots:
- Include monthly snapshots from {years_back} year ago to {years_forward} years in future
- Past snapshots should reflect actual market history (approximate)
- Future snapshots should project realistic growth/decline based on scenario
- sentiment_score: -1.0 (very bearish) to +1.0 (very bullish)

## Requirements for macro_events:
- 4-6 events per reality (mix of past and future)
- Past events: Real events that impacted these holdings
- Future events: Plausible events that could occur
- Be specific to the holdings in this portfolio
- Include dates spread across the timeline

Generate realistic, thoughtful projections. For past events, reference real market events. For future events, create plausible scenarios based on each company's sector and business model."""

    return prompt


def parse_llm_response(response: str) -> Optional[Dict]:
    """Parse LLM response, handling various formats."""
    import re

    # Try to extract JSON from response
    # First try: direct JSON parse
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # Second try: find JSON block
    json_match = re.search(r'\{[\s\S]*\}', response)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # Third try: find JSON in code blocks
    code_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', response)
    if code_match:
        try:
            return json.loads(code_match.group(1))
        except json.JSONDecodeError:
            pass

    return None


def generate_fallback_projections(portfolio: Dict, years_forward: int = 3, years_back: int = 1) -> Dict:
    """Generate basic projections without LLM."""
    from datetime import datetime, timedelta

    now = datetime.now()
    start_date = now - timedelta(days=365 * years_back)
    end_date = now + timedelta(days=365 * years_forward)

    base_value = portfolio['total_value']

    def generate_snapshots(growth_rate: float, volatility: float) -> List[Dict]:
        snapshots = []
        current = start_date
        months = 0

        while current <= end_date:
            # Calculate value at this point
            years_from_present = (current - now).days / 365

            if years_from_present < 0:
                # Past: use lower volatility
                value = base_value * (1 + growth_rate * years_from_present * 0.8)
            else:
                # Future: project with growth rate
                value = base_value * (1 + growth_rate) ** years_from_present

            # Add some variation
            import math
            variation = math.sin(months * 0.5) * volatility * base_value
            value += variation

            sentiment_score = growth_rate + (variation / base_value)

            snapshots.append({
                'date': current.strftime('%Y-%m-%d'),
                'total_value': round(value, 0),
                'change_from_present_pct': round((value - base_value) / base_value * 100, 1),
                'sentiment': 'bullish' if sentiment_score > 0.05 else ('bearish' if sentiment_score < -0.05 else 'neutral'),
                'sentiment_score': round(max(-1, min(1, sentiment_score * 5)), 2)
            })

            current += timedelta(days=30)
            months += 1

        return snapshots

    # Generate macro events
    def generate_events(scenario: str) -> List[Dict]:
        events = []

        # Past event
        past_date = (now - timedelta(days=180)).strftime('%Y-%m-%d')
        events.append({
            'date': past_date,
            'title': 'Market Volatility' if scenario != 'bull' else 'Tech Rally',
            'description': 'Market experienced significant movement affecting growth stocks',
            'impact': 'neutral' if scenario == 'base' else ('positive' if scenario == 'bull' else 'negative'),
            'magnitude': 'moderate',
            'affected_holdings': [h['ticker'] for h in portfolio['holdings'][:3]]
        })

        # Future events
        future_dates = [
            (now + timedelta(days=90)).strftime('%Y-%m-%d'),
            (now + timedelta(days=365)).strftime('%Y-%m-%d'),
            (now + timedelta(days=730)).strftime('%Y-%m-%d')
        ]

        if scenario == 'bull':
            events.extend([
                {'date': future_dates[0], 'title': 'AI Boom Accelerates', 'description': 'Major AI breakthroughs drive tech valuations higher', 'impact': 'positive', 'magnitude': 'major', 'affected_holdings': [h['ticker'] for h in portfolio['holdings'][:2]]},
                {'date': future_dates[1], 'title': 'Fed Cuts Rates', 'description': 'Interest rate cuts boost growth stocks', 'impact': 'positive', 'magnitude': 'moderate', 'affected_holdings': [h['ticker'] for h in portfolio['holdings']]},
                {'date': future_dates[2], 'title': 'Space Economy Expansion', 'description': 'Commercial space industry reaches new milestones', 'impact': 'positive', 'magnitude': 'major', 'affected_holdings': ['RKLB'] if any(h['ticker'] == 'RKLB' for h in portfolio['holdings']) else []}
            ])
        elif scenario == 'bear':
            events.extend([
                {'date': future_dates[0], 'title': 'Recession Fears', 'description': 'Economic indicators point to slowdown', 'impact': 'negative', 'magnitude': 'major', 'affected_holdings': [h['ticker'] for h in portfolio['holdings']]},
                {'date': future_dates[1], 'title': 'Tech Regulation', 'description': 'New regulations impact tech sector', 'impact': 'negative', 'magnitude': 'moderate', 'affected_holdings': [h['ticker'] for h in portfolio['holdings'][:3]]},
                {'date': future_dates[2], 'title': 'Market Correction', 'description': 'Valuations normalize after prolonged rally', 'impact': 'negative', 'magnitude': 'moderate', 'affected_holdings': [h['ticker'] for h in portfolio['holdings']]}
            ])
        else:
            events.extend([
                {'date': future_dates[0], 'title': 'Mixed Earnings Season', 'description': 'Companies report varied results', 'impact': 'neutral', 'magnitude': 'minor', 'affected_holdings': [h['ticker'] for h in portfolio['holdings'][:2]]},
                {'date': future_dates[1], 'title': 'Sector Rotation', 'description': 'Investors shift between growth and value', 'impact': 'neutral', 'magnitude': 'moderate', 'affected_holdings': [h['ticker'] for h in portfolio['holdings']]},
                {'date': future_dates[2], 'title': 'Steady Growth', 'description': 'Markets continue gradual appreciation', 'impact': 'positive', 'magnitude': 'minor', 'affected_holdings': [h['ticker'] for h in portfolio['holdings']]}
            ])

        return events

    return {
        'generated_at': now.isoformat(),
        'source': 'fallback',
        'timeline': {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'present_date': now.strftime('%Y-%m-%d')
        },
        'realities': [
            {
                'id': 'base',
                'name': 'Base Case',
                'description': 'Most likely scenario - moderate growth continues',
                'probability': 0.50,
                'color': '#06b6d4',
                'sentiment': 'neutral',
                'snapshots': generate_snapshots(0.08, 0.03),
                'macro_events': generate_events('base')
            },
            {
                'id': 'bull',
                'name': 'Bull Scenario',
                'description': 'Optimistic - strong growth driven by favorable conditions',
                'probability': 0.25,
                'color': '#22c55e',
                'sentiment': 'bullish',
                'snapshots': generate_snapshots(0.25, 0.05),
                'macro_events': generate_events('bull')
            },
            {
                'id': 'bear',
                'name': 'Bear Scenario',
                'description': 'Pessimistic - downturn from adverse conditions',
                'probability': 0.25,
                'color': '#ef4444',
                'sentiment': 'bearish',
                'snapshots': generate_snapshots(-0.15, 0.06),
                'macro_events': generate_events('bear')
            }
        ],
        'portfolio_context': {
            'total_value': portfolio['total_value'],
            'holdings': [h['ticker'] for h in portfolio['holdings']]
        }
    }


async def generate_projections(
    years_forward: int = 3,
    years_back: int = 1,
    use_llm: bool = True
) -> Dict:
    """
    Generate timeline projections for the multiverse visualization.

    Args:
        years_forward: Years to project into future
        years_back: Years of history to include
        use_llm: Whether to use LLM for intelligent projections

    Returns:
        Structured projection data for visualization
    """
    from llm.config import get_llm_config

    portfolio = get_portfolio_context()

    if not use_llm:
        return generate_fallback_projections(portfolio, years_forward, years_back)

    config = get_llm_config()
    if not config.enabled:
        return generate_fallback_projections(portfolio, years_forward, years_back)

    try:
        from llm.client import get_llm_response

        prompt = build_projection_prompt(portfolio, years_forward, years_back)
        response = get_llm_response(prompt, max_tokens=4000)

        parsed = parse_llm_response(response)

        if parsed and 'realities' in parsed:
            parsed['source'] = 'llm'
            parsed['model'] = config.local_model if config.provider == 'local' else config.claude_model
            parsed['portfolio_context'] = {
                'total_value': portfolio['total_value'],
                'holdings': [h['ticker'] for h in portfolio['holdings']]
            }
            return parsed
        else:
            # LLM response wasn't parseable, use fallback
            result = generate_fallback_projections(portfolio, years_forward, years_back)
            result['llm_error'] = 'Response not parseable'
            return result

    except Exception as e:
        result = generate_fallback_projections(portfolio, years_forward, years_back)
        result['llm_error'] = str(e)
        return result


def generate_projections_sync(
    years_forward: int = 3,
    years_back: int = 1,
    use_llm: bool = True
) -> Dict:
    """Synchronous wrapper for generate_projections."""
    import asyncio

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            generate_projections(years_forward, years_back, use_llm)
        )
        loop.close()
        return result
    except Exception as e:
        portfolio = get_portfolio_context()
        result = generate_fallback_projections(portfolio, years_forward, years_back)
        result['error'] = str(e)
        return result
