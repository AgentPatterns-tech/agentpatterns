from __future__ import annotations

from typing import Any


def build_request(*, report_date: str, region: str, source: str) -> dict[str, Any]:
    rows = [
        {
            "order_id": "o-1001",
            "event_ts": "2026-03-01T10:00:00Z",
            "status": "paid",
            "amount": 120.0,
            "channel": "paid_search",
            "latency_ms": 180,
        },
        {
            "order_id": "o-1002",
            "event_ts": "2026-03-01T10:05:00Z",
            "status": "paid",
            "amount": 90.0,
            "channel": "email",
            "latency_ms": 160,
        },
        {
            "order_id": "o-1003",
            "event_ts": "2026-03-01T10:10:00Z",
            "status": "failed",
            "amount": 0.0,
            "channel": "paid_search",
            "latency_ms": 240,
        },
        {
            "order_id": "o-1004",
            "event_ts": "2026-03-01T10:15:00Z",
            "status": "refunded",
            "amount": 40.0,
            "channel": "email",
            "latency_ms": 210,
        },
        {
            "order_id": "o-1005",
            "event_ts": "2026-03-01T10:20:00Z",
            "status": "paid",
            "amount": 140.0,
            "channel": "paid_search",
            "latency_ms": 170,
        },
        {
            "order_id": "o-1006",
            "event_ts": "2026-03-01T10:25:00Z",
            "status": "paid",
            "amount": 110.0,
            "channel": None,
            "latency_ms": 190,
        },
        {
            "order_id": "o-1007",
            "event_ts": "2026-03-01T10:30:00Z",
            "status": "failed",
            "amount": 0.0,
            "channel": "organic",
            "latency_ms": 260,
        },
        {
            "order_id": "o-1008",
            "event_ts": "2026-03-01T10:35:00Z",
            "status": "paid",
            "amount": 80.0,
            "channel": "paid_social",
            "latency_ms": 200,
        },
        {
            "order_id": "o-1009",
            "event_ts": "2026-03-01T10:40:00Z",
            "status": "refunded",
            "amount": 30.0,
            "channel": "paid_social",
            "latency_ms": 230,
        },
        {
            "order_id": "o-1010",
            "event_ts": "2026-03-01T10:45:00Z",
            "status": "paid",
            "amount": 70.0,
            "channel": "paid_search",
            "latency_ms": 175,
        },
        {
            "order_id": "o-1006",
            "event_ts": "2026-03-01T10:50:00Z",
            "status": "paid",
            "amount": 110.0,
            "channel": "email",
            "latency_ms": 188,
        },
        {
            "order_id": "o-1011",
            "event_ts": "2026-03-01T10:55:00Z",
            "status": "paid",
            "amount": 60.0,
            "channel": None,
            "latency_ms": 195,
        },
    ]

    return {
        "request": {
            "report_date": report_date,
            "region": region.upper(),
            "source": source,
            "rows": rows,
        },
        "policy_hints": {
            "allowed_sources": ["warehouse_sales_daily", "warehouse_refunds_daily"],
            "allowed_regions": ["US", "CA"],
            "max_rows": 5000,
            "max_missing_channel_pct": 0.25,
            "analysis_rules": {
                "dedupe_key": "order_id",
                "dedupe_ts_key": "event_ts",
                "dedupe_strategy": "latest_by_event_ts",
                "fill_missing_channel": "unknown",
                "normalize_status": "lower_strip",
            },
        },
    }
