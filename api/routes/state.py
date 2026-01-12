"""Portfolio state routes."""

from fastapi import APIRouter
from datetime import datetime
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from reconstruct_state import load_event_log, reconstruct_state
from api.database import get_cached_prices

# Cache for daily change data (refreshed on price updates)
_daily_change_cache = {}
_daily_change_timestamp = None


def get_daily_changes(tickers: list) -> dict:
    """Get daily change percentages for tickers from yfinance.

    Returns dict of ticker -> {day_change_pct, day_change_value, previous_close}
    """
    global _daily_change_cache, _daily_change_timestamp

    # Check cache freshness (5 minutes)
    now = datetime.now()
    if _daily_change_timestamp and (now - _daily_change_timestamp).seconds < 300:
        # Return cached data if still fresh
        return {t: _daily_change_cache.get(t, {}) for t in tickers}

    try:
        import yfinance as yf

        result = {}
        for ticker in tickers:
            try:
                t = yf.Ticker(ticker)
                info = t.fast_info

                current = info.get('lastPrice', 0)
                previous_close = info.get('previousClose', info.get('regularMarketPreviousClose', 0))

                if previous_close and current:
                    day_change = current - previous_close
                    day_change_pct = (day_change / previous_close) * 100
                    result[ticker] = {
                        'day_change_pct': round(day_change_pct, 2),
                        'day_change_value': round(day_change, 2),
                        'previous_close': round(previous_close, 2)
                    }
                else:
                    result[ticker] = {'day_change_pct': 0, 'day_change_value': 0, 'previous_close': 0}
            except Exception:
                result[ticker] = {'day_change_pct': 0, 'day_change_value': 0, 'previous_close': 0}

        # Update cache
        _daily_change_cache = result
        _daily_change_timestamp = now

        return result
    except Exception:
        return {t: {'day_change_pct': 0, 'day_change_value': 0, 'previous_close': 0} for t in tickers}

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

    # Get tickers for daily change lookup
    tickers = [t for t, s in state.get('holdings', {}).items() if s > 0.01]
    daily_changes = get_daily_changes(tickers)

    for ticker, shares in state.get('holdings', {}).items():
        if shares > 0.01:  # Filter out dust/fractional positions
            price = state.get('latest_prices', {}).get(ticker, 0)
            cost_info = state.get('cost_basis', {}).get(ticker, {})
            market_value = shares * price
            total_cost = cost_info.get('total_cost', 0)
            unrealized_gain = market_value - total_cost
            gain_pct = ((market_value - total_cost) / total_cost * 100) if total_cost > 0 else 0

            # Get daily change data
            day_data = daily_changes.get(ticker, {})
            day_change_pct = day_data.get('day_change_pct', 0)
            day_change_value = day_data.get('day_change_value', 0) * shares  # Total position change

            holdings.append({
                "ticker": ticker,
                "shares": shares,
                "current_price": price,
                "market_value": market_value,
                "cost_basis": total_cost,
                "avg_cost": cost_info.get('avg_price', 0),
                "unrealized_gain": unrealized_gain,
                "unrealized_gain_pct": round(gain_pct, 2),
                "day_change_pct": day_change_pct,
                "day_change_value": round(day_change_value, 2)
            })
            total_holdings_value += market_value

    # Calculate allocation percentages
    for h in holdings:
        h["allocation_pct"] = round((h["market_value"] / total_holdings_value * 100) if total_holdings_value > 0 else 0, 2)

    # Sort by market value descending
    holdings.sort(key=lambda x: x["market_value"], reverse=True)

    # Build active options list with P&L calculation
    active_options = []
    options_to_price = []

    # First pass: collect options info
    for opt in state.get('active_options', []):
        exp_date = datetime.strptime(opt.get('expiration', '2099-12-31'), '%Y-%m-%d')
        days_to_expiry = (exp_date - datetime.now()).days
        premium_received = opt.get('total_premium', opt.get('premium', 0))
        contracts = opt.get('contracts', 1)

        option_info = {
            "event_id": opt.get('event_id', 0),
            "position_id": opt.get('position_id', ''),
            "ticker": opt.get('ticker', ''),
            "strategy": opt.get('strategy', ''),
            "strike": opt.get('strike', 0),
            "expiration": opt.get('expiration', ''),
            "contracts": contracts,
            "premium": premium_received,
            "premium_per_contract": premium_received / contracts if contracts > 0 else 0,
            "days_to_expiry": days_to_expiry,
            # P&L fields (will be updated with live prices)
            "current_price": None,
            "current_value": None,
            "unrealized_pnl": None,
            "unrealized_pnl_pct": None
        }

        options_to_price.append(option_info)
        active_options.append(option_info)

    # Fetch current option prices
    try:
        import yfinance as yf

        for opt in options_to_price:
            try:
                ticker = opt['ticker']
                strike = opt['strike']
                expiration = opt['expiration']
                strategy = opt['strategy'].lower()
                contracts = opt['contracts']
                premium_received = opt['premium']

                # Determine option type
                is_call = 'call' in strategy
                is_put = 'put' in strategy or 'secured' in strategy

                if not (is_call or is_put):
                    continue

                # Get option chain from yfinance
                stock = yf.Ticker(ticker)
                exp_dates = stock.options

                if expiration in exp_dates:
                    opt_chain = stock.option_chain(expiration)

                    if is_call:
                        chain = opt_chain.calls
                    else:
                        chain = opt_chain.puts

                    # Find our strike
                    option_row = chain[chain['strike'] == strike]

                    if not option_row.empty:
                        # Use last price or mid of bid/ask
                        last_price = option_row['lastPrice'].iloc[0]
                        bid = option_row['bid'].iloc[0]
                        ask = option_row['ask'].iloc[0]

                        # Use mid if last price seems stale
                        if bid > 0 and ask > 0:
                            mid = (bid + ask) / 2
                            current_price = mid if last_price == 0 else last_price
                        else:
                            current_price = last_price

                        # Current value = price * 100 * contracts (options are 100 shares each)
                        current_value = current_price * 100 * contracts

                        # For sold options: profit if current_value < premium
                        # (we'd pay less to close than we received)
                        unrealized_pnl = premium_received - current_value
                        unrealized_pnl_pct = (unrealized_pnl / premium_received * 100) if premium_received > 0 else 0

                        opt['current_price'] = round(current_price, 2)
                        opt['current_value'] = round(current_value, 2)
                        opt['unrealized_pnl'] = round(unrealized_pnl, 2)
                        opt['unrealized_pnl_pct'] = round(unrealized_pnl_pct, 2)

            except Exception as e:
                # If we can't get price, leave P&L as None
                pass

    except ImportError:
        # yfinance not available
        pass

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

    # 2. Tax reserve calculation
    # Short-term capital gains (trading gains + options) taxed at 25%
    SHORT_TERM_TAX_RATE = 0.25
    # Qualified dividends taxed at 15%
    DIVIDEND_TAX_RATE = 0.15

    ytd_trading_gains = state.get('ytd_trading_gains', 0)
    ytd_option_income = state.get('ytd_option_income', 0)
    ytd_dividends = state.get('ytd_dividends', 0)

    # Calculate tax on each income type
    trading_tax = max(0, ytd_trading_gains) * SHORT_TERM_TAX_RATE
    option_tax = max(0, ytd_option_income) * SHORT_TERM_TAX_RATE
    dividend_tax = max(0, ytd_dividends) * DIVIDEND_TAX_RATE

    # Total tax reserve
    tax_reserve = trading_tax + option_tax + dividend_tax

    # 3. Available cash (what's actually deployable)
    available_cash = max(0, total_cash - secured_put_collateral - tax_reserve)

    cash_breakdown = {
        "total": total_cash,
        "secured_put_collateral": secured_put_collateral,
        "tax_reserve": tax_reserve,
        "tax_breakdown": {
            "trading_gains": ytd_trading_gains,
            "trading_tax": trading_tax,
            "trading_rate": SHORT_TERM_TAX_RATE,
            "option_income": ytd_option_income,
            "option_tax": option_tax,
            "option_rate": SHORT_TERM_TAX_RATE,
            "dividend_income": ytd_dividends,
            "dividend_tax": dividend_tax,
            "dividend_rate": DIVIDEND_TAX_RATE
        },
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


def calculate_monthly_dividends(transactions: list, year: int) -> dict:
    """Calculate dividend income by month for the given year."""
    from collections import defaultdict

    monthly = defaultdict(float)

    for trans in transactions:
        try:
            date_str = trans.get('date', '')
            if date_str:
                month = int(date_str.split('-')[1])
                monthly[month] += trans.get('amount', 0)
        except (ValueError, IndexError):
            continue

    # Return all 12 months with 0 for missing months
    return {
        "by_month": {i: monthly.get(i, 0) for i in range(1, 13)},
        "monthly_avg": sum(monthly.values()) / max(1, len([m for m in monthly.values() if m > 0])),
        "months_with_dividends": len([m for m in monthly.values() if m > 0])
    }


def project_annual_dividends(transactions: list, year: int) -> dict:
    """Project annual dividend income based on YTD data."""
    from datetime import datetime

    total_ytd = sum(t.get('amount', 0) for t in transactions)
    current_month = datetime.now().month
    current_day = datetime.now().day

    # Calculate days elapsed in year
    days_elapsed = (datetime.now() - datetime(year, 1, 1)).days
    days_in_year = 365

    if days_elapsed > 0:
        daily_rate = total_ytd / days_elapsed
        projected_annual = daily_rate * days_in_year
    else:
        projected_annual = 0

    # Calculate by ticker for recurring dividend estimates
    by_ticker = {}
    for trans in transactions:
        ticker = trans.get('ticker', 'Unknown')
        if ticker not in by_ticker:
            by_ticker[ticker] = {'total': 0, 'count': 0, 'last_amount': 0}
        by_ticker[ticker]['total'] += trans.get('amount', 0)
        by_ticker[ticker]['count'] += 1
        by_ticker[ticker]['last_amount'] = trans.get('amount', 0)

    # Estimate annual per ticker (assuming quarterly dividends)
    ticker_projections = {}
    for ticker, data in by_ticker.items():
        if data['count'] > 0:
            avg_payment = data['total'] / data['count']
            # Most dividends are quarterly (4x/year)
            ticker_projections[ticker] = {
                'ytd': data['total'],
                'count': data['count'],
                'avg_payment': avg_payment,
                'projected_annual': avg_payment * 4  # Assume quarterly
            }

    return {
        "ytd": total_ytd,
        "projected_annual": round(projected_annual, 2),
        "days_elapsed": days_elapsed,
        "daily_rate": round(daily_rate, 2) if days_elapsed > 0 else 0,
        "by_ticker": ticker_projections
    }


@router.get("/income-breakdown")
async def get_income_breakdown(year: int = None):
    """Get detailed income breakdown with individual transactions and tax calculations.

    Args:
        year: Year to filter by (defaults to current year)
    """
    import json
    import pandas as pd

    # Load events
    events_df = load_event_log(str(SCRIPT_DIR / 'data' / 'event_log_enhanced.csv'))
    current_year = year if year else datetime.now().year

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

        # Dividend breakdown with monthly analysis
        "dividends": {
            "transactions": sorted(dividend_transactions, key=lambda x: x['date'], reverse=True),
            "income": dividend_income,
            "tax": dividend_tax,
            "count": len(dividend_transactions),
            "monthly": calculate_monthly_dividends(dividend_transactions, current_year),
            "projected_annual": project_annual_dividends(dividend_transactions, current_year)
        },

        # Totals
        "totals": {
            "gross_income": total_income,
            "total_tax": total_tax,
            "net_after_tax": total_income - total_tax,
            "effective_tax_rate": round((total_tax / total_income * 100) if total_income > 0 else 0, 1)
        }
    }
