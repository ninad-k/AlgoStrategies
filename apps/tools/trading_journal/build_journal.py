"""CLI for building the Rey Capital scalping trading journal.

Two input modes:

    --config PATH   Live MT5 pull (Windows + MetaTrader5 package required).
                    Reuses apps/tools/pnl_dashboard/extract_mt5_data.py end
                    to end — no duplicated connection logic.

    --csv PATH      Rebuild from an already-extracted combined CSV (produced
                    by extract_mt5_data.py or TradeHistoryExporter_EA.mq5).
                    Works anywhere, no MT5 runtime needed.

Output is a timestamped workbook in apps/tools/trading_journal/out/ plus a
ReyCapital_ScalpingJournal_latest.xlsx pointer for convenience.
"""
from __future__ import annotations

import argparse
import logging
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from . import transform
from .journal_writer import build_workbook

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("trading_journal")

OUT_DIR = Path(__file__).resolve().parent / "out"


def _load_from_csvs(paths: list[Path]) -> pd.DataFrame:
    frames = []
    for p in paths:
        logger.info("Loading CSV %s", p)
        frames.append(pd.read_csv(p))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _load_from_mt5(config_path: Path) -> pd.DataFrame:
    """Pull all configured accounts via extract_mt5_data. Requires Windows + MT5."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "pnl_dashboard"))
        import extract_mt5_data as extractor
    except ImportError as exc:
        raise RuntimeError(
            "Could not import extract_mt5_data from apps/tools/pnl_dashboard. "
            "Is the MetaTrader5 Python package installed? (Windows only.)"
        ) from exc

    cfg = extractor.load_config(config_path)
    start_date = datetime.strptime(cfg.get("start_date", "2020-01-01"), "%Y-%m-%d")
    end_date = datetime.now() + timedelta(days=1)

    frames = []
    for account in cfg.get("accounts", []):
        logger.info("Pulling MT5 account %s (%s)", account["login"], account.get("label", ""))
        frame = extractor.extract_account(account, start_date, end_date)
        if not frame.empty:
            frames.append(frame)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _output_path(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return OUT_DIR / f"ReyCapital_ScalpingJournal_{ts}.xlsx"


def _write_latest_pointer(written: Path) -> Path:
    latest = written.parent / "ReyCapital_ScalpingJournal_latest.xlsx"
    shutil.copyfile(written, latest)
    return latest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the Rey Capital scalping trading journal.")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--config", type=Path, help="Path to accounts.yaml for live MT5 pull.")
    src.add_argument("--csv", type=Path, nargs="+", help="One or more pre-extracted combined CSVs.")
    parser.add_argument("--output", type=Path, help="Explicit output xlsx path. Default: timestamped in out/.")
    parser.add_argument("--source-label", default=None,
                        help="Override the 'Data Source' label shown on the Cover sheet.")
    args = parser.parse_args(argv)

    if args.config:
        raw = _load_from_mt5(args.config)
        source_label = args.source_label or f"MT5 live ({args.config.name})"
    else:
        raw = _load_from_csvs(args.csv)
        source_label = args.source_label or f"CSV: {', '.join(p.name for p in args.csv)}"

    if raw.empty:
        logger.warning("No trade data loaded. Writing an empty journal anyway.")

    logger.info("Raw rows: %d", len(raw))
    df = transform.normalise(raw)
    logger.info("Normalised closed trades: %d", len(df))

    out_path = _output_path(args.output)
    written = build_workbook(df, out_path, generated_at=datetime.utcnow(), source_label=source_label)
    latest = _write_latest_pointer(written)
    logger.info("Wrote %s", written)
    logger.info("Updated %s", latest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
