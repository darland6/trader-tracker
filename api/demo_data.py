"""Demo data generator for portfolio dashboard.

Creates 6 months of realistic fake trading data for demonstration purposes.
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

SCRIPT_DIR = Path(__file__).parent.parent.resolve()
DEMO_CSV_PATH = SCRIPT_DIR / 'demo_event_log.csv'
DEMO_DB_PATH = SCRIPT_DIR / 'demo_portfolio.db'

# Demo stock universe with realistic price ranges
DEMO_STOCKS = {
    'AAPL': {'base_price': 185, 'volatility': 0.02, 'name': 'Apple Inc'},
    'MSFT': {'base_price': 420, 'volatility': 0.018, 'name': 'Microsoft'},
    'GOOGL': {'base_price': 175, 'volatility': 0.022, 'name': 'Alphabet'},
    'AMZN': {'base_price': 195, 'volatility': 0.025, 'name': 'Amazon'},
    'NVDA': {'base_price': 880, 'volatility': 0.035, 'name': 'NVIDIA'},
    'TSLA': {'base_price': 245, 'volatility': 0.04, 'name': 'Tesla'},
    'META': {'base_price': 520, 'volatility': 0.028, 'name': 'Meta'},
    'AMD': {'base_price': 165, 'volatility': 0.032, 'name': 'AMD'},
}

# Reasons for different event types
BUY_REASONS = [
    "Value opportunity - stock trading below fair value",
    "Technical breakout - strong momentum signals",
    "Earnings beat expectations - bullish outlook",
    "Sector rotation play - tech leading market",
    "Adding to core position on dip",
    "Dollar cost averaging into position",
    "Strong fundamentals and growth potential",
]

SELL_REASONS = [
    "Taking profits after strong run",
    "Rebalancing portfolio allocation",
    "Raising cash for options strategy",
    "Risk reduction ahead of earnings",
    "Position sizing adjustment",
    "Trimming winner to lock in gains",
]

OPTION_REASONS = [
    "Income generation through premium collection",
    "Willing to buy at strike price if assigned",
    "Bullish on underlying, collecting premium",
    "High implied volatility opportunity",
    "Monthly income strategy execution",
]


def generate_price_history(stock_info: dict, days: int = 180) -> list:
    """Generate realistic price history with random walk."""
    prices = []
    price = stock_info['base_price']
    volatility = stock_info['volatility']

    for _ in range(days):
        # Random walk with slight upward bias (0.0002 daily)
        change = random.gauss(0.0002, volatility)
        price *= (1 + change)
        prices.append(round(price, 2))

    return prices


def generate_demo_data(start_cash: float = 50000) -> pd.DataFrame:
    """Generate 6 months of demo trading data.

    Creates a realistic trading history including:
    - Initial deposit
    - Stock purchases building portfolio
    - Periodic sells for profit-taking
    - Options trades for income
    - Price updates
    - Some dividends
    """
    events = []
    event_id = 1

    # Start date: 6 months ago
    start_date = datetime.now() - timedelta(days=180)
    current_date = start_date

    # Track portfolio state
    cash = 0
    holdings = {}  # ticker -> {shares, cost_basis}
    active_options = []  # list of open options

    # Generate price histories for all stocks
    price_histories = {
        ticker: generate_price_history(info)
        for ticker, info in DEMO_STOCKS.items()
    }

    def get_price(ticker: str, day_offset: int) -> float:
        """Get price for a stock on a given day."""
        idx = min(day_offset, len(price_histories[ticker]) - 1)
        return price_histories[ticker][idx]

    def add_event(event_type: str, data: dict, reason: dict, notes: str,
                  tags: list, affects_cash: bool, cash_delta: float):
        nonlocal event_id, current_date
        events.append({
            'event_id': event_id,
            'timestamp': current_date.strftime('%Y-%m-%d %H:%M:%S'),
            'event_type': event_type,
            'data_json': json.dumps(data),
            'reason_json': json.dumps(reason),
            'notes': notes,
            'tags_json': json.dumps(tags),
            'affects_cash': affects_cash,
            'cash_delta': cash_delta
        })
        event_id += 1

    # Day 1: Initial deposit (with demo marker)
    add_event(
        'DEPOSIT',
        {'amount': start_cash, 'source': 'Demo portfolio initial funding', 'is_demo': True},
        {'primary': 'INITIAL_FUNDING', 'explanation': 'Starting demo portfolio with initial capital'},
        'Demo portfolio initial funding - DEMO MODE',
        ['cash', 'deposit', 'initial', 'demo'],
        True,
        start_cash
    )
    cash = start_cash

    # Build initial positions over first 2 weeks
    initial_tickers = random.sample(list(DEMO_STOCKS.keys()), 5)
    for i, ticker in enumerate(initial_tickers):
        current_date = start_date + timedelta(days=i * 2 + 1)
        day_offset = (current_date - start_date).days
        price = get_price(ticker, day_offset)

        # Buy 5-15% of cash
        allocation = random.uniform(0.05, 0.15)
        amount = cash * allocation
        shares = int(amount / price)
        if shares < 1:
            shares = 1
        total = round(shares * price, 2)

        if total <= cash:
            add_event(
                'TRADE',
                {
                    'action': 'BUY',
                    'ticker': ticker,
                    'shares': shares,
                    'price': price,
                    'total': total,
                    'gain_loss': 0
                },
                {
                    'primary': 'VALUE_OPPORTUNITY',
                    'explanation': random.choice(BUY_REASONS),
                    'confidence': random.choice(['HIGH', 'MEDIUM']),
                    'timeframe': 'MEDIUM_TERM'
                },
                f"Building position in {DEMO_STOCKS[ticker]['name']}",
                ['trade', ticker.lower(), 'buy'],
                True,
                -total
            )
            cash -= total
            holdings[ticker] = {'shares': shares, 'cost_basis': price}

    # Main trading period: simulate 6 months
    day = 14
    while day < 180:
        current_date = start_date + timedelta(days=day)
        day_offset = day

        # Weekly price update
        if day % 7 == 0:
            prices = {ticker: get_price(ticker, day_offset) for ticker in holdings.keys()}
            add_event(
                'PRICE_UPDATE',
                {'prices': prices, 'source': 'market_data'},
                {'primary': 'PRICE_UPDATE', 'analysis': 'Weekly price sync'},
                'Weekly price update',
                ['prices', 'market_data'],
                False,
                0
            )

        # Random events throughout the week
        event_chance = random.random()

        # 15% chance of a trade
        if event_chance < 0.15 and holdings:
            ticker = random.choice(list(holdings.keys()))
            price = get_price(ticker, day_offset)
            holding = holdings[ticker]

            # 40% sell, 60% buy more
            if random.random() < 0.4 and holding['shares'] > 5:
                # Sell some shares
                sell_shares = random.randint(1, max(1, holding['shares'] // 3))
                total = round(sell_shares * price, 2)
                cost = sell_shares * holding['cost_basis']
                gain = round(total - cost, 2)

                add_event(
                    'TRADE',
                    {
                        'action': 'SELL',
                        'ticker': ticker,
                        'shares': sell_shares,
                        'price': price,
                        'total': total,
                        'gain_loss': gain
                    },
                    {
                        'primary': 'PROFIT_TAKING' if gain > 0 else 'RISK_REDUCTION',
                        'explanation': random.choice(SELL_REASONS),
                        'confidence': 'MEDIUM',
                        'timeframe': 'SHORT_TERM'
                    },
                    f"{'Profit taking' if gain > 0 else 'Reducing position'} on {ticker}",
                    ['trade', ticker.lower(), 'sell'],
                    True,
                    total
                )
                cash += total
                holding['shares'] -= sell_shares
                if holding['shares'] <= 0:
                    del holdings[ticker]
            else:
                # Buy more
                buy_amount = min(cash * 0.1, cash - 1000)  # Keep some cash
                if buy_amount > 100:
                    shares = int(buy_amount / price)
                    if shares > 0:
                        total = round(shares * price, 2)
                        add_event(
                            'TRADE',
                            {
                                'action': 'BUY',
                                'ticker': ticker,
                                'shares': shares,
                                'price': price,
                                'total': total,
                                'gain_loss': 0
                            },
                            {
                                'primary': 'VALUE_OPPORTUNITY',
                                'explanation': random.choice(BUY_REASONS),
                                'confidence': random.choice(['HIGH', 'MEDIUM']),
                                'timeframe': 'MEDIUM_TERM'
                            },
                            f"Adding to {ticker} position",
                            ['trade', ticker.lower(), 'buy'],
                            True,
                            -total
                        )
                        cash -= total
                        # Update cost basis (weighted average)
                        old_cost = holding['shares'] * holding['cost_basis']
                        new_cost = shares * price
                        holding['shares'] += shares
                        holding['cost_basis'] = (old_cost + new_cost) / holding['shares']

        # 8% chance of opening an option
        elif event_chance < 0.23 and cash > 5000 and len(active_options) < 3:
            ticker = random.choice(list(holdings.keys())) if holdings else random.choice(list(DEMO_STOCKS.keys()))
            price = get_price(ticker, day_offset)

            # Cash-secured put at 5-10% below current price
            strike = round(price * random.uniform(0.90, 0.95), 0)
            expiration = (current_date + timedelta(days=random.choice([14, 21, 30, 45]))).strftime('%Y-%m-%d')
            premium = round(strike * random.uniform(0.02, 0.05) * 100, 2)  # 2-5% premium

            option_id = event_id
            add_event(
                'OPTION_OPEN',
                {
                    'position_id': f'demo-{event_id}',
                    'ticker': ticker,
                    'strategy': 'Secured Put',
                    'strike': strike,
                    'expiration': expiration,
                    'contracts': 1,
                    'premium_per_contract': premium,
                    'total_premium': premium,
                    'status': 'OPEN'
                },
                {
                    'primary': 'INCOME_GENERATION',
                    'explanation': random.choice(OPTION_REASONS),
                    'confidence': 'HIGH',
                    'timeframe': 'SHORT_TERM'
                },
                f"Sold {ticker} ${strike} put exp {expiration} for ${premium}",
                ['options', 'income_generation', ticker.lower()],
                True,
                premium
            )
            cash += premium
            active_options.append({
                'id': option_id,
                'ticker': ticker,
                'strike': strike,
                'expiration': datetime.strptime(expiration, '%Y-%m-%d'),
                'premium': premium
            })

        # Check for option expirations
        for opt in active_options[:]:
            if current_date >= opt['expiration']:
                # Option expired - 70% expire worthless, 30% get closed early
                close_cost = 0
                if random.random() < 0.3:
                    close_cost = round(opt['premium'] * random.uniform(0.1, 0.5), 2)

                profit = opt['premium'] - close_cost
                add_event(
                    'OPTION_EXPIRE' if close_cost == 0 else 'OPTION_CLOSE',
                    {
                        'option_id': opt['id'],
                        'position_id': f'demo-{opt["id"]}',
                        'ticker': opt['ticker'],
                        'strike': opt['strike'],
                        'expiration': opt['expiration'].strftime('%Y-%m-%d'),
                        'original_premium': opt['premium'],
                        'close_cost': close_cost,
                        'profit': profit
                    },
                    {
                        'primary': 'OPTION_EXPIRE' if close_cost == 0 else 'OPTION_CLOSE',
                        'explanation': 'Option expired worthless' if close_cost == 0 else 'Closed option early',
                        'profit': profit
                    },
                    f"Option {'expired' if close_cost == 0 else 'closed'}: kept ${profit:.0f}",
                    ['options', opt['ticker'].lower()],
                    close_cost > 0,
                    -close_cost if close_cost > 0 else 0
                )
                if close_cost > 0:
                    cash -= close_cost
                active_options.remove(opt)

        # 3% chance of dividend
        if event_chance > 0.97 and holdings:
            ticker = random.choice(list(holdings.keys()))
            shares = holdings[ticker]['shares']
            div_per_share = random.uniform(0.20, 0.80)
            amount = round(shares * div_per_share, 2)

            add_event(
                'DIVIDEND',
                {
                    'ticker': ticker,
                    'amount': amount,
                    'shares': shares,
                    'per_share': round(div_per_share, 4)
                },
                {
                    'primary': 'DIVIDEND',
                    'explanation': 'Quarterly dividend payment'
                },
                f"{ticker} dividend: ${amount:.2f}",
                ['dividend', ticker.lower(), 'income'],
                True,
                amount
            )
            cash += amount

        # Advance 1-3 days
        day += random.randint(1, 3)

    # Final price update
    current_date = datetime.now()
    final_prices = {ticker: get_price(ticker, 179) for ticker in holdings.keys()}
    if final_prices:
        add_event(
            'PRICE_UPDATE',
            {'prices': final_prices, 'source': 'market_data'},
            {'primary': 'PRICE_UPDATE', 'analysis': 'Current prices'},
            'Latest price update',
            ['prices', 'market_data'],
            False,
            0
        )

    return pd.DataFrame(events)


def create_demo_csv():
    """Create demo CSV file."""
    df = generate_demo_data()
    df.to_csv(DEMO_CSV_PATH, index=False)
    return DEMO_CSV_PATH


def create_demo_database():
    """Create demo SQLite database from generated data."""
    import sqlite3

    # Generate demo data
    df = generate_demo_data()
    df.to_csv(DEMO_CSV_PATH, index=False)

    # Create database
    conn = sqlite3.connect(DEMO_DB_PATH)
    cursor = conn.cursor()

    # Create schema
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            event_id INTEGER PRIMARY KEY,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            data_json TEXT NOT NULL,
            reason_json TEXT DEFAULT '{}',
            notes TEXT DEFAULT '',
            tags_json TEXT DEFAULT '[]',
            affects_cash INTEGER DEFAULT 0,
            cash_delta REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_event_type ON events(event_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON events(timestamp)')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_cache (
            ticker TEXT PRIMARY KEY,
            price REAL NOT NULL,
            updated_at TEXT NOT NULL,
            session TEXT DEFAULT 'regular'
        )
    ''')

    # Insert events
    for _, row in df.iterrows():
        cursor.execute('''
            INSERT INTO events
            (event_id, timestamp, event_type, data_json, reason_json, notes, tags_json, affects_cash, cash_delta)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            int(row['event_id']),
            str(row['timestamp']),
            str(row['event_type']),
            str(row['data_json']),
            str(row.get('reason_json', '{}')),
            str(row.get('notes', '')),
            str(row.get('tags_json', '[]')),
            1 if row.get('affects_cash', False) else 0,
            float(row.get('cash_delta', 0))
        ))

    # Add initial prices to cache
    final_event = df[df['event_type'] == 'PRICE_UPDATE'].iloc[-1] if not df[df['event_type'] == 'PRICE_UPDATE'].empty else None
    if final_event is not None:
        prices = json.loads(final_event['data_json']).get('prices', {})
        now = datetime.now().isoformat()
        for ticker, price in prices.items():
            cursor.execute('''
                INSERT OR REPLACE INTO price_cache (ticker, price, updated_at, session)
                VALUES (?, ?, ?, ?)
            ''', (ticker, price, now, 'regular'))

    conn.commit()
    conn.close()

    return DEMO_DB_PATH


def is_demo_mode() -> bool:
    """Check if running in demo mode."""
    return DEMO_DB_PATH.exists() and not (SCRIPT_DIR / 'portfolio.db').exists()


def get_demo_status() -> dict:
    """Get current demo/database status."""
    real_db = SCRIPT_DIR / 'portfolio.db'
    real_csv = SCRIPT_DIR / 'event_log_enhanced.csv'

    return {
        'has_real_db': real_db.exists(),
        'has_real_csv': real_csv.exists(),
        'has_demo_db': DEMO_DB_PATH.exists(),
        'is_demo_mode': is_demo_mode(),
        'needs_setup': not real_db.exists() and not real_csv.exists() and not DEMO_DB_PATH.exists()
    }


if __name__ == '__main__':
    # Test generation
    print("Generating demo data...")
    df = generate_demo_data()
    print(f"Generated {len(df)} events")
    print("\nEvent types:")
    print(df['event_type'].value_counts())
    print("\nSample events:")
    print(df.head(10))
