"""Authenticated ingestion workload with successful-response latency measurements."""

import json
import math
import os
import time
import uuid
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

from locust import HttpUser, constant, events, task
from locust.env import Environment
from requests import Response

_statuses: Counter[str] = Counter()
_successful_latencies: Counter[int] = Counter()
_successes = 0
_failures = 0
_started = 0.0


def _percentile(percentile: float) -> int | None:
    if not _successes:
        return None
    position = math.ceil(_successes * percentile)
    seen = 0
    for latency, count in sorted(_successful_latencies.items()):
        seen += count
        if seen >= position:
            return latency
    return None


@events.test_start.add_listener
def start_measurement(environment: Environment, **kwargs: object) -> None:
    global _successes, _failures, _started
    _statuses.clear()
    _successful_latencies.clear()
    _successes = 0
    _failures = 0
    _started = time.monotonic()


@events.request.add_listener
def record_request(
    request_type: str,
    name: str,
    response_time: float,
    response: Response | None = None,
    exception: Exception | None = None,
    **kwargs: object,
) -> None:
    global _successes, _failures
    if request_type != "POST" or name != "/api/v1/trades/ingest/":
        return
    status = str(response.status_code) if response is not None else "connection_error"
    _statuses[status] += 1
    if exception is None:
        _successes += 1
        _successful_latencies[math.ceil(response_time)] += 1
    else:
        _failures += 1


@events.quitting.add_listener
def write_measurement(environment: Environment, **kwargs: object) -> None:
    path = os.getenv("BENCHMARK_SUMMARY_PATH")
    if not path:
        return
    elapsed = max(time.monotonic() - _started, 0.001)
    total = _successes + _failures
    report = {
        "elapsed_seconds": round(elapsed, 3),
        "total_requests": total,
        "successful_requests": _successes,
        "failed_requests": _failures,
        "error_rate": _failures / total if total else 1,
        "successful_rps": _successes / elapsed,
        "total_rps": total / elapsed,
        "successful_p95_ms": _percentile(0.95),
        "successful_p99_ms": _percentile(0.99),
        "latency_resolution_ms": 1,
        "http_status_counts": dict(_statuses),
    }
    Path(path).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


class TradeUser(HttpUser):
    wait_time = constant(0)

    def on_start(self) -> None:
        token = os.getenv("BENCHMARK_TOKEN")
        if not token:
            raise ValueError("BENCHMARK_TOKEN is required for the ingestion workload")
        self.client.headers.update({"Authorization": f"Bearer {token}"})

    @task
    def ingest_trade(self) -> None:
        payload = {
            "symbol": "SOL/USDT",
            "side": "BUY",
            "price": "150.250000000",
            "quantity": "10.500000000",
            "exchange_id": "binance",
            "trade_id": f"benchmark_{uuid.uuid4().hex}",
        }
        with self.client.post("/api/v1/trades/ingest/", json=payload, catch_response=True) as response:
            if response.status_code not in {200, 201}:
                response.failure(f"unexpected HTTP status {response.status_code}")
                return
            try:
                result = response.json()
                valid = (
                    isinstance(result, dict)
                    and result.get("symbol") == payload["symbol"]
                    and isinstance(result.get("price"), str)
                    and isinstance(result.get("quantity"), str)
                    and isinstance(result.get("notional"), str)
                    and isinstance(result.get("risk"), dict)
                    and result.get("side") == payload["side"]
                    and result.get("quote_currency") == "USDT"
                    and Decimal(result["price"]) == Decimal(payload["price"])
                    and Decimal(result["quantity"]) == Decimal(payload["quantity"])
                    and Decimal(result["notional"]) == Decimal("1577.625")
                    and result["risk"].get("is_high_risk") is False
                )
            except (ValueError, InvalidOperation):
                valid = False
            if not valid:
                response.failure("response does not match the ingestion contract")
