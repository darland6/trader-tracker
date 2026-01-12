"""
Prepare Event Log for AI Agent Consumption

Converts event log CSV into structured JSON optimized for AI agent analysis.
Includes portfolio context, market context, and reason analysis.

Usage:
  python prepare_for_agent.py                    # Full log
  python prepare_for_agent.py --since "2025-12-01"  # Recent events
  python prepare_for_agent.py --ticker TSLA       # Ticker-specific
  python prepare_for_agent.py --reason-analysis   # Reason pattern analysis
"""

import pandas as pd
import json
import sys
import argparse
from datetime import datetime
from collections import Counter
from pathlib import Path

# Get the project root directory (one level up from scripts/)
SCRIPT_DIR = Path(__file__).parent.parent.resolve()

# Add project root to path for imports
sys.path.insert(0, str(SCRIPT_DIR))

def load_event_log(filepath='event_log_enhanced.csv'):
    """Load enhanced event log with reason field"""
    try:
        df = pd.read_csv(filepath)
    except FileNotFoundError:
        print(f"Error: {filepath} not found")
        print("Using standard event log instead...")
        filepath = 'event_log.csv'
        df = pd.read_csv(filepath)
    
    # Parse JSON columns
    if 'data_json' in df.columns:
        df['data'] = df['data_json'].apply(json.loads)
    if 'reason_json' in df.columns:
        df['reason'] = df['reason_json'].apply(json.loads)
    if 'tags_json' in df.columns:
        df['tags'] = df['tags_json'].apply(json.loads)
    
    # Use format='mixed' to handle both ISO8601 and standard datetime formats
    df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed')
    return df

def prepare_agent_context(events_df, include_full_history=True):
    """Prepare complete context for AI agent"""
    
    # Load current state from reconstruction
    from reconstruct_state import reconstruct_state
    current_state = reconstruct_state(events_df)
    
    # Build agent context
    context = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "total_events": len(events_df),
            "date_range": {
                "start": events_df['timestamp'].min().isoformat(),
                "end": events_df['timestamp'].max().isoformat()
            },
            "event_log_version": "enhanced_v1.0"
        },
        
        "current_portfolio": {
            "total_value": current_state['total_value'],
            "portfolio_value": current_state['portfolio_value'],
            "cash": current_state['cash'],
            "holdings": current_state['holdings'],
            "holdings_value": current_state['holdings_value'],
            "active_options": current_state['active_options'],
            "unrealized_gains": current_state['unrealized_gains']
        },
        
        "goals": {
            "annual_income_target": 30000,
            "monthly_income_target": 2500,
            "ytd_income_actual": current_state['ytd_income'],
            "ytd_income_breakdown": {
                "trading_gains": current_state['ytd_trading_gains'],
                "option_income": current_state['ytd_option_income'],
                "dividends": current_state['ytd_dividends']
            },
            "progress_pct": round((current_state['ytd_income'] / 30000) * 100, 1),
            "on_track": current_state['ytd_income'] > 30000 * (datetime.now().month / 12)
        },
        
        "investment_theses": current_state['theses'],
        
        "strategy": {
            "name": "Two-Part Income Strategy",
            "objectives": [
                "Generate $30k/year through options premiums",
                "Maintain portfolio growth through quality holdings",
                "Build toward PAL account for tax-free living"
            ]
        },
        
        "events": []
    }
    
    # Add events
    if include_full_history:
        for idx, event in events_df.iterrows():
            event_obj = {
                "event_id": int(event['event_id']),
                "timestamp": event['timestamp'].isoformat(),
                "event_type": event['event_type'],
                "data": event.get('data', {}),
                "notes": event['notes'],
                "affects_cash": bool(event['affects_cash']),
                "cash_delta": float(event['cash_delta'])
            }
            
            # Add reason if present
            if 'reason' in event.index and event['reason'] is not None:
                reason_val = event['reason']
                if isinstance(reason_val, dict):
                    event_obj['reason'] = reason_val

            # Add tags if present
            if 'tags' in event.index and event['tags'] is not None:
                tags_val = event['tags']
                if isinstance(tags_val, list):
                    event_obj['tags'] = tags_val
            
            context['events'].append(event_obj)
    
    return context

