"""Web UI routes - serves HTML templates."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.routes.state import build_portfolio_state
from api.database import get_all_events, sync_csv_to_db
from cli.events import get_active_options

router = APIRouter(tags=["web"])

# Templates directory
TEMPLATES_DIR = Path(__file__).parent.parent.parent / "web" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def format_event(event: dict) -> dict:
    """Format event for template rendering."""
    return {
        "event_id": event.get('event_id'),
        "timestamp": event.get('timestamp'),
        "event_type": event.get('event_type'),
        "data": json.loads(event.get('data_json', '{}')),
        "reason": json.loads(event.get('reason_json', '{}')),
        "notes": event.get('notes', ''),
        "tags": json.loads(event.get('tags_json', '[]')),
        "affects_cash": bool(event.get('affects_cash')),
        "cash_delta": event.get('cash_delta', 0)
    }


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page."""
    from api.routes.prices import is_market_hours
    from api.database import get_cached_prices

    state = build_portfolio_state()

    # Get market session info
    is_open, market_session = is_market_hours()
    cached_prices = get_cached_prices()

    # Build state object for template
    template_state = {
        "cash": state.get('cash', 0),
        "portfolio_value": sum(
            shares * state.get('latest_prices', {}).get(ticker, 0)
            for ticker, shares in state.get('holdings', {}).items()
            if shares > 0.01  # Filter out dust positions
        ),
        "total_value": 0,
        "holdings": [],
        "active_options": [],
        "income": {
            "trading_gains": state.get('ytd_trading_gains', 0),
            "option_income": state.get('ytd_option_income', 0),
            "dividends": state.get('ytd_dividends', 0),
            "total": state.get('ytd_income', 0),
            "progress_pct": (state.get('ytd_income', 0) / 30000) * 100 if state.get('ytd_income', 0) else 0
        },
        "gains": {
            "realized_gains": state.get('ytd_realized_gains', 0),
            "realized_losses": state.get('ytd_realized_losses', 0),
            "realized_net": state.get('ytd_trading_gains', 0),
            "unrealized_gains": 0,  # Will be calculated from holdings
            "unrealized_losses": 0,
            "unrealized_net": 0
        }
    }

    # Build holdings
    total_holdings_value = 0
    for ticker, shares in state.get('holdings', {}).items():
        if shares > 0.01:  # Filter out dust positions
            price = state.get('latest_prices', {}).get(ticker, 0)
            cost_info = state.get('cost_basis', {}).get(ticker, {})
            market_value = shares * price
            total_cost = cost_info.get('total_cost', 0)
            unrealized_gain = market_value - total_cost
            gain_pct = ((market_value - total_cost) / total_cost * 100) if total_cost > 0 else 0

            # Get session info for this ticker
            price_info = cached_prices.get(ticker, {})
            price_session = price_info.get('session', 'regular')

            template_state["holdings"].append({
                "ticker": ticker,
                "shares": shares,
                "current_price": price,
                "market_value": market_value,
                "cost_basis": total_cost,
                "unrealized_gain": unrealized_gain,
                "unrealized_gain_pct": gain_pct,
                "allocation_pct": 0,
                "price_session": price_session
            })
            total_holdings_value += market_value

    # Calculate allocation percentages and unrealized gains totals
    total_unrealized_gain = 0
    total_unrealized_loss = 0
    for h in template_state["holdings"]:
        h["allocation_pct"] = (h["market_value"] / total_holdings_value * 100) if total_holdings_value > 0 else 0
        if h["unrealized_gain"] >= 0:
            total_unrealized_gain += h["unrealized_gain"]
        else:
            total_unrealized_loss += abs(h["unrealized_gain"])

    # Sort by value
    template_state["holdings"].sort(key=lambda x: x["market_value"], reverse=True)

    template_state["portfolio_value"] = total_holdings_value
    template_state["total_value"] = total_holdings_value + template_state["cash"]

    # Update unrealized gains in state
    template_state["gains"]["unrealized_gains"] = total_unrealized_gain
    template_state["gains"]["unrealized_losses"] = total_unrealized_loss
    template_state["gains"]["unrealized_net"] = total_unrealized_gain - total_unrealized_loss

    # Get active options
    from datetime import datetime
    for opt in state.get('active_options', []):
        exp_date = datetime.strptime(opt.get('expiration', '2099-12-31'), '%Y-%m-%d')
        days_to_expiry = (exp_date - datetime.now()).days

        template_state["active_options"].append({
            "event_id": opt.get('event_id', 0),
            "position_id": opt.get('position_id', ''),
            "ticker": opt.get('ticker', ''),
            "action": opt.get('action', 'SELL'),  # BUY or SELL
            "strategy": opt.get('strategy', ''),
            "strike": opt.get('strike', 0),
            "expiration": opt.get('expiration', ''),
            "contracts": opt.get('contracts', 1),
            "premium": opt.get('total_premium', opt.get('premium', 0)),
            "days_to_expiry": days_to_expiry
        })

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "state": template_state,
        "market_session": market_session,
        "market_open": is_open,
        "active": "dashboard"
    })


@router.get("/trade", response_class=HTMLResponse)
async def trade_page(request: Request):
    """Trade entry page."""
    return templates.TemplateResponse("trade.html", {
        "request": request,
        "active": "trade"
    })


