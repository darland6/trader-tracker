"""LLM integration module for generating AI insights on portfolio events."""

from .client import LLMClient, generate_event_insights
from .config import get_llm_config, LLMConfig

__all__ = ['LLMClient', 'generate_event_insights', 'get_llm_config', 'LLMConfig']
