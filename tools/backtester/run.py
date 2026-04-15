"""Entry point for the PineScript Backtester."""

import os
import sys
from pathlib import Path

import uvicorn

sys.path.insert(0, str(Path(__file__).parent))

if __name__ == "__main__":
    port = int(os.environ.get("BACKTESTER_PORT", "8002"))
    host = os.environ.get("BACKTESTER_HOST", "0.0.0.0")
    uvicorn.run(
        "server.main:app",
        host=host,
        port=port,
        log_level="debug",
        reload=True,
        reload_dirs=[str(Path(__file__).parent / "server")],
    )
