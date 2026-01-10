"""Portfolio state routes."""

from fastapi import APIRouter
from datetime import datetime
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from reconstruct_state import load_event_log, reconstruct_state
from api.models import PortfolioState, Holding, ActiveOption, IncomeBreakdown
from api.database import get_cached_prices

router = APIRouter(prefix="/api", tags=["state"])

SCRIPT_DIR = Path(__file__).parent.parent.parent.resolve()


def build_portfolio_state() -> dict:
    """Build portfolio state from event log."""
    events_df = load_event_log(str(SCRIPT_DIR / 'data' / 'event_log_enhanced.csv'))
    state = reconstruct_state(events_df)

    # Get cached prices if available
    cached = get_cached_prices()
    for ticker in state.get('holdings', {}):
        if ticker in cached:
            state['latest_prices'][ticker] = cached[ticker]['price']

    return state


@router.get("/state")
async def get_state():
    """Get current portfolio state."""
    state = build_portfolio_state()

    # Build holdings list
    holdings = []
    total_holdings_value = 0

    for ticker, shares in state.get('holdings', {}).items():
        if shares > 0.01:  # Filter out dust/fractional positions
            price = state.get('latest_prices', {}).get(ticker, 0)
            cost_info = state.get('cost_basis', {}).get(ticker, {})
            market_value = shares * price
            total_cost = cost_info.get('total_cost', 0)
            unrealized_gain = market_value - total_cost
            gain_pct = ((market_value - total_cost) / total_cost * 100) if total_cost > 0 else 0

            holdings.append({
                "ticker": ticker,
                "shares": shares,
                "current_price": price,
                "market_value": market_value,
                "cost_basis": total_cost,
                "avg_cost": cost_info.get('avg_price', 0),
                "unrealized_gain": unrealized_gain,
                "unrealized_gain_pct": round(gain_pct, 2)
            })
            total_holdings_value += market_value

    # Calculate allocation percentages
    for h in holdings:
        h["allocation_pct"] = round((h["market_value"] / total_holdings_value * 100) if total_holdings_value > 0 else 0, 2)

    # Sort by market value descending
    holdings.sort(key=lambda x: x["market_value"], reverse=True)

    # Build active options list
    active_options = []
    for opt in state.get('active_options', []):
        exp_date = datetime.strptime(opt.get('expiration', '2099-12-31'), '%Y-%m-%d')
        days_to_expiry = (exp_date - datetime.now()).days

        active_options.append({
            "event_id": opt.get('event_id', 0),
            "position_id": opt.get('position_id', ''),
            "ticker": opt.get('ticker', ''),
            "strategy": opt.get('strategy', ''),
            "strike": opt.get('strike', 0),
            "expiration": opt.get('expiration', ''),
            "contracts": opt.get('contracts', 1),
            "premium": opt.get('total_premium', opt.get('premium', 0)),
            "days_to_expiry": days_to_expiry
        })

    # Calculate totals
    portfolio_value = sum(h["market_value"] for h in holdings)
    cash = state.get('cash', 0)
    total_value = portfolio_value + cash

    # Income breakdown
    ytd_income = state.get('ytd_income', 0)
    income = {
        "trading_gains": state.get('ytd_trading_gains', 0),
        "option_income": state.get('ytd_option_income', 0),
        "dividends": state.get('ytd_dividends', 0),
        "total": ytd_income,
        "goal": 30000,
        "progress_pct": round((ytd_income / 30000) * 100, 1) if ytd_income else 0
    }

    # Calculate cash breakdown
    total_cash = cash

    # 1. Secured put collateral (strike * 100 * contracts for each put)
    secured_put_collateral = 0
    for opt in state.get('active_options', []):
        strategy = opt.get('strategy', '').lower()
        if 'put' in strategy or 'secured' in strategy:
            strike = opt.get('strike', 0)
            contracts = opt.get('contracts', 1)
            secured_put_collateral += strike * 100 * contracts

    # 2. Short-term capital gains tax reserve
    # Calculate estimated taxes on YTD realized gains at 25% rate
    SHORT_TERM_TAX_RATE = 0.25
    ytd_realized_gains = state.get('ytd_trading_gains', 0) + state.get('ytd_option_income', 0)
    # Only reserve for gains (not losses)
    tax_reserve = max(0, ytd_realized_gains * SHORT_TERM_TAX_RATE)

    # 3. Available cash (what's actually deployable)
    available_cash = max(0, total_cash - secured_put_collateral - tax_reserve)

    cash_breakdown = {
        "total": total_cash,
        "secured_put_collateral": secured_put_collateral,
        "tax_reserve": tax_reserve,
        "tax_rate": SHORT_TERM_TAX_RATE,
        "ytd_realized_gains": ytd_realized_gains,
        "available": available_cash,
        "allocated_pct": round(((secured_put_collateral + tax_reserve) / total_cash * 100) if total_cash > 0 else 0, 1)
    }

    return {
        "as_of": datetime.now().isoformat(),
        "cash": cash,
        "cash_breakdown": cash_breakdown,
        "portfolio_value": portfolio_value,
        "total_value": total_value,
        "holdings": holdings,
        "active_options": active_options,
        "income": income,
        "events_processed": state.get('events_processed', 0)
    }


@router.get("/summary")
async def get_summary():
    """Get quick portfolio summary."""
    state = build_portfolio_state()

    holdings_value = sum(
        shares * state.get('latest_prices', {}).get(ticker, 0)
        for ticker, shares in state.get('holdings', {}).items()
        if shares > 0
    )

    return {
        "cash": state.get('cash', 0),
        "holdings_value": holdings_value,
        "total_value": holdings_value + state.get('cash', 0),
        "ytd_income": state.get('ytd_income', 0),
        "active_options_count": len(state.get('active_options', []))
    }
