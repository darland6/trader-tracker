"""Command implementations for the portfolio CLI."""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import yfinance as yf
from reconstruct_state import load_event_log, load_starting_state, reconstruct_state

from .events import (
    create_trade_event,
    create_option_event,
    create_option_close_event,
    create_cash_event,
    create_price_update_event,
    get_active_options,
    get_recent_events
)

# Import LLM config module
try:
    from llm.config import get_llm_config, update_config, LLMConfig
    from llm.client import test_connection
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
from .display import (
    console,
    display_portfolio_summary,
    display_holdings,
    display_options,
    display_income,
    display_event_history,
    display_trade_confirmation,
    display_option_confirmation,
    display_cash_confirmation,
    print_success,
    print_error,
    print_info
)
from .prompts import (
    prompt_trade,
    prompt_option,
    prompt_option_close,
    prompt_cash
)

SCRIPT_DIR = Path(__file__).parent.parent.resolve()


def fetch_prices(tickers):
    """Fetch current prices from yfinance."""
    prices = {}
    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            price = t.fast_info.get('lastPrice')
            if price:
                prices[ticker] = round(price, 2)
        except:
            pass
    return prices


def cmd_view(args):
    """View portfolio summary."""
    print_info("Loading portfolio...")

    # Load and reconstruct state
    events_df = load_event_log(SCRIPT_DIR / 'event_log_enhanced.csv')
    state = reconstruct_state(events_df)

    # Fetch live prices unless --no-prices
    if not args.no_prices:
        print_info("Fetching live prices...")
        tickers = list(state['holdings'].keys())
        prices = fetch_prices(tickers)
        if prices:
            state['latest_prices'].update(prices)
            # Save price update to event log
            create_price_update_event(prices)

    # Display based on flags
    if args.holdings:
        display_holdings(state)
    elif args.options:
        display_options(state)
    elif args.income:
        display_income(state)
    else:
        display_portfolio_summary(state)
        display_holdings(state)
        display_options(state)
        display_income(state)


def cmd_trade(args):
    """Execute a trade."""
    if args.action:
        # Command mode
        action = args.action.upper()
        ticker = args.ticker.upper()
        shares = args.shares
        price = args.price
        total = shares * price
        gain_loss = getattr(args, 'gain', 0) or 0
        reason = getattr(args, 'reason', '') or ''
        notes = getattr(args, 'notes', '') or ''

        event_id = create_trade_event(
            action=action,
            ticker=ticker,
            shares=shares,
            price=price,
            total=total,
            gain_loss=gain_loss,
            reason_text=reason,
            notes=notes
        )
        display_trade_confirmation(event_id, action, ticker, shares, price, total)
    else:
        # Interactive mode
        result = prompt_trade()
        if result:
            event_id = create_trade_event(
                action=result['action'],
                ticker=result['ticker'],
                shares=result['shares'],
                price=result['price'],
                total=result['total'],
                gain_loss=result['gain_loss'],
                reason_text=result['reason'],
                notes=result['notes']
            )
            display_trade_confirmation(
                event_id,
                result['action'],
                result['ticker'],
                result['shares'],
                result['price'],
                result['total']
            )


def cmd_option(args):
    """Manage options."""
    if args.option_action == 'open':
        if args.ticker:
            # Command mode
            ticker = args.ticker.upper()
            strategy = f"{args.type.title()}" if args.type else "Secured Put"
            strike = args.strike
            expiration = args.exp
            contracts = args.contracts or 1
            premium = args.premium
            reason = getattr(args, 'reason', '') or ''

            event_id, position_id = create_option_event(ticker, strategy, strike, expiration, contracts, premium, reason_text=reason)
            display_option_confirmation(event_id, ticker, strategy, strike, expiration, premium)
            print_info(f"Position ID: {position_id}")
        else:
            # Interactive mode
            result = prompt_option()
            if result:
                event_id, position_id = create_option_event(
                    result['ticker'],
                    result['strategy'],
                    result['strike'],
                    result['expiration'],
                    result['contracts'],
                    result['premium'],
                    reason_text=result['reason']
                )
                display_option_confirmation(
                    event_id,
                    result['ticker'],
                    result['strategy'],
                    result['strike'],
                    result['expiration'],
                    result['premium']
                )
                print_info(f"Position ID: {position_id}")

    elif args.option_action in ('close', 'expire', 'assign'):
        if args.event_id:
            # Command mode
            event_type = f"OPTION_{args.option_action.upper()}"
            close_cost = getattr(args, 'cost', 0) or 0
            reason = getattr(args, 'reason', '') or ''
            position_id = getattr(args, 'position_id', None)
            event_id = create_option_close_event(
                option_id=args.event_id,
                position_id=position_id,
                close_cost=close_cost,
                event_type=event_type,
                reason_text=reason
            )
            print_success(f"Option {args.event_id} {args.option_action}d. Event ID: {event_id}")
        else:
            # Interactive mode
            active = get_active_options()
            result = prompt_option_close(active)
            if result:
                event_id = create_option_close_event(
                    option_id=result.get('option_id'),
                    position_id=result.get('position_id'),
                    close_cost=result['close_cost'],
                    event_type=result['event_type'],
                    reason_text=result['reason']
                )
                print_success(f"Option closed. Event ID: {event_id}")

    else:
        # No subcommand - interactive mode
        result = prompt_option()
        if result:
            event_id, position_id = create_option_event(
                result['ticker'],
                result['strategy'],
                result['strike'],
                result['expiration'],
                result['contracts'],
                result['premium'],
                reason_text=result['reason']
            )
            display_option_confirmation(
                event_id,
                result['ticker'],
                result['strategy'],
                result['strike'],
                result['expiration'],
                result['premium']
            )
            print_info(f"Position ID: {position_id}")


