# ML-SuperTrend Training Script
# Author: Ninad
#
# Downloads full history across all timeframes from MT5, engineers features
# from multi-factor SuperTrend + multi-TF context, trains XGBoost models
# with walk-forward validation, and saves per-timeframe models for live use.
#
# Usage:
#   python train.py --symbol EURUSD --account demo
#   python train.py --symbol XAUUSD --timeframes H1 H4 D1
#   python train.py --symbol EURUSD --all-timeframes

import argparse
import logging
import sys
import MetaTrader5 as mt5

from core.data_fetcher import fetch_all_timeframes, ALL_TIMEFRAMES
from core.ml_trainer import MLTrainer, TrainConfig

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('training.log'),
    ],
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Train ML SuperTrend models on historical data")
    parser.add_argument("--symbol", default="EURUSD", help="Trading symbol")
    parser.add_argument("--account", default="demo", help="Account name from config.json")
    parser.add_argument(
        "--timeframes", nargs="+", default=["M15", "M30", "H1", "H4", "D1", "W1"],
        help="Target timeframes to train models for",
    )
    parser.add_argument(
        "--all-timeframes", action="store_true",
        help="Train on all available timeframes (M1 through MN1)",
    )
    parser.add_argument("--forward-bars", type=int, default=10, help="Look-ahead bars for labeling")
    parser.add_argument("--min-move-atr", type=float, default=1.0, help="Minimum move in ATR multiples")
    parser.add_argument("--n-estimators", type=int, default=500, help="Number of boosting rounds")
    parser.add_argument("--max-depth", type=int, default=6, help="Max tree depth")
    parser.add_argument("--learning-rate", type=float, default=0.05, help="Learning rate")
    parser.add_argument("--n-splits", type=int, default=5, help="Walk-forward CV splits")
    parser.add_argument("--model-dir", default="models", help="Directory to save trained models")
    parser.add_argument("--data-dir", default="data/raw", help="Directory for cached data")
    args = parser.parse_args()

    # Load account credentials
    import json
    with open("config.json") as f:
        config = json.load(f)
    account = config["accounts"][args.account]

    # Connect to MT5
    if not mt5.initialize():
        logger.error("MT5 initialization failed")
        sys.exit(1)

    if not mt5.login(account["login"], password=account["password"], server=account["server"]):
        logger.error(f"MT5 login failed: {mt5.last_error()}")
        mt5.shutdown()
        sys.exit(1)

    logger.info(f"Connected to MT5: {mt5.account_info().server}")
    logger.info(f"Account: {mt5.account_info().login}")

    # Determine which timeframes to download (need context TFs too)
    if args.all_timeframes:
        target_tfs = list(ALL_TIMEFRAMES.keys())
    else:
        target_tfs = args.timeframes

    # Always fetch higher TFs needed for context
    all_needed = set(target_tfs)
    default_context = {
        "M1": ["M15", "H1"], "M5": ["M30", "H1", "H4"],
        "M15": ["H1", "H4", "D1"], "M30": ["H1", "H4", "D1"],
        "H1": ["H4", "D1", "W1"], "H4": ["D1", "W1"],
        "D1": ["W1", "MN1"], "W1": ["MN1"],
    }
    for tf in target_tfs:
        for ctx_tf in default_context.get(tf, []):
            all_needed.add(ctx_tf)

    # Download data
    logger.info(f"\nFetching data for {args.symbol}: {sorted(all_needed)}")
    all_data = fetch_all_timeframes(
        symbol=args.symbol,
        timeframes=sorted(all_needed, key=lambda x: list(ALL_TIMEFRAMES.keys()).index(x)),
        cache_dir=args.data_dir,
    )

    if not all_data:
        logger.error("No data fetched. Check MT5 connection and symbol name.")
        mt5.shutdown()
        sys.exit(1)

    # Print data summary
    logger.info(f"\n{'='*50}")
    logger.info(f"{'DATA SUMMARY':^50}")
    logger.info(f"{'='*50}")
    for tf_name, df in sorted(all_data.items(), key=lambda x: list(ALL_TIMEFRAMES.keys()).index(x[0])):
        logger.info(f"  {tf_name:>4}: {len(df):>10,} bars | {df.index[0].date()} -> {df.index[-1].date()}")
    logger.info(f"{'='*50}\n")

    # Configure and run training
    train_config = TrainConfig(
        symbol=args.symbol,
        timeframes=target_tfs,
        context_timeframes=default_context,
        forward_bars=args.forward_bars,
        min_move_atr=args.min_move_atr,
        n_splits=args.n_splits,
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        learning_rate=args.learning_rate,
        model_dir=args.model_dir,
        data_dir=args.data_dir,
    )

    trainer = MLTrainer(train_config)
    results = trainer.train_all(all_data)

    # Final summary
    logger.info(f"\n{'#'*70}")
    logger.info(f"{'TRAINING COMPLETE':^70}")
    logger.info(f"{'#'*70}")
    logger.info(f"Symbol: {args.symbol}")
    logger.info(f"Models trained: {len(results)}")
    logger.info(f"Models saved to: {args.model_dir}/")
    for tf, res in results.items():
        logger.info(f"  {tf}: acc={res.final_test_accuracy:.4f}, f1={res.final_test_f1_macro:.4f}")
    logger.info(f"{'#'*70}\n")

    mt5.shutdown()


if __name__ == "__main__":
    main()
