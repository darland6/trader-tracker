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
    """Setup historical trades from CSV files or manual input."""
    print("\n" + "="*60)
    print("HISTORICAL TRADES")
    print("="*60)
    print("Import options:")
    print("  1. Directory of ticker-named CSVs (e.g., TSLA.csv, META.csv)")
    print("  2. Single CSV file with all trades")
    print("  3. Manual entry")
    print()

    trades = []

    choice = input("Import method (1=directory, 2=single file, 3=manual, Enter=skip): ").strip()

    if choice == '1':
        # Batch import from directory
        dir_path = input("Path to directory with CSV files: ").strip()
        if dir_path:
            dir_path = Path(dir_path).expanduser()
            if dir_path.is_dir():
                trades.extend(import_trades_from_directory(dir_path))
            else:
                print(f"  Not a valid directory: {dir_path}")

    elif choice == '2':
        # Single CSV file
        csv_path = input("Path to trades CSV file: ").strip()
        if csv_path:
            csv_path = Path(csv_path).expanduser()
            if csv_path.exists():
                trades.extend(import_trades_from_csv(csv_path))
                print(f"\nImported {len(trades)} trades from CSV")
            else:
                print(f"  File not found: {csv_path}")

    elif choice == '3':
        trades.extend(manual_trade_input())

    # Option to add more manually after import
    if choice in ['1', '2'] and trades:
        add_manual = input("\nAdd more trades manually? (yes/no): ").strip().lower()
        if add_manual in ['yes', 'y']:
            trades.extend(manual_trade_input())

    return trades


def import_trades_from_directory(dir_path):
    """Batch import trades from a directory of ticker-named CSV files."""
    trades = []
    csv_files = sorted(dir_path.glob('*.csv'))

    if not csv_files:
        print(f"  No CSV files found in {dir_path}")
        return trades

    print(f"\nFound {len(csv_files)} CSV files:")
    for f in csv_files:
        print(f"  - {f.name}")
    print()

    for csv_file in csv_files:
        ticker = csv_file.stem.upper()  # Filename without extension
        print(f"Processing {ticker}...")
        file_trades = import_trades_from_csv(csv_file, ticker_override=ticker)
        trades.extend(file_trades)
        print(f"  → {len(file_trades)} trades for {ticker}\n")

    print(f"Total imported: {len(trades)} trades")
    return trades


def import_trades_from_csv(csv_path, ticker_override=None):
    """Import trades from a CSV file.

    Args:
        csv_path: Path to the CSV file
        ticker_override: If provided, use this ticker for all rows (for ticker-named files)
    """
    trades = []

    with open(csv_path, 'r') as f:
        content = f.read()

    # Detect Schwab lot export format (has "Lot Details" in first line)
    if 'Lot Details' in content:
        return schwab_csv_adapter(csv_path, ticker_override)

    with open(csv_path, 'r') as f:
        # Try to detect if there's a header
        first_line = f.readline().strip()
        f.seek(0)

        # Check if first line looks like a header
        has_header = any(h in first_line.lower() for h in ['date', 'ticker', 'action', 'shares', 'price', 'quantity'])

        reader = csv.DictReader(f) if has_header else None

        if reader:
            # CSV with headers
            for row in reader:
                trade = parse_trade_row(row, ticker_override=ticker_override)
                if trade:
                    trades.append(trade)
                    print(f"  Imported: {trade['action']} {trade['shares']} {trade['ticker']} @ ${trade['price']:.2f}")
        else:
            # CSV without headers
            # If ticker_override: assume date,action,shares,price[,total][,gain_loss][,notes]
            # Otherwise: assume date,action,ticker,shares,price[,total][,gain_loss][,notes]
            f.seek(0)
            reader = csv.reader(f)
            for row in reader:
                if not row or not row[0].strip():
                    continue

                try:
                    if ticker_override:
                        # Format: date,action,shares,price[,total][,gain_loss][,notes]
                        if len(row) >= 4:
                            shares = float(row[2])
                            price = float(row[3])
                            trade = {
                                'date': row[0].strip(),
                                'action': row[1].strip().upper(),
                                'ticker': ticker_override,
                                'shares': shares,
                                'price': price,
                                'total': float(row[4]) if len(row) > 4 and row[4] else shares * price,
                                'gain_loss': float(row[5]) if len(row) > 5 and row[5] else 0,
                                'notes': row[6].strip() if len(row) > 6 else ''
                            }
                            trades.append(trade)
                            print(f"  Imported: {trade['action']} {trade['shares']} {trade['ticker']} @ ${trade['price']:.2f}")
                    else:
                        # Format: date,action,ticker,shares,price[,total][,gain_loss][,notes]
                        if len(row) >= 5:
                            shares = float(row[3])
                            price = float(row[4])
                            trade = {
                                'date': row[0].strip(),
                                'action': row[1].strip().upper(),
                                'ticker': row[2].strip().upper(),
                                'shares': shares,
                                'price': price,
                                'total': float(row[5]) if len(row) > 5 and row[5] else shares * price,
                                'gain_loss': float(row[6]) if len(row) > 6 and row[6] else 0,
                                'notes': row[7].strip() if len(row) > 7 else ''
                            }
                            trades.append(trade)
                            print(f"  Imported: {trade['action']} {trade['shares']} {trade['ticker']} @ ${trade['price']:.2f}")
                except (ValueError, IndexError) as e:
                    print(f"  Warning: Could not parse row: {row} - {e}")

    return trades


