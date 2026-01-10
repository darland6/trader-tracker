#!/usr/bin/env python3
"""
Portfolio Setup Script
======================
Interactive script to create initial event_log_enhanced.csv and starting_state.json
for the portfolio tracker.

Usage:
    python scripts/setup_portfolio.py

This will guide you through:
1. Setting initial cash balance
2. Adding existing stock positions (with cost basis)
3. Adding historical trades
4. Adding historical option trades
"""

import json
import csv
import os
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.parent.resolve()
DATA_DIR = SCRIPT_DIR / 'data'
EVENT_LOG_PATH = DATA_DIR / 'event_log_enhanced.csv'
STARTING_STATE_PATH = DATA_DIR / 'starting_state.json'

# CSV columns
CSV_COLUMNS = [
    'event_id', 'timestamp', 'event_type', 'data_json', 'reason_json',
    'notes', 'tags_json', 'affects_cash', 'cash_delta'
]


def get_input(prompt, default=None, type_fn=str):
    """Get input with optional default value."""
    if default is not None:
        prompt = f"{prompt} [{default}]: "
    else:
        prompt = f"{prompt}: "

    value = input(prompt).strip()
    if not value and default is not None:
        return default

    try:
        return type_fn(value)
    except ValueError:
        print(f"  Invalid input, using default: {default}")
        return default


def get_date_input(prompt, default=None):
    """Get a date input in YYYY-MM-DD format."""
    while True:
        if default:
            date_str = input(f"{prompt} [YYYY-MM-DD, default={default}]: ").strip()
            if not date_str:
                date_str = default
        else:
            date_str = input(f"{prompt} [YYYY-MM-DD]: ").strip()

        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return date_str
        except ValueError:
            print("  Invalid date format. Use YYYY-MM-DD")


def create_event(event_id, timestamp, event_type, data, reason=None, notes="", tags=None, affects_cash=False, cash_delta=0):
    """Create an event dictionary."""
    return {
        'event_id': event_id,
        'timestamp': timestamp,
        'event_type': event_type,
        'data_json': json.dumps(data),
        'reason_json': json.dumps(reason or {}),
        'notes': notes,
        'tags_json': json.dumps(tags or []),
        'affects_cash': affects_cash,
        'cash_delta': cash_delta
    }


def setup_initial_holdings():
    """Interactive setup for initial holdings."""
    print("\n" + "="*60)
    print("INITIAL STOCK HOLDINGS")
    print("="*60)
    print("Enter your existing stock positions.")
    print("These will be set as your starting state (not as trade events).\n")

    holdings = {}

    while True:
        ticker = input("Ticker symbol (or 'done' to finish): ").strip().upper()
        if ticker == 'DONE' or ticker == '':
            break

        shares = get_input(f"  Number of shares for {ticker}", type_fn=float)
        cost_basis = get_input(f"  Total cost basis for {ticker} (what you paid)", type_fn=float)

        holdings[ticker] = {
            'shares': shares,
            'cost_basis_per_share': round(cost_basis / shares, 2) if shares > 0 else 0
        }
        print(f"  Added: {shares} shares of {ticker} @ ${cost_basis/shares:.2f}/share\n")

    return holdings


def setup_initial_cash():
    """Get initial cash balance."""
    print("\n" + "="*60)
    print("INITIAL CASH BALANCE")
    print("="*60)

    cash = get_input("Enter your starting cash balance", default=0, type_fn=float)
    return cash


def setup_historical_trades():
    """Interactive setup for historical trades."""
    print("\n" + "="*60)
    print("HISTORICAL TRADES (Optional)")
    print("="*60)
    print("Enter any historical buy/sell trades you want to record.")
    print("These will be added as TRADE events.\n")

    trades = []

    while True:
        print("-" * 40)
        action = input("Trade type (buy/sell) or 'done' to finish: ").strip().lower()
        if action == 'done' or action == '':
            break

        if action not in ['buy', 'sell']:
            print("  Please enter 'buy' or 'sell'")
            continue

        ticker = input("  Ticker symbol: ").strip().upper()
        if not ticker:
            continue

        date = get_date_input("  Trade date")
        shares = get_input("  Number of shares", type_fn=float)
        price = get_input("  Price per share", type_fn=float)
        total = shares * price

        gain_loss = 0
        if action == 'sell':
            gain_loss = get_input("  Realized gain/loss (0 if unknown)", default=0, type_fn=float)

        notes = input("  Notes (optional): ").strip()

        trades.append({
            'date': date,
            'action': action.upper(),
            'ticker': ticker,
            'shares': shares,
            'price': price,
            'total': total,
            'gain_loss': gain_loss,
            'notes': notes
        })

        print(f"  Added: {action.upper()} {shares} {ticker} @ ${price:.2f} = ${total:,.2f}\n")

    return trades


