"""Ideas API - Seed ideas that manifest into actionable trades."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from pathlib import Path
import json
import uuid
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.database import get_db, get_all_events, sync_csv_to_db
from llm.config import get_llm_config
from llm.client import LLMClient

router = APIRouter(prefix="/api/ideas", tags=["ideas"])

CSV_PATH = Path(__file__).parent.parent.parent / "data" / "event_log_enhanced.csv"


class IdeaSeed(BaseModel):
    """A seed idea to explore and manifest into actions."""
    title: str
    description: str
    tickers: list[str] = []
    category: str = "opportunity"  # opportunity, income, hedge, growth, experiment
    priority: str = "medium"  # low, medium, high


class IdeaAction(BaseModel):
    """An action to execute for an idea."""
    action_type: str  # sell_put, sell_call, buy_stock, research, etc.
    ticker: str
    details: dict = {}
    approved: bool = False


class ManifestRequest(BaseModel):
    """Request to manifest an idea into concrete actions."""
    context: str = ""  # Additional context for the LLM


def get_next_event_id():
    """Get the next event ID from CSV."""
    import pandas as pd
    if CSV_PATH.exists():
        df = pd.read_csv(CSV_PATH)
        return int(df['event_id'].max()) + 1 if len(df) > 0 else 1
    return 1


def append_event_to_csv(event_id, event_type, data, reason=None, notes="", affects_cash=False, cash_delta=0):
    """Append a new event to the CSV file."""
    import pandas as pd

    new_row = {
        'event_id': event_id,
        'timestamp': datetime.now().isoformat(),
        'event_type': event_type,
        'data_json': json.dumps(data),
        'reason_json': json.dumps(reason or {}),
        'notes': notes,
        'tags_json': '[]',
        'affects_cash': affects_cash,
        'cash_delta': cash_delta
    }

    if CSV_PATH.exists():
        df = pd.read_csv(CSV_PATH)
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    else:
        df = pd.DataFrame([new_row])

    df.to_csv(CSV_PATH, index=False)
    sync_csv_to_db()
    return event_id


def get_ideas(status_filter: str = None) -> list:
    """Get all ideas from events, reconstructing their state."""
    events = get_all_events(limit=1000)

    ideas = {}
    actions_by_idea = {}

    for event in events:
        if event['event_type'] == 'IDEA_SEED':
            data = json.loads(event['data_json'])
            idea_id = data.get('idea_id')
            ideas[idea_id] = {
                'id': idea_id,
                'event_id': event['event_id'],
                'created_at': event['timestamp'],
                'title': data.get('title'),
                'description': data.get('description'),
                'tickers': data.get('tickers', []),
                'category': data.get('category', 'opportunity'),
                'priority': data.get('priority', 'medium'),
                'status': data.get('status', 'seed'),
                'actions': [],
                'manifested_at': None,
                'executed_at': None
            }
            actions_by_idea[idea_id] = []

        elif event['event_type'] == 'IDEA_ACTION':
            data = json.loads(event['data_json'])
            idea_id = data.get('idea_id')
            if idea_id not in actions_by_idea:
                actions_by_idea[idea_id] = []

            action = {
                'action_id': data.get('action_id'),
                'event_id': event['event_id'],
                'created_at': event['timestamp'],
                'action_type': data.get('action_type'),
                'ticker': data.get('ticker'),
                'details': data.get('details', {}),
                'llm_generated': data.get('llm_generated', False),
                'approved': data.get('approved', False),
                'executed': data.get('executed', False),
                'executed_event_id': data.get('executed_event_id'),
                'reasoning': data.get('reasoning', '')
            }
            actions_by_idea[idea_id].append(action)

        elif event['event_type'] == 'IDEA_STATUS':
            data = json.loads(event['data_json'])
            idea_id = data.get('idea_id')
            if idea_id in ideas:
                ideas[idea_id]['status'] = data.get('status')
                if data.get('status') == 'manifested':
                    ideas[idea_id]['manifested_at'] = event['timestamp']
                elif data.get('status') == 'executed':
                    ideas[idea_id]['executed_at'] = event['timestamp']

    # Attach actions to ideas
    for idea_id, idea in ideas.items():
        idea['actions'] = actions_by_idea.get(idea_id, [])

    result = list(ideas.values())
    result.sort(key=lambda x: x['created_at'], reverse=True)

    if status_filter:
        result = [i for i in result if i['status'] == status_filter]

    return result


def get_idea_by_id(idea_id: str) -> dict:
    """Get a single idea by its ID."""
    ideas = get_ideas()
    for idea in ideas:
        if idea['id'] == idea_id:
            return idea
    return None


@router.get("/")
async def list_ideas(status: str = None):
    """List all ideas, optionally filtered by status."""
    ideas = get_ideas(status_filter=status)
    return {
        "ideas": ideas,
        "count": len(ideas),
        "statuses": {
            "seed": len([i for i in ideas if i['status'] == 'seed']),
            "manifested": len([i for i in ideas if i['status'] == 'manifested']),
            "actionable": len([i for i in ideas if i['status'] == 'actionable']),
            "executed": len([i for i in ideas if i['status'] == 'executed']),
            "archived": len([i for i in ideas if i['status'] == 'archived'])
        }
    }


@router.get("/as-mods")
async def list_ideas_as_mods():
    """Get all ideas formatted as toggleable modifications for projections."""
    mods = get_ideas_as_mods()
    return {
        "mods": mods,
        "count": len(mods),
        "categories": {
            "income": len([m for m in mods if m['category'] == 'income']),
            "growth": len([m for m in mods if m['category'] == 'growth']),
            "opportunity": len([m for m in mods if m['category'] == 'opportunity']),
            "hedge": len([m for m in mods if m['category'] == 'hedge'])
        }
    }


@router.get("/{idea_id}")
async def get_idea(idea_id: str):
    """Get a specific idea with all its actions."""
    idea = get_idea_by_id(idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")
    return idea


@router.post("/")
async def create_idea(idea: IdeaSeed):
    """Create a new seed idea."""
    idea_id = str(uuid.uuid4())[:8]
    event_id = get_next_event_id()

    data = {
        'idea_id': idea_id,
        'title': idea.title,
        'description': idea.description,
        'tickers': [t.upper() for t in idea.tickers],
        'category': idea.category,
        'priority': idea.priority,
        'status': 'seed'
    }

    append_event_to_csv(
        event_id=event_id,
        event_type='IDEA_SEED',
        data=data,
        notes=f"New idea: {idea.title}"
    )

    return {
        "success": True,
        "idea_id": idea_id,
        "event_id": event_id,
        "message": f"Idea '{idea.title}' created successfully"
    }


@router.post("/{idea_id}/manifest")
async def manifest_idea(idea_id: str, request: ManifestRequest = None):
    """Use LLM to generate concrete action items for an idea."""
    idea = get_idea_by_id(idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")

    config = get_llm_config()
    if not config.enabled:
        raise HTTPException(status_code=400, detail="LLM is disabled")

    # Build context for LLM
    tickers_str = ", ".join(idea['tickers']) if idea['tickers'] else "No specific tickers"

    # Get current portfolio state for context
    from api.routes.state import build_portfolio_state
    state = build_portfolio_state()

    cash = state.get('cash', 0)
    holdings = state.get('holdings', {})
    active_options = state.get('active_options', [])

    prompt = f"""You are a financial advisor helping manifest a trading idea into concrete, actionable steps.

