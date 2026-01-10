"""Alert rule engine for generating notifications."""

import json
from datetime import datetime, timedelta
from pathlib import Path

from api.database import create_notification, get_active_notifications, get_db

SCRIPT_DIR = Path(__file__).parent.parent.parent.resolve()


def check_option_expirations() -> list:
    """
    Check for expiring options and create notifications.
    Returns list of created notification IDs.
    """
    from reconstruct_state import load_event_log, reconstruct_state

    events_df = load_event_log(str(SCRIPT_DIR / 'data' / 'event_log_enhanced.csv'))
    state = reconstruct_state(events_df)

    active_options = state.get('active_options', [])
    created_notifications = []
    today = datetime.now().date()

    # Get existing notifications to avoid duplicates
    existing = get_active_notifications(include_snoozed=True)
    existing_option_ids = {
        n['data'].get('option_event_id')
        for n in existing
        if n['type'] == 'option_expiration'
    }

    for option in active_options:
        option_id = option.get('event_id')
        if option_id in existing_option_ids:
            continue  # Already have notification for this

        expiration_str = option.get('expiration', '')
        if not expiration_str:
            continue

        try:
            exp_date = datetime.strptime(expiration_str, '%Y-%m-%d').date()
        except ValueError:
            continue

        days_to_expiry = (exp_date - today).days
        ticker = option.get('ticker', 'Unknown')
        strike = option.get('strike', 0)
        premium = option.get('total_premium', 0)
        strategy = option.get('strategy', 'option')

        # Determine severity and create notification
        if days_to_expiry < 0:
            # Already expired - urgent
            notification_id = create_notification(
                type='option_expiration',
                title=f'{ticker} ${strike} {strategy} EXPIRED',
                message=f'This option expired on {expiration_str}. Please close or mark as expired.',
                severity='urgent',
                data={
                    'option_event_id': option_id,
                    'ticker': ticker,
                    'strike': strike,
                    'expiration': expiration_str,
                    'premium': premium,
                    'days_to_expiry': days_to_expiry
                },
                action_type='option_action',
                action_data={'option_id': option_id, 'suggested_action': 'expire'}
            )
            created_notifications.append(notification_id)

        elif days_to_expiry <= 1:
            # Expiring tomorrow or today - urgent
            notification_id = create_notification(
                type='option_expiration',
                title=f'{ticker} ${strike} {strategy} expires {"TODAY" if days_to_expiry == 0 else "TOMORROW"}',
                message=f'Premium collected: ${premium:,.0f}. Review position before expiration.',
                severity='urgent',
                data={
                    'option_event_id': option_id,
                    'ticker': ticker,
                    'strike': strike,
                    'expiration': expiration_str,
                    'premium': premium,
                    'days_to_expiry': days_to_expiry
                },
                action_type='option_action',
                action_data={'option_id': option_id, 'suggested_action': 'review'}
            )
            created_notifications.append(notification_id)

        elif days_to_expiry <= 3:
            # 3 days or less - warning
            notification_id = create_notification(
                type='option_expiration',
                title=f'{ticker} ${strike} {strategy} expires in {days_to_expiry} days',
                message=f'Expiration: {expiration_str}. Premium: ${premium:,.0f}. Consider rolling or closing.',
                severity='warning',
                data={
                    'option_event_id': option_id,
                    'ticker': ticker,
                    'strike': strike,
                    'expiration': expiration_str,
                    'premium': premium,
                    'days_to_expiry': days_to_expiry
                },
                action_type='option_action',
                action_data={'option_id': option_id, 'suggested_action': 'roll'}
            )
            created_notifications.append(notification_id)

        elif days_to_expiry <= 7:
            # 1 week warning - info
            notification_id = create_notification(
                type='option_expiration',
                title=f'{ticker} ${strike} {strategy} expires in {days_to_expiry} days',
                message=f'Expiration: {expiration_str}. Start planning exit strategy.',
                severity='info',
                data={
                    'option_event_id': option_id,
                    'ticker': ticker,
                    'strike': strike,
                    'expiration': expiration_str,
                    'premium': premium,
                    'days_to_expiry': days_to_expiry
                },
                action_type='option_action',
                action_data={'option_id': option_id, 'suggested_action': 'monitor'}
            )
            created_notifications.append(notification_id)

    return created_notifications


