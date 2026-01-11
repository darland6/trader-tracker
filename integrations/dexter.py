"""
Dexter Integration - Financial Research Agent

Integrates with virattt/dexter for autonomous financial research.
Dexter can analyze income statements, balance sheets, cash flows, and more.

Setup:
1. Clone dexter: git clone https://github.com/virattt/dexter.git
2. Install bun: https://bun.sh
3. cd dexter && bun install
4. Configure dexter/.env with API keys
5. Set DEXTER_PATH in your .env to the dexter directory

Local LLM Support:
When your portfolio system is configured to use a local LLM, Dexter will
automatically be configured to use the same LLM via OpenAI-compatible API.
"""

import subprocess
import os
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import asyncio

# Get Dexter path from environment or default to sibling directory
DEXTER_PATH = os.getenv('DEXTER_PATH', str(Path(__file__).parent.parent.parent / 'dexter'))


def get_dexter_env() -> dict:
    """Build environment variables for Dexter, matching the portfolio LLM config."""
    env = {**os.environ}

    try:
        # Import LLM config to sync Dexter with portfolio settings
        from llm.config import get_llm_config
        config = get_llm_config()

        if config.provider == "claude":
            # Configure Dexter to use Claude/Anthropic API
            if config.anthropic_api_key:
                env['ANTHROPIC_API_KEY'] = config.anthropic_api_key
            env['ANTHROPIC_MODEL'] = config.claude_model
            # Clear any local LLM settings that might override
            env.pop('OPENAI_API_BASE', None)
            env.pop('OPENAI_BASE_URL', None)
            env.pop('LLM_BASE_URL', None)

        elif config.provider == "local" and config.local_url:
            # Configure Dexter to use the local LLM via OpenAI-compatible API
            env['OPENAI_API_BASE'] = config.local_url
            env['OPENAI_BASE_URL'] = config.local_url
            env['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY', 'local-llm')  # Dummy key for local
            env['OPENAI_MODEL'] = config.local_model

            # Some frameworks use these alternative names
            env['LLM_BASE_URL'] = config.local_url
            env['LLM_MODEL'] = config.local_model

            # Clear Anthropic settings when using local
            env.pop('ANTHROPIC_API_KEY', None)

    except ImportError:
        pass  # LLM module not available, use default env

    # Ensure CI mode for non-interactive
    env['CI'] = 'true'

    return env


@dataclass
class DexterResult:
    """Result from a Dexter research query."""
    success: bool
    query: str
    answer: str
    error: Optional[str] = None
    raw_output: Optional[str] = None


# MCP Server Configuration
MCP_SERVER_NAME = "dexter-mcp"
MCP_SERVER_PORT = int(os.getenv('DEXTER_MCP_PORT', '3001'))

def get_mcp_host() -> str:
    """Get MCP host - from env, or infer from LLM config if using local LLM."""
    explicit_host = os.getenv('DEXTER_MCP_HOST')
    if explicit_host:
        return explicit_host

    # Try to infer from LLM config - if using local LLM, MCP is likely on same host
    try:
        from llm.config import get_llm_config
        config = get_llm_config()
        if config.provider == "local" and config.local_url:
            # Extract host from URL like "http://192.168.50.10:1234/v1"
            from urllib.parse import urlparse
            parsed = urlparse(config.local_url)
            if parsed.hostname and parsed.hostname != 'localhost':
                return parsed.hostname
    except Exception:
        pass

    return 'localhost'

MCP_SERVER_HOST = get_mcp_host()


def is_mcp_available() -> bool:
    """Check if the dexter-mcp server is running and accessible."""
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((MCP_SERVER_HOST, MCP_SERVER_PORT))
        sock.close()
        if result == 0:
            return True
        # Also try SSE endpoint path
        try:
            import httpx
            response = httpx.get(
                f"http://{MCP_SERVER_HOST}:{MCP_SERVER_PORT}/sse",
                timeout=2.0,
                headers={"Accept": "text/event-stream"}
            )
            return response.status_code in [200, 204]
        except Exception:
            pass
        return False
    except Exception:
        return False


def get_mcp_status() -> dict:
    """Get MCP server status for dexter-mcp."""
    available = is_mcp_available()

    status = {
        "name": MCP_SERVER_NAME,
        "host": MCP_SERVER_HOST,
        "port": MCP_SERVER_PORT,
        "available": available,
        "url": f"http://{MCP_SERVER_HOST}:{MCP_SERVER_PORT}" if available else None
    }

    # Try to get more info if available
    if available:
        try:
            import httpx
            response = httpx.get(
                f"http://{MCP_SERVER_HOST}:{MCP_SERVER_PORT}/health",
                timeout=2.0
            )
            if response.status_code == 200:
                status["health"] = response.json() if response.headers.get('content-type', '').startswith('application/json') else "ok"
        except Exception:
            status["health"] = "connected"  # Port is open but no health endpoint

    return status


def is_dexter_available() -> bool:
    """Check if Dexter is installed and configured."""
    dexter_dir = Path(DEXTER_PATH)
    return (
        dexter_dir.exists() and
        (dexter_dir / 'package.json').exists() and
        (dexter_dir / 'node_modules').exists()
    )


