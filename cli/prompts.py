"""Interactive prompts for CLI."""

from rich.console import Console
from rich.prompt import Prompt, Confirm, FloatPrompt, IntPrompt
from .display import print_error, print_warning

console = Console()


def prompt_reason(action_type="this action"):
    """Prompt for reason - required for all entries."""
    console.print(f"\n[bold yellow]Why are you making {action_type}?[/bold yellow]")
    console.print("[dim]This reason will be logged for future learning and AI analysis.[/dim]")
    reason = Prompt.ask("Reason (required)")
    while not reason.strip():
        print_error("Reason is required for learning purposes")
        reason = Prompt.ask("Reason")
    return reason.strip()


def prompt_trade():
    """Interactive prompt for trade entry."""
    console.print("\n[bold cyan]Enter Trade Details[/bold cyan]\n")

    action = Prompt.ask(
        "Action",
        choices=["buy", "sell"],
        default="buy"
    ).upper()

    ticker = Prompt.ask("Ticker symbol").upper()
    if not ticker:
        print_error("Ticker is required")
        return None

    shares = IntPrompt.ask("Number of shares")
    if shares <= 0:
        print_error("Shares must be positive")
        return None

    price = FloatPrompt.ask("Price per share")
    if price <= 0:
        print_error("Price must be positive")
        return None

    total = shares * price
    console.print(f"\n[dim]Total: ${total:,.2f}[/dim]")

    gain_loss = 0
    if action == "SELL":
        gain_loss = FloatPrompt.ask("Gain/Loss on this sale", default=0.0)

    reason = prompt_reason(f"this {action.lower()}")

    notes = Prompt.ask("Additional notes (optional)", default="")

    if Confirm.ask(f"\nConfirm {action} {shares} {ticker} @ ${price:.2f}?"):
        return {
            "action": action,
            "ticker": ticker,
            "shares": shares,
            "price": price,
            "total": total,
            "gain_loss": gain_loss,
            "reason": reason,
            "notes": notes
        }

    return None


def prompt_option():
    """Interactive prompt for option entry."""
    console.print("\n[bold yellow]Enter Option Details[/bold yellow]\n")

    ticker = Prompt.ask("Underlying ticker").upper()
    if not ticker:
        print_error("Ticker is required")
        return None

    strategy = Prompt.ask(
        "Strategy",
        choices=["secured put", "covered call", "put", "call"],
        default="secured put"
    ).title()

    strike = FloatPrompt.ask("Strike price")
    if strike <= 0:
        print_error("Strike must be positive")
        return None

    expiration = Prompt.ask("Expiration date (YYYY-MM-DD)")

    contracts = IntPrompt.ask("Number of contracts", default=1)
    if contracts <= 0:
        print_error("Contracts must be positive")
        return None

    premium = FloatPrompt.ask("Total premium received")
    if premium <= 0:
        print_error("Premium must be positive")
        return None

    console.print(f"\n[dim]Premium per contract: ${premium / contracts:,.2f}[/dim]")

    reason = prompt_reason("this option trade")

    if Confirm.ask(f"\nConfirm {strategy} on {ticker} @ ${strike} exp {expiration}?"):
        return {
            "ticker": ticker,
            "strategy": strategy,
            "strike": strike,
            "expiration": expiration,
            "contracts": contracts,
            "premium": premium,
            "reason": reason
        }

    return None


def prompt_option_close(active_options):
    """Interactive prompt for closing an option."""
    if not active_options:
        print_warning("No active options to close")
        return None

    console.print("\n[bold yellow]Close Option Position[/bold yellow]\n")

    console.print("Active options:")
    for opt in active_options:
        premium = opt.get('total_premium', opt.get('premium', 0))
        pos_id = opt.get('position_id', '')
        id_display = pos_id if pos_id else str(opt.get('event_id'))
        console.print(f"  [{id_display}] {opt['ticker']} {opt['strategy']} ${opt['strike']} exp {opt['expiration']} [green](${premium:,.0f} premium)[/green]")

    console.print()
    identifier = Prompt.ask("Position ID or Event ID to close")

    # Find the option by position_id or event_id
    selected_opt = None
    for opt in active_options:
        if opt.get('position_id') == identifier or str(opt.get('event_id')) == identifier:
            selected_opt = opt
            break

    if selected_opt is None:
        print_error(f"Option {identifier} not found")
        return None

    original_premium = selected_opt.get('total_premium', selected_opt.get('premium', 0))
    console.print(f"\n[dim]Original premium received: ${original_premium:,.0f}[/dim]")

    close_type = Prompt.ask(
        "Close type",
        choices=["close", "expire", "assign"],
        default="expire"
    ).upper()

    close_cost = 0.0
    if close_type == "CLOSE":
        close_cost = FloatPrompt.ask("Cost to buy back (close cost)", default=0.0)
        profit = original_premium - close_cost
        console.print(f"\n[bold]Calculated gain: ${original_premium:,.0f} - ${close_cost:,.0f} = [green]${profit:,.0f}[/green][/bold]")
    elif close_type == "EXPIRE":
        profit = original_premium
        console.print(f"\n[bold]Full premium kept: [green]${profit:,.0f}[/green][/bold]")
    else:
        profit = original_premium
        console.print(f"\n[dim]Assignment - shares will change hands[/dim]")

    reason = prompt_reason("closing this option")

    event_type = f"OPTION_{close_type}"

    pos_id = selected_opt.get('position_id', '')
    display_id = pos_id if pos_id else str(selected_opt.get('event_id'))
    if Confirm.ask(f"\nConfirm {close_type} option {display_id}?"):
        return {
            "option_id": selected_opt.get('event_id'),
            "position_id": pos_id,
            "event_type": event_type,
            "close_cost": close_cost,
            "reason": reason
        }

    return None


def prompt_cash():
    """Interactive prompt for cash transaction."""
    console.print("\n[bold green]Cash Transaction[/bold green]\n")

    action = Prompt.ask(
        "Transaction type",
        choices=["deposit", "withdraw"],
        default="deposit"
    ).upper()

    amount = FloatPrompt.ask("Amount")
    if amount <= 0:
        print_error("Amount must be positive")
        return None

    reason = prompt_reason(f"this {action.lower()}")

    if action == "DEPOSIT":
        source = Prompt.ask("Source (optional)", default="")
    else:
        source = Prompt.ask("Purpose (optional)", default="")

    if Confirm.ask(f"\nConfirm {action} ${amount:,.2f}?"):
        return {
            "type": "DEPOSIT" if action == "DEPOSIT" else "WITHDRAWAL",
            "amount": amount,
            "reason": reason,
            "description": source
        }

    return None
