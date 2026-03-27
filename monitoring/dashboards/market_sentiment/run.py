"""
Entry point for the Market Sentiment Dashboard.

Usage:
    python run.py

Or with custom host/port:
    python run.py --host 127.0.0.1 --port 9000
"""

import argparse
import os
import sys
from pathlib import Path

# Ensure the package is importable from this directory
sys.path.insert(0, str(Path(__file__).parent))

import uvicorn
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env", override=True)


def main():
    parser = argparse.ArgumentParser(description="Market Sentiment Dashboard")
    parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", 8000)))
    parser.add_argument("--reload", action="store_true", help="Enable hot reload (dev mode)")
    args = parser.parse_args()

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("\nWARNING: ANTHROPIC_API_KEY is not set.")
        print("  Copy .env.example -> .env and add your key.\n")

    print(f"\nMarket Sentiment Dashboard")
    print(f"  Server : http://{args.host}:{args.port}")
    print(f"  API    : http://{args.host}:{args.port}/docs")
    print(f"  Press Ctrl+C to stop\n")

    uvicorn.run(
        "server.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
