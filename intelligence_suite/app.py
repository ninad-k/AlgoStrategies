"""
Intelligence Suite — Unified Entry Point
==========================================
Launches selected modules: ensemble trading engine, dashboards, and services.

Usage:
    python app.py                           # Full suite (paper mode)
    python app.py --mode paper              # Paper trading
    python app.py --mode live               # Live trading
    python app.py --modules ensemble regime # Only specific modules
    python app.py --dashboard-only          # Only dashboards (no trading)
    python app.py --help                    # Show all options
"""

import argparse
import logging
import sys
import threading
import time
from pathlib import Path

import yaml

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from shared.logging_config import setup_logging


def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration from YAML file."""
    path = Path(__file__).parent / config_path
    if not path.exists():
        print(f"Config not found at {path}, using defaults")
        return {}
    with open(path) as f:
        return yaml.safe_load(f)


def run_trading_engine(config: dict):
    """Run the ensemble trading engine in a loop."""
    from shared.indicators import calculate_indicators
    from shared.risk_manager import RiskManager
    from shared.broker import create_broker
    from ensemble.ensemble_engine import EnsembleEngine
    from regime_detector.detector import RegimeDetector
    from volume_profile.realtime_tracker import RealtimeVolumeTracker
    from shared.db import Database

    logger = logging.getLogger("trading_engine")

    ensemble = EnsembleEngine(config)
    risk_manager = RiskManager(config)
    broker = create_broker(config)
    regime_detector = RegimeDetector(config)
    volume_tracker = RealtimeVolumeTracker(config)
    db = Database()

    # Try MT5 data feed
    mt5_feed = None
    try:
        from shared.mt5_connector import MT5Connector
        mt5_feed = MT5Connector(config)
        if not mt5_feed.connected:
            mt5_feed = None
    except Exception as e:
        logger.warning(f"MT5 not available: {e}")

    symbols = config.get("trading", {}).get("allowed_symbols", [])
    timeframe = config.get("mt5_data", {}).get("timeframe", "1m")
    n_bars = config.get("mt5_data", {}).get("n_bars", 500)
    poll_interval = config.get("mt5_data", {}).get("poll_interval_seconds", 60)

    logger.info(f"Trading engine started | Mode: {config.get('trading', {}).get('mode', 'paper')}")
    logger.info(f"Symbols: {symbols} | Timeframe: {timeframe}")
    logger.info(f"Ensemble models: {[a.name for a in ensemble.analyzers]}")

    cycle = 0
    while True:
        cycle += 1
        logger.info(f"\n{'='*60}")
        logger.info(f"  Cycle {cycle} | Balance: {broker.get_balance():.2f}")
        logger.info(f"{'='*60}")

        for symbol in symbols:
            try:
                # Fetch data
                df = None
                if mt5_feed and mt5_feed.connected:
                    df = mt5_feed.get_candles(symbol, timeframe, n_bars)

                if df is None or len(df) < 50:
                    logger.warning(f"  {symbol}: insufficient data, skipping")
                    continue

                # Calculate indicators
                indicators = calculate_indicators(df, symbol)
                if not indicators:
                    continue
                indicators["timeframe"] = timeframe

                # Detect regime
                regime_result = regime_detector.detect(df, symbol)
                indicators["regime"] = regime_result.get("regime", "RANGING")
                logger.info(f"  {symbol} regime: {regime_result['regime']} (conf={regime_result['confidence']:.2f})")

                # Update volume profile
                vp = volume_tracker.update(symbol, df)
                if vp.get("poc"):
                    indicators["volume_poc"] = vp["poc"]
                    indicators["volume_vah"] = vp.get("vah", 0)
                    indicators["volume_val"] = vp.get("val", 0)

                # Run ensemble
                decision = ensemble.analyze(indicators)
                logger.info(
                    f"  {symbol} → {decision['final_action']} "
                    f"(conf={decision['final_confidence']:.2f}) | "
                    f"{decision.get('reason', '')[:80]}"
                )

                # Log to database
                db.log_ensemble_decision({
                    "symbol": symbol,
                    "final_action": decision["final_action"],
                    "final_confidence": decision["final_confidence"],
                    "individual_decisions": decision.get("individual_decisions", []),
                    "regime": regime_result.get("regime"),
                    "reason": decision.get("reason", ""),
                })

                # Risk check
                if decision["final_action"] != "HOLD":
                    check_decision = {
                        "symbol": symbol,
                        "confidence": decision["final_confidence"],
                    }
                    allowed, reason = risk_manager.can_trade(check_decision, indicators)

                    if allowed:
                        atr = float(indicators.get("atr", 0))
                        sl_mult = decision.get("sl_distance_atr", 1.0)
                        tp_mult = decision.get("tp_distance_atr", 1.5)

                        pos_size = risk_manager.calculate_position_size(
                            broker.get_balance(), atr, sl_mult, symbol
                        )

                        if pos_size["qty"] > 0:
                            close_price = float(indicators["close"])
                            sl = close_price - (atr * sl_mult) if decision["final_action"] == "BUY" else close_price + (atr * sl_mult)
                            tp = close_price + (atr * tp_mult) if decision["final_action"] == "BUY" else close_price - (atr * tp_mult)

                            result = broker.place_order(
                                symbol, decision["final_action"],
                                pos_size["qty"], round(sl, 5), round(tp, 5),
                            )

                            if result.get("status") == "filled":
                                trade = {
                                    "symbol": symbol,
                                    "action": decision["final_action"],
                                    "qty": pos_size["qty"],
                                    "entry_price": close_price,
                                    "sl": sl, "tp": tp,
                                    "confidence": decision["final_confidence"],
                                    "reason": decision.get("reason", ""),
                                    "timestamp": decision.get("timestamp", ""),
                                }
                                risk_manager.register_trade(trade)
                                logger.info(f"  TRADE: {decision['final_action']} {pos_size['qty']} {symbol}")
                    else:
                        logger.info(f"  Blocked: {reason}")

                time.sleep(1)  # Pause between symbols

            except Exception as e:
                logger.error(f"  {symbol} error: {e}", exc_info=True)

        logger.info(f"  Cycle {cycle} complete. Next in {poll_interval}s")
        time.sleep(poll_interval)


def run_heatmap_dashboard(config: dict):
    """Launch the Portfolio Heatmap Dashboard."""
    import uvicorn
    from heatmap_dashboard.server import create_app

    app = create_app(config)
    port = config.get("heatmap", {}).get("port", 8061)
    logging.getLogger("heatmap_dashboard").info(f"Heatmap dashboard starting on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


def run_multi_account_dashboard(config: dict):
    """Launch the Multi-Account Dashboard."""
    import uvicorn
    from multi_account.server import create_app

    app = create_app(config)
    port = config.get("multi_account", {}).get("port", 8062)
    logging.getLogger("multi_account").info(f"Multi-account dashboard starting on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


def main():
    parser = argparse.ArgumentParser(description="Intelligence Suite — Trading Engine")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--mode", choices=["paper", "live"], help="Trading mode override")
    parser.add_argument("--modules", nargs="*", default=None,
                        help="Modules to run: ensemble regime sentiment volume correlation pattern")
    parser.add_argument("--dashboard-only", action="store_true", help="Only run dashboards")
    parser.add_argument("--no-dashboard", action="store_true", help="Skip dashboards")
    parser.add_argument("--symbols", nargs="*", help="Override allowed symbols")
    parser.add_argument("--port", type=int, help="Override main server port")
    args = parser.parse_args()

    config = load_config(args.config)

    # Apply overrides
    if args.mode:
        config.setdefault("trading", {})["mode"] = args.mode
    if args.symbols:
        config.setdefault("trading", {})["allowed_symbols"] = args.symbols
    if args.port:
        config.setdefault("server", {})["port"] = args.port

    setup_logging(config.get("logging", {}).get("level", "INFO"))
    logger = logging.getLogger("app")

    logger.info("=" * 60)
    logger.info("  Intelligence Suite v1.0.0")
    logger.info(f"  Mode: {config.get('trading', {}).get('mode', 'paper')}")
    logger.info("=" * 60)

    threads = []

    if not args.dashboard_only:
        t = threading.Thread(target=run_trading_engine, args=(config,), daemon=True)
        t.start()
        threads.append(("Trading Engine", t))
        logger.info("Trading engine started")

    if not args.no_dashboard:
        t1 = threading.Thread(target=run_heatmap_dashboard, args=(config,), daemon=True)
        t1.start()
        threads.append(("Heatmap Dashboard", t1))

        if config.get("multi_account", {}).get("accounts"):
            t2 = threading.Thread(target=run_multi_account_dashboard, args=(config,), daemon=True)
            t2.start()
            threads.append(("Multi-Account Dashboard", t2))

    logger.info(f"Running {len(threads)} service(s)")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")


if __name__ == "__main__":
    main()
