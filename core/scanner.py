"""
Consolidated Options Scanner - Unified module for options chain analysis.

Combines:
- yfinance options chain fetching
- Algorithmic scoring for income opportunities
- LLM-enhanced recommendations with Dexter research
- Self-reflective agent prompts for intelligent analysis

This scanner analyzes options chains for income opportunities based on:
- Theta decay (time value)
- Delta (probability of ITM)
- Premium yield (annualized return on capital)
- Contract sizing and capital requirements
- Fundamental analysis (via Dexter)
- LLM agent reasoning

Uses parallel processing to scan multiple tickers concurrently.
"""

import asyncio
import json
import math
import yfinance as yf
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPT_DIR = Path(__file__).parent.parent.resolve()

# Number of parallel workers for options chain scanning
MAX_WORKERS = 5


# ============================================================================
# Portfolio Data Fetching
# ============================================================================

def get_portfolio_holdings() -> dict:
    """Get current holdings from portfolio state."""
    from reconstruct_state import load_event_log, reconstruct_state
    from api.database import get_cached_prices

    events_df = load_event_log(str(SCRIPT_DIR / 'data' / 'event_log_enhanced.csv'))
    state = reconstruct_state(events_df)

    # Get cached prices
    cached = get_cached_prices()
    for ticker in state.get('holdings', {}):
        if ticker in cached:
            state['latest_prices'][ticker] = cached[ticker]['price']

    holdings = {}
    for ticker, shares in state.get('holdings', {}).items():
        if shares >= 100:  # Need at least 100 shares for covered calls
            price = state.get('latest_prices', {}).get(ticker, 0)
            cost_basis = state.get('cost_basis', {}).get(ticker, {})
            holdings[ticker] = {
                'shares': shares,
                'price': price,
                'avg_cost': cost_basis.get('avg_price', 0),
                'contracts_available': int(shares // 100)
            }

    # Also get available cash for cash-secured puts
    cash = state.get('cash', 0)

    # Get active options to avoid doubling up
    active_options = state.get('active_options', [])
    tickers_with_options = set()
    for opt in active_options:
        tickers_with_options.add(opt.get('ticker'))

    # Get income goal progress
    ytd_income = state.get('ytd_income', 0)
    income_goal = 30000  # TODO: make configurable
    remaining_goal = max(0, income_goal - ytd_income)

    return {
        'holdings': holdings,
        'cash': cash,
        'tickers_with_options': list(tickers_with_options),
        'ytd_income': ytd_income,
        'income_goal': income_goal,
        'remaining_goal': remaining_goal
    }


# ============================================================================
# Options Chain Fetching
# ============================================================================

def fetch_options_chain(ticker: str, max_dte: int = 45) -> list:
    """
    Fetch options chain for a ticker within DTE range.

    Args:
        ticker: Stock ticker symbol
        max_dte: Maximum days to expiration (default 45)

    Returns:
        List of option contract dicts with greeks
    """
    try:
        stock = yf.Ticker(ticker)
        current_price = stock.info.get('regularMarketPrice') or stock.info.get('currentPrice', 0)

        if not current_price:
            # Try to get from history
            hist = stock.history(period='1d')
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]

        if not current_price:
            return []

        # Get expiration dates
        try:
            expirations = stock.options
        except:
            return []

        if not expirations:
            return []

        today = datetime.now().date()
        options = []

        for exp_str in expirations:
            exp_date = datetime.strptime(exp_str, '%Y-%m-%d').date()
            dte = (exp_date - today).days

            # Filter to our DTE range (7-45 days ideal for theta decay)
            if dte < 7 or dte > max_dte:
                continue

            try:
                chain = stock.option_chain(exp_str)
            except:
                continue

            # Process puts (for cash-secured puts)
            for _, row in chain.puts.iterrows():
                strike = row['strike']

                # Only consider OTM puts (strike below current price)
                if strike >= current_price:
                    continue

                # Calculate key metrics
                bid = row.get('bid', 0) or 0
                ask = row.get('ask', 0) or 0
                mid = (bid + ask) / 2 if bid and ask else row.get('lastPrice', 0)

                if mid <= 0:
                    continue

                # Greeks (may not always be available, handle NaN)
                delta = abs(row.get('delta', 0) or 0)
                if math.isnan(delta): delta = 0
                theta = row.get('theta', 0) or 0
                if math.isnan(theta): theta = 0
                iv = row.get('impliedVolatility', 0) or 0
                if math.isnan(iv): iv = 0
                volume = row.get('volume', 0) or 0
                if math.isnan(volume): volume = 0
                open_interest = row.get('openInterest', 0) or 0
                if math.isnan(open_interest): open_interest = 0

                # Calculate premium metrics
                premium_per_contract = mid * 100
                collateral = strike * 100
                premium_yield = (mid / strike) * 100 if strike > 0 else 0
                annualized_yield = (premium_yield / dte * 365) if dte > 0 else 0

                # Distance from current price (safety margin)
                otm_pct = ((current_price - strike) / current_price) * 100

                options.append({
                    'ticker': ticker,
                    'type': 'PUT',
                    'strategy': 'Cash-Secured Put',
                    'expiration': exp_str,
                    'dte': dte,
                    'strike': strike,
                    'current_price': current_price,
                    'bid': bid,
                    'ask': ask,
                    'mid': mid,
                    'premium_per_contract': premium_per_contract,
                    'collateral_required': collateral,
                    'premium_yield_pct': round(premium_yield, 2),
                    'annualized_yield_pct': round(annualized_yield, 1),
                    'otm_pct': round(otm_pct, 1),
                    'delta': round(delta, 3),
                    'theta': round(theta, 4) if theta else None,
                    'iv': round(iv * 100, 1) if iv else None,
                    'volume': int(volume),
                    'open_interest': int(open_interest),
                    'prob_otm': round((1 - delta) * 100, 1) if delta else None
                })

            # Process calls (for covered calls)
            for _, row in chain.calls.iterrows():
                strike = row['strike']

                # Only consider OTM calls (strike above current price)
                if strike <= current_price:
                    continue

                bid = row.get('bid', 0) or 0
                ask = row.get('ask', 0) or 0
                mid = (bid + ask) / 2 if bid and ask else row.get('lastPrice', 0)

                if mid <= 0:
                    continue

                delta = row.get('delta', 0) or 0
                if math.isnan(delta): delta = 0
                theta = row.get('theta', 0) or 0
                if math.isnan(theta): theta = 0
                iv = row.get('impliedVolatility', 0) or 0
                if math.isnan(iv): iv = 0
                volume = row.get('volume', 0) or 0
                if math.isnan(volume): volume = 0
                open_interest = row.get('openInterest', 0) or 0
                if math.isnan(open_interest): open_interest = 0

                premium_per_contract = mid * 100
                premium_yield = (mid / current_price) * 100 if current_price > 0 else 0
                annualized_yield = (premium_yield / dte * 365) if dte > 0 else 0

                # Upside before assignment
                upside_pct = ((strike - current_price) / current_price) * 100

                options.append({
                    'ticker': ticker,
                    'type': 'CALL',
                    'strategy': 'Covered Call',
                    'expiration': exp_str,
                    'dte': dte,
                    'strike': strike,
                    'current_price': current_price,
                    'bid': bid,
                    'ask': ask,
                    'mid': mid,
                    'premium_per_contract': premium_per_contract,
                    'collateral_required': current_price * 100,
                    'premium_yield_pct': round(premium_yield, 2),
                    'annualized_yield_pct': round(annualized_yield, 1),
                    'otm_pct': round(upside_pct, 1),
                    'delta': round(delta, 3),
                    'theta': round(theta, 4) if theta else None,
                    'iv': round(iv * 100, 1) if iv else None,
                    'volume': int(volume),
                    'open_interest': int(open_interest),
                    'prob_otm': round((1 - delta) * 100, 1) if delta else None
                })

        return options

    except Exception as e:
        print(f"Error fetching options for {ticker}: {e}")
        return []


