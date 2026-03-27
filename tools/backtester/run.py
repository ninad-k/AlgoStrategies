"""Entry point for the PineScript Backtester."""

import sys
from pathlib import Path

import uvicorn

sys.path.insert(0, str(Path(__file__).parent))

if __name__ == "__main__":
    uvicorn.run(
        "server.main:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
        reload_dirs=[str(Path(__file__).parent / "server")],
    )
