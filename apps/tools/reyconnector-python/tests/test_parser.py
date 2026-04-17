"""Unit tests for the alert body parser."""

import pytest

from reyconnector.execution.parser import AlertParseError, ParsedAlert, parse_alert


# ── CSV parsing ──────────────────────────────────────────────────────


class TestParseCSVBasic:
    def test_minimal_csv(self):
        result = parse_alert("ema200,buy,EURUSD")
        assert result.strategy == "ema200"
        assert result.action == "buy"
        assert result.symbol == "EURUSD"
        assert result.lots is None
        assert result.stop_loss is None
        assert result.partial_tps == []
        assert result.trailing is None

    def test_action_case_insensitive(self):
        result = parse_alert("ema200,BUY,EURUSD")
        assert result.action == "buy"

        result = parse_alert("ema200,Sell,XAUUSD")
        assert result.action == "sell"

    def test_symbol_uppercased(self):
        result = parse_alert("ema200,buy,eurusd")
        assert result.symbol == "EURUSD"

    def test_whitespace_trimmed(self):
        result = parse_alert("  ema200 , buy , EURUSD  ")
        assert result.strategy == "ema200"
        assert result.action == "buy"
        assert result.symbol == "EURUSD"


class TestParseCSVWithParams:
    def test_stop_loss(self):
        result = parse_alert("ema200,buy,EURUSD,sl=1.0800")
        assert result.stop_loss == 1.0800

    def test_lots_override(self):
        result = parse_alert("ema200,buy,EURUSD,lots=0.50")
        assert result.lots == 0.50

    def test_magic_number(self):
        result = parse_alert("ema200,buy,EURUSD,magic=100001")
        assert result.magic == 100001

    def test_comment(self):
        result = parse_alert("ema200,buy,EURUSD,comment=manual_entry")
        assert result.comment == "manual_entry"

    def test_single_tp(self):
        result = parse_alert("ema200,buy,EURUSD,tp1=1.0900")
        assert len(result.partial_tps) == 1
        assert result.partial_tps[0].level == 1
        assert result.partial_tps[0].price == 1.0900
        assert result.partial_tps[0].close_percent is None

    def test_three_tps(self):
        result = parse_alert("ema200,sell,XAUUSD,tp1=2010.00,tp2=2000.00,tp3=1990.00")
        assert len(result.partial_tps) == 3
        assert result.partial_tps[0].level == 1
        assert result.partial_tps[0].price == 2010.00
        assert result.partial_tps[1].level == 2
        assert result.partial_tps[1].price == 2000.00
        assert result.partial_tps[2].level == 3
        assert result.partial_tps[2].price == 1990.00

    def test_tps_with_close_percents(self):
        result = parse_alert(
            "ema200,buy,EURUSD,tp1=1.0900,close1=50,tp2=1.1000,close2=30,tp3=1.1100,close3=20"
        )
        assert len(result.partial_tps) == 3
        assert result.partial_tps[0].close_percent == 50.0
        assert result.partial_tps[1].close_percent == 30.0
        assert result.partial_tps[2].close_percent == 20.0

    def test_trailing_stop(self):
        result = parse_alert("ema200,buy,EURUSD,trailing=1.0950:0.0020")
        assert result.trailing is not None
        assert result.trailing.activation_price == 1.0950
        assert result.trailing.trailing_distance == 0.0020

    def test_full_csv(self):
        raw = (
            "smartmoney,buy,GBPUSD,lots=0.20,sl=1.2600,"
            "tp1=1.2700,close1=40,tp2=1.2800,close2=30,tp3=1.2900,close3=30,"
            "trailing=1.2750:0.0020,magic=200,comment=smc_entry"
        )
        result = parse_alert(raw)
        assert result.strategy == "smartmoney"
        assert result.action == "buy"
        assert result.symbol == "GBPUSD"
        assert result.lots == 0.20
        assert result.stop_loss == 1.2600
        assert result.magic == 200
        assert result.comment == "smc_entry"
        assert len(result.partial_tps) == 3
        assert result.trailing is not None
        assert result.trailing.activation_price == 1.2750

    def test_tps_sorted_by_level(self):
        result = parse_alert("ema200,buy,EURUSD,tp3=1.1100,tp1=1.0900,tp2=1.1000")
        assert result.partial_tps[0].level == 1
        assert result.partial_tps[1].level == 2
        assert result.partial_tps[2].level == 3

    def test_close_percent_without_tp_price_creates_placeholder(self):
        result = parse_alert("ema200,buy,EURUSD,close1=50")
        assert len(result.partial_tps) == 1
        assert result.partial_tps[0].level == 1
        assert result.partial_tps[0].price == 0.0
        assert result.partial_tps[0].close_percent == 50.0

    def test_unknown_kv_params_ignored(self):
        result = parse_alert("ema200,buy,EURUSD,foo=bar,baz=123")
        assert result.strategy == "ema200"

    def test_param_without_equals_ignored(self):
        result = parse_alert("ema200,buy,EURUSD,extrafield")
        assert result.strategy == "ema200"


