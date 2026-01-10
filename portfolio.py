#!/usr/bin/env python3
"""
Portfolio CLI - Manage your financial portfolio from the command line.

Usage:
    python portfolio.py view              # View portfolio summary
    python portfolio.py trade             # Interactive trade entry
    python portfolio.py trade buy TSLA 10 --price 445
    python portfolio.py option            # Interactive option entry
    python portfolio.py option open BMNR put --strike 31 --exp 2026-02-28 --premium 4000
    python portfolio.py cash              # Interactive cash transaction
    python portfolio.py cash deposit 5000
    python portfolio.py prices            # Update stock prices
    python portfolio.py history           # View recent events
"""

import argparse
import sys
from pathlib import Path

# Ensure we can import from the project directory
sys.path.insert(0, str(Path(__file__).parent))

from cli.commands import (
    cmd_view,
    cmd_trade,
    cmd_option,
    cmd_cash,
    cmd_prices,
    cmd_history,
    cmd_config
)


def main():
    parser = argparse.ArgumentParser(
        description='Portfolio CLI - Manage your financial portfolio',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # VIEW command
    view_parser = subparsers.add_parser('view', help='View portfolio summary')
    view_parser.add_argument('--no-prices', action='store_true', help='Skip price fetch')
    view_parser.add_argument('--holdings', action='store_true', help='Show only holdings')
    view_parser.add_argument('--options', action='store_true', help='Show only options')
    view_parser.add_argument('--income', action='store_true', help='Show only income')

    # TRADE command
    trade_parser = subparsers.add_parser('trade', help='Enter a trade')
    trade_parser.add_argument('action', nargs='?', choices=['buy', 'sell'], help='Buy or sell')
    trade_parser.add_argument('ticker', nargs='?', help='Stock ticker')
    trade_parser.add_argument('shares', nargs='?', type=int, help='Number of shares')
    trade_parser.add_argument('--price', type=float, help='Price per share')
    trade_parser.add_argument('--gain', type=float, help='Gain/loss (for sells)')
    trade_parser.add_argument('--reason', help='Reason for trade')
    trade_parser.add_argument('--notes', help='Additional notes')

    # OPTION command
    option_parser = subparsers.add_parser('option', help='Manage options')
    option_subparsers = option_parser.add_subparsers(dest='option_action')

    # option open
    option_open = option_subparsers.add_parser('open', help='Open new option position')
    option_open.add_argument('ticker', nargs='?', help='Underlying ticker')
    option_open.add_argument('type', nargs='?', choices=['put', 'call'], help='Option type')
    option_open.add_argument('--strike', type=float, help='Strike price')
    option_open.add_argument('--exp', help='Expiration date (YYYY-MM-DD)')
    option_open.add_argument('--contracts', type=int, default=1, help='Number of contracts')
    option_open.add_argument('--premium', type=float, help='Total premium received')
    option_open.add_argument('--reason', help='Reason for this trade (required for learning)')

    # option close
    option_close = option_subparsers.add_parser('close', help='Close option position (buy back)')
    option_close.add_argument('event_id', nargs='?', type=int, help='Option event ID')
    option_close.add_argument('--cost', type=float, default=0, help='Cost to buy back (gain = premium - cost)')
    option_close.add_argument('--reason', help='Reason for closing (required for learning)')

    # option expire
    option_expire = option_subparsers.add_parser('expire', help='Option expired worthless (keep full premium)')
    option_expire.add_argument('event_id', nargs='?', type=int, help='Option event ID')
    option_expire.add_argument('--reason', help='Reason/notes about expiration')

    # option assign
    option_assign = option_subparsers.add_parser('assign', help='Option assigned')
    option_assign.add_argument('event_id', nargs='?', type=int, help='Option event ID')
    option_assign.add_argument('--reason', help='Reason/notes about assignment')

    # CASH command
    cash_parser = subparsers.add_parser('cash', help='Cash transactions')
    cash_subparsers = cash_parser.add_subparsers(dest='cash_action')

    # cash deposit
    cash_deposit = cash_subparsers.add_parser('deposit', help='Deposit cash')
    cash_deposit.add_argument('amount', type=float, help='Amount to deposit')
    cash_deposit.add_argument('--source', help='Source of funds')
    cash_deposit.add_argument('--reason', help='Reason for deposit (required for learning)')

    # cash withdraw
    cash_withdraw = cash_subparsers.add_parser('withdraw', help='Withdraw cash')
    cash_withdraw.add_argument('amount', type=float, help='Amount to withdraw')
    cash_withdraw.add_argument('--purpose', help='Purpose of withdrawal')
    cash_withdraw.add_argument('--reason', help='Reason for withdrawal (required for learning)')

    # PRICES command
    prices_parser = subparsers.add_parser('prices', help='Update stock prices')
    prices_parser.add_argument('--show', action='store_true', help='Show prices only, do not save')

    # HISTORY command
    history_parser = subparsers.add_parser('history', help='View event history')
    history_parser.add_argument('--all', action='store_true', help='Show all events')
    history_parser.add_argument('--ticker', help='Filter by ticker')

    # CONFIG command (for LLM settings)
    config_parser = subparsers.add_parser('config', help='Configure LLM settings for AI insights')
    config_subparsers = config_parser.add_subparsers(dest='config_action')

    config_subparsers.add_parser('show', help='Show current LLM configuration')
    config_subparsers.add_parser('enable', help='Enable AI insights')
    config_subparsers.add_parser('disable', help='Disable AI insights')
    config_subparsers.add_parser('test', help='Test LLM connection')

    config_provider = config_subparsers.add_parser('provider', help='Set LLM provider (claude or local)')
    config_provider.add_argument('value', nargs='?', help='Provider: claude or local')

    config_url = config_subparsers.add_parser('url', help='Set local LLM URL')
    config_url.add_argument('value', nargs='?', help='URL (e.g., http://192.168.50.10:1234/v1)')

    config_model = config_subparsers.add_parser('model', help='Set model name')
    config_model.add_argument('value', nargs='?', help='Model name')

    # Parse arguments
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    # Route to command handlers
    if args.command == 'view':
        cmd_view(args)
    elif args.command == 'trade':
        cmd_trade(args)
    elif args.command == 'option':
        cmd_option(args)
    elif args.command == 'cash':
        cmd_cash(args)
    elif args.command == 'prices':
        cmd_prices(args)
    elif args.command == 'history':
        cmd_history(args)
    elif args.command == 'config':
        cmd_config(args)


if __name__ == '__main__':
    main()