def setup_historical_options():
    """Interactive setup for historical option trades."""
    print("\n" + "="*60)
    print("HISTORICAL OPTIONS (Optional)")
    print("="*60)
    print("Enter any historical option trades (puts/calls sold).")
    print("These will be added as OPTION_OPEN events.\n")

    options = []

    while True:
        print("-" * 40)
        cont = input("Add an option trade? (yes/no): ").strip().lower()
        if cont != 'yes' and cont != 'y':
            break

        ticker = input("  Ticker symbol: ").strip().upper()
        if not ticker:
            continue

        strategy = input("  Strategy (Secured Put / Covered Call): ").strip()
        if not strategy:
            strategy = "Secured Put"

        date = get_date_input("  Open date")
        expiration = get_date_input("  Expiration date")
        strike = get_input("  Strike price", type_fn=float)
        contracts = get_input("  Number of contracts", default=1, type_fn=int)
        premium = get_input("  Total premium collected", type_fn=float)

        notes = input("  Notes (optional): ").strip()

        options.append({
            'date': date,
            'ticker': ticker,
            'strategy': strategy,
            'strike': strike,
            'expiration': expiration,
            'contracts': contracts,
            'premium': premium,
            'notes': notes
        })

        print(f"  Added: {ticker} ${strike} {strategy} exp {expiration} for ${premium:,.2f}\n")

    return options


def setup_deposits_withdrawals():
    """Interactive setup for cash deposits/withdrawals."""
    print("\n" + "="*60)
    print("DEPOSITS & WITHDRAWALS (Optional)")
    print("="*60)
    print("Enter any historical deposits or withdrawals.\n")

    transactions = []

    while True:
        print("-" * 40)
        trans_type = input("Type (deposit/withdrawal) or 'done' to finish: ").strip().lower()
        if trans_type == 'done' or trans_type == '':
            break

        if trans_type not in ['deposit', 'withdrawal']:
            print("  Please enter 'deposit' or 'withdrawal'")
            continue

        date = get_date_input("  Date")
        amount = get_input("  Amount", type_fn=float)
        source = input("  Source/Purpose: ").strip()

        transactions.append({
            'date': date,
            'type': trans_type.upper(),
            'amount': amount,
            'source': source
        })

        print(f"  Added: {trans_type.upper()} ${amount:,.2f}\n")

    return transactions