def schwab_transaction_history_adapter(csv_path):
    """Import from Schwab transaction history export format.

    This is the complete transaction history from Schwab with columns:
    "Date","Action","Symbol","Description","Quantity","Price","Fees & Comm","Amount"

    Handles:
    - Buy/Sell trades
    - MoneyLink Transfer (deposits)
    - Qualified Dividend / Non-Qualified Dividend / Reinvest Dividend
    - Bank Interest
    - Sell to Open / Buy to Close / Sell to Close / Buy to Open (options)
    - Expired options
    - Stock Plan Activity (RSU vesting)
    - Journal entries
    """
    import re
    import uuid

    events = []
    option_positions = {}  # Track open option positions by symbol

    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Reverse to process chronologically (oldest first)
    rows = rows[::-1]

    for row in rows:
        date_str = row.get('Date', '').strip()
        action = row.get('Action', '').strip()
        symbol = row.get('Symbol', '').strip()
        description = row.get('Description', '').strip()
        quantity_str = row.get('Quantity', '').strip().replace(',', '')
        price_str = row.get('Price', '').strip().replace('$', '').replace(',', '')
        fees_str = row.get('Fees & Comm', '').strip().replace('$', '').replace(',', '')
        amount_str = row.get('Amount', '').strip().replace('$', '').replace(',', '')

        # Parse date (handle "MM/DD/YYYY as of MM/DD/YYYY" format)
        if ' as of ' in date_str:
            date_str = date_str.split(' as of ')[0]

        # Convert MM/DD/YYYY to YYYY-MM-DD
        if '/' in date_str:
            parts = date_str.split('/')
            if len(parts) == 3:
                date_str = f"{parts[2]}-{parts[0].zfill(2)}-{parts[1].zfill(2)}"

        timestamp = f"{date_str} 10:00:00"

        # Parse numeric values
        quantity = float(quantity_str) if quantity_str else 0
        price = float(price_str) if price_str else 0
        fees = float(fees_str) if fees_str else 0
        amount = float(amount_str) if amount_str else 0

        event = None

        # Handle different action types
        if action == 'Buy':
            # Stock purchase
            event = {
                'event_type': 'TRADE',
                'timestamp': timestamp,
                'data': {
                    'action': 'BUY',
                    'ticker': symbol,
                    'shares': quantity,
                    'price': price,
                    'total': abs(amount),
                    'fees': fees,
                    'gain_loss': 0
                },
                'affects_cash': True,
                'cash_delta': amount,  # Negative for buys
                'notes': description
            }

        elif action == 'Sell':
            # Stock sale
            event = {
                'event_type': 'TRADE',
                'timestamp': timestamp,
                'data': {
                    'action': 'SELL',
                    'ticker': symbol,
                    'shares': quantity,
                    'price': price,
                    'total': abs(amount),
                    'fees': fees,
                    'gain_loss': 0  # We don't have cost basis info
                },
                'affects_cash': True,
                'cash_delta': amount,  # Positive for sells
                'notes': description
            }

        elif action == 'MoneyLink Transfer':
            # Deposit
            event = {
                'event_type': 'DEPOSIT',
                'timestamp': timestamp,
                'data': {
                    'amount': amount,
                    'source': description
                },
                'affects_cash': True,
                'cash_delta': amount,
                'notes': description
            }

        elif action in ('Qualified Dividend', 'Non-Qualified Div', 'Reinvest Dividend'):
            # Dividend
            event = {
                'event_type': 'DIVIDEND',
                'timestamp': timestamp,
                'data': {
                    'ticker': symbol,
                    'amount': amount,
                    'dividend_type': action
                },
                'affects_cash': True,
                'cash_delta': amount,
                'notes': f"{action}: {description}"
            }

        elif action == 'Bank Interest':
            # Bank interest (treat as dividend-like income)
            event = {
                'event_type': 'DIVIDEND',
                'timestamp': timestamp,
                'data': {
                    'ticker': 'CASH',
                    'amount': amount,
                    'dividend_type': 'Bank Interest'
                },
                'affects_cash': True,
                'cash_delta': amount,
                'notes': description
            }

        elif action == 'Sell to Open':
            # Option opened (sold)
            # Parse option symbol: "BMNR 01/30/2026 31.00 P"
            opt_uuid = str(uuid.uuid4())[:8]

            # Extract option details from symbol
            opt_match = re.match(r'(\w+)\s+(\d{2}/\d{2}/\d{4})\s+([\d.]+)\s+([PC])', symbol)
            if opt_match:
                opt_ticker = opt_match.group(1)
                opt_exp = opt_match.group(2)
                opt_strike = float(opt_match.group(3))
                opt_type = 'Put' if opt_match.group(4) == 'P' else 'Call'

                # Convert expiration date
                exp_parts = opt_exp.split('/')
                opt_exp = f"{exp_parts[2]}-{exp_parts[0].zfill(2)}-{exp_parts[1].zfill(2)}"

                strategy = 'Secured Put' if opt_type == 'Put' else 'Covered Call'

                event = {
                    'event_type': 'OPTION_OPEN',
                    'timestamp': timestamp,
                    'data': {
                        'ticker': opt_ticker,
                        'strategy': strategy,
                        'strike': opt_strike,
                        'expiration': opt_exp,
                        'contracts': int(quantity),
                        'total_premium': amount,
                        'premium_per_contract': amount / quantity if quantity else 0,
                        'uuid': opt_uuid,
                        'status': 'OPEN'
                    },
                    'affects_cash': True,
                    'cash_delta': amount,
                    'notes': description
                }

                # Track position
                option_positions[symbol] = opt_uuid

        elif action == 'Buy to Close':
            # Option closed (bought back)
            opt_uuid = option_positions.get(symbol, str(uuid.uuid4())[:8])

            event = {
                'event_type': 'OPTION_CLOSE',
                'timestamp': timestamp,
                'data': {
                    'uuid': opt_uuid,
                    'close_cost': abs(amount),
                    'gain': 0,  # Would need original premium to calculate
                    'contracts': int(quantity)
                },
                'affects_cash': True,
                'cash_delta': amount,  # Negative (buying back)
                'notes': description
            }

        elif action == 'Sell to Close':
            # Option sold to close (bought option being sold)
            event = {
                'event_type': 'OPTION_CLOSE',
                'timestamp': timestamp,
                'data': {
                    'uuid': str(uuid.uuid4())[:8],
                    'close_proceeds': amount,
                    'contracts': int(quantity)
                },
                'affects_cash': True,
                'cash_delta': amount,
                'notes': description
            }

        elif action == 'Buy to Open':
            # Option bought (long position opened)
            # Parse option symbol: "BMNR 01/30/2026 31.00 P"
            opt_match = re.match(r'(\w+)\s+(\d{2}/\d{2}/\d{4})\s+([\d.]+)\s+([PC])', symbol)
            if opt_match:
                opt_ticker = opt_match.group(1)
                opt_exp = opt_match.group(2)
                opt_strike = float(opt_match.group(3))
                opt_type = 'Put' if opt_match.group(4) == 'P' else 'Call'

                # Convert expiration date
                exp_parts = opt_exp.split('/')
                opt_exp = f"{exp_parts[2]}-{exp_parts[0].zfill(2)}-{exp_parts[1].zfill(2)}"

                strategy = f'Long {opt_type}'

                event = {
                    'event_type': 'OPTION_OPEN',
                    'timestamp': timestamp,
                    'data': {
                        'ticker': opt_ticker,
                        'strategy': strategy,
                        'strike': opt_strike,
                        'expiration': opt_exp,
                        'contracts': int(quantity),
                        'total_premium': abs(amount),
                        'uuid': str(uuid.uuid4())[:8],
                        'status': 'OPEN'
                    },
                    'affects_cash': True,
                    'cash_delta': amount,  # Negative
                    'notes': description
                }

        elif action == 'Expired':
            # Option expired
            opt_uuid = option_positions.get(symbol, str(uuid.uuid4())[:8])

            event = {
                'event_type': 'OPTION_EXPIRE',
                'timestamp': timestamp,
                'data': {
                    'uuid': opt_uuid,
                    'contracts': int(quantity) if quantity else 0
                },
                'affects_cash': False,
                'cash_delta': 0,
                'notes': f"Expired: {symbol} - {description}"
            }

        elif action == 'Stock Plan Activity':
            # RSU vesting - creates shares (like a buy at $0 from employer)
            if quantity > 0:
                event = {
                    'event_type': 'TRADE',
                    'timestamp': timestamp,
                    'data': {
                        'action': 'BUY',
                        'ticker': symbol,
                        'shares': quantity,
                        'price': 0,
                        'total': 0,
                        'gain_loss': 0,
                        'source': 'RSU_VEST'
                    },
                    'affects_cash': False,
                    'cash_delta': 0,
                    'notes': f"RSU Vest: {description}"
                }

        elif action == 'Journal':
            # Journal entries (tax withholding, transfers, etc.)
            if amount != 0:
                event = {
                    'event_type': 'ADJUSTMENT',
                    'timestamp': timestamp,
                    'data': {
                        'amount': amount,
                        'type': 'journal'
                    },
                    'affects_cash': True,
                    'cash_delta': amount,
                    'notes': description
                }

        elif action == 'Wire Funds Received':
            # Wire transfer (deposit)
            event = {
                'event_type': 'DEPOSIT',
                'timestamp': timestamp,
                'data': {
                    'amount': amount,
                    'source': f"Wire: {description}"
                },
                'affects_cash': True,
                'cash_delta': amount,
                'notes': description
            }

        # Add event if created
        if event:
            events.append(event)

    return events


