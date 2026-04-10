"""DynamoDB-backed signal store for AWS deployment mode.

Requires boto3: pip install teletrader[aws]
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from teletrader.models.trading_signal import TradingSignal

try:
    import boto3
    from boto3.dynamodb.conditions import Key
except ImportError:
    boto3 = None  # type: ignore[assignment]


class DynamoDBSignalStore:
    """Signal store backed by AWS DynamoDB.

    Table schema:
        Partition key: pk (S) = "SIGNALS"
        Sort key: seq (N) = auto-increment sequence number
        TTL attribute: ttl (N) = Unix timestamp for 24h expiry

    All signals share the same partition key for simple cursor-based queries.
    """

    def __init__(self, table_name: str, region: str = "us-east-1") -> None:
        if boto3 is None:
            raise ImportError("boto3 is required: pip install teletrader[aws]")

        self._dynamodb = boto3.resource("dynamodb", region_name=region)
        self._table = self._dynamodb.Table(table_name)
        self._pk = "SIGNALS"

    def append(self, signal: TradingSignal) -> TradingSignal:
        # Get next sequence number via atomic counter
        seq = self._next_seq()
        signal.seq = seq

        ttl = int(datetime.now(UTC).timestamp()) + 86400  # 24h expiry

        item: dict[str, Any] = {
            "pk": self._pk,
            "seq": seq,
            "signal_id": signal.signal_id,
            "symbol": signal.symbol,
            "direction": signal.direction,
            "order_type": signal.order_type,
            "entry_price": str(signal.entry_price),
            "stop_loss": str(signal.stop_loss),
            "take_profits": json.dumps(signal.take_profits),
            "raw_text": signal.raw_text,
            "parsed_at_utc": signal.parsed_at_utc.isoformat(),
            "ttl": ttl,
        }
        self._table.put_item(Item=item)
        return signal

    def since(self, seq: int) -> list[TradingSignal]:
        response = self._table.query(
            KeyConditionExpression=Key("pk").eq(self._pk) & Key("seq").gt(seq),
            ScanIndexForward=True,
        )
        return [self._item_to_signal(item) for item in response.get("Items", [])]

    def get(self, signal_id: str) -> TradingSignal | None:
        # Scan is acceptable here since it's infrequent and table is small (24h TTL)
        response = self._table.scan(
            FilterExpression="signal_id = :sid",
            ExpressionAttributeValues={":sid": signal_id},
            Limit=1,
        )
        items = response.get("Items", [])
        return self._item_to_signal(items[0]) if items else None

    def _next_seq(self) -> int:
        """Atomic counter via DynamoDB UpdateItem."""
        response = self._table.update_item(
            Key={"pk": "COUNTER", "seq": 0},
            UpdateExpression="ADD #c :inc",
            ExpressionAttributeNames={"#c": "counter"},
            ExpressionAttributeValues={":inc": 1},
            ReturnValues="UPDATED_NEW",
        )
        return int(response["Attributes"]["counter"])

    @staticmethod
    def _item_to_signal(item: dict[str, Any]) -> TradingSignal:
        return TradingSignal(
            signal_id=item["signal_id"],
            seq=int(item["seq"]),
            symbol=item["symbol"],
            direction=item["direction"],
            order_type=item["order_type"],
            entry_price=float(item["entry_price"]),
            stop_loss=float(item["stop_loss"]),
            take_profits=json.loads(item["take_profits"]),
            raw_text=item["raw_text"],
            parsed_at_utc=datetime.fromisoformat(item["parsed_at_utc"]),
        )