@router.get("/options", response_class=HTMLResponse)
async def options_page(request: Request):
    """Options management page."""
    from datetime import datetime
    options = get_active_options()

    # Add days to expiry
    for opt in options:
        exp_date = datetime.strptime(opt.get('expiration', '2099-12-31'), '%Y-%m-%d')
        opt['days_to_expiry'] = (exp_date - datetime.now()).days
        opt['premium'] = opt.get('total_premium', opt.get('premium', 0))

    return templates.TemplateResponse("options.html", {
        "request": request,
        "active_options": options,
        "active": "options"
    })


@router.get("/cash", response_class=HTMLResponse)
async def cash_page(request: Request):
    """Cash transaction page."""
    state = build_portfolio_state()

    return templates.TemplateResponse("cash.html", {
        "request": request,
        "cash": state.get('cash', 0),
        "active": "cash"
    })


@router.get("/ideas", response_class=HTMLResponse)
async def ideas_page(request: Request, status: str = None):
    """Ideas Lab page - create, view, and manage investment ideas."""
    from api.routes.ideas import get_ideas

    ideas = get_ideas(status_filter=status)

    # Count by status
    status_counts = {
        "seed": len([i for i in ideas if i['status'] == 'seed']),
        "manifested": len([i for i in ideas if i['status'] == 'manifested']),
        "actionable": len([i for i in ideas if i['status'] == 'actionable']),
        "executed": len([i for i in ideas if i['status'] == 'executed']),
        "archived": len([i for i in ideas if i['status'] == 'archived'])
    }

    return templates.TemplateResponse("ideas.html", {
        "request": request,
        "ideas": ideas,
        "status_counts": status_counts,
        "selected_status": status,
        "active": "ideas"
    })


@router.get("/events", response_class=HTMLResponse)
async def events_page(request: Request, event_type: str = None, t: str = None):
    """Event history page.

    Args:
        t: Cache-busting timestamp parameter (ignored but allows cache bypass)
    """
    sync_csv_to_db()
    events = get_all_events(limit=100, event_type=event_type if event_type else None)
    formatted_events = [format_event(e) for e in events]

    # Track which options have been closed
    closed_option_ids = set()
    closed_position_ids = set()

    for e in formatted_events:
        if e['event_type'] in ['OPTION_CLOSE', 'OPTION_EXPIRE', 'OPTION_ASSIGN']:
            if e['data'].get('option_id'):
                closed_option_ids.add(e['data']['option_id'])
            if e['data'].get('position_id'):
                closed_position_ids.add(e['data']['position_id'])

    # Mark closed options in OPTION_OPEN events (only if status not already set)
    for e in formatted_events:
        if e['event_type'] == 'OPTION_OPEN':
            # Don't overwrite if status was manually set in CSV
            if 'status' not in e['data']:
                is_closed = (
                    e['event_id'] in closed_option_ids or
                    e['data'].get('position_id') in closed_position_ids
                )
                if is_closed:
                    e['data']['status'] = 'CLOSED'
                else:
                    e['data']['status'] = 'OPEN'

    # Check if this is an HTMX request - return only the table partial
    is_htmx = request.headers.get("HX-Request") == "true"

    if is_htmx:
        response = templates.TemplateResponse("partials/events_table.html", {
            "request": request,
            "events": formatted_events
        })
    else:
        response = templates.TemplateResponse("events.html", {
            "request": request,
            "events": formatted_events,
            "selected_type": event_type,
            "active": "events"
        })

    # Prevent caching to ensure fresh data after edits
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    return response


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Settings page for backup/restore and LLM configuration."""
    import json
    import os

    # Read directly from llm_config.json
    config_file = Path(__file__).parent.parent.parent / "llm_config.json"
    try:
        with open(config_file) as f:
            config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        config = {
            "provider": "local",
            "enabled": True,
            "claude_model": "claude-sonnet-4-20250514",
            "local_url": "http://192.168.50.10:1234/v1",
            "local_model": "meta/llama-3.3-70b",
            "timeout": 180,
            "max_history_events": 10
        }

    # Add API key status
    config["has_api_key"] = bool(os.getenv("ANTHROPIC_API_KEY"))

    return templates.TemplateResponse("settings.html", {
        "request": request,
        "llm_config": config,
        "active": "settings"
    })


@router.get("/docs", response_class=HTMLResponse)
async def docs_page(request: Request, doc: str = "readme"):
    """Documentation viewer page."""
    PROJECT_ROOT = Path(__file__).parent.parent.parent

    # Map doc names to file paths
    doc_files = {
        "readme": PROJECT_ROOT / "README.md",
        "changelog": PROJECT_ROOT / "CHANGELOG.md",
        "claude": PROJECT_ROOT / "CLAUDE.md",
        "event-sourcing": PROJECT_ROOT / "docs" / "README_Event_Sourcing.md",
        "ai-integration": PROJECT_ROOT / "docs" / "README_AI_Agent_Integration.md",
        "specification": PROJECT_ROOT / "docs" / "PROJECT_SPECIFICATION.md",
    }

    # Get selected doc content
    doc_path = doc_files.get(doc, doc_files["readme"])
    content = ""
    if doc_path.exists():
        content = doc_path.read_text()

    # Get list of available docs
    available_docs = []
    for name, path in doc_files.items():
        if path.exists():
            available_docs.append({
                "id": name,
                "name": name.replace("-", " ").title(),
                "path": str(path.name)
            })

    return templates.TemplateResponse("docs.html", {
        "request": request,
        "content": content,
        "selected_doc": doc,
        "available_docs": available_docs,
        "active": "docs"
    })