def schwab_csv_adapter(csv_path, ticker_override=None):
    """Import from Schwab lot details export format.

    Schwab exports lot details in CSV format with:
    - First row: "TICKER Lot Details for..." title
    - Header row with: Open Date, [Transaction Open], Quantity, Price, Cost/Share, etc.
    - Data rows for each lot
    - Total row at the end
    """
    trades = []

    with open(csv_path, 'r') as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        return trades

    # Extract ticker from first row if not overridden (format: "BMNR Lot Details for...")
    ticker = ticker_override
    if not ticker and rows[0]:
        first_cell = rows[0][0]
        if 'Lot Details' in first_cell:
            ticker = first_cell.split()[0].upper()

    if not ticker:
        print(f"  Could not determine ticker for {csv_path}")
        return trades

    # Find header row (contains "Open Date" and "Quantity")
    header_idx = None
    for i, row in enumerate(rows):
        if row and 'Open Date' in row[0] and any('Quantity' in str(c) for c in row):
            header_idx = i
            break

    if header_idx is None:
        print(f"  Could not find header row in {csv_path}")
        return trades

    # Map column indices
    header = rows[header_idx]
    col_map = {}
    for i, col in enumerate(header):
        col_lower = col.lower().strip()
        if 'open date' in col_lower:
            col_map['date'] = i
        elif col_lower == 'quantity':
            col_map['quantity'] = i
        elif 'cost/share' in col_lower or 'cost per share' in col_lower:
            col_map['cost_share'] = i
        elif 'cost basis' in col_lower and 'transaction' not in col_lower:
            col_map['cost_basis'] = i

    if 'date' not in col_map or 'quantity' not in col_map:
        print(f"  Missing required columns in {csv_path}")
        return trades

    # Parse data rows
    for row in rows[header_idx + 1:]:
        if not row or not row[0].strip():
            continue

        # Skip total row
        if row[0].strip().lower() == 'total':
            continue

        try:
            date_str = row[col_map['date']].strip()
            quantity_str = row[col_map['quantity']].strip().replace(',', '')

            # Skip if not a valid date
            if not date_str or date_str == '--':
                continue

            quantity = float(quantity_str)
            if quantity <= 0:
                continue

            # Get cost per share (preferred) or calculate from cost basis
            if 'cost_share' in col_map:
                cost_str = row[col_map['cost_share']].strip().replace('$', '').replace(',', '')
                price = float(cost_str)
            elif 'cost_basis' in col_map:
                cost_basis_str = row[col_map['cost_basis']].strip().replace('$', '').replace(',', '')
                cost_basis = float(cost_basis_str)
                price = cost_basis / quantity
            else:
                print(f"  Skipping row - no price data: {row}")
                continue

            # Convert date format MM/DD/YYYY to YYYY-MM-DD
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    date_str = f"{parts[2]}-{parts[0].zfill(2)}-{parts[1].zfill(2)}"

            trade = {
                'date': date_str,
                'action': 'BUY',
                'ticker': ticker,
                'shares': quantity,
                'price': round(price, 2),
                'total': round(quantity * price, 2),
                'gain_loss': 0,
                'notes': 'Imported from brokerage lot export'
            }
            trades.append(trade)
            print(f"  Imported: BUY {quantity} {ticker} @ ${price:.2f} on {date_str}")

        except (ValueError, IndexError, KeyError) as e:
            # Skip rows that can't be parsed (empty rows, headers, etc.)
            continue

    return trades


