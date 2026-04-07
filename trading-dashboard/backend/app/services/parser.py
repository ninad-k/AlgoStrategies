import uuid
from datetime import datetime, timezone
from typing import Optional

import pandas as pd


REQUIRED_COLUMNS = {"ticket", "open_time", "symbol", "type", "lots", "open_price"}

COLUMN_ALIASES = {
    "ticket": ["ticket", "order", "deal"],
    "open_time": ["open time", "opentime", "open_time", "time"],
    "close_time": ["close time", "closetime", "close_time"],
    "symbol": ["symbol", "instrument"],
    "type": ["type", "direction", "action"],
    "lots": ["lots", "volume", "size"],
    "open_price": ["open price", "openprice", "open_price", "price"],
    "close_price": ["close price", "closeprice", "close_price"],
    "sl": ["s/l", "sl", "stop loss", "stoploss"],
    "tp": ["t/p", "tp", "take profit", "takeprofit"],
    "profit": ["profit", "pnl", "p&l"],
    "commission": ["commission", "comm"],
    "swap": ["swap"],
    "comment": ["comment", "comments"],
    "magic": ["magic", "magic number", "magicnumber", "expert"],
}


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Map actual column names to canonical names via COLUMN_ALIASES."""
    rename_map = {}
    lower_cols = {c.lower().strip(): c for c in df.columns}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in lower_cols:
                rename_map[lower_cols[alias]] = canonical
                break
    return df.rename(columns=rename_map)


def _parse_datetime(val) -> Optional[datetime]:
    if pd.isna(val) or val == "" or val is None:
        return None
    if isinstance(val, datetime):
        return val.replace(tzinfo=timezone.utc) if val.tzinfo is None else val
    try:
        dt = pd.to_datetime(val, dayfirst=False)
        return dt.to_pydatetime().replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _parse_float(val) -> Optional[float]:
    if pd.isna(val) or val == "" or val is None:
        return None
    try:
        f = float(val)
        return None if f == 0.0 else f
    except (ValueError, TypeError):
        return None


def _parse_type(val: str) -> str:
    v = str(val).strip().lower()
    if v in ("0", "buy"):
        return "BUY"
    if v in ("1", "sell"):
        return "SELL"
    return str(val).upper()


def parse_file(file_bytes: bytes, filename: str, account_id: str) -> tuple[list[dict], list[str]]:
    """
    Parse CSV or Excel trade history file.
    Returns (rows, warnings).
    Each row is a dict ready for DB insertion.
    """
    if filename.endswith(".csv"):
        df = pd.read_csv(pd.io.common.BytesIO(file_bytes), thousands=",")
    elif filename.endswith((".xlsx", ".xls")):
        df = pd.read_excel(pd.io.common.BytesIO(file_bytes))
    else:
        raise ValueError(f"Unsupported file format: {filename}")

    df = _normalise_columns(df)

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    batch_id = uuid.uuid4()
    rows = []
    warnings = []

    for idx, row in df.iterrows():
        try:
            ticket = int(row["ticket"])
            open_time = _parse_datetime(row.get("open_time"))
            if open_time is None:
                warnings.append(f"Row {idx}: invalid open_time, skipping")
                continue

            sl_raw = _parse_float(row.get("sl"))
            tp_raw = _parse_float(row.get("tp"))
            magic_raw = row.get("magic")
            magic = None
            if magic_raw is not None and not pd.isna(magic_raw):
                try:
                    magic = int(magic_raw)
                    if magic == 0:
                        magic = None
                except (ValueError, TypeError):
                    magic = None

            rows.append({
                "account_id": account_id,
                "ticket": ticket,
                "open_time": open_time,
                "close_time": _parse_datetime(row.get("close_time")),
                "symbol": str(row["symbol"]).strip(),
                "type": _parse_type(row["type"]),
                "lots": float(row["lots"]),
                "open_price": float(row["open_price"]),
                "close_price": _parse_float(row.get("close_price")),
                "sl": sl_raw,
                "tp": tp_raw,
                "profit": _parse_float(row.get("profit")) or 0.0,
                "commission": float(row.get("commission") or 0),
                "swap": float(row.get("swap") or 0),
                "comment": str(row.get("comment") or "").strip() or None,
                "magic": magic,
                "upload_batch_id": batch_id,
            })
        except Exception as e:
            warnings.append(f"Row {idx}: {e}")

    return rows, warnings
