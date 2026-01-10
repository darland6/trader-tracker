#!/usr/bin/env python3
"""
Run the Portfolio Dashboard server.

Usage:
    python run_server.py           # Start API server only
    python run_server.py --dev     # Start with auto-reload

The server will be available at:
    - Web UI: http://localhost:8000/
    - API Docs: http://localhost:8000/docs
    - Dashboard (requires npm install): Run `npm run dev` in /dashboard folder
"""

import argparse
import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Run Portfolio Dashboard API")
    parser.add_argument("--port", type=int, default=8000, help="Port to run on")
    parser.add_argument("--dev", action="store_true", help="Enable auto-reload")
    args = parser.parse_args()

    print("=" * 60)
    print("Portfolio Dashboard Server")
    print("=" * 60)
    print(f"\n  Web UI:     http://localhost:{args.port}/")
    print(f"  API Docs:   http://localhost:{args.port}/docs")
    print(f"  API State:  http://localhost:{args.port}/api/state")
    print("\n  For 3D Dashboard:")
    print("    cd dashboard && npm install && npm run dev")
    print("=" * 60 + "\n")

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=args.port,
        reload=args.dev
    )


if __name__ == "__main__":
    main()
