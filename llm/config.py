"""LLM configuration management."""

import os
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

# Config file location
CONFIG_DIR = Path(__file__).parent.parent.resolve()
CONFIG_FILE = CONFIG_DIR / "llm_config.json"


@dataclass
class LLMConfig:
    """LLM configuration settings."""
    provider: str = "claude"  # "claude" or "local"
    enabled: bool = True

    # Claude API settings
    anthropic_api_key: Optional[str] = None
    claude_model: str = "claude-sonnet-4-20250514"

    # Local/OpenAI-compatible API settings
    local_url: str = "http://192.168.50.10:1234/v1"
    local_model: str = "nvidia/nemotron-3-nano"

    # Request settings
    timeout: int = 30
    max_history_events: int = 10

    def to_dict(self) -> dict:
        """Convert to dictionary, hiding sensitive keys."""
        d = asdict(self)
        if d.get('anthropic_api_key'):
            d['anthropic_api_key'] = d['anthropic_api_key'][:10] + "..."
        return d


def load_config() -> LLMConfig:
    """Load LLM configuration from file and environment."""
    config = LLMConfig()

    # Load from JSON config file if exists
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                data = json.load(f)
                config.provider = data.get('provider', config.provider)
                config.enabled = data.get('enabled', config.enabled)
                config.claude_model = data.get('claude_model', config.claude_model)
                config.local_url = data.get('local_url', config.local_url)
                config.local_model = data.get('local_model', config.local_model)
                config.timeout = data.get('timeout', config.timeout)
                config.max_history_events = data.get('max_history_events', config.max_history_events)
        except (json.JSONDecodeError, IOError):
            pass

    # Override with environment variables (higher priority)
    if os.getenv('LLM_PROVIDER'):
        config.provider = os.getenv('LLM_PROVIDER')
    if os.getenv('LLM_ENABLED'):
        config.enabled = os.getenv('LLM_ENABLED', '').lower() in ('true', '1', 'yes')
    if os.getenv('ANTHROPIC_API_KEY'):
        config.anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
    if os.getenv('CLAUDE_MODEL'):
        config.claude_model = os.getenv('CLAUDE_MODEL')
    if os.getenv('LOCAL_LLM_URL'):
        config.local_url = os.getenv('LOCAL_LLM_URL')
    if os.getenv('LOCAL_LLM_MODEL'):
        config.local_model = os.getenv('LOCAL_LLM_MODEL')

    return config


def save_config(config: LLMConfig) -> None:
    """Save LLM configuration to file (excluding API keys)."""
    data = {
        'provider': config.provider,
        'enabled': config.enabled,
        'claude_model': config.claude_model,
        'local_url': config.local_url,
        'local_model': config.local_model,
        'timeout': config.timeout,
        'max_history_events': config.max_history_events
    }
    # Don't save API keys to file - use environment variables
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def get_llm_config() -> LLMConfig:
    """Get current LLM configuration (singleton pattern)."""
    return load_config()


def update_config(**kwargs) -> LLMConfig:
    """Update and save configuration."""
    config = load_config()
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
    save_config(config)
    return config