# ── JSON parsing ─────────────────────────────────────────────────────


class TestParseJSON:
    def test_minimal_json(self):
        result = parse_alert('{"strategy":"ema200","action":"buy","symbol":"EURUSD"}')
        assert result.strategy == "ema200"
        assert result.action == "buy"
        assert result.symbol == "EURUSD"

    def test_short_keys(self):
        result = parse_alert('{"s":"ema200","a":"buy","sym":"eurusd"}')
        assert result.strategy == "ema200"
        assert result.action == "buy"
        assert result.symbol == "EURUSD"

    def test_json_with_all_fields(self):
        raw = (
            '{"strategy":"goldFib","action":"sell","symbol":"XAUUSD",'
            '"lots":0.30,"sl":2050.00,'
            '"tp1":2030.00,"close1":40,"tp2":2010.00,"close2":30,"tp3":1990.00,"close3":30,'
            '"trailing":{"activation_price":2020.00,"trailing_distance":5.00},'
            '"magic":300,"comment":"gold_short"}'
        )
        result = parse_alert(raw)
        assert result.strategy == "goldFib"
        assert result.action == "sell"
        assert result.symbol == "XAUUSD"
        assert result.lots == 0.30
        assert result.stop_loss == 2050.00
        assert len(result.partial_tps) == 3
        assert result.partial_tps[0].price == 2030.00
        assert result.partial_tps[0].close_percent == 40.0
        assert result.trailing is not None
        assert result.trailing.activation_price == 2020.00
        assert result.trailing.trailing_distance == 5.00
        assert result.magic == 300
        assert result.comment == "gold_short"

    def test_json_trailing_as_string(self):
        raw = '{"strategy":"ema200","action":"buy","symbol":"EURUSD","trailing":"1.0950:0.0020"}'
        result = parse_alert(raw)
        assert result.trailing is not None
        assert result.trailing.activation_price == 1.0950

    def test_json_partial_tps_only_tp1(self):
        raw = '{"strategy":"ema200","action":"buy","symbol":"EURUSD","tp1":1.0900}'
        result = parse_alert(raw)
        assert len(result.partial_tps) == 1
        assert result.partial_tps[0].level == 1


# ── Error cases ──────────────────────────────────────────────────────


class TestParseErrors:
    def test_empty_body(self):
        with pytest.raises(AlertParseError, match="Empty alert body"):
            parse_alert("")

    def test_whitespace_only(self):
        with pytest.raises(AlertParseError, match="Empty alert body"):
            parse_alert("   ")

    def test_csv_too_few_fields(self):
        with pytest.raises(AlertParseError, match="at least 3 fields"):
            parse_alert("ema200,buy")

    def test_csv_invalid_action(self):
        with pytest.raises(AlertParseError, match="Invalid action"):
            parse_alert("ema200,hold,EURUSD")

    def test_csv_empty_strategy(self):
        with pytest.raises(AlertParseError, match="Strategy name cannot be empty"):
            parse_alert(",buy,EURUSD")

    def test_csv_empty_symbol(self):
        with pytest.raises(AlertParseError, match="Symbol cannot be empty"):
            parse_alert("ema200,buy,")

    def test_json_invalid(self):
        with pytest.raises(AlertParseError, match="Invalid JSON"):
            parse_alert("{bad json}")

    def test_json_not_object(self):
        with pytest.raises(AlertParseError, match="must be an object"):
            parse_alert("[1,2,3]")

    def test_json_missing_fields(self):
        with pytest.raises(AlertParseError, match="must contain"):
            parse_alert('{"strategy":"ema200"}')

    def test_json_invalid_action(self):
        with pytest.raises(AlertParseError, match="Invalid action"):
            parse_alert('{"strategy":"ema200","action":"hold","symbol":"EURUSD"}')
