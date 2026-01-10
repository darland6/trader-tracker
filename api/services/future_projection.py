"""Future Projection Service - Generate AI-powered portfolio projections.

Uses LLM analysis to project portfolio performance based on:
- Current catalysts and trends for each ticker
- Seasonality patterns
- Expected macro trends
- 3-5 year time horizon
"""

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import random
import math

# Storage
DATA_DIR = Path(__file__).parent.parent.parent / "data"
PROJECTIONS_DIR = DATA_DIR / "projections"


def ensure_storage():
    """Ensure storage directory exists."""
    PROJECTIONS_DIR.mkdir(parents=True, exist_ok=True)


def generate_projection(
    history_id: str = "reality",
    years: int = 3,
    use_llm: bool = True
) -> dict:
    """Generate a future projection for a portfolio.

    Args:
        history_id: The history to project from ("reality" or alt history ID)
        years: Number of years to project (1-5)
        use_llm: Whether to use LLM for analysis (falls back to statistical if False)

    Returns:
        Projection data with future frames
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    from reconstruct_state import load_event_log, reconstruct_state
    from api.services.alt_history import get_history_events, get_history

    # Get alternate history metadata if not reality
    history_context = None
    if history_id != "reality":
        history_metadata = get_history(history_id)
        if history_metadata:
            history_context = {
                "name": history_metadata.get("name", ""),
                "description": history_metadata.get("description", ""),
                "modifications": history_metadata.get("modifications", [])
            }

    # Load current state
    if history_id == "reality":
        events = load_event_log(str(DATA_DIR / "event_log_enhanced.csv"))
    else:
        events = get_history_events(history_id)

    if events is None:
        return {"error": "History not found"}

    current_state = reconstruct_state(events)

    # Always load reality's prices as fallback for alternates
    reality_prices = current_state.get('latest_prices', {})
    if history_id != "reality":
        # Load reality prices to use as fallback
        reality_events = load_event_log(str(DATA_DIR / "event_log_enhanced.csv"))
        reality_state = reconstruct_state(reality_events)
        reality_prices = reality_state.get('latest_prices', {})

    # Get holdings for analysis
    holdings = []
    for ticker, shares in current_state.get('holdings', {}).items():
        if shares > 0.01:
            # Use reality prices as fallback if alternate doesn't have prices
            price = current_state.get('latest_prices', {}).get(ticker, 0)
            if price == 0:
                price = reality_prices.get(ticker, 0)
            cost_info = current_state.get('cost_basis', {}).get(ticker, {})
            holdings.append({
                "ticker": ticker,
                "shares": shares,
                "current_price": price,
                "market_value": shares * price,
                "avg_cost": cost_info.get('avg_price', 0),
                "unrealized_gain_pct": ((price - cost_info.get('avg_price', 1)) / cost_info.get('avg_price', 1) * 100) if cost_info.get('avg_price', 0) > 0 else 0
            })

    # Generate analysis and projections
    if use_llm:
        analysis = get_llm_analysis(holdings, years, history_context)
    else:
        analysis = get_statistical_analysis(holdings, years, history_context)

    # Generate future price frames
    projection_id = str(uuid.uuid4())[:8]
    start_date = datetime.now()
    frames = generate_future_frames(
        holdings,
        analysis,
        start_date,
        years
    )

    projection = {
        "id": projection_id,
        "history_id": history_id,
        "created_at": datetime.now().isoformat(),
        "years": years,
        "start_date": start_date.isoformat(),
        "end_date": (start_date + timedelta(days=years * 365)).isoformat(),
        "current_state": {
            "total_value": current_state.get('total_value', 0),
            "cash": current_state.get('cash', 0),
            "portfolio_value": current_state.get('portfolio_value', 0),
            "holdings_count": len(holdings)
        },
        "analysis": analysis,
        "frames": frames,
        "projected_state": frames[-1] if frames else None
    }

    # Save projection
    save_projection(projection)

    return projection


def get_llm_analysis(holdings: list, years: int, history_context: dict = None) -> dict:
    """Get LLM-powered analysis of holdings and market trends.

    Args:
        holdings: List of portfolio holdings
        years: Number of years to project
        history_context: Optional context for alternate realities with name, description, modifications
    """
    try:
        from llm.config import get_llm_config
        from llm.client import get_llm_client

        config = get_llm_config()
        if not config.enabled:
            return get_statistical_analysis(holdings, years, history_context)

        # Build analysis prompt
        holdings_summary = "\n".join([
            f"- {h['ticker']}: {h['shares']:.0f} shares @ ${h['current_price']:.2f} "
            f"(${h['market_value']:,.0f}, {h['unrealized_gain_pct']:+.1f}%)"
            for h in holdings
        ])

        # Build alternate reality context if provided
        reality_context = ""
        if history_context and history_context.get("description"):
            reality_context = f"""
