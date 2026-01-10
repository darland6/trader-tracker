"""LLM client for generating event insights."""

import json
import sys
from datetime import datetime, date
from pathlib import Path
from typing import Optional
import pandas as pd

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from .config import get_llm_config, LLMConfig
from .prompts import INSIGHT_SYSTEM_PROMPT, build_event_context

# Path to event log
SCRIPT_DIR = Path(__file__).parent.parent.resolve()
EVENT_LOG = SCRIPT_DIR / 'data' / 'event_log_enhanced.csv'


def _log_daily_insight_usage(event_type: str, model: str):
    """Log insight generation - one event per day with run count.

    Creates an INSIGHT_LOG event for today if none exists,
    otherwise updates the existing one with incremented count.
    """
    try:
        if not EVENT_LOG.exists():
            return

        df = pd.read_csv(EVENT_LOG)
        today = date.today().isoformat()

        # Check if we already have an INSIGHT_LOG for today
        df['data'] = df['data_json'].apply(lambda x: json.loads(x) if pd.notna(x) else {})
        today_logs = df[
            (df['event_type'] == 'INSIGHT_LOG') &
            (df['data'].apply(lambda x: x.get('date') == today))
        ]

        if len(today_logs) > 0:
            # Update existing log - increment count
            idx = today_logs.index[0]
            existing_data = today_logs.iloc[0]['data']
            existing_data['run_count'] = existing_data.get('run_count', 1) + 1
            existing_data['last_run'] = datetime.now().strftime('%H:%M:%S')
            existing_data['last_model'] = model
            existing_data['last_event_type'] = event_type

            # Track event types processed
            event_types = existing_data.get('event_types', [])
            if event_type not in event_types:
                event_types.append(event_type)
            existing_data['event_types'] = event_types

            df.at[idx, 'data_json'] = json.dumps(existing_data)
            df.at[idx, 'notes'] = f"AI insights generated {existing_data['run_count']} times today"
            df = df.drop('data', axis=1)
            df.to_csv(EVENT_LOG, index=False)
        else:
            # Create new daily log
            df = df.drop('data', axis=1)
            event_id = int(df['event_id'].max()) + 1
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            new_row = {
                'event_id': event_id,
                'timestamp': timestamp,
                'event_type': 'INSIGHT_LOG',
                'data_json': json.dumps({
                    'date': today,
                    'run_count': 1,
                    'first_run': datetime.now().strftime('%H:%M:%S'),
                    'last_run': datetime.now().strftime('%H:%M:%S'),
                    'last_model': model,
                    'last_event_type': event_type,
                    'event_types': [event_type]
                }),
                'reason_json': json.dumps({'primary': 'SYSTEM', 'explanation': 'Daily AI insight usage log'}),
                'notes': 'AI insights generated 1 time today',
                'tags_json': json.dumps(['system', 'ai', 'insights']),
                'affects_cash': False,
                'cash_delta': 0
            }

            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            df.to_csv(EVENT_LOG, index=False)

    except Exception as e:
        # Don't let logging failures break insight generation
        print(f"[LLM] Failed to log insight usage: {e}")


