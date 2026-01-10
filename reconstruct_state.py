"""
State Reconstruction Engine - Event Sourcing
Reconstructs complete portfolio state from canonical event log

Usage:
  python reconstruct_state.py                    # Current state
  python reconstruct_state.py --as-of "2026-01-05 23:59:59"  # Historical state
  python reconstruct_state.py --ticker TSLA       # TSLA-specific events
"""

import pandas as pd
import json
import sys
import argparse
from datetime import datetime
from pathlib import Path

# Get the directory where this script is located (project root)
SCRIPT_DIR = Path(__file__).parent.resolve()

def load_event_log(filepath='event_log.csv'):
    """Load and parse the canonical event log"""
    df = pd.read_csv(filepath)
    
    # Parse JSON data column
    df['data'] = df['data_json'].apply(json.loads)
    df = df.drop('data_json', axis=1)
    
    # Convert timestamp to datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Sort by timestamp (should already be sorted, but ensure)
    df = df.sort_values('timestamp')
    
    return df

def load_starting_state(filepath='starting_state.json'):
    """Load the initial state"""
    with open(filepath, 'r') as f:
        return json.load(f)

def reconstruct_state(events_df, as_of_timestamp=None, ticker_filter=None):
    """
    Reconstruct portfolio state by replaying events
    
    Args:
        events_df: DataFrame of events
        as_of_timestamp: Optional datetime to stop reconstruction
        ticker_filter: Optional ticker to filter events
    
    Returns:
        dict: Complete portfolio state
    """
    
    # Load starting state
    starting = load_starting_state(SCRIPT_DIR / 'data' / 'starting_state.json')
    
    state = {
        'as_of': as_of_timestamp or datetime.now(),
        'cash': starting['cash'],
        'holdings': {},  # ticker -> shares
        'cost_basis': {},  # ticker -> {total_cost, shares, avg_price}
        'active_options': [],
        'ytd_income': 0.0,
        'ytd_trading_gains': 0.0,
        'ytd_option_income': 0.0,
        'ytd_dividends': 0.0,
        'withdrawals': 0.0,
        'notes': [],
        'goals': [],
        'strategies': [],
        'theses': {},
        'latest_prices': {},
        'events_processed': 0
    }
    
    # Initialize with starting holdings
    for ticker, info in starting['initial_holdings'].items():
        state['holdings'][ticker] = info['shares']
        if info['cost_basis_per_share'] > 0:
            state['cost_basis'][ticker] = {
                'total_cost': info['shares'] * info['cost_basis_per_share'],
                'shares': info['shares'],
                'avg_price': info['cost_basis_per_share']
            }
    
    # Replay events
    for idx, event in events_df.iterrows():
        # Stop if past desired timestamp
        if as_of_timestamp and event['timestamp'] > pd.to_datetime(as_of_timestamp):
            break
        
        # Filter by ticker if specified
        if ticker_filter:
            event_ticker = event['data'].get('ticker', '')
            if event_ticker != ticker_filter:
                continue
        
        # Process event based on type
        event_type = event['event_type']
        data = event['data']
        
        if event_type == 'TRADE':
            ticker = data['ticker']
            action = data['action']
            shares = data.get('shares', 0)
            
            # Handle "multiple" or "partial" shares
            if isinstance(shares, str):
                shares = 0  # Will need to be filled in later
            
            if action == 'BUY':
                # Add to holdings
                state['holdings'][ticker] = state['holdings'].get(ticker, 0) + shares
                
                # Update cost basis
                if ticker not in state['cost_basis']:
                    state['cost_basis'][ticker] = {'total_cost': 0, 'shares': 0, 'avg_price': 0}
                
                cost_basis = state['cost_basis'][ticker]
                cost_basis['total_cost'] += data.get('total', 0)
                cost_basis['shares'] += shares
                if cost_basis['shares'] > 0:
                    cost_basis['avg_price'] = cost_basis['total_cost'] / cost_basis['shares']
                
            elif action == 'SELL':
                # Remove from holdings
                state['holdings'][ticker] = state['holdings'].get(ticker, 0) - shares
                
                # Update cost basis (reduce proportionally)
                if ticker in state['cost_basis'] and shares > 0:
                    cost_basis = state['cost_basis'][ticker]
                    proportion = shares / cost_basis['shares'] if cost_basis['shares'] > 0 else 0
                    cost_basis['total_cost'] *= (1 - proportion)
                    cost_basis['shares'] -= shares
                    if cost_basis['shares'] > 0:
                        cost_basis['avg_price'] = cost_basis['total_cost'] / cost_basis['shares']
                
                # Track gains
                gain = data.get('gain_loss', 0)
                state['ytd_trading_gains'] += gain
                state['ytd_income'] += gain
            
            # Update cash
            state['cash'] += event['cash_delta']
        
        elif event_type == 'OPTION_OPEN':
            state['active_options'].append({
                'event_id': event['event_id'],
                'position_id': data.get('position_id', ''),
                'ticker': data['ticker'],
                'strategy': data['strategy'],
                'strike': data['strike'],
                'expiration': data['expiration'],
                'contracts': data.get('contracts', 1),
                'total_premium': data.get('total_premium', data.get('premium', 0))
            })
            
            premium = data.get('total_premium', data.get('premium', 0))
            state['ytd_option_income'] += premium
            state['ytd_income'] += premium
            state['cash'] += event['cash_delta']
        
        elif event_type in ['OPTION_CLOSE', 'OPTION_EXPIRE', 'OPTION_ASSIGN']:
            # Remove from active options (try position_id, uuid, then event_id)
            position_id = data.get('position_id')
            option_id = data.get('option_id')
            uuid = data.get('uuid')

            if position_id:
                state['active_options'] = [opt for opt in state['active_options']
                                          if opt.get('position_id') != position_id]
            elif uuid:
                state['active_options'] = [opt for opt in state['active_options']
                                          if opt.get('uuid') != uuid]
            elif option_id:
                state['active_options'] = [opt for opt in state['active_options']
                                          if opt['event_id'] != option_id]

            # Track profit
            profit = data.get('profit', 0)
            state['ytd_option_income'] += profit
            state['ytd_income'] += profit

            # Update cash (e.g., buying back an option costs money)
            state['cash'] += event['cash_delta']
        
        elif event_type == 'DIVIDEND':
            amount = data['amount']
            state['ytd_dividends'] += amount
            state['ytd_income'] += amount
            state['cash'] += event['cash_delta']
        
        elif event_type == 'WITHDRAWAL':
            state['withdrawals'] += abs(event['cash_delta'])
            state['cash'] += event['cash_delta']
        
        elif event_type == 'DEPOSIT':
            state['cash'] += event['cash_delta']
        
        elif event_type == 'PRICE_UPDATE':
            prices = data.get('prices', {})
            state['latest_prices'].update(prices)
        
        elif event_type == 'NOTE':
            category = data.get('category', 'general')
            if category == 'investment_thesis':
                ticker = data['ticker']
                state['theses'][ticker] = data['content']
            else:
                state['notes'].append({
                    'timestamp': event['timestamp'],
                    'category': category,
                    'content': data['content']
                })
        
        elif event_type == 'GOAL_UPDATE':
            state['goals'].append({
                'timestamp': event['timestamp'],
                'type': data['goal_type'],
                'content': data['content']
            })
        
        elif event_type == 'STRATEGY_UPDATE':
            state['strategies'].append({
                'timestamp': event['timestamp'],
                'name': data['strategy_name'],
                'details': {k: v for k, v in data.items() if k != 'strategy_name'}
            })

        elif event_type == 'ADJUSTMENT':
            # Cash adjustments (journal entries, reconciliation, etc.)
            state['cash'] += event['cash_delta']

        elif event_type == 'INSIGHT_LOG':
            # AI insight usage logging - no state change
            pass

        state['events_processed'] += 1
    
    # Calculate current portfolio value
    state['portfolio_value'] = 0
    state['holdings_value'] = {}
    for ticker, shares in state['holdings'].items():
        if ticker in state['latest_prices'] and shares > 0:
            price = state['latest_prices'][ticker]
            value = shares * price
            state['holdings_value'][ticker] = value
            state['portfolio_value'] += value
    
    state['total_value'] = state['portfolio_value'] + state['cash']
    
    # Calculate unrealized gains
    state['unrealized_gains'] = 0
    for ticker in state['holdings_value']:
        if ticker in state['cost_basis']:
            market_value = state['holdings_value'][ticker]
            cost = state['cost_basis'][ticker]['total_cost']
            state['unrealized_gains'] += (market_value - cost)
    
    return state