def generate_files(cash, holdings, trades, options, deposits):
    """Generate the CSV and JSON files."""

    # Create data directory if needed
    DATA_DIR.mkdir(exist_ok=True)

    # Generate starting_state.json
    starting_state = {
        'cash': cash,
        'initial_holdings': holdings,
        'created_at': datetime.now().isoformat()
    }

    with open(STARTING_STATE_PATH, 'w') as f:
        json.dump(starting_state, f, indent=2)
    print(f"\nCreated: {STARTING_STATE_PATH}")

    # Generate events
    events = []
    event_id = 1

    # Add deposits/withdrawals first (sorted by date)
    for trans in sorted(deposits, key=lambda x: x['date']):
        timestamp = f"{trans['date']} 09:00:00"

        if trans['type'] == 'DEPOSIT':
            data = {'amount': trans['amount'], 'source': trans['source']}
            events.append(create_event(
                event_id, timestamp, 'DEPOSIT', data,
                notes=f"Deposit from {trans['source']}",
                tags=['deposit'],
                affects_cash=True,
                cash_delta=trans['amount']
            ))
        else:
            data = {'amount': trans['amount'], 'purpose': trans['source']}
            events.append(create_event(
                event_id, timestamp, 'WITHDRAWAL', data,
                notes=f"Withdrawal for {trans['source']}",
                tags=['withdrawal'],
                affects_cash=True,
                cash_delta=-trans['amount']
            ))
        event_id += 1

    # Add trades (sorted by date)
    for trade in sorted(trades, key=lambda x: x['date']):
        timestamp = f"{trade['date']} 10:00:00"

        data = {
            'action': trade['action'],
            'ticker': trade['ticker'],
            'shares': trade['shares'],
            'price': trade['price'],
            'total': trade['total'],
            'gain_loss': trade['gain_loss']
        }

        if trade['action'] == 'BUY':
            cash_delta = -trade['total']
        else:
            cash_delta = trade['total']

        events.append(create_event(
            event_id, timestamp, 'TRADE', data,
            reason={'primary': 'INITIAL_SETUP'},
            notes=trade['notes'],
            tags=['trade', trade['ticker'].lower()],
            affects_cash=True,
            cash_delta=cash_delta
        ))
        event_id += 1

    # Add options (sorted by date)
    for opt in sorted(options, key=lambda x: x['date']):
        timestamp = f"{opt['date']} 11:00:00"

        data = {
            'ticker': opt['ticker'],
            'strategy': opt['strategy'],
            'strike': opt['strike'],
            'expiration': opt['expiration'],
            'contracts': opt['contracts'],
            'total_premium': opt['premium'],
            'premium_per_contract': opt['premium'] / opt['contracts'],
            'status': 'OPEN'
        }

        events.append(create_event(
            event_id, timestamp, 'OPTION_OPEN', data,
            reason={'primary': 'INCOME_GENERATION'},
            notes=opt['notes'],
            tags=['options', opt['ticker'].lower()],
            affects_cash=True,
            cash_delta=opt['premium']
        ))
        event_id += 1

    # Sort all events by timestamp
    events.sort(key=lambda x: x['timestamp'])

    # Reassign event IDs after sorting
    for i, event in enumerate(events, 1):
        event['event_id'] = i

    # Write CSV
    with open(EVENT_LOG_PATH, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(events)

    print(f"Created: {EVENT_LOG_PATH}")
    print(f"Total events: {len(events)}")

    return len(events)


def main():
    print("\n" + "="*60)
    print("   PORTFOLIO TRACKER - INITIAL SETUP")
    print("="*60)
    print("\nThis script will help you create the initial portfolio files.")
    print("You can always edit the CSV later or add events through the app.\n")

    # Check for existing files
    if EVENT_LOG_PATH.exists():
        overwrite = input(f"WARNING: {EVENT_LOG_PATH} already exists. Overwrite? (yes/no): ")
        if overwrite.lower() != 'yes':
            print("Aborted. Existing files preserved.")
            return

    # Gather data
    cash = setup_initial_cash()
    holdings = setup_initial_holdings()
    trades = setup_historical_trades()
    options = setup_historical_options()
    deposits = setup_deposits_withdrawals()

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Starting cash: ${cash:,.2f}")
    print(f"Initial holdings: {len(holdings)} positions")
    for ticker, info in holdings.items():
        print(f"  - {ticker}: {info['shares']} shares @ ${info['cost_basis_per_share']:.2f}")
    print(f"Historical trades: {len(trades)}")
    print(f"Historical options: {len(options)}")
    print(f"Deposits/Withdrawals: {len(deposits)}")

    # Confirm
    confirm = input("\nGenerate files with this data? (yes/no): ")
    if confirm.lower() != 'yes':
        print("Aborted.")
        return

    # Generate
    num_events = generate_files(cash, holdings, trades, options, deposits)

    print("\n" + "="*60)
    print("SETUP COMPLETE!")
    print("="*60)
    print(f"\nFiles created:")
    print(f"  - {STARTING_STATE_PATH}")
    print(f"  - {EVENT_LOG_PATH}")
    print(f"\nNext steps:")
    print(f"  1. Start the server: python run_server.py")
    print(f"  2. Open http://localhost:8000/ to view your portfolio")
    print(f"  3. Use 'Update Prices' to fetch current market prices")
    print(f"\nTo add more events, use the web UI or edit the CSV directly.")


if __name__ == '__main__':
    main()