def cmd_cash(args):
    """Manage cash transactions."""
    if args.cash_action:
        # Command mode
        event_type = args.cash_action.upper()
        amount = args.amount
        description = getattr(args, 'source', '') or getattr(args, 'purpose', '') or ''
        reason = getattr(args, 'reason', '') or ''

        event_id = create_cash_event(event_type, amount, reason_text=reason, description=description)
        display_cash_confirmation(event_id, event_type, amount, description)
    else:
        # Interactive mode
        result = prompt_cash()
        if result:
            event_id = create_cash_event(
                result['type'],
                result['amount'],
                reason_text=result['reason'],
                description=result['description']
            )
            display_cash_confirmation(event_id, result['type'], result['amount'], result['description'])


def cmd_prices(args):
    """Update stock prices."""
    print_info("Fetching prices...")

    # Get holdings from current state
    events_df = load_event_log(SCRIPT_DIR / 'event_log_enhanced.csv')
    state = reconstruct_state(events_df)
    tickers = list(state['holdings'].keys())

    prices = fetch_prices(tickers)

    if prices:
        console.print("\n[bold]Current Prices:[/bold]")
        for ticker, price in sorted(prices.items()):
            console.print(f"  {ticker}: [green]${price:.2f}[/green]")

        if not args.show:
            create_price_update_event(prices)
            print_success("\nPrices saved to event log")
    else:
        print_error("Failed to fetch prices")


def cmd_history(args):
    """View event history."""
    limit = None if args.all else 10
    ticker = getattr(args, 'ticker', None)

    events = get_recent_events(limit=limit or 100, ticker=ticker)

    if not args.all:
        events = events[-10:]

    display_event_history(events)


def cmd_config(args):
    """Manage LLM configuration."""
    if not LLM_AVAILABLE:
        print_error("LLM module not available. Install dependencies: pip install anthropic httpx python-dotenv")
        return

    config = get_llm_config()

    # Handle subcommands
    if args.config_action == 'show' or args.config_action is None:
        # Show current config
        console.print("\n[bold cyan]LLM Configuration[/bold cyan]\n")
        console.print(f"  Enabled:   {'[green]Yes[/green]' if config.enabled else '[red]No[/red]'}")
        console.print(f"  Provider:  [yellow]{config.provider}[/yellow]")

        if config.provider == 'claude':
            key_status = '[green]Set[/green]' if config.anthropic_api_key else '[red]Not set[/red]'
            console.print(f"  API Key:   {key_status}")
            console.print(f"  Model:     {config.claude_model}")
        else:
            console.print(f"  URL:       {config.local_url}")
            console.print(f"  Model:     {config.local_model}")

        console.print(f"  Timeout:   {config.timeout}s")
        console.print(f"  History:   {config.max_history_events} events")

        # Test connection
        console.print("\n[dim]Testing connection...[/dim]")
        success, message = test_connection()
        if success:
            print_success(f"  {message}")
        else:
            print_error(f"  {message}")

    elif args.config_action == 'enable':
        update_config(enabled=True)
        print_success("AI insights enabled")

    elif args.config_action == 'disable':
        update_config(enabled=False)
        print_success("AI insights disabled")

    elif args.config_action == 'provider':
        if args.value:
            if args.value not in ('claude', 'local'):
                print_error("Provider must be 'claude' or 'local'")
                return
            update_config(provider=args.value)
            print_success(f"Provider set to: {args.value}")
        else:
            console.print(f"Current provider: {config.provider}")

    elif args.config_action == 'url':
        if args.value:
            update_config(local_url=args.value)
            print_success(f"Local LLM URL set to: {args.value}")
        else:
            console.print(f"Current URL: {config.local_url}")

    elif args.config_action == 'model':
        if args.value:
            if config.provider == 'claude':
                update_config(claude_model=args.value)
            else:
                update_config(local_model=args.value)
            print_success(f"Model set to: {args.value}")
        else:
            model = config.claude_model if config.provider == 'claude' else config.local_model
            console.print(f"Current model: {model}")

    elif args.config_action == 'test':
        console.print("[dim]Testing LLM connection...[/dim]")
        success, message = test_connection()
        if success:
            print_success(message)
        else:
            print_error(message)
