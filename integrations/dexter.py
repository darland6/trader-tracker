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


def is_dexter_available() -> bool:
    """Check if Dexter is installed and configured."""
    dexter_dir = Path(DEXTER_PATH)
    return (
        dexter_dir.exists() and
        (dexter_dir / 'package.json').exists() and
        (dexter_dir / 'node_modules').exists()
    )


def get_dexter_status() -> dict:
    """Get Dexter installation status."""
    dexter_dir = Path(DEXTER_PATH)

    status = {
        "installed": False,
        "path": str(dexter_dir),
        "has_package_json": False,
        "has_node_modules": False,
        "has_env": False,
        "ready": False,
        "llm_provider": None,
        "llm_model": None,
        "llm_url": None
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