def parse_trade_row(row, ticker_override=None):
    """Parse a trade row from CSV with headers.

    Args:
        row: CSV row as dict
        ticker_override: If provided, use this ticker instead of reading from row
    """
    try:
        # Normalize column names (handle various formats)
        normalized = {k.lower().strip().replace(' ', '_'): v for k, v in row.items()}

        date = normalized.get('date', normalized.get('trade_date', ''))
        action = normalized.get('action', normalized.get('type', normalized.get('side', ''))).upper()
        ticker = ticker_override or normalized.get('ticker', normalized.get('symbol', '')).upper()
        shares = float(normalized.get('shares', normalized.get('quantity', normalized.get('qty', 0))))
        price = float(normalized.get('price', normalized.get('price_per_share', normalized.get('avg_price', 0))))

        # Optional fields
        total = normalized.get('total', normalized.get('amount', normalized.get('cost_basis', '')))
        total = float(total) if total else shares * price

        gain_loss = normalized.get('gain_loss', normalized.get('gain', normalized.get('realized_gain', 0)))
        gain_loss = float(gain_loss) if gain_loss else 0

        notes = normalized.get('notes', normalized.get('description', normalized.get('memo', '')))

        if date and action and ticker and shares:
            return {
                'date': date,
                'action': action,
                'ticker': ticker,
                'shares': shares,
                'price': price,
                'total': total,
                'gain_loss': gain_loss,
                'notes': notes
            }
    except (ValueError, KeyError) as e:
        print(f"  Warning: Could not parse row: {row} - {e}")

    return None