# ============================================================================
# Option Scoring & Analysis
# ============================================================================

def score_option(option: dict, context: dict) -> float:
    """
    Score an option for income generation suitability.

    Higher scores = better candidates for selling.
    Uses continuous scoring for better granularity.

    Factors:
    - Premium yield (annualized) - 40 points max
    - Safety margin (OTM distance) - 25 points max
    - Theta decay rate - 10 points max
    - Probability of profit (delta) - 20 points max
    - DTE sweet spot - 10 points max
    - Liquidity (volume, open interest) - 5 points max

    Total: 110 points max, normalized to 100
    """
    score = 0.0

    # Premium yield (0-40 points) - continuous scoring
    ann_yield = option.get('annualized_yield_pct', 0)
    if ann_yield >= 60:
        score += 40
    elif ann_yield >= 5:
        # Linear scaling from 5% (10 pts) to 60% (40 pts)
        score += 10 + (ann_yield - 5) * (30 / 55)
    else:
        score += ann_yield * 2  # 0-5% gets 0-10 points

    # Safety margin / OTM distance (0-25 points) - continuous
    otm_pct = option.get('otm_pct', 0)
    if option['type'] == 'PUT':
        # For puts, want good cushion below current price
        if otm_pct >= 20:
            score += 25
        elif otm_pct >= 3:
            # Linear scaling from 3% (5 pts) to 20% (25 pts)
            score += 5 + (otm_pct - 3) * (20 / 17)
        else:
            score += otm_pct * (5 / 3)  # 0-3% gets 0-5 points
    else:
        # For calls, want room for upside
        if otm_pct >= 15:
            score += 25
        elif otm_pct >= 3:
            score += 5 + (otm_pct - 3) * (20 / 12)
        else:
            score += otm_pct * (5 / 3)

    # Theta decay bonus (0-10 points) - more theta = faster decay = better
    theta = abs(option.get('theta', 0) or 0)
    if theta > 0:
        # Theta typically ranges from 0.01 to 0.10 for most options
        # Higher theta means faster time decay (good for sellers)
        theta_score = min(10, theta * 100)  # Cap at 10 points
        score += theta_score

    # Delta-based probability (0-20 points) - continuous
    delta = abs(option.get('delta', 0) or 0)
    prob_otm = option.get('prob_otm')
    if prob_otm:
        if prob_otm >= 90:
            score += 20
        elif prob_otm >= 60:
            # Linear scaling from 60% (5 pts) to 90% (20 pts)
            score += 5 + (prob_otm - 60) * (15 / 30)
        else:
            score += max(0, prob_otm - 50) * 0.5  # Below 60% gets minimal points

    # DTE sweet spot (0-10 points) - continuous with peak at 35 days
    dte = option.get('dte', 0)
    # Peak at 35 days, taper off on both sides
    if 28 <= dte <= 42:
        score += 10  # Sweet spot
    elif 21 <= dte < 28:
        score += 7 + (dte - 21) * (3 / 7)  # 7-10 points
    elif 42 < dte <= 50:
        score += 10 - (dte - 42) * (3 / 8)  # 7-10 points
    elif 14 <= dte < 21:
        score += 4 + (dte - 14) * (3 / 7)  # 4-7 points
    elif 7 <= dte < 14:
        score += 2 + (dte - 7) * (2 / 7)  # 2-4 points
    elif dte > 50:
        score += max(0, 7 - (dte - 50) * 0.1)  # Diminishing returns

    # Liquidity (0-5 points) - continuous
    volume = option.get('volume', 0) or 0
    oi = option.get('open_interest', 0) or 0

    # Volume component (0-2.5 points)
    if volume >= 200:
        score += 2.5
    else:
        score += min(2.5, volume / 80)  # Linear up to 200

    # Open interest component (0-2.5 points)
    if oi >= 1000:
        score += 2.5
    else:
        score += min(2.5, oi / 400)  # Linear up to 1000

    # Normalize to 100-point scale (max theoretical is 110)
    normalized_score = min(100, score * (100 / 110))

    return round(normalized_score, 1)


