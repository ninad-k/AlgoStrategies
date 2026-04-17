"""
Unit test for broker_bridge.is_bot_trade().

Ensures that only positions / deals / orders with magic=BOT_MAGIC pass the
filter, so the dashboard and reviewer never mix in trades from other
strategies sharing the same MT5 account.

Usage:
    python test_bot_filter.py
"""

from types import SimpleNamespace

from broker_bridge import BOT_MAGIC, is_bot_trade


def main():
    cases = [
        (SimpleNamespace(magic=BOT_MAGIC, symbol="BTCUSD"), True,  "bot namedtuple"),
        (SimpleNamespace(magic=0,         symbol="BTCUSD"), False, "manual click (magic=0)"),
        (SimpleNamespace(magic=99999,     symbol="BTCUSD"), False, "other EA (magic=99999)"),
        ({"magic": BOT_MAGIC, "symbol": "ETHUSD"},          True,  "bot dict"),
        ({"magic": 0,         "symbol": "ETHUSD"},          False, "manual dict"),
        ({},                                                False, "empty dict"),
        (None,                                              False, "None"),
        (SimpleNamespace(symbol="BTCUSD"),                  False, "object with no magic"),
    ]

    failures = 0
    for obj, expected, label in cases:
        got = is_bot_trade(obj)
        status = "ok" if got == expected else "FAIL"
        if got != expected:
            failures += 1
        print(f"  [{status}] is_bot_trade({label}) = {got} (expected {expected})")

    print()
    if failures:
        print(f"FAILED: {failures}/{len(cases)} cases")
        raise SystemExit(1)
    print(f"PASSED: {len(cases)} cases")


if __name__ == "__main__":
    main()
