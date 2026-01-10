"""Display formatting using Rich library."""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn
from rich.layout import Layout
from rich import box
import json

console = Console()


def print_success(message):
    console.print(f"[green]{message}[/green]")


def print_error(message):
    console.print(f"[red]{message}[/red]")


def print_warning(message):
    console.print(f"[yellow]{message}[/yellow]")


def print_info(message):
    console.print(f"[cyan]{message}[/cyan]")


def display_portfolio_summary(state):
    """Display full portfolio summary with Rich formatting."""
    console.print()

    # Header
    console.print(Panel.fit(
        f"[bold blue]Portfolio Summary[/bold blue]\n[dim]As of {state['as_of']}[/dim]",
        border_style="blue"
    ))

    # Cash & Value Summary
    cash = state['cash']
    portfolio_value = sum(
        state['holdings'].get(t, 0) * state['latest_prices'].get(t, 0)
        for t in state['holdings']
    )
    total_value = cash + portfolio_value

    summary_table = Table(show_header=False, box=box.ROUNDED, border_style="cyan")
    summary_table.add_column("Metric", style="bold")
    summary_table.add_column("Value", justify="right")

    summary_table.add_row("Cash", f"[green]${cash:,.2f}[/green]")
    summary_table.add_row("Portfolio Value", f"[blue]${portfolio_value:,.2f}[/blue]")
    summary_table.add_row("Total Value", f"[bold white]${total_value:,.2f}[/bold white]")

    console.print(summary_table)
    console.print()


def display_holdings(state):
    """Display holdings table."""
    table = Table(title="Holdings", box=box.ROUNDED, border_style="green")

    table.add_column("Ticker", style="bold cyan")
    table.add_column("Shares", justify="right")
    table.add_column("Price", justify="right")
    table.add_column("Value", justify="right")
    table.add_column("Cost Basis", justify="right")
    table.add_column("Gain/Loss", justify="right")
    table.add_column("%", justify="right")

    for ticker, shares in sorted(state['holdings'].items()):
        if shares <= 0:
            continue

        price = state['latest_prices'].get(ticker, 0)
        value = shares * price
        cost_info = state['cost_basis'].get(ticker, {})
        avg_cost = cost_info.get('avg_price', 0)
        total_cost = shares * avg_cost
        gain = value - total_cost
        gain_pct = (gain / total_cost * 100) if total_cost > 0 else 0

        gain_color = "green" if gain >= 0 else "red"
        gain_str = f"[{gain_color}]${gain:,.0f} ({gain_pct:+.1f}%)[/{gain_color}]"

        table.add_row(
            ticker,
            f"{shares:,}",
            f"${price:.2f}",
            f"${value:,.0f}",
            f"${avg_cost:.2f}",
            gain_str,
            f"{value / sum(state['holdings'].get(t, 0) * state['latest_prices'].get(t, 0) for t in state['holdings']) * 100:.1f}%" if sum(state['holdings'].get(t, 0) * state['latest_prices'].get(t, 0) for t in state['holdings']) > 0 else "0%"
        )

    console.print(table)
    console.print()


def display_options(state):
    """Display active options."""
    if not state.get('active_options'):
        console.print("[dim]No active options[/dim]")
        return

    table = Table(title="Active Options", box=box.ROUNDED, border_style="yellow")

    table.add_column("ID", style="dim")
    table.add_column("Ticker", style="bold cyan")
    table.add_column("Strategy")
    table.add_column("Strike", justify="right")
    table.add_column("Expiration")
    table.add_column("Premium", justify="right", style="green")

    for opt in state['active_options']:
        premium = opt.get('total_premium', opt.get('premium', 0))
        table.add_row(
            str(opt.get('event_id', '')),
            opt.get('ticker', '?'),
            opt.get('strategy', '?'),
            f"${opt.get('strike', 0):.2f}",
            opt.get('expiration', '?'),
            f"${premium:,.0f}"
        )

    console.print(table)
    console.print()