def calculate_contract_recommendation(option: dict, context: dict) -> dict:
    """
    Calculate recommended number of contracts based on risk and goal.

    Returns dict with:
    - suggested_contracts: recommended qty
    - conservative_contracts: low-risk qty
    - aggressive_contracts: higher-risk qty
    - rationale: explanation
    """
    cash = context.get('cash', 0)
    remaining_goal = context.get('remaining_goal', 10000)
    premium_per_contract = option.get('premium_per_contract', 0)
    collateral = option.get('collateral_required', 0)
    delta = abs(option.get('delta', 0) or 0)

    if premium_per_contract <= 0 or collateral <= 0:
        return {
            'suggested_contracts': 1,
            'conservative_contracts': 1,
            'aggressive_contracts': 1,
            'rationale': 'Minimum position'
        }

    # Calculate max contracts by capital
    if option['type'] == 'PUT':
        # For puts, need collateral = strike * 100
        max_by_capital = int(cash * 0.5 / collateral) if collateral > 0 else 1
    else:
        # For calls, need to own shares (contracts_available already set)
        max_by_capital = option.get('contracts_available', 1)

    max_by_capital = max(1, max_by_capital)

    # Calculate contracts needed to hit a meaningful portion of remaining goal
    # Target: each trade contributes 5-10% of remaining goal
    target_premium_low = remaining_goal * 0.03  # 3% of goal = conservative
    target_premium_mid = remaining_goal * 0.05  # 5% of goal = suggested
    target_premium_high = remaining_goal * 0.08  # 8% of goal = aggressive

    contracts_for_low = max(1, int(target_premium_low / premium_per_contract))
    contracts_for_mid = max(1, int(target_premium_mid / premium_per_contract))
    contracts_for_high = max(1, int(target_premium_high / premium_per_contract))

    # Adjust by delta (risk-based)
    # Higher delta = higher assignment risk = fewer contracts
    risk_multiplier = 1.0 - (delta * 0.5)  # 0.30 delta -> 0.85 multiplier
    risk_multiplier = max(0.5, min(1.0, risk_multiplier))

    conservative = min(max_by_capital, max(1, int(contracts_for_low * risk_multiplier)))
    suggested = min(max_by_capital, max(1, int(contracts_for_mid * risk_multiplier)))
    aggressive = min(max_by_capital, contracts_for_high)

    # Build rationale
    if suggested == max_by_capital:
        rationale = f"Limited by {'cash' if option['type'] == 'PUT' else 'shares'} ({max_by_capital} max)"
    elif delta > 0.25:
        rationale = f"Reduced due to higher delta ({delta:.0%} assignment risk)"
    else:
        rationale = f"Based on {5}% of remaining ${remaining_goal:,.0f} goal"

    return {
        'suggested_contracts': suggested,
        'conservative_contracts': conservative,
        'aggressive_contracts': aggressive,
        'max_by_capital': max_by_capital,
        'rationale': rationale
    }


