"""Event creation and management for the event log."""

import pandas as pd
import json
import uuid
from datetime import datetime, date
from pathlib import Path

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SCRIPT_DIR = Path(__file__).parent.parent.resolve()
EVENT_LOG = SCRIPT_DIR / 'data' / 'event_log_enhanced.csv'


def _generate_ai_insights(event_type: str, data: dict, reason: dict, notes: str) -> dict:
    """Generate AI insights for an event. Returns empty dict on failure."""
    try:
        from llm.client import generate_event_insights
        user_reason = reason.get('explanation', '') if reason else ''
        return generate_event_insights(
            event_type=event_type,
            event_data=data,
            user_reason=user_reason,
            notes=notes
        )
    except Exception as e:
        print(f"[AI] Insight generation skipped: {e}")
        return {}


def _generate_price_commentary(prices: dict, portfolio_state: dict = None) -> dict:
    """Generate LLM market commentary for a price update. Returns empty dict on failure."""
    try:
        from llm.config import get_llm_config
        config = get_llm_config()

        if not config.enabled:
            return {}

        # Build context about the price changes
        price_summary = "\n".join([f"  {ticker}: ${price:.2f}" for ticker, price in prices.items()])

        # Get previous prices for comparison if available
        from api.database import get_cached_prices
        cached = get_cached_prices()
        changes = []
        for ticker, price in prices.items():
            if ticker in cached:
                old_price = cached[ticker].get('price', price)
                if old_price and old_price != price:
                    pct_change = ((price - old_price) / old_price) * 100
                    changes.append(f"{ticker}: ${old_price:.2f} -> ${price:.2f} ({pct_change:+.1f}%)")

        change_summary = "\n".join(changes) if changes else "No previous prices to compare"

        prompt = f"""You are a portfolio assistant. A price update just occurred for these holdings:

Current Prices:
{price_summary}

Price Changes:
{change_summary}

Write a brief (2-3 sentences) market note for future reference:
1. Note any significant moves (>2%)
2. Any patterns or concerns?
3. Anything to watch?

Keep it concise and actionable. Respond with just the commentary, no JSON."""

        if config.provider == "claude":
            import anthropic
            client = anthropic.Anthropic(api_key=config.anthropic_api_key)
            response = client.messages.create(
                model=config.claude_model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )
            commentary = response.content[0].text
            model = config.claude_model
        else:
            import httpx
            response = httpx.post(
                f"{config.local_url}/chat/completions",
                json={
                    "model": config.local_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 200,
                    "temperature": 0.7
                },
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            commentary = result["choices"][0]["message"]["content"]
            model = config.local_model

        return {
            "market_note": commentary.strip(),
            "model": model,
            "generated_at": datetime.now().isoformat()
        }

    except Exception as e:
        print(f"[AI] Price commentary skipped: {e}")
        return {}


def get_next_event_id():
    """Get the next available event ID."""
    df = pd.read_csv(EVENT_LOG)
    return int(df['event_id'].max()) + 1


def append_event(event_type, data, reason=None, notes="", tags=None, affects_cash=False, cash_delta=0, skip_ai=False):
    """Append a new event to the event log.

    Args:
        event_type: Type of event (TRADE, OPTION_OPEN, etc.)
        data: Event data dictionary
        reason: Reason dictionary with primary, explanation, etc.
        notes: Free-form notes
        tags: List of tags
        affects_cash: Whether this event affects cash balance
        cash_delta: Change in cash (positive = inflow)
        skip_ai: Skip AI insight generation (for system events)
    """
    df = pd.read_csv(EVENT_LOG)

    event_id = int(df['event_id'].max()) + 1
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if reason is None:
        reason = {}
    if tags is None:
        tags = []

    # Generate AI insights for user events
    if not skip_ai and event_type not in ("PRICE_UPDATE",):
        ai_insights = _generate_ai_insights(event_type, data, reason, notes)
        if ai_insights:
            reason['ai_insights'] = {
                'reasoning': ai_insights.get('reasoning', ''),
                'future_advice': ai_insights.get('future_advice', ''),
                'past_reflection': ai_insights.get('past_reflection', '')
            }
            reason['ai_generated_at'] = ai_insights.get('generated_at', '')
            reason['ai_model'] = ai_insights.get('model', '')

    new_row = {
        'event_id': event_id,
        'timestamp': timestamp,
        'event_type': event_type,
        'data_json': json.dumps(data),
        'reason_json': json.dumps(reason),
        'notes': notes,
        'tags_json': json.dumps(tags),
        'affects_cash': affects_cash,
        'cash_delta': cash_delta
    }

    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(EVENT_LOG, index=False)

    return event_id


def create_trade_event(action, ticker, shares, price, total, gain_loss=0, reason_text="", notes=""):
    """Create a TRADE event (BUY or SELL)."""
    data = {
        "action": action.upper(),
        "ticker": ticker.upper(),
        "shares": shares,
        "price": price,
        "total": total,
        "gain_loss": gain_loss
    }

    reason = {
        "primary": "BUY" if action.upper() == "BUY" else "SELL",
        "explanation": reason_text,
        "confidence": "MEDIUM",
        "timeframe": "SHORT_TERM",
        "logged_by": "user"
    }

    tags = ["trade", ticker.lower(), action.lower()]
    affects_cash = True
    cash_delta = total if action.upper() == "SELL" else -total

    return append_event("TRADE", data, reason, notes or reason_text, tags, affects_cash, cash_delta)


def create_option_event(ticker, action, strategy, strike, expiration, contracts, premium, reason_text=""):
    """Create an OPTION_OPEN event with a unique position UUID.

    Args:
        ticker: Underlying stock ticker
        action: BUY or SELL
        strategy: Put or Call
        strike: Strike price
        expiration: Expiration date (YYYY-MM-DD)
        contracts: Number of contracts
        premium: Total premium (positive = received if SELL, paid if BUY)
        reason_text: Optional reason
    """
    position_id = str(uuid.uuid4())[:8]  # Short UUID for readability
    action_upper = action.upper()
    total_premium = float(premium)
    premium_per_contract = total_premium / int(contracts) if contracts > 0 else 0

    data = {
        "position_id": position_id,
        "ticker": ticker.upper(),
        "action": action_upper,  # BUY or SELL
        "strategy": strategy,
        "strike": float(strike),
        "expiration": expiration,
        "contracts": int(contracts),
        "premium_per_contract": premium_per_contract,
        "total_premium": total_premium,
        "status": "OPEN"
    }

    reason = {
        "primary": "OPTION_OPEN",
        "explanation": reason_text,
        "confidence": "HIGH",
        "timeframe": "SHORT_TERM",
        "logged_by": "user"
    }

    tags = ["options", ticker.lower()]

    # Cash flow: SELL = receive premium (positive), BUY = pay premium (negative)
    if action_upper == "SELL":
        affects_cash = True
        cash_delta = total_premium
        notes = reason_text or f"Sold {contracts} {ticker} {strategy} @ ${strike}"
    else:  # BUY
        affects_cash = True
        cash_delta = -total_premium
        notes = reason_text or f"Bought {contracts} {ticker} {strategy} @ ${strike}"

    event_id = append_event("OPTION_OPEN", data, reason, notes, tags, affects_cash, cash_delta)
    return event_id, position_id


def get_option_by_id(option_id):
    """Get option data by event_id."""
    df = pd.read_csv(EVENT_LOG)
    row = df[df['event_id'] == int(option_id)]
    if row.empty:
        return None
    row = row.iloc[0]
    if row['event_type'] != 'OPTION_OPEN':
        return None
    data = json.loads(row['data_json'])
    data['event_id'] = int(option_id)
    return data


def get_option_by_position_id(position_id):
    """Get option data by position UUID."""
    df = pd.read_csv(EVENT_LOG)
    opens = df[df['event_type'] == 'OPTION_OPEN']

    for _, row in opens.iterrows():
        data = json.loads(row['data_json'])
        if data.get('position_id') == position_id:
            data['event_id'] = row['event_id']
            return data

    return None


def create_option_close_event(option_id=None, position_id=None, close_cost=0, event_type="OPTION_CLOSE", reason_text="", skip_ai=False):
    """Create an OPTION_CLOSE, OPTION_EXPIRE, or OPTION_ASSIGN event.

    Args:
        option_id: The event_id of the OPTION_OPEN event (optional if position_id provided)
        position_id: The position UUID (optional if option_id provided)
        close_cost: Cost to close (buy back) the option. 0 if expired worthless.
        event_type: OPTION_CLOSE, OPTION_EXPIRE, or OPTION_ASSIGN
        reason_text: Why this action was taken
        skip_ai: Skip AI insight generation

    Gain is calculated as: original_premium - close_cost
    """
    # Look up original option by position_id or event_id
    original = None
    if position_id:
        original = get_option_by_position_id(position_id)
    if original is None and option_id:
        original = get_option_by_id(option_id)

    if original is None:
        raise ValueError(f"Option not found (id={option_id}, position_id={position_id})")

    original_premium = original.get('total_premium', 0)
    profit = original_premium - float(close_cost)

    data = {
        "option_id": int(original.get('event_id')),
        "position_id": original.get('position_id', ''),
        "ticker": original.get('ticker', ''),
        "strike": original.get('strike', 0),
        "expiration": original.get('expiration', ''),
        "original_premium": original_premium,
        "close_cost": float(close_cost),
        "profit": profit
    }

    reason = {
        "primary": event_type,
        "explanation": reason_text,
        "profit": profit,
        "logged_by": "user" if event_type != "OPTION_EXPIRE" else "system"
    }

    # For OPTION_CLOSE: cash decreases by close_cost (buying back)
    # For OPTION_EXPIRE: no cash change (already received premium)
    # For OPTION_ASSIGN: handled separately (shares change hands)
    if event_type == "OPTION_CLOSE":
        affects_cash = True
        cash_delta = -float(close_cost)  # Paying to close
    else:
        affects_cash = False
        cash_delta = 0

    ticker = original.get('ticker', '')
    strike = original.get('strike', 0)
    notes = reason_text or f"Closed {ticker} ${strike} option: Premium ${original_premium:,.0f} - Close ${close_cost:,.0f} = Profit ${profit:,.0f}"
    return append_event(event_type, data, reason, notes, ["options", ticker.lower()], affects_cash, cash_delta, skip_ai=skip_ai)


def auto_expire_options():
    """Check for expired options and close them automatically.

    Returns list of expired option position_ids that were closed.
    """
    today = date.today()
    active = get_active_options()
    expired = []

    for opt in active:
        exp_str = opt.get('expiration', '')
        if not exp_str:
            continue

        try:
            exp_date = datetime.strptime(exp_str, '%Y-%m-%d').date()
        except ValueError:
            continue

        if exp_date < today:
            # Option has expired - close it (skip AI for automated action)
            position_id = opt.get('position_id')
            event_id = opt.get('event_id')

            create_option_close_event(
                option_id=event_id,
                position_id=position_id,
                close_cost=0,
                event_type="OPTION_EXPIRE",
                reason_text=f"Auto-expired on {exp_str}",
                skip_ai=True
            )
            expired.append({
                'position_id': position_id,
                'ticker': opt.get('ticker'),
                'strike': opt.get('strike'),
                'expiration': exp_str,
                'premium': opt.get('total_premium', 0)
            })

    return expired


def create_cash_event(event_type, amount, reason_text="", description=""):
    """Create a DEPOSIT or WITHDRAWAL event."""
    if event_type.upper() == "DEPOSIT":
        data = {"amount": float(amount), "source": description}
        cash_delta = float(amount)
    else:
        data = {"amount": float(amount), "purpose": description}
        cash_delta = -float(amount)

    reason = {
        "primary": event_type.upper(),
        "explanation": reason_text,
        "logged_by": "user"
    }

    tags = ["cash", event_type.lower()]
    notes = reason_text or description

    return append_event(event_type.upper(), data, reason, notes, tags, True, cash_delta)


def create_price_update_event(prices, source="yfinance", with_commentary=True):
    """Create a PRICE_UPDATE event with optional LLM market commentary."""
    data = {
        "prices": prices,
        "source": source
    }

    reason = {
        "primary": "PRICE_UPDATE",
        "analysis": f"Live price fetch via {source}"
    }

    notes = f"Price update from {source}"

    # Generate LLM market commentary
    if with_commentary:
        commentary = _generate_price_commentary(prices)
        if commentary:
            reason['ai_insights'] = {
                'market_note': commentary.get('market_note', '')
            }
            reason['ai_generated_at'] = commentary.get('generated_at', '')
            reason['ai_model'] = commentary.get('model', '')
            # Add commentary to notes for easy viewing
            if commentary.get('market_note'):
                notes += f"\n\nMarket Note: {commentary['market_note']}"

    return append_event("PRICE_UPDATE", data, reason, notes, ["prices", "market_data"], False, 0, skip_ai=True)


def get_active_options():
    """Get list of active options from the event log."""
    df = pd.read_csv(EVENT_LOG)

    # Get all OPTION_OPEN events
    opens = df[df['event_type'] == 'OPTION_OPEN'].copy()

    # Get all closed option IDs
    closes = df[df['event_type'].isin(['OPTION_CLOSE', 'OPTION_EXPIRE', 'OPTION_ASSIGN'])]
    closed_ids = set()
    for _, row in closes.iterrows():
        data = json.loads(row['data_json'])
        closed_ids.add(data.get('option_id'))

    # Filter to only active options
    active = []
    for _, row in opens.iterrows():
        if row['event_id'] not in closed_ids:
            data = json.loads(row['data_json'])
            data['event_id'] = row['event_id']
            active.append(data)

    return active


def get_recent_events(limit=10, ticker=None):
    """Get recent events, optionally filtered by ticker."""
    df = pd.read_csv(EVENT_LOG)

    if ticker:
        ticker = ticker.upper()
        # Filter events that mention this ticker
        mask = df['data_json'].str.contains(f'"{ticker}"', case=False, na=False)
        df = df[mask]

    return df.tail(limit).to_dict('records')
