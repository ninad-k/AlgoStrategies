#!/usr/bin/env python3
"""Convert rules/default-rules.json into rules/rules-for-ea.csv for the MT5 Expert Advisor."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "rules" / "default-rules.json",
        help="Path to rules JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "rules" / "rules-for-ea.csv",
        help="Path to write EA CSV",
    )
    args = parser.parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))
    rows: list[list[str]] = []
    header = [
        "category_id",
        "category_label",
        "match",
        "field",
        "op",
        "value",
        "value2",
        "min",
        "max",
    ]
    for cat in data.get("categories", []):
        match = cat.get("match", "all")
        cid = cat["id"]
        label = cat.get("label", cid)
        for cond in cat.get("conditions", []):
            op = cond["op"]
            field = cond["field"]
            value = value2 = min_v = max_v = ""
            if op == "between":
                min_v = str(cond.get("min", ""))
                max_v = str(cond.get("max", ""))
            elif op == "contains":
                value = str(cond.get("value", ""))
            else:
                value = str(cond.get("value", ""))
            rows.append([cid, label, match, field, op, value, value2, min_v, max_v])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)

    print(f"Wrote {len(rows)} condition row(s) to {args.output}")


if __name__ == "__main__":
    main()