ALTERNATE REALITY SCENARIO:
Name: {history_context.get('name', 'Alternate')}
Description: {history_context.get('description', '')}

This is a "what-if" scenario. The user's description above should STRONGLY influence your projections.
Interpret the description to adjust growth rates, risk levels, and key events accordingly.
For example:
- "More aggressive on tech" → Higher growth rates for tech stocks, but also higher volatility
- "Conservative dividend focus" → Lower growth but more stable, income-focused projections
- "What if crypto crashed?" → Model a significant downturn scenario
- "Bull market continues" → Optimistic projections across the board

Apply the user's intent to ALL growth rate estimates and analysis.
"""

        prompt = f"""Analyze these portfolio holdings and provide a {years}-year projection:
{reality_context}
CURRENT HOLDINGS:
{holdings_summary}

For each ticker, analyze:
1. Current catalysts (earnings, products, market position)
2. Industry trends and competitive landscape
3. Seasonality patterns (e.g., retail Q4 strength, summer doldrums)
4. Macro sensitivity (interest rates, inflation, GDP)
5. Risk factors

Then provide a {years}-year projection with:
- Expected annual growth rate (pessimistic, base, optimistic)
- Key inflection points or catalysts
- Confidence level (low/medium/high)

Respond in JSON format:
{{
    "macro_outlook": {{
        "summary": "overall market outlook",
        "interest_rates": "expected trend",
        "inflation": "expected trend",
        "gdp_growth": "expected range"
    }},
    "ticker_analysis": {{
        "TICKER": {{
            "current_catalysts": ["list of catalysts"],
            "industry_trend": "growing/stable/declining",
            "seasonality": "Q4 strong, summer weak, etc",
            "annual_growth_rates": {{
                "pessimistic": -10,
                "base": 15,
                "optimistic": 40
            }},
            "key_events": ["potential future events"],
            "confidence": "medium",
            "risk_factors": ["list of risks"]
        }}
    }},
    "portfolio_projection": {{
        "year_1": {{"pessimistic": -5, "base": 12, "optimistic": 25}},
        "year_2": {{"pessimistic": -8, "base": 24, "optimistic": 55}},
        "year_3": {{"pessimistic": -10, "base": 38, "optimistic": 90}}
    }}
}}"""

        client = get_llm_client()
        if client is None:
            return get_statistical_analysis(holdings, years, history_context)

        response = client.generate(prompt, max_tokens=2000)

        # Parse JSON from response
        try:
            # Find JSON in response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                analysis = json.loads(response[json_start:json_end])
                analysis["source"] = "llm"
                if history_context:
                    analysis["history_context"] = history_context
                return analysis
        except json.JSONDecodeError:
            pass

        return get_statistical_analysis(holdings, years, history_context)

    except Exception as e:
        print(f"LLM analysis failed: {e}")
        return get_statistical_analysis(holdings, years, history_context)


def get_statistical_analysis(holdings: list, years: int, history_context: dict = None) -> dict:
    """Generate statistical analysis without LLM.

    Args:
        holdings: List of portfolio holdings
        years: Number of years to project
        history_context: Optional context for alternate realities - used to adjust projections
    """

    # Parse description to get adjustment multipliers
    growth_multiplier = 1.0
    volatility_multiplier = 1.0
    scenario_note = "Statistical projection"

    if history_context and history_context.get("description"):
        desc = history_context.get("description", "").lower()

        # Bullish/optimistic keywords → higher growth
        if any(word in desc for word in ["bull", "optimistic", "moon", "rocket", "aggressive", "growth", "boom"]):
            growth_multiplier = 1.5
            scenario_note = "Bullish scenario - higher growth rates"

        # Bearish/pessimistic keywords → lower growth
        elif any(word in desc for word in ["bear", "pessimistic", "crash", "recession", "conservative", "safe", "downturn"]):
            growth_multiplier = 0.5
            volatility_multiplier = 1.5
            scenario_note = "Bearish scenario - reduced growth, higher volatility"

        # Tech-focused keywords → boost tech stocks
        elif any(word in desc for word in ["tech", "ai", "innovation", "disruption"]):
            growth_multiplier = 1.3
            scenario_note = "Tech-focused scenario - higher tech growth"

        # Doubling/scaling specific ticker (check modifications)
        mods = history_context.get("modifications", [])
        for mod in mods:
            if mod.get("type") == "scale_position":
                scale = mod.get("scale", 1.0)
                if scale > 1:
                    growth_multiplier *= 1.1  # Scaled up = more aggressive
                    scenario_note = f"Position scaled {scale}x - adjusted projections"
            elif mod.get("type") == "remove_ticker":
                scenario_note = f"Removed {mod.get('ticker', 'ticker')} - portfolio rebalanced"

    # Default sector characteristics
    sector_profiles = {
        # Tech/Growth
        "TSLA": {"growth": 20, "volatility": 45, "seasonality": [1.0, 0.95, 1.05, 1.1], "sector": "EV/Tech"},
        "META": {"growth": 15, "volatility": 30, "seasonality": [0.95, 1.0, 1.0, 1.15], "sector": "Tech/Advertising"},
        "PLTR": {"growth": 25, "volatility": 50, "seasonality": [1.0, 1.0, 1.0, 1.1], "sector": "Tech/Government"},
        "RKLB": {"growth": 30, "volatility": 55, "seasonality": [1.0, 1.0, 1.0, 1.0], "sector": "Space"},
        "NBIS": {"growth": 20, "volatility": 40, "seasonality": [1.0, 1.0, 1.0, 1.0], "sector": "Tech"},

        # Default for unknown
        "DEFAULT": {"growth": 10, "volatility": 25, "seasonality": [1.0, 1.0, 1.0, 1.0], "sector": "Unknown"}
    }

    ticker_analysis = {}
    for h in holdings:
        ticker = h['ticker']
        profile = sector_profiles.get(ticker, sector_profiles["DEFAULT"])

        # Apply multipliers from description
        base_growth = profile["growth"] * growth_multiplier
        volatility = profile["volatility"] * volatility_multiplier

        ticker_analysis[ticker] = {
            "current_catalysts": [scenario_note],
            "industry_trend": "projected based on historical patterns",
            "seasonality": f"Q1-Q4 factors: {profile['seasonality']}",
            "annual_growth_rates": {
                "pessimistic": base_growth - volatility * 0.5,
                "base": base_growth,
                "optimistic": base_growth + volatility * 0.5
            },
            "key_events": ["Earnings reports", "Product launches"],
            "confidence": "low" if growth_multiplier == 1.0 else "medium",
            "risk_factors": ["Market volatility", "Competition", "Macro conditions"],
            "sector": profile["sector"]
        }

    # Portfolio-level projections
    portfolio_projection = {}
    cumulative = {"pessimistic": 0, "base": 0, "optimistic": 0}

    for year in range(1, years + 1):
        # Add compounding growth
        for scenario in ["pessimistic", "base", "optimistic"]:
            avg_growth = sum(
                ticker_analysis[h['ticker']]["annual_growth_rates"][scenario] *
                (h['market_value'] / sum(x['market_value'] for x in holdings))
                for h in holdings if h['ticker'] in ticker_analysis
            )
            cumulative[scenario] = (1 + cumulative[scenario]/100) * (1 + avg_growth/100) * 100 - 100

        portfolio_projection[f"year_{year}"] = {
            "pessimistic": round(cumulative["pessimistic"], 1),
            "base": round(cumulative["base"], 1),
            "optimistic": round(cumulative["optimistic"], 1)
        }

    result = {
        "source": "statistical",
        "scenario_note": scenario_note,
        "growth_multiplier": growth_multiplier,
        "macro_outlook": {
            "summary": scenario_note if growth_multiplier != 1.0 else "Projection based on historical patterns and sector analysis",
            "interest_rates": "Assumed stable",
            "inflation": "Moderate (2-3%)",
            "gdp_growth": "2-3% annually"
        },
        "ticker_analysis": ticker_analysis,
        "portfolio_projection": portfolio_projection
    }

    if history_context:
        result["history_context"] = history_context

    return result


def generate_future_frames(
    holdings: list,
    analysis: dict,
    start_date: datetime,
    years: int
) -> list:
    """Generate daily/weekly frames for the projected future."""

    frames = []
    ticker_analysis = analysis.get("ticker_analysis", {})

    # Check scenario type from analysis
    growth_multiplier = analysis.get("growth_multiplier", 1.0)
    scenario_note = analysis.get("scenario_note", "").lower()

    # Determine noise bias based on scenario
    noise_bias = 0  # neutral
    if "bear" in scenario_note or "recession" in scenario_note or "crash" in scenario_note:
        noise_bias = -0.01  # Negative bias for bearish scenarios
    elif "bull" in scenario_note or "aggressive" in scenario_note or "growth" in scenario_note:
        noise_bias = 0.005  # Slight positive bias for bullish scenarios

    # Generate monthly frames (more manageable than daily)
    months = years * 12

    for month in range(months + 1):
        frame_date = start_date + timedelta(days=month * 30)
        year_progress = month / 12

        frame_holdings = []
        total_value = 0

        for h in holdings:
            ticker = h["ticker"]
            current_price = h.get("current_price", 0)

            # Skip holdings with no price data
            if current_price <= 0:
                continue

            ta = ticker_analysis.get(ticker, {})
            growth_rates = ta.get("annual_growth_rates", {"base": 10})

            # Use base case with some randomness
            base_growth = growth_rates.get("base", 10)
            pessimistic = growth_rates.get("pessimistic", base_growth - 15)
            optimistic = growth_rates.get("optimistic", base_growth + 15)

            # Add seasonality
            quarter = (frame_date.month - 1) // 3
            seasonality_factors = [1.0, 0.98, 1.0, 1.05]  # Default
            if "seasonality" in ta and isinstance(ta["seasonality"], list):
                seasonality_factors = ta["seasonality"]

            seasonality = seasonality_factors[quarter] if quarter < len(seasonality_factors) else 1.0

            # Calculate projected price with randomness
            annual_growth = base_growth / 100
            # Add noise with scenario-appropriate bias
            noise = random.gauss(noise_bias, 0.015)  # Reduced noise with scenario bias

            # Compound growth
            growth_factor = (1 + annual_growth / 12 + noise) ** month * seasonality
            projected_price = current_price * growth_factor

            # Ensure reasonable bounds - tighter for bearish scenarios
            if noise_bias < 0:
                # Bearish: favor pessimistic bound
                min_price = current_price * (1 + pessimistic / 100) ** year_progress
                max_price = current_price * (1 + base_growth / 100) ** year_progress
            else:
                min_price = current_price * (1 + pessimistic / 100) ** year_progress
                max_price = current_price * (1 + optimistic / 100) ** year_progress

            projected_price = max(min_price * 0.9, min(max_price * 1.1, projected_price))

            holding_value = h["shares"] * projected_price
            total_value += holding_value

            frame_holdings.append({
                "ticker": ticker,
                "shares": h["shares"],
                "price": round(projected_price, 2),
                "value": round(holding_value, 2),
                "change_from_start": round((projected_price / current_price - 1) * 100, 1)
            })

        frames.append({
            "date": frame_date.isoformat()[:10],
            "month": month,
            "year": round(month / 12, 2),
            "total_value": round(total_value, 2),
            "holdings": frame_holdings,
            "is_projection": True
        })

    return frames


def save_projection(projection: dict):
    """Save a projection to disk."""
    ensure_storage()
    filepath = PROJECTIONS_DIR / f"{projection['id']}.json"
    with open(filepath, 'w') as f:
        json.dump(projection, f, indent=2, default=str)


def load_projection(projection_id: str) -> Optional[dict]:
    """Load a projection from disk."""
    filepath = PROJECTIONS_DIR / f"{projection_id}.json"
    if not filepath.exists():
        return None
    with open(filepath) as f:
        return json.load(f)


def list_projections() -> list:
    """List all saved projections."""
    ensure_storage()
    projections = []
    for f in PROJECTIONS_DIR.glob("*.json"):
        try:
            with open(f) as file:
                p = json.load(file)
                projections.append({
                    "id": p.get("id"),
                    "history_id": p.get("history_id"),
                    "created_at": p.get("created_at"),
                    "years": p.get("years"),
                    "end_date": p.get("end_date")
                })
        except:
            pass
    return sorted(projections, key=lambda x: x.get("created_at", ""), reverse=True)


def delete_projection(projection_id: str) -> bool:
    """Delete a projection."""
    filepath = PROJECTIONS_DIR / f"{projection_id}.json"
    if filepath.exists():
        filepath.unlink()
        return True
    return False
