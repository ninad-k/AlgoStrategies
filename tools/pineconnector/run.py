"""PineConnector entry point — starts the FastAPI server."""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def main() -> None:
    parser = argparse.ArgumentParser(description="PineConnector Trading Automation")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8003, help="Bind port (default: 8003)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--dry-run", action="store_true", help="Paper trading mode (no real orders)")
    args = parser.parse_args()

    if args.dry_run:
        os.environ["DRY_RUN"] = "true"

    import uvicorn

    print(f"\n  PineConnector v1.0")
    print(f"  http://{args.host}:{args.port}")
    print(f"  Webhook: POST http://{args.host}:{args.port}/webhook")
    print(f"  Dashboard: http://{args.host}:{args.port}/")
    print(f"  Mode: {'DRY RUN' if args.dry_run else 'LIVE'}\n")

    uvicorn.run(
        "python.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