def print_state(state):
    """Pretty print the portfolio state"""
    print("="*80)
    print(f"PORTFOLIO STATE AS OF {state['as_of']}")
    print("="*80)
    
    print(f"\n💵 CASH: ${state['cash']:,.2f}")
    print(f"📊 PORTFOLIO VALUE: ${state['portfolio_value']:,.2f}")
    print(f"💰 TOTAL VALUE: ${state['total_value']:,.2f}")
    
    print(f"\n📈 HOLDINGS:")
    if state['holdings']:
        for ticker, shares in sorted(state['holdings'].items()):
            if shares > 0:
                value = state['holdings_value'].get(ticker, 0)
                price = state['latest_prices'].get(ticker, 0)
                cost_basis = state['cost_basis'].get(ticker, {})
                avg_cost = cost_basis.get('avg_price', 0)
                
                gain = value - cost_basis.get('total_cost', 0) if ticker in state['cost_basis'] else 0
                gain_pct = (gain / cost_basis.get('total_cost', 1)) * 100 if ticker in state['cost_basis'] and cost_basis['total_cost'] > 0 else 0
                
                print(f"   {ticker:6} | {shares:>8,.0f} shares @ ${price:>8.2f} = ${value:>12,.2f} "
                      f"(cost: ${avg_cost:.2f}, gain: ${gain:>10,.2f} / {gain_pct:>6.1f}%)")
    else:
        print("   (none)")
    
    print(f"\n🎯 ACTIVE OPTIONS: {len(state['active_options'])}")
    for opt in state['active_options']:
        print(f"   {opt['ticker']} {opt['strategy']} ${opt['strike']:.2f} exp {opt['expiration']} - ${opt['premium']:,.2f}")
    
    print(f"\n💸 INCOME (YTD):")
    print(f"   Total Income:     ${state['ytd_income']:>12,.2f}")
    print(f"   ├─ Trading Gains: ${state['ytd_trading_gains']:>12,.2f}")
    print(f"   ├─ Options:       ${state['ytd_option_income']:>12,.2f}")
    print(f"   └─ Dividends:     ${state['ytd_dividends']:>12,.2f}")
    print(f"   Withdrawals:      ${state['withdrawals']:>12,.2f}")
    
    print(f"\n📝 INVESTMENT THESES:")
    for ticker, thesis in state['theses'].items():
        print(f"   {ticker:6} - {thesis}")
    
    print(f"\n🎯 GOALS:")
    for goal in state['goals'][-3:]:  # Show last 3
        print(f"   [{goal['timestamp']}] {goal['type']}")
        print(f"   {goal['content'][:100]}...")
    
    print(f"\n⚙️  STRATEGIES:")
    for strat in state['strategies'][-2:]:  # Show last 2
        print(f"   [{strat['timestamp']}] {strat['name']}")
    
    print(f"\n📊 STATISTICS:")
    print(f"   Events Processed: {state['events_processed']}")
    print(f"   Unrealized Gains: ${state['unrealized_gains']:,.2f}")
    print(f"   Portfolio + Cash: ${state['total_value']:,.2f}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Reconstruct portfolio state from event log')
    parser.add_argument('--as-of', help='Reconstruct state as of timestamp (YYYY-MM-DD HH:MM:SS)')
    parser.add_argument('--ticker', help='Filter events by ticker')
    parser.add_argument('--event-log', default=str(SCRIPT_DIR / 'data' / 'event_log_enhanced.csv'), help='Path to event log')
    
    args = parser.parse_args()
    
    # Load events
    print("Loading event log...")
    events_df = load_event_log(args.event_log)
    print(f"Loaded {len(events_df)} events")
    
    # Reconstruct state
    print("Reconstructing state...")
    state = reconstruct_state(events_df, args.as_of, args.ticker)
    
    # Print results
    print_state(state)

