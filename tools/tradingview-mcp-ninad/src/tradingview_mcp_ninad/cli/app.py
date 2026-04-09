"""Root typer application — exposed as the ``tv`` command via pyproject.toml.

Each sub-command wraps a core module coroutine, runs it in an asyncio loop,
and pretty-prints the result as JSON (for piping) or a rich table (for humans).
The CLI is intentionally separate from the MCP server so it can run without
Claude Code — useful for cron-scheduled morning briefs and quick health checks.
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Annotated

import typer
from rich.console import Console
from rich.syntax import Syntax

app = typer.Typer(
    name="tv",
    help="TradingView MCP CLI — drive TradingView Desktop from the terminal.",
    no_args_is_help=True,
)
console = Console(stderr=True)
_json_out = Console()  # stdout for JSON output


def _run(coro):
    """Run an async coroutine and print the result as pretty JSON to stdout."""
    try:
        result = asyncio.run(coro)
        raw = json.dumps(result, indent=2, default=str)
        _json_out.print(Syntax(raw, "json", theme="monokai"))
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(1)


# ── Sub-commands ─────────────────────────────────────────────────────────────


@app.command()
def health():
    """Check CDP connection to TradingView and show current chart state."""
    from ..core.health import health_check
    _run(health_check())


@app.command()
def discover():
    """Report which TradingView API paths are available."""
    from ..core.health import discover
    _run(discover())


@app.command()
def ui():
    """Show current UI state: open panels, visible buttons."""
    from ..core.health import ui_state
    _run(ui_state())


@app.command()
def launch(
    port: Annotated[int, typer.Option(help="CDP port")] = 9222,
    kill_existing: Annotated[bool, typer.Option(help="Kill existing TV instances first")] = True,
):
    """Start TradingView Desktop with CDP enabled."""
    from ..core.health import launch as _launch
    _run(_launch(port=port, kill_existing=kill_existing))


@app.command()
def brief(
    rules_path: Annotated[str | None, typer.Option(help="Path to rules.json")] = None,
):
    """Run the morning brief: scan watchlist, read indicators, apply rules."""
    from ..core.morning import run_brief
    _run(run_brief(rules_path=rules_path))


@app.command()
def state():
    """Get current chart state (symbol, timeframe, indicators)."""
    from ..core.chart import get_state
    _run(get_state())


@app.command()
def quote(
    symbol: Annotated[str | None, typer.Argument(help="Symbol to quote (blank = current)")] = None,
):
    """Get real-time quote for a symbol."""
    from ..core.data import get_quote
    _run(get_quote(symbol=symbol))


@app.command()
def ohlcv(
    count: Annotated[int, typer.Option(help="Number of bars")] = 100,
    summary: Annotated[bool, typer.Option(help="Return summary stats instead of all bars")] = True,
):
    """Get OHLCV price data."""
    from ..core.data import get_ohlcv
    _run(get_ohlcv(count=count, summary=summary))


@app.command()
def indicators():
    """Get current indicator values from the data window."""
    from ..core.data import get_study_values
    _run(get_study_values())


@app.command()
def replay_status():
    """Show current replay mode status."""
    from ..core.replay import status
    _run(status())


@app.command()
def screenshot(
    region: Annotated[str, typer.Option(help="Region: full, chart, strategy_tester")] = "full",
):
    """Take a screenshot of the chart."""
    from ..core.capture import capture_screenshot
    _run(capture_screenshot(region=region))


@app.command()
def tabs():
    """List open chart tabs."""
    from ..core.tab import list_tabs
    _run(list_tabs())


@app.command()
def panes():
    """List chart panes in the current layout."""
    from ..core.pane import list_panes
    _run(list_panes())


@app.command()
def watchlist():
    """Get all symbols in the current watchlist."""
    from ..core.watchlist import get_watchlist
    _run(get_watchlist())


@app.command()
def alerts():
    """List all active alerts."""
    from ..core.alerts import list_alerts
    _run(list_alerts())


@app.command()
def session_get(
    date: Annotated[str | None, typer.Argument(help="Date (YYYY-MM-DD), defaults to today")] = None,
):
    """Retrieve a saved morning brief session."""
    from ..core.morning import get_session
    raw = json.dumps(get_session(date=date), indent=2, default=str)
    _json_out.print(Syntax(raw, "json", theme="monokai"))


@app.command()
def analyze(
    file: Annotated[str, typer.Argument(help="Path to a .pine file")],
):
    """Run static analysis on a Pine Script file (offline, no chart needed)."""
    from pathlib import Path

    from ..core.pine import analyze as _analyze
    source = Path(file).read_text(encoding="utf-8")
    result = _analyze(source=source)
    raw = json.dumps(result, indent=2, default=str)
    _json_out.print(Syntax(raw, "json", theme="monokai"))


@app.command()
def check(
    file: Annotated[str, typer.Argument(help="Path to a .pine file")],
):
    """Compile a Pine Script via TradingView's server API (no chart needed)."""
    from pathlib import Path

    from ..core.pine import check as _check
    source = Path(file).read_text(encoding="utf-8")
    _run(_check(source=source))


