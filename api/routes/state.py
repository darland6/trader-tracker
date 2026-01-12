"""Portfolio state routes."""

from fastapi import APIRouter
from datetime import datetime
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from reconstruct_state import load_event_log, reconstruct_state
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

    # Calculate unrealized gains/losses from holdings
    total_unrealized_gain = 0
    total_unrealized_loss = 0
    for h in holdings:
        if h["unrealized_gain"] >= 0:
            total_unrealized_gain += h["unrealized_gain"]
        else:
            total_unrealized_loss += abs(h["unrealized_gain"])

    # Income breakdown with realized/unrealized separation
    ytd_income = state.get('ytd_income', 0)
    income = {
        # Realized (closed positions)
        "realized_gains": state.get('ytd_realized_gains', 0),
        "realized_losses": state.get('ytd_realized_losses', 0),
        "trading_gains_net": state.get('ytd_trading_gains', 0),  # Net of gains - losses
        # Unrealized (open positions)
        "unrealized_gains": total_unrealized_gain,
        "unrealized_losses": total_unrealized_loss,
        "unrealized_net": total_unrealized_gain - total_unrealized_loss,
        # Other income
        "option_income": state.get('ytd_option_income', 0),
        "dividends": state.get('ytd_dividends', 0),
        # Totals
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


@router.get("/income-breakdown")
async def get_income_breakdown():
    """Get detailed income breakdown with individual transactions and tax calculations."""
    import json
    import pandas as pd

    # Load events
    events_df = load_event_log(str(SCRIPT_DIR / 'data' / 'event_log_enhanced.csv'))
    current_year = datetime.now().year

    # Tax rate for short-term capital gains
    TAX_RATE = 0.25

    # Track individual transactions
    trade_transactions = []
    option_transactions = []
    dividend_transactions = []

    for _, event in events_df.iterrows():
        try:
            event_date = event['timestamp']  # Already datetime from load_event_log
            if event_date.year != current_year:
                continue

            event_type = event['event_type']
            data = event['data']  # Already parsed by load_event_log

            if event_type == 'TRADE' and data.get('action') == 'SELL':
                gain = data.get('gain_loss', 0)
                if gain != 0:
                    trade_transactions.append({
                        'date': event_date.strftime('%Y-%m-%d'),
                        'ticker': data.get('ticker', ''),
                        'shares': data.get('shares', 0),
                        'price': data.get('price', 0),
                        'gain': gain,
                        'type': 'trade'
                    })

            elif event_type == 'OPTION_OPEN':
                action = data.get('action', 'SELL')
                premium = data.get('total_premium', 0)
                # SELL = income, BUY = expense (but we track it when closed)
                if action == 'SELL':
                    option_transactions.append({
                        'date': event_date.strftime('%Y-%m-%d'),
                        'ticker': data.get('ticker', ''),
                        'strategy': data.get('strategy', ''),
                        'strike': data.get('strike', 0),
                        'contracts': data.get('contracts', 0),
                        'gain': premium,
                        'action': 'SELL',
                        'status': 'open',
                        'type': 'option'
                    })

            elif event_type in ['OPTION_CLOSE', 'OPTION_EXPIRE']:
                profit = data.get('profit', 0)
                if profit != 0:
                    option_transactions.append({
                        'date': event_date.strftime('%Y-%m-%d'),
                        'ticker': data.get('ticker', ''),
                        'strategy': data.get('strategy', ''),
                        'gain': profit,
                        'status': 'closed',
                        'type': 'option'
                    })

            elif event_type == 'DIVIDEND':
                amount = data.get('amount', 0)
                if amount > 0:
                    dividend_transactions.append({
                        'date': event_date.strftime('%Y-%m-%d'),
                        'ticker': data.get('ticker', ''),
                        'amount': amount,
                        'type': 'dividend'
                    })

        except Exception:
            continue

    # Calculate totals
    trade_gains = sum(t['gain'] for t in trade_transactions if t['gain'] > 0)
    trade_losses = sum(abs(t['gain']) for t in trade_transactions if t['gain'] < 0)
    trade_net = trade_gains - trade_losses

    option_income = sum(t['gain'] for t in option_transactions)
    dividend_income = sum(t['amount'] for t in dividend_transactions)

    total_income = trade_net + option_income + dividend_income

    # Tax calculations (short-term capital gains rate)
    trade_tax = max(0, trade_net) * TAX_RATE
    option_tax = max(0, option_income) * TAX_RATE
    # Qualified dividends taxed at lower rate, but simplify to same rate
    dividend_tax = dividend_income * 0.15  # Lower rate for qualified dividends
    total_tax = trade_tax + option_tax + dividend_tax

    return {
        "year": current_year,
        "tax_rate": TAX_RATE,
        "dividend_tax_rate": 0.15,

        # Trade breakdown
        "trades": {
            "transactions": sorted(trade_transactions, key=lambda x: x['date'], reverse=True),
            "gains": trade_gains,
            "losses": trade_losses,
            "net": trade_net,
            "tax": trade_tax,
            "count": len(trade_transactions)
        },

        # Option breakdown
        "options": {
            "transactions": sorted(option_transactions, key=lambda x: x['date'], reverse=True),
            "income": option_income,
            "tax": option_tax,
            "count": len(option_transactions)
        },

        # Dividend breakdown
        "dividends": {
            "transactions": sorted(dividend_transactions, key=lambda x: x['date'], reverse=True),
            "income": dividend_income,
            "tax": dividend_tax,
            "count": len(dividend_transactions)
        },

        # Totals
        "totals": {
            "gross_income": total_income,
            "total_tax": total_tax,
            "net_after_tax": total_income - total_tax
        }
    }
