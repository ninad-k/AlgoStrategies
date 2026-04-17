"""Tests for the Telegram signal parser."""

import pytest

from teletrader.parsing.signal_parser import parse_signal


class TestParseSignal:
    """Test parse_signal with various Telegram message formats."""

    def test_standard_buy_above(self):
        msg = (
            "XAUUSD Buy Trigger only Above 4756 \U0001F4C8\n"
            "\n"
            "SL 4736\n"
            "\n"
            "\n"
            "Target 4760 4764 4785+ \U0001F3AF"
        )
        sig = parse_signal(msg)
        assert sig is not None
        assert sig.symbol == "XAUUSD"
        assert sig.direction == "buy"
        assert sig.order_type == "buy_stop"
        assert sig.entry_price == 4756.0
        assert sig.stop_loss == 4736.0
        assert sig.take_profits == [4760.0, 4764.0, 4785.0]

    def test_sell_below(self):
        msg = (
            "XAUUSD Sell Trigger only Below 2345\n"
            "SL: 2360\n"
            "Target 2340 2330 2310"
        )
        sig = parse_signal(msg)
        assert sig is not None
        assert sig.symbol == "XAUUSD"
        assert sig.direction == "sell"
        assert sig.order_type == "sell_stop"
        assert sig.entry_price == 2345.0
        assert sig.stop_loss == 2360.0
        assert sig.take_profits == [2340.0, 2330.0, 2310.0]

    def test_buy_below_limit(self):
        msg = (
            "EURUSD Buy Below 1.0850\n"
            "SL 1.0800\n"
            "Target 1.0900 1.0950 1.1000"
        )
        sig = parse_signal(msg)
        assert sig is not None
        assert sig.order_type == "buy_limit"
        assert sig.entry_price == 1.0850

    def test_sell_above_limit(self):
        msg = (
            "GBPUSD Sell Above 1.2750\n"
            "Stop Loss: 1.2800\n"
            "Target 1.2700 1.2650 1.2600"
        )
        sig = parse_signal(msg)
        assert sig is not None
        assert sig.order_type == "sell_limit"
        assert sig.entry_price == 1.2750
        assert sig.stop_loss == 1.2800

    def test_tp_labeled_format(self):
        msg = (
            "XAUUSD Buy Above 4756\n"
            "SL 4736\n"
            "TP1: 4760 TP2: 4764 TP3: 4785"
        )
        sig = parse_signal(msg)
        assert sig is not None
        assert sig.take_profits == [4760.0, 4764.0, 4785.0]

    def test_at_sign_entry(self):
        msg = (
            "XAUUSD BUY @ 4756\n"
            "SL 4736\n"
            "Target 4760 4764 4785"
        )
        sig = parse_signal(msg)
        assert sig is not None
        assert sig.direction == "buy"
        assert sig.entry_price == 4756.0
        # No above/below keyword → defaults to buy_stop
        assert sig.order_type == "buy_stop"

    def test_gold_alias(self):
        msg = (
            "GOLD Buy Above 4756\n"
            "SL 4736\n"
            "Target 4760 4764 4785"
        )
        sig = parse_signal(msg)
        assert sig is not None
        assert sig.symbol == "XAUUSD"  # resolved alias

    def test_slash_separated_targets(self):
        msg = (
            "XAUUSD Buy Above 4756\n"
            "SL 4736\n"
            "Targets: 4760/4764/4785"
        )
        sig = parse_signal(msg)
        assert sig is not None
        assert sig.take_profits == [4760.0, 4764.0, 4785.0]

    def test_stoploss_variation(self):
        msg = (
            "USDJPY Sell Below 150.50\n"
            "Stoploss 151.00\n"
            "Target 150.00 149.50 149.00"
        )
        sig = parse_signal(msg)
        assert sig is not None
        assert sig.stop_loss == 151.00

    def test_decimal_prices(self):
        msg = (
            "EURUSD Buy Above 1.08550\n"
            "SL 1.08200\n"
            "Target 1.08800 1.09100 1.09500"
        )
        sig = parse_signal(msg)
        assert sig is not None
        assert sig.entry_price == 1.08550
        assert sig.stop_loss == 1.08200
        assert sig.take_profits == [1.08800, 1.09100, 1.09500]

    def test_empty_message(self):
        assert parse_signal("") is None
        assert parse_signal("   ") is None

    def test_no_symbol(self):
        msg = "Buy Above 4756\nSL 4736\nTarget 4760 4764 4785"
        assert parse_signal(msg) is None

    def test_no_direction(self):
        msg = "XAUUSD Above 4756\nSL 4736\nTarget 4760 4764 4785"
        assert parse_signal(msg) is None

    def test_no_entry_price(self):
        msg = "XAUUSD Buy\nSL 4736\nTarget 4760 4764 4785"
        assert parse_signal(msg) is None

    def test_no_stop_loss(self):
        msg = "XAUUSD Buy Above 4756\nTarget 4760 4764 4785"
        assert parse_signal(msg) is None

    def test_no_targets(self):
        msg = "XAUUSD Buy Above 4756\nSL 4736"
        assert parse_signal(msg) is None

    def test_signal_id_generated(self):
        msg = (
            "XAUUSD Buy Above 4756\n"
            "SL 4736\n"
            "Target 4760 4764 4785"
        )
        sig1 = parse_signal(msg)
        sig2 = parse_signal(msg)
        assert sig1 is not None and sig2 is not None
        assert sig1.signal_id != sig2.signal_id

    def test_raw_text_preserved(self):
        msg = "XAUUSD Buy Above 4756 \U0001F4C8\nSL 4736\nTarget 4760 4764 4785 \U0001F3AF"
        sig = parse_signal(msg)
        assert sig is not None
        assert sig.raw_text == msg

    def test_to_ea_dict(self):
        msg = (
            "XAUUSD Buy Above 4756\n"
            "SL 4736\n"
            "Target 4760 4764 4785"
        )
        sig = parse_signal(msg)
        assert sig is not None
        d = sig.to_ea_dict()
        assert d["symbol"] == "XAUUSD"
        assert d["direction"] == "buy"
        assert d["orderType"] == "buy_stop"
        assert d["entryPrice"] == 4756.0
        assert d["stopLoss"] == 4736.0
        assert d["takeProfits"] == [4760.0, 4764.0, 4785.0]
        assert "signalId" in d
        assert "seq" in d
        assert "parsedAtUtc" in d