# ── Trade execution commands ─────────────────────────────────────────────────


@app.command()
def trade(
    symbol: Annotated[str, typer.Argument(help="Symbol to trade (e.g., BTCUSD, AAPL)")],
    side: Annotated[str, typer.Argument(help="buy or sell")],
    quantity: Annotated[float, typer.Argument(help="Quantity to trade")],
    order_type: Annotated[str, typer.Option(help="market, limit, stop, stop_limit")] = "market",
    price: Annotated[float | None, typer.Option(help="Limit/stop price")] = None,
    stop_loss: Annotated[float | None, typer.Option("--sl", help="Stop loss price")] = None,
    take_profit: Annotated[float | None, typer.Option("--tp", help="Take profit price")] = None,
):
    """Place a trade (paper mode by default)."""
    from ..core.execution import execute_trade
    _run(execute_trade(
        symbol=symbol, side=side, quantity=quantity,
        order_type=order_type, price=price,
        stop_loss=stop_loss, take_profit=take_profit,
    ))


@app.command()
def positions():
    """List all open positions."""
    from ..core.execution import get_positions
    _run(get_positions())


@app.command()
def account():
    """Get account balance, equity, and margin."""
    from ..core.execution import get_account
    _run(get_account())


@app.command()
def close_position(
    ticket: Annotated[int, typer.Argument(help="Position ticket to close")],
    reason: Annotated[str, typer.Option(help="Reason for closing")] = "",
):
    """Close a specific position."""
    from ..core.execution import close_position as _close
    _run(_close(ticket=ticket, reason=reason))


@app.command()
def set_mode(
    mode: Annotated[str, typer.Argument(help="paper, paper_broker, or live")],
    confirm: Annotated[bool, typer.Option(help="Required for live mode")] = False,
):
    """Switch execution mode."""
    from ..core.execution import set_mode as _set_mode
    raw = json.dumps(_set_mode(mode=mode, confirm=confirm), indent=2, default=str)
    _json_out.print(Syntax(raw, "json", theme="monokai"))


@app.command()
def get_mode():
    """Show current execution mode."""
    from ..core.execution import get_mode as _get_mode
    raw = json.dumps(_get_mode(), indent=2, default=str)
    _json_out.print(Syntax(raw, "json", theme="monokai"))


@app.command()
def broker_status():
    """Check which brokers are configured and connected."""
    from ..core.execution import broker_status as _status
    raw = json.dumps(_status(), indent=2, default=str)
    _json_out.print(Syntax(raw, "json", theme="monokai"))


@app.command()
def trade_history():
    """Show trade history for this session."""
    from ..core.execution import get_trade_history
    _run(get_trade_history())


def main():
    """Entry point for the ``tv`` console script."""
    app()
