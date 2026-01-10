#!/usr/bin/env python3
"""LLM Connection Diagnostics"""

import sys
sys.path.insert(0, '.')

print("=" * 50)
print("LLM Connection Diagnostics")
print("=" * 50)

# 1. Check config
print("\n1. Configuration:")
from llm.config import load_config
config = load_config()
print(f"   Provider: {config.provider}")
print(f"   URL: {config.local_url}")
print(f"   Model: {config.local_model}")
print(f"   Enabled: {config.enabled}")
print(f"   Timeout: {config.timeout}s")

# 2. Test basic connectivity
print("\n2. Testing connectivity to server...")
import httpx

try:
    # Test /models endpoint
    response = httpx.get(f"{config.local_url.rstrip('/')}/models", timeout=10)
    print(f"   GET /models: Status {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   Available models: {data}")
    else:
        print(f"   Response: {response.text[:200]}")
except httpx.ConnectError as e:
    print(f"   CONNECTION ERROR: Cannot reach server at {config.local_url}")
    print(f"   Details: {e}")
except httpx.TimeoutException:
    print(f"   TIMEOUT: Server did not respond within {10}s")
except Exception as e:
    print(f"   ERROR: {type(e).__name__}: {e}")

# 3. Test chat completion
print("\n3. Testing chat completion...")
try:
    payload = {
        "model": config.local_model,
        "messages": [{"role": "user", "content": "Say hello in 5 words or less"}],
        "max_tokens": 20,
        "temperature": 0.7
    }
    response = httpx.post(
        f"{config.local_url.rstrip('/')}/chat/completions",
        json=payload,
        timeout=30
    )
    print(f"   POST /chat/completions: Status {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        content = data.get('choices', [{}])[0].get('message', {}).get('content', 'No content')
        print(f"   Response: {content}")
        print("   SUCCESS!")
    else:
        print(f"   Error response: {response.text[:300]}")
except Exception as e:
    print(f"   ERROR: {type(e).__name__}: {e}")

print("\n" + "=" * 50)
