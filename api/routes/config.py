"""LLM configuration API endpoints - Direct JSON file access."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
import json
import os

router = APIRouter(prefix="/api/config", tags=["config"])

# Direct path to config file
CONFIG_FILE = Path(__file__).parent.parent.parent / "llm_config.json"
ENV_FILE = Path(__file__).parent.parent.parent / ".env"


class LLMConfigFull(BaseModel):
    """Full LLM config matching llm_config.json structure."""
    provider: str = "local"
    enabled: bool = True
    claude_model: str = "claude-sonnet-4-20250514"
    local_url: str = "http://192.168.50.10:1234/v1"
    local_model: str = "meta/llama-3.3-70b"
    timeout: int = 180
    max_history_events: int = 10


@router.get("/llm")
async def get_config():
    """Get LLM config directly from llm_config.json."""
    try:
        with open(CONFIG_FILE) as f:
            config = json.load(f)

        # Add API key status from env
        config["has_api_key"] = bool(os.getenv("ANTHROPIC_API_KEY"))

        return config
    except FileNotFoundError:
        # Return defaults
        return {
            "provider": "local",
            "enabled": True,
            "claude_model": "claude-sonnet-4-20250514",
            "local_url": "http://192.168.50.10:1234/v1",
            "local_model": "meta/llama-3.3-70b",
            "timeout": 180,
            "max_history_events": 10,
            "has_api_key": False
        }
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Invalid JSON in config file: {e}")


@router.post("/llm")
async def save_config(config: LLMConfigFull):
    """Save LLM config directly to llm_config.json."""
    try:
        # Write config to JSON file
        config_dict = config.model_dump()
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_dict, f, indent=2)

        # Return saved config with API key status
        config_dict["has_api_key"] = bool(os.getenv("ANTHROPIC_API_KEY"))
        return config_dict
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save config: {e}")


@router.get("/llm/raw")
async def get_raw_config():
    """Get raw llm_config.json content as string for editing."""
    try:
        with open(CONFIG_FILE) as f:
            return {"content": f.read(), "path": str(CONFIG_FILE)}
    except FileNotFoundError:
        return {"content": "{}", "path": str(CONFIG_FILE)}


@router.post("/llm/raw")
async def save_raw_config(data: dict):
    """Save raw JSON string to llm_config.json."""
    content = data.get("content", "")
    try:
        # Validate it's valid JSON
        parsed = json.loads(content)

        # Write to file
        with open(CONFIG_FILE, 'w') as f:
            json.dump(parsed, f, indent=2)

        return {"success": True, "config": parsed}
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save: {e}")


@router.post("/llm/api-key")
async def save_api_key(data: dict):
    """Save Anthropic API key to .env file."""
    api_key = data.get("api_key", "").strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="API key is required")

    try:
        # Read existing .env
        env_lines = []
        if ENV_FILE.exists():
            with open(ENV_FILE) as f:
                env_lines = f.readlines()

        # Update or add ANTHROPIC_API_KEY
        key_found = False
        new_lines = []
        for line in env_lines:
            if line.strip().startswith('ANTHROPIC_API_KEY='):
                new_lines.append(f'ANTHROPIC_API_KEY={api_key}\n')
                key_found = True
            else:
                new_lines.append(line)

        if not key_found:
            new_lines.append(f'ANTHROPIC_API_KEY={api_key}\n')

        with open(ENV_FILE, 'w') as f:
            f.writelines(new_lines)

        # Update current process env
        os.environ['ANTHROPIC_API_KEY'] = api_key

        return {"success": True, "message": "API key saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save API key: {e}")


@router.post("/llm/test")
async def test_llm():
    """Test the current LLM configuration."""
    try:
        with open(CONFIG_FILE) as f:
            config = json.load(f)
    except:
        return {"success": False, "error": "Could not read config file"}

    if not config.get("enabled", True):
        return {"success": False, "error": "LLM is disabled"}

    provider = config.get("provider", "local")

    try:
        if provider == "claude":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                return {"success": False, "error": "No Anthropic API key configured"}

            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model=config.get("claude_model", "claude-sonnet-4-20250514"),
                max_tokens=50,
                messages=[{"role": "user", "content": "Say 'OK' if you can hear me."}]
            )
            return {
                "success": True,
                "provider": "claude",
                "model": config.get("claude_model"),
                "response": response.content[0].text
            }

        else:  # local
            import httpx
            response = httpx.post(
                f"{config.get('local_url', 'http://localhost:1234/v1')}/chat/completions",
                json={
                    "model": config.get("local_model", ""),
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
                "model": config.get("local_model"),
                "response": result["choices"][0]["message"]["content"]
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/llm/status")
async def get_llm_status():
    """Get LLM connection status."""
    try:
        with open(CONFIG_FILE) as f:
            config = json.load(f)
    except:
        return {"connected": False, "error": "Config file not found"}

    provider = config.get("provider", "local")
    model = config.get("local_model") if provider == "local" else config.get("claude_model")

    status = {
        "provider": provider,
        "model": model,
        "enabled": config.get("enabled", True),
        "connected": False,
        "latency_ms": None,
        "error": None
    }

    if not config.get("enabled", True):
        status["error"] = "LLM disabled"
        return status

    import time

    try:
        start = time.time()

        if provider == "claude":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                status["error"] = "No API key"
                return status

            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model=config.get("claude_model", "claude-sonnet-4-20250514"),
                max_tokens=5,
                messages=[{"role": "user", "content": "ping"}]
            )
            status["connected"] = True
            status["latency_ms"] = int((time.time() - start) * 1000)

        else:  # local
            import httpx
            response = httpx.post(
                f"{config.get('local_url')}/chat/completions",
                json={
                    "model": config.get("local_model"),
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


@router.get("/learning-files")
async def get_learning_files():
    """Get stats about learning/memory files used by the system."""
    from datetime import datetime

    DATA_DIR = Path(__file__).parent.parent.parent / "data"

    files = [
        {"name": "llm_memory.json", "description": "Chat memory & conversation summaries", "category": "Memory"},
        {"name": "llm_usage.json", "description": "Token usage tracking", "category": "Analytics"},
        {"name": "agent_context.json", "description": "Agent context & knowledge", "category": "Memory"},
        {"name": "skill_cache.json", "description": "Installed skills cache", "category": "Skills"},
        {"name": "reason_taxonomy.json", "description": "Decision reason categories", "category": "Config"},
        {"name": "agent_context_reason_analysis.json", "description": "Reason analysis data", "category": "Analytics"},
    ]

    result = []
    for f in files:
        path = DATA_DIR / f["name"]
        if path.exists():
            stat = path.stat()
            try:
                with open(path) as fp:
                    data = json.load(fp)
                    # Count entries based on file type
                    if "conversation_memories" in data:
                        entries = len(data.get("conversation_memories", []))
                    elif "learned_patterns" in data:
                        entries = len(data.get("learned_patterns", []))
                    elif "daily_usage" in data:
                        entries = len(data.get("daily_usage", {}))
                    elif isinstance(data, list):
                        entries = len(data)
                    elif isinstance(data, dict):
                        entries = len(data.keys())
                    else:
                        entries = 1
            except:
                entries = 0

            result.append({
                "name": f["name"],
                "description": f["description"],
                "category": f["category"],
                "exists": True,
                "size_bytes": stat.st_size,
                "size_kb": round(stat.st_size / 1024, 1),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "entries": entries
            })
        else:
            result.append({
                "name": f["name"],
                "description": f["description"],
                "category": f["category"],
                "exists": False,
                "size_bytes": 0,
                "size_kb": 0,
                "modified": None,
                "entries": 0
            })

    return {"files": result, "data_dir": str(DATA_DIR)}