def calculate_break_even(option: dict) -> float:
    """Calculate break-even price for the option seller."""
    strike = option.get('strike', 0)
    mid = option.get('mid', 0)

    if option['type'] == 'PUT':
        # For selling puts: break-even = strike - premium received
        return round(strike - mid, 2)
    else:
        # For selling calls: break-even = strike + premium received
        # (but you keep shares if assigned, so this is where you'd be called away)
        return round(strike + mid, 2)


def scan_ticker_options(ticker: str, max_dte: int, holding_info: dict = None) -> Tuple[str, List[dict], str]:
    """
    Scan a single ticker for options opportunities.

    This is a worker function that can be run in parallel.

    Args:
        ticker: Stock ticker symbol
        max_dte: Maximum days to expiration
        holding_info: Optional holding info (shares, avg_cost) for covered calls

    Returns:
        Tuple of (ticker, options_list, error_message)
    """
    try:
        options = fetch_options_chain(ticker, max_dte)

        if not options:
            return (ticker, [], f"{ticker}: No options data available")

        # Add holding info if provided
        if holding_info:
            for opt in options:
                if opt['type'] == 'CALL':
                    opt['contracts_available'] = holding_info.get('contracts_available', 0)
                    opt['holding_cost_basis'] = holding_info.get('avg_cost', 0)

        return (ticker, options, None)

    except Exception as e:
        return (ticker, [], f"{ticker}: {str(e)}")