def get_dexter_status() -> dict:
    """Get Dexter installation status including MCP server status."""
    dexter_dir = Path(DEXTER_PATH)

    # Get MCP status first
    mcp_status = get_mcp_status()

    status = {
        "installed": False,
        "path": str(dexter_dir),
        "has_package_json": False,
        "has_node_modules": False,
        "has_env": False,
        "ready": False,
        "llm_provider": None,
        "llm_model": None,
        "llm_url": None,
        # MCP server status
        "mcp": mcp_status,
        "mcp_available": mcp_status["available"]
    }

    if dexter_dir.exists():
        status["has_package_json"] = (dexter_dir / 'package.json').exists()
        status["has_node_modules"] = (dexter_dir / 'node_modules').exists()
        status["has_env"] = (dexter_dir / '.env').exists()
        status["installed"] = status["has_package_json"]
        status["ready"] = all([
            status["has_package_json"],
            status["has_node_modules"],
            status["has_env"]
        ])

    # Show which LLM provider Dexter will use (synced with portfolio config)
    try:
        from llm.config import get_llm_config
        config = get_llm_config()
        status["llm_provider"] = config.provider
        if config.provider == "claude":
            status["llm_model"] = config.claude_model
            status["llm_url"] = "api.anthropic.com"
        elif config.provider == "local":
            status["llm_model"] = config.local_model
            status["llm_url"] = config.local_url
    except ImportError:
        pass

    return status