def analyze_reasons(events_df):
    """Analyze reason patterns in the event log"""
    
    if 'reason' not in events_df.columns:
        return {"error": "No reason field in event log. Use enhanced event log."}
    
    analysis = {
        "reason_distribution": {},
        "confidence_distribution": {},
        "timeframe_distribution": {},
        "strategic_alignment": {},
        "patterns": []
    }
    
    # Extract reason data
    reasons = []
    for idx, event in events_df.iterrows():
        if pd.notna(event.get('reason')):
            reason = event['reason']
            reasons.append({
                'event_id': event['event_id'],
                'event_type': event['event_type'],
                'primary': reason.get('primary', 'UNKNOWN'),
                'secondary': reason.get('secondary', 'NONE'),
                'strategic': reason.get('strategic_alignment', 'NONE'),
                'confidence': reason.get('confidence', 'UNKNOWN'),
                'timeframe': reason.get('timeframe', 'UNKNOWN'),
                'cash_delta': event['cash_delta']
            })
    
    if not reasons:
        return {"error": "No reasons found in events"}
    
    # Count distributions
    primary_reasons = Counter([r['primary'] for r in reasons])
    analysis['reason_distribution'] = dict(primary_reasons)
    
    confidence_levels = Counter([r['confidence'] for r in reasons])
    analysis['confidence_distribution'] = dict(confidence_levels)
    
    timeframes = Counter([r['timeframe'] for r in reasons])
    analysis['timeframe_distribution'] = dict(timeframes)
    
    strategic = Counter([r['strategic'] for r in reasons])
    analysis['strategic_alignment'] = dict(strategic)
    
    # Analyze patterns
    # Pattern 1: Income generation success
    income_events = [r for r in reasons if r['primary'] == 'INCOME_GENERATION']
    if income_events:
        total_income = sum([r['cash_delta'] for r in income_events if r['cash_delta'] > 0])
        analysis['patterns'].append({
            'pattern': 'INCOME_GENERATION',
            'count': len(income_events),
            'total_generated': total_income,
            'average_per_event': total_income / len(income_events) if income_events else 0
        })
    
    # Pattern 2: Confidence vs outcome
    high_conf = [r for r in reasons if r['confidence'] == 'HIGH']
    if high_conf:
        analysis['patterns'].append({
            'pattern': 'HIGH_CONFIDENCE_DECISIONS',
            'count': len(high_conf),
            'net_cash_impact': sum([r['cash_delta'] for r in high_conf])
        })
    
    return analysis

def main():
    parser = argparse.ArgumentParser(description='Prepare event log for AI agent')
    parser.add_argument('--since', help='Include events since date (YYYY-MM-DD)')
    parser.add_argument('--ticker', help='Filter by ticker')
    parser.add_argument('--reason-analysis', action='store_true', help='Analyze reason patterns')
    parser.add_argument('--output', default=str(SCRIPT_DIR / 'data' / 'agent_context.json'),
                       help='Output file path')
    parser.add_argument('--event-log', default=str(SCRIPT_DIR / 'data' / 'event_log_enhanced.csv'),
                       help='Input event log path')
    
    args = parser.parse_args()
    
    # Load event log
    print(f"Loading event log from {args.event_log}...")
    events_df = load_event_log(args.event_log)
    print(f"Loaded {len(events_df)} events")
    
    # Filter if requested
    if args.since:
        since_date = pd.to_datetime(args.since)
        events_df = events_df[events_df['timestamp'] >= since_date]
        print(f"Filtered to {len(events_df)} events since {args.since}")
    
    if args.ticker:
        # Filter events related to ticker
        mask = events_df['data'].apply(lambda x: x.get('ticker', '') == args.ticker if isinstance(x, dict) else False)
        events_df = events_df[mask]
        print(f"Filtered to {len(events_df)} events for {args.ticker}")
    
    # Reason analysis mode
    if args.reason_analysis:
        print("\nAnalyzing reason patterns...")
        analysis = analyze_reasons(events_df)
        print(json.dumps(analysis, indent=2))
        
        with open(args.output.replace('.json', '_reason_analysis.json'), 'w') as f:
            json.dump(analysis, f, indent=2)
        print(f"\n✅ Reason analysis saved to {args.output.replace('.json', '_reason_analysis.json')}")
        return
    
    # Prepare full context for agent
    print("\nPreparing context for AI agent...")
    context = prepare_agent_context(events_df)
    
    # Save to file
    with open(args.output, 'w') as f:
        json.dump(context, f, indent=2)
    
    print(f"\n✅ Agent context saved to {args.output}")
    print(f"\n📊 Context Summary:")
    print(f"   Total Events: {context['metadata']['total_events']}")
    print(f"   Portfolio Value: ${context['current_portfolio']['total_value']:,.2f}")
    print(f"   YTD Income: ${context['goals']['ytd_income_actual']:,.2f}")
    print(f"   Goal Progress: {context['goals']['progress_pct']}%")
    print(f"   Active Options: {len(context['current_portfolio']['active_options'])}")
    print(f"\n🤖 Ready for AI agent consumption!")
    print(f"\nUsage:")
    print(f"   Load this JSON into your AI agent")
    print(f"   Use the system prompt from ai_agent_prompt.md")
    print(f"   Ask questions about patterns, decisions, and strategy")

if __name__ == "__main__":
    main()