def format_recommendation_text(rec: dict) -> str:
    """Format a recommendation for display."""
    lines = [
        f"{rec['ticker']} {rec['strategy']}",
        f"  Strike: ${rec['strike']:.2f} | Exp: {rec['expiration']} ({rec['dte']}d)",
        f"  Premium: ${rec['premium_per_contract']:.0f} | Yield: {rec['annualized_yield_pct']:.1f}% ann.",
        f"  OTM: {rec['otm_pct']:.1f}% | Delta: {rec['delta']:.2f}",
        f"  Score: {rec['score']:.0f}/100"
    ]
    return '\n'.join(lines)


# ============================================================================
# Basic Scanner (Algorithmic)
# ============================================================================

def get_recommendations(
    max_dte: int = 45,
    min_premium: float = 50,
    max_results: int = 10,
    use_llm: bool = False
) -> dict:
    """
    Get options selling recommendations for income generation.

    Uses parallel processing to scan multiple tickers concurrently.

    Args:
        max_dte: Maximum days to expiration
        min_premium: Minimum premium per contract
        max_results: Maximum recommendations to return
        use_llm: Whether to use LLM for enhanced analysis

    Returns:
        Dict with recommendations and analysis
    """
    portfolio = get_portfolio_holdings()
    holdings = portfolio['holdings']
    cash = portfolio['cash']
    remaining_goal = portfolio['remaining_goal']

    # Load idea tags for matching (only from enabled, non-archived ideas)
    idea_tags = set()
    try:
        from api.routes.ideas import get_ideas
        ideas = get_ideas()
        for idea in ideas:
            # Only include tags from enabled and non-archived ideas
            if idea.get('status') != 'archived' and idea.get('enabled', True):
                for tag in idea.get('tags', []):
                    idea_tags.add(tag.upper())
    except Exception:
        pass  # Ideas not available, continue without matching

    all_options = []
    scan_errors = []

    # Prepare scan tasks: each holding gets scanned for both calls and puts
    scan_tasks = []
    for ticker, info in holdings.items():
        scan_tasks.append((ticker, max_dte, info))

    # Run scans in parallel using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all tasks
        future_to_ticker = {
            executor.submit(scan_ticker_options, ticker, max_dte, info): ticker
            for ticker, max_dte_arg, info in [(t[0], t[1], t[2]) for t in scan_tasks]
        }

        # Collect results as they complete
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                ticker, options, error = future.result()

                if error:
                    scan_errors.append(error)
                    continue

                # Get holding info for this ticker
                info = holdings.get(ticker, {})

                # Process calls (covered calls)
                calls = [o for o in options if o['type'] == 'CALL']
                for opt in calls:
                    opt['score'] = score_option(opt, portfolio)
                    if opt['premium_per_contract'] >= min_premium:
                        # Add enhanced metrics
                        opt['break_even'] = calculate_break_even(opt)
                        contract_rec = calculate_contract_recommendation(opt, portfolio)
                        opt['suggested_contracts'] = contract_rec['suggested_contracts']
                        opt['conservative_contracts'] = contract_rec['conservative_contracts']
                        opt['aggressive_contracts'] = contract_rec['aggressive_contracts']
                        opt['max_contracts'] = contract_rec['max_by_capital']
                        opt['contract_rationale'] = contract_rec['rationale']
                        # Assignment risk is delta as percentage
                        opt['assignment_risk_pct'] = round(abs(opt.get('delta', 0) or 0) * 100, 1)
                        # Time decay per day (theta is negative for options, so abs)
                        opt['daily_decay'] = round(abs(opt.get('theta', 0) or 0) * 100, 2)
                        # Check if ticker matches any idea tag
                        opt['matches_idea'] = ticker.upper() in idea_tags
                        all_options.append(opt)

                # Process puts (cash-secured puts)
                puts = [o for o in options if o['type'] == 'PUT']
                for opt in puts:
                    collateral = opt['collateral_required']
                    if collateral > cash * 0.5:
                        continue
                    opt['cash_available'] = cash
                    opt['score'] = score_option(opt, portfolio)
                    if opt['premium_per_contract'] >= min_premium:
                        # Add enhanced metrics
                        opt['break_even'] = calculate_break_even(opt)
                        contract_rec = calculate_contract_recommendation(opt, portfolio)
                        opt['suggested_contracts'] = contract_rec['suggested_contracts']
                        opt['conservative_contracts'] = contract_rec['conservative_contracts']
                        opt['aggressive_contracts'] = contract_rec['aggressive_contracts']
                        opt['max_contracts'] = contract_rec['max_by_capital']
                        opt['contract_rationale'] = contract_rec['rationale']
                        # Assignment risk is delta as percentage
                        opt['assignment_risk_pct'] = round(abs(opt.get('delta', 0) or 0) * 100, 1)
                        # Time decay per day (theta is negative for options, so abs)
                        opt['daily_decay'] = round(abs(opt.get('theta', 0) or 0) * 100, 2)
                        # Check if ticker matches any idea tag
                        opt['matches_idea'] = ticker.upper() in idea_tags
                        all_options.append(opt)

            except Exception as e:
                scan_errors.append(f"{ticker}: Scan failed - {str(e)}")

    # Sort by score descending
    all_options.sort(key=lambda x: x['score'], reverse=True)

    # Take top recommendations
    recommendations = all_options[:max_results]

    # Calculate potential income from top picks
    potential_income = sum(r['premium_per_contract'] for r in recommendations[:5])

    result = {
        'generated_at': datetime.now().isoformat(),
        'portfolio_summary': {
            'holdings_scanned': len(holdings),
            'cash_available': cash,
            'ytd_income': portfolio['ytd_income'],
            'income_goal': portfolio['income_goal'],
            'remaining_goal': remaining_goal
        },
        'recommendations': recommendations,
        'potential_income': potential_income,
        'scan_errors': scan_errors if scan_errors else None,
        'analysis': None
    }

    # Add LLM analysis if requested
    if use_llm and recommendations:
        result['analysis'] = get_llm_analysis(recommendations, portfolio)

    return result