## The Idea
**Title**: {idea['title']}
**Description**: {idea['description']}
**Category**: {idea['category']}
**Tickers**: {tickers_str}
**Priority**: {idea['priority']}

## Current Portfolio Context
- Available Cash: ${cash:,.0f}
- Current Holdings: {json.dumps(holdings, indent=2)}
- Active Options: {len(active_options)} positions

## Additional Context
{request.context if request and request.context else "None provided"}

## Your Task
Generate 2-5 specific, actionable trading recommendations to implement this idea.
For each action, provide:
1. Action type (sell_put, sell_call, buy_stock, sell_stock, research)
2. Ticker symbol
3. Specific details (strike price, expiration, quantity, etc.)
4. Brief reasoning (1-2 sentences)

Focus on the income-generation strategy: selling cash-secured puts on stocks the user is willing to own.

Respond in this exact JSON format:
{{
    "summary": "Brief summary of the manifestation strategy",
    "actions": [
        {{
            "action_type": "sell_put",
            "ticker": "TSLA",
            "details": {{
                "strike": 400,
                "expiration": "2026-02-21",
                "contracts": 1,
                "estimated_premium": 500
            }},
            "reasoning": "TSLA is trading at X, selling a put at 400 strike gives Y% downside protection while generating premium."
        }}
    ],
    "risks": "Key risks to consider",
    "timeline": "Suggested execution timeline"
}}"""

    try:
        import time
        start_time = time.time()

        if config.provider == "claude":
            import anthropic
            client = anthropic.Anthropic(api_key=config.anthropic_api_key)
            response = client.messages.create(
                model=config.claude_model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            response_text = response.content[0].text
        else:
            import httpx
            api_response = httpx.post(
                f"{config.local_url}/chat/completions",
                json={
                    "model": config.local_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 2000,
                    "temperature": 0.7
                },
                timeout=config.timeout
            )
            api_response.raise_for_status()
            result = api_response.json()
            response_text = result["choices"][0]["message"]["content"]

        # Parse JSON from response
        import re
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if not json_match:
            raise ValueError("No JSON found in response")

        manifest_data = json.loads(json_match.group())

        # Create action events for each generated action
        actions_created = []
        for action in manifest_data.get('actions', []):
            action_id = str(uuid.uuid4())[:8]
            event_id = get_next_event_id()

            action_data = {
                'idea_id': idea_id,
                'action_id': action_id,
                'action_type': action.get('action_type'),
                'ticker': action.get('ticker', '').upper(),
                'details': action.get('details', {}),
                'reasoning': action.get('reasoning', ''),
                'llm_generated': True,
                'approved': False,
                'executed': False
            }

            append_event_to_csv(
                event_id=event_id,
                event_type='IDEA_ACTION',
                data=action_data,
                notes=f"LLM-generated action for idea {idea_id}"
            )

            actions_created.append({
                'action_id': action_id,
                'event_id': event_id,
                **action
            })

        # Update idea status to manifested
        status_event_id = get_next_event_id()
        append_event_to_csv(
            event_id=status_event_id,
            event_type='IDEA_STATUS',
            data={'idea_id': idea_id, 'status': 'manifested'},
            notes=f"Idea manifested with {len(actions_created)} actions"
        )

        return {
            "success": True,
            "idea_id": idea_id,
            "summary": manifest_data.get('summary', ''),
            "actions": actions_created,
            "risks": manifest_data.get('risks', ''),
            "timeline": manifest_data.get('timeline', ''),
            "action_count": len(actions_created)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Manifestation failed: {str(e)}")


@router.post("/{idea_id}/actions/{action_id}/approve")
async def approve_action(idea_id: str, action_id: str, feedback: str = None):
    """Approve an action for execution."""
    idea = get_idea_by_id(idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")

    # Find the action
    action = None
    for a in idea.get('actions', []):
        if a['action_id'] == action_id:
            action = a
            break

    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    # Create approval event
    event_id = get_next_event_id()
    approval_data = {
        'idea_id': idea_id,
        'action_id': action_id,
        'action_type': action['action_type'],
        'ticker': action['ticker'],
        'details': action['details'],
        'reasoning': action.get('reasoning', ''),
        'llm_generated': action.get('llm_generated', False),
        'approved': True,
        'executed': False,
        'user_feedback': feedback
    }

    append_event_to_csv(
        event_id=event_id,
        event_type='IDEA_ACTION',
        data=approval_data,
        notes=f"Action {action_id} approved"
    )

    return {
        "success": True,
        "action_id": action_id,
        "message": "Action approved and ready for execution"
    }


@router.post("/{idea_id}/actions/{action_id}/reject")
async def reject_action(idea_id: str, action_id: str, reason: str = None):
    """Reject an action."""
    idea = get_idea_by_id(idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")

    event_id = get_next_event_id()
    rejection_data = {
        'idea_id': idea_id,
        'action_id': action_id,
        'approved': False,
        'rejected': True,
        'rejection_reason': reason
    }

    append_event_to_csv(
        event_id=event_id,
        event_type='IDEA_ACTION',
        data=rejection_data,
        notes=f"Action {action_id} rejected: {reason or 'No reason given'}"
    )

    return {
        "success": True,
        "action_id": action_id,
        "message": "Action rejected"
    }


@router.post("/{idea_id}/actions/{action_id}/execute")
async def execute_action(idea_id: str, action_id: str):
    """Execute an approved action by creating the actual trade/option event."""
    idea = get_idea_by_id(idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")

    # Find the approved action
    action = None
    for a in idea.get('actions', []):
        if a['action_id'] == action_id and a.get('approved'):
            action = a
            break

    if not action:
        raise HTTPException(status_code=404, detail="Approved action not found")

    # Create the actual trade event based on action type
    event_id = get_next_event_id()

    if action['action_type'] == 'sell_put':
        details = action['details']
        trade_data = {
            'ticker': action['ticker'],
            'strategy': 'put',
            'strike': details.get('strike'),
            'expiration': details.get('expiration'),
            'contracts': details.get('contracts', 1),
            'premium': details.get('estimated_premium', 0),
            'total_premium': details.get('estimated_premium', 0) * details.get('contracts', 1),
            'uuid': str(uuid.uuid4())[:8],
            'from_idea': idea_id,
            'from_action': action_id
        }

        append_event_to_csv(
            event_id=event_id,
            event_type='OPTION_OPEN',
            data=trade_data,
            reason={'explanation': f"Executed from idea: {idea['title']}", 'from_idea': idea_id},
            affects_cash=True,
            cash_delta=trade_data['total_premium']
        )

    elif action['action_type'] == 'sell_call':
        details = action['details']
        trade_data = {
            'ticker': action['ticker'],
            'strategy': 'call',
            'strike': details.get('strike'),
            'expiration': details.get('expiration'),
            'contracts': details.get('contracts', 1),
            'premium': details.get('estimated_premium', 0),
            'total_premium': details.get('estimated_premium', 0) * details.get('contracts', 1),
            'uuid': str(uuid.uuid4())[:8],
            'from_idea': idea_id,
            'from_action': action_id
        }

        append_event_to_csv(
            event_id=event_id,
            event_type='OPTION_OPEN',
            data=trade_data,
            reason={'explanation': f"Executed from idea: {idea['title']}", 'from_idea': idea_id},
            affects_cash=True,
            cash_delta=trade_data['total_premium']
        )

    elif action['action_type'] == 'buy_stock':
        details = action['details']
        trade_data = {
            'ticker': action['ticker'],
            'action': 'BUY',
            'shares': details.get('shares', 1),
            'price': details.get('price', 0),
            'total': details.get('shares', 1) * details.get('price', 0),
            'from_idea': idea_id,
            'from_action': action_id
        }

        append_event_to_csv(
            event_id=event_id,
            event_type='TRADE',
            data=trade_data,
            reason={'explanation': f"Executed from idea: {idea['title']}", 'from_idea': idea_id},
            affects_cash=True,
            cash_delta=-trade_data['total']
        )

    else:
        # For research or other action types, just mark as executed
        pass

    # Mark action as executed
    exec_event_id = get_next_event_id()
    exec_data = {
        'idea_id': idea_id,
        'action_id': action_id,
        'executed': True,
        'executed_event_id': event_id
    }

    append_event_to_csv(
        event_id=exec_event_id,
        event_type='IDEA_ACTION',
        data=exec_data,
        notes=f"Action {action_id} executed as event {event_id}"
    )

    return {
        "success": True,
        "action_id": action_id,
        "executed_event_id": event_id,
        "message": f"Action executed successfully as event #{event_id}"
    }


@router.post("/{idea_id}/archive")
async def archive_idea(idea_id: str):
    """Archive an idea."""
    idea = get_idea_by_id(idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")

    event_id = get_next_event_id()
    append_event_to_csv(
        event_id=event_id,
        event_type='IDEA_STATUS',
        data={'idea_id': idea_id, 'status': 'archived'},
        notes=f"Idea archived"
    )

    return {
        "success": True,
        "idea_id": idea_id,
        "message": "Idea archived"
    }


@router.delete("/{idea_id}")
async def delete_idea(idea_id: str):
    """Soft-delete an idea by archiving it."""
    return await archive_idea(idea_id)


def get_ideas_as_mods() -> list:
    """Get all active ideas formatted as toggleable modifications for projections.

    Returns list of dicts with:
    - id: idea_id
    - name: idea title
    - description: idea description
    - tickers: related tickers
    - mod_type: type of modification (income_strategy, growth_strategy, etc.)
    - projected_impact: estimated impact on projections
    - actions: concrete actions that would be applied
    """
    ideas = get_ideas()
    mods = []

    for idea in ideas:
        # Skip archived ideas
        if idea.get('status') == 'archived':
            continue

        # Build modification based on idea category and actions
        mod = {
            'id': idea['id'],
            'name': idea['title'],
            'description': idea['description'],
            'tickers': idea.get('tickers', []),
            'category': idea.get('category', 'opportunity'),
            'priority': idea.get('priority', 'medium'),
            'status': idea.get('status', 'seed'),
            'enabled': False,  # Default to not enabled in projections
            'actions': [],
            'projected_impact': {}
        }

        # Calculate projected impact based on actions
        if idea.get('actions'):
            total_premium = 0
            total_cost = 0
            tickers_affected = set()

            for action in idea['actions']:
                action_type = action.get('action_type', '')
                details = action.get('details', {})
                ticker = action.get('ticker', '')

                if ticker:
                    tickers_affected.add(ticker)

                if action_type in ['sell_put', 'sell_call']:
                    premium = details.get('estimated_premium', 0) * details.get('contracts', 1)
                    total_premium += premium
                    mod['actions'].append({
                        'type': action_type,
                        'ticker': ticker,
                        'strike': details.get('strike'),
                        'premium': premium,
                        'contracts': details.get('contracts', 1)
                    })
                elif action_type == 'buy_stock':
                    cost = details.get('price', 0) * details.get('shares', 0)
                    total_cost += cost
                    mod['actions'].append({
                        'type': action_type,
                        'ticker': ticker,
                        'shares': details.get('shares'),
                        'cost': cost
                    })

            mod['projected_impact'] = {
                'premium_income': total_premium,
                'capital_required': total_cost,
                'tickers_affected': list(tickers_affected),
                'net_cash_impact': total_premium - total_cost
            }
        else:
            # For unmanifestedideas, estimate based on category
            if idea.get('category') == 'income':
                mod['projected_impact'] = {
                    'type': 'income_boost',
                    'estimated_annual': 5000,  # Placeholder
                    'confidence': 'low'
                }
            elif idea.get('category') == 'growth':
                mod['projected_impact'] = {
                    'type': 'growth_boost',
                    'estimated_multiplier': 1.1,
                    'confidence': 'low'
                }

        mods.append(mod)

    return mods


def apply_idea_to_projection(idea_id: str, projection_context: dict) -> dict:
    """Apply an idea's effects to a projection context.

    Args:
        idea_id: The idea to apply
        projection_context: Current projection context dict with holdings, cash, etc.

    Returns:
        Modified projection context with idea effects applied
    """
    idea = get_idea_by_id(idea_id)
    if not idea:
        return projection_context

    context = projection_context.copy()

    # Apply income from options strategies
    for action in idea.get('actions', []):
        action_type = action.get('action_type', '')
        details = action.get('details', {})

        if action_type in ['sell_put', 'sell_call']:
            # Add premium income to cash
            premium = details.get('estimated_premium', 0) * details.get('contracts', 1)
            context['projected_option_income'] = context.get('projected_option_income', 0) + premium

        elif action_type == 'buy_stock':
            # Add to holdings projection
            ticker = action.get('ticker', '')
            shares = details.get('shares', 0)
            if ticker and shares:
                if 'projected_holdings' not in context:
                    context['projected_holdings'] = {}
                context['projected_holdings'][ticker] = context['projected_holdings'].get(ticker, 0) + shares

    # Add idea metadata to context
    if 'applied_ideas' not in context:
        context['applied_ideas'] = []
    context['applied_ideas'].append({
        'id': idea_id,
        'title': idea['title'],
        'category': idea.get('category')
    })

    return context