def check_price_alerts(prices: dict, old_prices: dict, threshold_pct: float = 5.0) -> list:
    """
    Check for significant price movements and create notifications.

    Args:
        prices: Current prices dict {ticker: price}
        old_prices: Previous prices dict {ticker: price}
        threshold_pct: Percentage change threshold for alert

    Returns list of created notification IDs.
    """
    created_notifications = []

    for ticker, new_price in prices.items():
        old_price = old_prices.get(ticker)
        if not old_price or old_price == 0:
            continue

        change_pct = ((new_price - old_price) / old_price) * 100

        if abs(change_pct) >= threshold_pct:
            direction = 'up' if change_pct > 0 else 'down'
            severity = 'warning' if abs(change_pct) >= 10 else 'info'

            notification_id = create_notification(
                type='price_alert',
                title=f'{ticker} {direction} {abs(change_pct):.1f}%',
                message=f'Price moved from ${old_price:.2f} to ${new_price:.2f}',
                severity=severity,
                data={
                    'ticker': ticker,
                    'old_price': old_price,
                    'new_price': new_price,
                    'change_pct': round(change_pct, 2)
                },
                action_type='view_position',
                action_data={'ticker': ticker}
            )
            created_notifications.append(notification_id)

    return created_notifications


def check_portfolio_concentration(threshold_pct: float = 25.0) -> list:
    """
    Check for overconcentrated positions and create notifications.

    Args:
        threshold_pct: Maximum percentage for a single position

    Returns list of created notification IDs.
    """
    from reconstruct_state import load_event_log, reconstruct_state

    events_df = load_event_log(str(SCRIPT_DIR / 'data' / 'event_log_enhanced.csv'))
    state = reconstruct_state(events_df)

    holdings = state.get('holdings', {})
    prices = state.get('latest_prices', {})
    created_notifications = []

    # Calculate total portfolio value (excluding cash)
    total_holdings_value = sum(
        holdings.get(ticker, 0) * prices.get(ticker, 0)
        for ticker in holdings
    )

    if total_holdings_value == 0:
        return []

    # Get existing concentration alerts to avoid duplicates
    existing = get_active_notifications(include_snoozed=True)
    existing_tickers = {
        n['data'].get('ticker')
        for n in existing
        if n['type'] == 'concentration_alert'
    }

    for ticker, shares in holdings.items():
        if shares <= 0 or ticker in existing_tickers:
            continue

        price = prices.get(ticker, 0)
        position_value = shares * price
        concentration = (position_value / total_holdings_value) * 100

        if concentration >= threshold_pct:
            notification_id = create_notification(
                type='concentration_alert',
                title=f'{ticker} is {concentration:.0f}% of portfolio',
                message=f'Position value: ${position_value:,.0f}. Consider rebalancing.',
                severity='warning' if concentration >= 30 else 'info',
                data={
                    'ticker': ticker,
                    'shares': shares,
                    'price': price,
                    'position_value': position_value,
                    'concentration_pct': round(concentration, 1)
                },
                action_type='rebalance',
                action_data={'ticker': ticker, 'current_pct': concentration}
            )
            created_notifications.append(notification_id)

    return created_notifications


def check_income_goal_progress() -> list:
    """
    Check YTD income progress and create milestone notifications.
    """
    from reconstruct_state import load_event_log, reconstruct_state

    events_df = load_event_log(str(SCRIPT_DIR / 'data' / 'event_log_enhanced.csv'))
    state = reconstruct_state(events_df)

    ytd_income = state.get('ytd_option_income', 0) + state.get('ytd_trading_gains', 0)
    annual_goal = 30000  # Could make this configurable

    progress_pct = (ytd_income / annual_goal) * 100 if annual_goal > 0 else 0

    # Check for milestone notifications (25%, 50%, 75%, 100%)
    milestones = [25, 50, 75, 100]
    created_notifications = []

    # Get existing milestone alerts
    existing = get_active_notifications(include_snoozed=True)
    existing_milestones = {
        n['data'].get('milestone')
        for n in existing
        if n['type'] == 'income_milestone'
    }

    for milestone in milestones:
        if progress_pct >= milestone and milestone not in existing_milestones:
            notification_id = create_notification(
                type='income_milestone',
                title=f'Income goal {milestone}% reached!',
                message=f'YTD income: ${ytd_income:,.0f} of ${annual_goal:,.0f} goal.',
                severity='info',
                data={
                    'milestone': milestone,
                    'ytd_income': ytd_income,
                    'annual_goal': annual_goal,
                    'progress_pct': round(progress_pct, 1)
                }
            )
            created_notifications.append(notification_id)

    return created_notifications


def run_all_alert_checks() -> dict:
    """
    Run all alert checks and return summary of created notifications.
    """
    results = {
        'option_expirations': check_option_expirations(),
        'concentration': check_portfolio_concentration(),
        'income_progress': check_income_goal_progress(),
        'total_created': 0
    }

    results['total_created'] = (
        len(results['option_expirations']) +
        len(results['concentration']) +
        len(results['income_progress'])
    )

    return results