def display_income(state):
    """Display YTD income with progress bar."""
    goal = 30000
    ytd_income = state.get('ytd_income', 0)
    progress_pct = min(ytd_income / goal * 100, 100)

    console.print(Panel.fit("[bold]YTD Income Progress[/bold]", border_style="green"))

    # Progress bar
    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=40),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("${task.completed:,.0f} / ${task.total:,.0f}"),
        console=console,
        transient=False
    ) as progress:
        task = progress.add_task("Income Goal", total=goal, completed=ytd_income)
        progress.refresh()

    console.print()

    # Breakdown table
    table = Table(show_header=False, box=box.SIMPLE)
    table.add_column("Source", style="bold")
    table.add_column("Amount", justify="right")

    table.add_row("Trading Gains", f"[green]${state.get('ytd_trading_gains', 0):,.2f}[/green]")
    table.add_row("Options Income", f"[green]${state.get('ytd_option_income', 0):,.2f}[/green]")
    table.add_row("Dividends", f"[green]${state.get('ytd_dividends', 0):,.2f}[/green]")
    table.add_row("", "")
    table.add_row("[bold]Total[/bold]", f"[bold green]${ytd_income:,.2f}[/bold green]")

    console.print(table)
    console.print()


def display_event_history(events):
    """Display recent events."""
    table = Table(title="Recent Events", box=box.ROUNDED)

    table.add_column("ID", style="dim")
    table.add_column("Date")
    table.add_column("Type", style="bold")
    table.add_column("Details")
    table.add_column("Cash", justify="right")

    for event in events:
        data = json.loads(event['data_json']) if isinstance(event['data_json'], str) else event['data_json']

        # Format details based on event type
        event_type = event['event_type']
        if event_type == 'TRADE':
            details = f"{data['action']} {data.get('shares', '?')} {data['ticker']} @ ${data.get('price', 0):.2f}"
        elif event_type == 'OPTION_OPEN':
            details = f"{data['strategy']} {data['ticker']} ${data['strike']} exp {data['expiration']}"
        elif event_type == 'PRICE_UPDATE':
            details = f"Updated {len(data.get('prices', {}))} prices"
        elif event_type in ('DEPOSIT', 'WITHDRAWAL'):
            details = f"${data['amount']:,.0f}"
        else:
            details = str(data)[:40]

        cash_delta = event['cash_delta']
        cash_str = f"[green]+${cash_delta:,.0f}[/green]" if cash_delta > 0 else f"[red]-${abs(cash_delta):,.0f}[/red]" if cash_delta < 0 else ""

        table.add_row(
            str(event['event_id']),
            event['timestamp'][:10],
            event_type,
            details,
            cash_str
        )

    console.print(table)


def display_trade_confirmation(event_id, action, ticker, shares, price, total):
    """Display trade confirmation."""
    color = "green" if action.upper() == "BUY" else "red"
    console.print(Panel.fit(
        f"[bold {color}]{action.upper()}[/bold {color}] {shares} shares of [bold]{ticker}[/bold]\n"
        f"Price: ${price:.2f}\n"
        f"Total: ${total:,.2f}\n"
        f"[dim]Event ID: {event_id}[/dim]",
        title="Trade Recorded",
        border_style=color
    ))


def display_option_confirmation(event_id, ticker, strategy, strike, expiration, premium):
    """Display option confirmation."""
    console.print(Panel.fit(
        f"[bold yellow]{strategy}[/bold yellow] on [bold]{ticker}[/bold]\n"
        f"Strike: ${strike:.2f}\n"
        f"Expiration: {expiration}\n"
        f"Premium: [green]${premium:,.2f}[/green]\n"
        f"[dim]Event ID: {event_id}[/dim]",
        title="Option Recorded",
        border_style="yellow"
    ))


def display_cash_confirmation(event_id, event_type, amount, description):
    """Display cash transaction confirmation."""
    color = "green" if event_type.upper() == "DEPOSIT" else "red"
    sign = "+" if event_type.upper() == "DEPOSIT" else "-"
    console.print(Panel.fit(
        f"[bold {color}]{event_type.upper()}[/bold {color}]\n"
        f"Amount: [{color}]{sign}${amount:,.2f}[/{color}]\n"
        f"{description}\n"
        f"[dim]Event ID: {event_id}[/dim]",
        title="Cash Transaction Recorded",
        border_style=color
    ))
