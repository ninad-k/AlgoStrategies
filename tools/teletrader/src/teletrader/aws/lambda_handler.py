"""AWS Lambda handler for TeleTrader.

Single Lambda function behind API Gateway:
  POST /signal  — parse raw Telegram text, store in DynamoDB
  GET  /signals — return signals since a given seq (EA polling)

Deploy via SAM: see template.yaml
"""

from __future__ import annotations

import json
import os
from typing import Any

from teletrader.parsing.signal_parser import parse_signal
from teletrader.store.dynamodb_store import DynamoDBSignalStore

_TABLE = os.environ.get("DYNAMODB_TABLE", "teletrader-signals")
_REGION = os.environ.get("AWS_REGION", "us-east-1")

_store: DynamoDBSignalStore | None = None


def _get_store() -> DynamoDBSignalStore:
    global _store
    if _store is None:
        _store = DynamoDBSignalStore(table_name=_TABLE, region=_REGION)
    return _store


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda entry point — routes based on HTTP method and path."""
    method = event.get("httpMethod", event.get("requestContext", {}).get("http", {}).get("method", ""))
    path = event.get("path", event.get("rawPath", ""))

    if method == "POST" and "/signal" in path:
        return _handle_post_signal(event)
    elif method == "GET" and "/signals" in path:
        return _handle_get_signals(event)
    elif method == "GET" and "/health" in path:
        return _response(200, {"status": "ok", "service": "teletrader-lambda"})
    else:
        return _response(404, {"error": "Not found"})


def _handle_post_signal(event: dict[str, Any]) -> dict[str, Any]:
    body = event.get("body", "")
    if event.get("isBase64Encoded"):
        import base64
        body = base64.b64decode(body).decode("utf-8")

    if not body or not body.strip():
        return _response(422, {"error": "Empty message body"})

    signal = parse_signal(body.strip())
    if signal is None:
        return _response(422, {"error": "Could not parse trading signal from message"})

    store = _get_store()
    stored = store.append(signal)
    return _response(201, stored.to_ea_dict())


def _handle_get_signals(event: dict[str, Any]) -> dict[str, Any]:
    params = event.get("queryStringParameters") or {}
    since = int(params.get("since", "0"))

    store = _get_store()
    signals = store.since(since)
    return _response(200, {"signals": [s.to_ea_dict() for s in signals]})


def _response(status_code: int, body: Any) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, default=str),
    }