def manual_trade_input():
    """Manually input trades."""
    trades = []

    print("\nEnter trades manually (type 'done' when finished):\n")

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


def quick_import(file_paths, output_csv=None):
    """Quick import from multiple CSV files.

    Args:
        file_paths: List of CSV file paths to import
        output_csv: Output path for combined events (default: data/event_log_enhanced.csv)
    """
    import sys

    all_trades = []

    for path in file_paths:
        path = Path(path).expanduser()
        if not path.exists():
            print(f"File not found: {path}")
            continue

        print(f"\n=== Importing {path.name} ===")
        trades = import_trades_from_csv(path)
        all_trades.extend(trades)

    if not all_trades:
        print("\nNo trades imported.")
        return

    # Sort by date
    all_trades.sort(key=lambda x: x['date'])

    # Generate events
    events = []
    for i, trade in enumerate(all_trades, 1):
        timestamp = f"{trade['date']} 10:00:00"

        data = {
            'action': trade['action'],
            'ticker': trade['ticker'],
            'shares': trade['shares'],
            'price': trade['price'],
            'total': trade['total'],
            'gain_loss': trade['gain_loss']
        }

        cash_delta = -trade['total'] if trade['action'] == 'BUY' else trade['total']

        events.append(create_event(
            i, timestamp, 'TRADE', data,
            reason={'primary': 'INITIAL_SETUP'},
            notes=trade.get('notes', ''),
            tags=['trade', trade['ticker'].lower()],
            affects_cash=True,
            cash_delta=cash_delta
        ))

    # Write to CSV
    output_path = Path(output_csv) if output_csv else EVENT_LOG_PATH
    output_path.parent.mkdir(exist_ok=True)

    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(events)

    print(f"\n{'='*60}")
    print(f"Imported {len(all_trades)} trades as {len(events)} events")
    print(f"Output: {output_path}")

    # Summary by ticker
    by_ticker = {}
    for t in all_trades:
        ticker = t['ticker']
        if ticker not in by_ticker:
            by_ticker[ticker] = {'count': 0, 'shares': 0, 'total': 0}
        by_ticker[ticker]['count'] += 1
        by_ticker[ticker]['shares'] += t['shares']
        by_ticker[ticker]['total'] += t['total']

    print(f"\nSummary:")
    for ticker, data in sorted(by_ticker.items()):
        print(f"  {ticker}: {data['count']} lots, {data['shares']:.0f} shares, ${data['total']:,.2f}")