def get_llm_analysis(recommendations: list, portfolio: dict) -> dict:
    """Get LLM-powered analysis of recommendations."""
    try:
        from llm.client import get_llm_response

        # Build context for LLM
        top_picks = recommendations[:5]

        context = f"""
Analyze these options selling opportunities for an income-focused portfolio:

Portfolio Context:
- YTD Income: ${portfolio['ytd_income']:,.0f}
- Income Goal: ${portfolio['income_goal']:,.0f}
- Remaining: ${portfolio['remaining_goal']:,.0f}
- Cash Available: ${portfolio['cash']:,.0f}

Top Recommendations:
"""
        for i, rec in enumerate(top_picks, 1):
            context += f"""
{i}. {rec['ticker']} {rec['type']} ${rec['strike']} exp {rec['expiration']}
   - Strategy: {rec['strategy']}
   - Premium: ${rec['premium_per_contract']:.0f}/contract
   - Annualized Yield: {rec['annualized_yield_pct']:.1f}%
   - OTM Distance: {rec['otm_pct']:.1f}%
   - Delta: {rec['delta']:.3f}
   - DTE: {rec['dte']} days
   - Score: {rec['score']:.0f}/100
"""

        prompt = f"""{context}

Please provide:
1. A brief assessment of the top 2-3 candidates
2. Any risk factors to consider
3. Which opportunities best align with the income goal
4. Suggested position sizing (conservative vs aggressive)

Keep response concise (under 300 words).
"""

        response = get_llm_response(prompt, max_tokens=500)

        return {
            'summary': response,
            'generated_by': 'llm'
        }

    except Exception as e:
        return {
            'summary': f"LLM analysis unavailable: {str(e)}",
            'generated_by': 'error'
        }


# ============================================================================
# Agent-Enhanced Scanner (with Dexter Research)
# ============================================================================

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
