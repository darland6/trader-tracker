"""
Options Scanner Service - Analyzes options chains for income opportunities.

Scans holdings for favorable put/call selling opportunities based on:
- Theta decay (time value)
- Delta (probability of ITM)
- Premium yield (annualized return on capital)
- Contract sizing and capital requirements

Uses parallel processing to scan multiple tickers concurrently.
"""

import yfinance as yf
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import math

SCRIPT_DIR = Path(__file__).parent.parent.parent.resolve()

# Number of parallel workers for options chain scanning
MAX_WORKERS = 5


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
                import math
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