def rebuild_from_schwab_history(csv_path, output_csv=None):
    """Rebuild event log from Schwab complete transaction history.

    Args:
        csv_path: Path to Schwab transaction history CSV
        output_csv: Output path for events (default: data/event_log_enhanced.csv)
    """
    from pathlib import Path

    csv_path = Path(csv_path).expanduser()
    if not csv_path.exists():
        print(f"File not found: {csv_path}")
        return

    print(f"\n=== Importing Schwab Transaction History ===")
    print(f"Source: {csv_path}")

    # Parse all transactions
    events = schwab_transaction_history_adapter(str(csv_path))

    if not events:
        print("\nNo events imported.")
        return

    # Sort by timestamp
    events.sort(key=lambda x: x['timestamp'])

    # Convert to CSV format
    csv_events = []
    for i, event in enumerate(events, 1):
        csv_events.append(create_event(
            event_id=i,
            timestamp=event['timestamp'],
            event_type=event['event_type'],
            data=event['data'],
            reason={'primary': 'IMPORTED_FROM_BROKERAGE'},
            notes=event.get('notes', ''),
            tags=[event['event_type'].lower()],
            affects_cash=event.get('affects_cash', False),
            cash_delta=event.get('cash_delta', 0)
        ))

    # Write to CSV
    output_path = Path(output_csv) if output_csv else EVENT_LOG_PATH
    output_path.parent.mkdir(exist_ok=True)

    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(csv_events)

    print(f"\nOutput: {output_path}")
    print(f"Total events: {len(csv_events)}")

    # Summary by event type
    by_type = {}
    for e in events:
        t = e['event_type']
        if t not in by_type:
            by_type[t] = {'count': 0, 'cash': 0}
        by_type[t]['count'] += 1
        by_type[t]['cash'] += e.get('cash_delta', 0)

    print(f"\n{'Event Type':<20} {'Count':>8} {'Cash Impact':>15}")
    print("-" * 45)
    for t, data in sorted(by_type.items()):
        print(f"{t:<20} {data['count']:>8} ${data['cash']:>14,.2f}")

    total_cash = sum(e.get('cash_delta', 0) for e in events)
    print("-" * 45)
    print(f"{'TOTAL':<20} {len(events):>8} ${total_cash:>14,.2f}")

    # Calculate final holdings
    print("\n=== Calculated Holdings ===")
    holdings = {}
    for e in events:
        if e['event_type'] == 'TRADE':
            ticker = e['data'].get('ticker')
            action = e['data'].get('action')
            shares = e['data'].get('shares', 0)

            if ticker not in holdings:
                holdings[ticker] = 0

            if action == 'BUY':
                holdings[ticker] += shares
            elif action == 'SELL':
                holdings[ticker] -= shares

    # Show non-zero holdings
    print(f"\n{'Ticker':<10} {'Shares':>12}")
    print("-" * 24)
    for ticker, shares in sorted(holdings.items()):
        if abs(shares) > 0.01:
            print(f"{ticker:<10} {shares:>12,.2f}")

    print(f"\nFinal cash balance: ${total_cash:,.2f}")

    return csv_events


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        # Check if it's a Schwab transaction history file
        first_arg = sys.argv[1]
        if 'Transaction' in first_arg or '--schwab-history' in sys.argv:
            # Rebuild from Schwab history
            csv_file = first_arg if 'Transaction' in first_arg else sys.argv[2]
            rebuild_from_schwab_history(csv_file)
        else:
            # Quick import mode: python setup_portfolio.py file1.csv file2.csv ...
            files = sys.argv[1:]
            quick_import(files)
    else:
        main()
