"""LLM configuration API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from llm.config import get_llm_config, update_config, LLMConfig

router = APIRouter(prefix="/api/config", tags=["config"])


class LLMConfigUpdate(BaseModel):
    provider: str | None = None
    enabled: bool | None = None
    claude_model: str | None = None
    local_url: str | None = None
    local_model: str | None = None


class LLMConfigResponse(BaseModel):
    provider: str
    enabled: bool
    claude_model: str
    local_url: str
    local_model: str
    has_api_key: bool


@router.get("/llm", response_model=LLMConfigResponse)
async def get_config():
    """Get current LLM configuration."""
    config = get_llm_config()

    return LLMConfigResponse(
        provider=config.provider,
        enabled=config.enabled,
        claude_model=config.claude_model,
        local_url=config.local_url,
        local_model=config.local_model,
        has_api_key=bool(config.anthropic_api_key)
    )


@router.post("/llm", response_model=LLMConfigResponse)
async def set_config(update: LLMConfigUpdate):
    """Update LLM configuration."""
    updates = {}

    if update.provider is not None:
        if update.provider not in ("claude", "local"):
            raise HTTPException(status_code=400, detail="Provider must be 'claude' or 'local'")
        updates["provider"] = update.provider

    if update.enabled is not None:
        updates["enabled"] = update.enabled

    if update.claude_model is not None:
        updates["claude_model"] = update.claude_model

    if update.local_url is not None:
        updates["local_url"] = update.local_url

    if update.local_model is not None:
        updates["local_model"] = update.local_model

    config = update_config(**updates)

    return LLMConfigResponse(
        provider=config.provider,
        enabled=config.enabled,
        claude_model=config.claude_model,
        local_url=config.local_url,
        local_model=config.local_model,
        has_api_key=bool(config.anthropic_api_key)
    )


@router.post("/llm/test")
async def test_llm():
    """Test the current LLM configuration."""
    config = get_llm_config()

    if not config.enabled:
        return {"success": False, "error": "LLM is disabled"}

    try:
        if config.provider == "claude":
            if not config.anthropic_api_key:
                return {"success": False, "error": "No Anthropic API key configured"}

            import anthropic
            client = anthropic.Anthropic(api_key=config.anthropic_api_key)
            response = client.messages.create(
                model=config.claude_model,
                max_tokens=50,
                messages=[{"role": "user", "content": "Say 'OK' if you can hear me."}]
            )
            return {
                "success": True,
                "provider": "claude",
                "model": config.claude_model,
                "response": response.content[0].text
            }

        else:  # local
            import httpx
            response = httpx.post(
                f"{config.local_url}/chat/completions",
                json={
                    "model": config.local_model,
                    "messages": [{"role": "user", "content": "Say 'OK' if you can hear me."}],
                    "max_tokens": 50
                },
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            return {
                "success": True,
                "provider": "local",
                "model": config.local_model,
                "response": result["choices"][0]["message"]["content"]
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/llm/status")
async def get_llm_status():
    """Get detailed LLM connection status for UI indicator."""
    config = get_llm_config()

    status = {
        "provider": config.provider,
        "model": config.claude_model if config.provider == "claude" else config.local_model,
        "enabled": config.enabled,
        "connected": False,
        "latency_ms": None,
        "error": None
    }

    if not config.enabled:
        status["error"] = "LLM disabled"
        return status

    import time

    try:
        start = time.time()

        if config.provider == "claude":
            if not config.anthropic_api_key:
                status["error"] = "No API key"
                return status

            import anthropic
            client = anthropic.Anthropic(api_key=config.anthropic_api_key)
            # Quick ping with minimal tokens
            response = client.messages.create(
                model=config.claude_model,
                max_tokens=5,
                messages=[{"role": "user", "content": "ping"}]
            )
            status["connected"] = True
            status["latency_ms"] = int((time.time() - start) * 1000)

        else:  # local
            import httpx
            response = httpx.post(
                f"{config.local_url}/chat/completions",
                json={
                    "model": config.local_model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 5
                },
                timeout=10.0
            )
            response.raise_for_status()
            status["connected"] = True
            status["latency_ms"] = int((time.time() - start) * 1000)

    except Exception as e:
        status["error"] = str(e)[:100]

    return status