class LLMClient:
    """Unified LLM client supporting Claude and OpenAI-compatible APIs."""

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or get_llm_config()
        self._anthropic_client = None
        self._httpx_client = None

    def _get_anthropic_client(self):
        """Lazy-load Anthropic client."""
        if self._anthropic_client is None:
            try:
                import anthropic
                if not self.config.anthropic_api_key:
                    raise ValueError("ANTHROPIC_API_KEY not set")
                self._anthropic_client = anthropic.Anthropic(
                    api_key=self.config.anthropic_api_key
                )
            except ImportError:
                raise ImportError("anthropic package not installed. Run: pip install anthropic")
        return self._anthropic_client

    def _get_httpx_client(self):
        """Lazy-load httpx client for local LLM."""
        if self._httpx_client is None:
            try:
                import httpx
                self._httpx_client = httpx.Client(timeout=self.config.timeout)
            except ImportError:
                raise ImportError("httpx package not installed. Run: pip install httpx")
        return self._httpx_client

    def generate_insights(self, event_type: str, event_data: dict,
                          user_reason: str, notes: str,
                          portfolio_state: dict, recent_events: list) -> dict:
        """Generate AI insights for an event.

        Returns:
            dict with keys: reasoning, future_advice, past_reflection, model, generated_at
            Or empty dict if generation fails
        """
        if not self.config.enabled:
            return {}

        # Build the context prompt
        context = build_event_context(
            event_type=event_type,
            event_data=event_data,
            user_reason=user_reason,
            notes=notes,
            portfolio_state=portfolio_state,
            recent_events=recent_events
        )

        try:
            if self.config.provider == "claude":
                result = self._call_claude(context)
            else:
                result = self._call_local(context)

            # Log successful insight generation (once per day)
            if result and not result.get('parse_error'):
                model = result.get('model', self.config.provider)
                _log_daily_insight_usage(event_type, model)

            return result
        except Exception as e:
            print(f"[LLM Warning] Failed to generate insights: {e}")
            return {}

    def _call_claude(self, context: str) -> dict:
        """Call Claude API."""
        client = self._get_anthropic_client()

        message = client.messages.create(
            model=self.config.claude_model,
            max_tokens=500,
            system=INSIGHT_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": context}
            ]
        )

        response_text = message.content[0].text
        return self._parse_response(response_text, self.config.claude_model)

    def _call_local(self, context: str) -> dict:
        """Call local OpenAI-compatible API."""
        client = self._get_httpx_client()

        url = f"{self.config.local_url.rstrip('/')}/chat/completions"

        payload = {
            "model": self.config.local_model,
            "messages": [
                {"role": "system", "content": INSIGHT_SYSTEM_PROMPT},
                {"role": "user", "content": context}
            ],
            "max_tokens": 500,
            "temperature": 0.7
        }

        response = client.post(url, json=payload)
        response.raise_for_status()

        data = response.json()
        response_text = data["choices"][0]["message"]["content"]
        return self._parse_response(response_text, self.config.local_model)

    def _parse_response(self, text: str, model: str) -> dict:
        """Parse LLM response into structured insights."""
        # Try to extract JSON from the response
        try:
            # Handle markdown code blocks
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            insights = json.loads(text.strip())

            # Validate required fields
            if not all(k in insights for k in ['reasoning', 'future_advice', 'past_reflection']):
                raise ValueError("Missing required insight fields")

            insights['model'] = model
            insights['generated_at'] = datetime.now().isoformat()
            return insights

        except (json.JSONDecodeError, ValueError, IndexError) as e:
            # If JSON parsing fails, try to extract insights from text
            print(f"[LLM Warning] Failed to parse JSON response, using raw text: {e}")
            return {
                'reasoning': text[:500] if len(text) > 500 else text,
                'future_advice': 'Unable to parse structured advice',
                'past_reflection': 'Unable to parse structured reflection',
                'model': model,
                'generated_at': datetime.now().isoformat(),
                'parse_error': True
            }


def generate_event_insights(event_type: str, event_data: dict,
                            user_reason: str = "", notes: str = "") -> dict:
    """Convenience function to generate insights for an event.

    This function loads portfolio state and recent events automatically.
    """
    from reconstruct_state import load_event_log, reconstruct_state

    config = get_llm_config()
    if not config.enabled:
        return {}

    # Load current state and history
    script_dir = Path(__file__).parent.parent.resolve()
    event_log_path = script_dir / 'data' / 'event_log_enhanced.csv'

    try:
        events_df = load_event_log(str(event_log_path))
        state = reconstruct_state(events_df)

        # Get recent events as list of dicts
        recent = events_df.tail(config.max_history_events).to_dict('records')

    except Exception as e:
        print(f"[LLM Warning] Failed to load portfolio state: {e}")
        state = {'holdings': {}, 'cash': 0, 'ytd_income': 0, 'active_options': []}
        recent = []

    # Generate insights
    client = LLMClient(config)
    return client.generate_insights(
        event_type=event_type,
        event_data=event_data,
        user_reason=user_reason,
        notes=notes,
        portfolio_state=state,
        recent_events=recent
    )


def test_connection() -> tuple[bool, str]:
    """Test LLM connection with current configuration.

    Returns:
        (success: bool, message: str)
    """
    config = get_llm_config()

    if not config.enabled:
        return False, "LLM insights are disabled"

    try:
        client = LLMClient(config)

        # Simple test
        if config.provider == "claude":
            c = client._get_anthropic_client()
            return True, f"Claude API connected (model: {config.claude_model})"
        else:
            import httpx
            response = httpx.get(f"{config.local_url.rstrip('/')}/models", timeout=5)
            if response.status_code == 200:
                return True, f"Local LLM connected at {config.local_url} (model: {config.local_model})"
            else:
                return False, f"Local LLM returned status {response.status_code}"

    except Exception as e:
        return False, f"Connection failed: {str(e)}"