async def query_dexter(question: str, timeout: int = 120) -> DexterResult:
    """
    Query Dexter with a financial research question.

    Args:
        question: The financial research question to ask
        timeout: Maximum seconds to wait for response

    Returns:
        DexterResult with the research findings
    """
    if not is_dexter_available():
        return DexterResult(
            success=False,
            query=question,
            answer="",
            error="Dexter is not installed or configured. Run setup first."
        )

    dexter_dir = Path(DEXTER_PATH)

    try:
        # Run Dexter in non-interactive mode with the question
        # Dexter uses bun as its runtime
        # Pass local LLM configuration via environment variables
        dexter_env = get_dexter_env()

        process = await asyncio.create_subprocess_exec(
            'bun', 'run', 'start', '--query', question,
            cwd=str(dexter_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=dexter_env
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            return DexterResult(
                success=False,
                query=question,
                answer="",
                error=f"Dexter query timed out after {timeout} seconds"
            )

        output = stdout.decode('utf-8', errors='replace')
        error_output = stderr.decode('utf-8', errors='replace')

        if process.returncode != 0:
            return DexterResult(
                success=False,
                query=question,
                answer="",
                error=f"Dexter error: {error_output or output}",
                raw_output=output
            )

        # Parse the output - Dexter outputs its answer in a specific format
        # Try to extract the final answer
        answer = extract_answer(output)

        return DexterResult(
            success=True,
            query=question,
            answer=answer,
            raw_output=output
        )

    except FileNotFoundError:
        return DexterResult(
            success=False,
            query=question,
            answer="",
            error="Bun runtime not found. Install from https://bun.sh"
        )
    except Exception as e:
        return DexterResult(
            success=False,
            query=question,
            answer="",
            error=f"Failed to run Dexter: {str(e)}"
        )


def extract_answer(output: str) -> str:
    """Extract the final answer from Dexter's output."""
    # Dexter outputs in a structured format
    # Look for the answer section
    lines = output.strip().split('\n')

    # Try to find answer markers
    answer_started = False
    answer_lines = []

    for line in lines:
        # Skip ANSI escape codes and formatting
        clean_line = line.strip()

        # Look for answer indicators
        if any(marker in clean_line.lower() for marker in ['answer:', 'final answer:', 'result:']):
            answer_started = True
            # Get content after the marker
            for marker in ['answer:', 'final answer:', 'result:']:
                if marker in clean_line.lower():
                    idx = clean_line.lower().index(marker)
                    remainder = clean_line[idx + len(marker):].strip()
                    if remainder:
                        answer_lines.append(remainder)
                    break
            continue

        if answer_started and clean_line:
            # Stop at obvious section breaks
            if clean_line.startswith('---') or clean_line.startswith('==='):
                break
            answer_lines.append(clean_line)

    if answer_lines:
        return '\n'.join(answer_lines)

    # Fallback: return last non-empty lines as the answer
    non_empty = [l.strip() for l in lines if l.strip()]
    if non_empty:
        return '\n'.join(non_empty[-5:])  # Last 5 lines

    return output


def query_dexter_sync(question: str, timeout: int = 120) -> DexterResult:
    """Synchronous wrapper for query_dexter."""
    return asyncio.run(query_dexter(question, timeout))


# Financial research prompts that work well with Dexter
EXAMPLE_QUERIES = [
    "What was {ticker}'s revenue growth over the last 4 quarters?",
    "Analyze {ticker}'s profit margins compared to industry average",
    "What is {ticker}'s debt-to-equity ratio and how has it changed?",
    "Compare {ticker}'s P/E ratio to its competitors",
    "What are {ticker}'s main revenue segments?",
    "Analyze {ticker}'s free cash flow trends",
    "What is {ticker}'s dividend history and payout ratio?",
]


def format_research_query(template: str, ticker: str) -> str:
    """Format a research query template with a ticker."""
    return template.format(ticker=ticker.upper())


async def query_dexter_mcp(question: str, timeout: int = 120) -> DexterResult:
    """
    Query Dexter via MCP server using JSON-RPC over SSE.

    MCP SSE protocol requires maintaining the SSE connection open while
    sending messages to the /messages endpoint.

    Args:
        question: The financial research question to ask
        timeout: Maximum seconds to wait for response

    Returns:
        DexterResult with the research findings
    """
    import httpx
    import uuid
    import re

    if not is_mcp_available():
        return DexterResult(
            success=False,
            query=question,
            answer="",
            error=f"Dexter MCP server not reachable at {MCP_SERVER_HOST}:{MCP_SERVER_PORT}. Check firewall settings."
        )

    base_url = f"http://{MCP_SERVER_HOST}:{MCP_SERVER_PORT}"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Step 1: Connect to SSE endpoint to get session
            async with client.stream(
                "GET",
                f"{base_url}/sse",
                headers={"Accept": "text/event-stream"}
            ) as sse_response:
                # Read the first event to get the session endpoint
                session_id = None
                messages_endpoint = None

                async for line in sse_response.aiter_lines():
                    if line.startswith("data:"):
                        data = line[5:].strip()
                        # Parse the endpoint URL to get session ID
                        if "sessionId=" in data:
                            match = re.search(r'sessionId=([a-f0-9-]+)', data)
                            if match:
                                session_id = match.group(1)
                                messages_endpoint = data
                                break

                if not session_id:
                    return DexterResult(
                        success=False,
                        query=question,
                        answer="",
                        error="Could not establish MCP session"
                    )

                # Step 2: First list available tools
                list_request = {
                    "jsonrpc": "2.0",
                    "id": "list-1",
                    "method": "tools/list",
                    "params": {}
                }

                list_response = await client.post(
                    f"{base_url}{messages_endpoint}",
                    json=list_request,
                    headers={"Content-Type": "application/json"}
                )

                available_tools = []
                if list_response.status_code == 200:
                    try:
                        list_result = list_response.json()
                        if "result" in list_result and "tools" in list_result["result"]:
                            available_tools = [t["name"] for t in list_result["result"]["tools"]]
                    except Exception:
                        pass

                # Step 3: Call the appropriate tool
                # Try common tool names for research
                tool_names_to_try = ["research", "query", "ask", "analyze"]
                if available_tools:
                    tool_names_to_try = available_tools + tool_names_to_try

                for tool_name in tool_names_to_try:
                    call_request = {
                        "jsonrpc": "2.0",
                        "id": str(uuid.uuid4()),
                        "method": "tools/call",
                        "params": {
                            "name": tool_name,
                            "arguments": {"query": question}
                        }
                    }

                    try:
                        call_response = await client.post(
                            f"{base_url}{messages_endpoint}",
                            json=call_request,
                            headers={"Content-Type": "application/json"}
                        )

                        if call_response.status_code == 200:
                            result = call_response.json()
                            if "result" in result:
                                content = result["result"]
                                if isinstance(content, dict) and "content" in content:
                                    content_list = content["content"]
                                    if content_list and isinstance(content_list, list):
                                        answer = content_list[0].get("text", str(content_list))
                                    else:
                                        answer = str(content)
                                else:
                                    answer = str(content)

                                return DexterResult(
                                    success=True,
                                    query=question,
                                    answer=answer,
                                    raw_output=str(result)
                                )
                            elif "error" in result:
                                # Tool not found, try next
                                continue
                    except Exception:
                        continue

                return DexterResult(
                    success=False,
                    query=question,
                    answer="",
                    error=f"MCP server has tools {available_tools} but none responded to research query"
                )

    except httpx.TimeoutException:
        return DexterResult(
            success=False,
            query=question,
            answer="",
            error=f"MCP query timed out after {timeout} seconds"
        )
    except Exception as e:
        return DexterResult(
            success=False,
            query=question,
            answer="",
            error=f"MCP query failed: {str(e)}"
        )


async def query_dexter_auto(question: str, timeout: int = 120) -> DexterResult:
    """
    Query Dexter using the best available method.

    Tries MCP server first, then falls back to local installation.

    Args:
        question: The financial research question to ask
        timeout: Maximum seconds to wait for response

    Returns:
        DexterResult with the research findings
    """
    # Try MCP first (faster, already running)
    if is_mcp_available():
        result = await query_dexter_mcp(question, timeout)
        if result.success:
            return result
        # MCP failed, try local if available

    # Fall back to local installation
    if is_dexter_available():
        return await query_dexter(question, timeout)

    # Neither available
    return DexterResult(
        success=False,
        query=question,
        answer="",
        error="Dexter is not available. Start the MCP server or install Dexter locally."
    )
