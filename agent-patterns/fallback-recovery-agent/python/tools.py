from __future__ import annotations

import time
from typing import Any


_PRIMARY_ATTEMPTS: dict[str, int] = {}


def _request_key(report_date: str, region: str, request_id: str, suffix: str) -> str:
    return f"{request_id}:{report_date}:{region.upper()}:{suffix}"


def payments_primary_api(report_date: str, region: str, request_id: str) -> dict[str, Any]:
    key = _request_key(report_date, region, request_id, "payments_primary")
    _PRIMARY_ATTEMPTS[key] = _PRIMARY_ATTEMPTS.get(key, 0) + 1
    attempt = _PRIMARY_ATTEMPTS[key]

    # Simulate primary instability: first two attempts timeout.
    if attempt <= 2:
        time.sleep(1.4)
        raise TimeoutError("primary_payments_timeout")

    return {
        "status": "ok",
        "data": {
            "failed_payment_rate": 0.034,
            "chargeback_alerts": 5,
            "incident_severity": "P1",
            "eta_minutes": 45,
            "source": "payments_primary_api",
        },
    }


def payments_replica_api(report_date: str, region: str, request_id: str) -> dict[str, Any]:
    del report_date, request_id
    time.sleep(0.2)
    return {
        "status": "ok",
        "data": {
            "failed_payment_rate": 0.034,
            "chargeback_alerts": 5,
            "incident_severity": "P1",
            "eta_minutes": 45,
            "source": f"payments_replica_api:{region.upper()}",
        },
    }


def payments_cached_snapshot(report_date: str, region: str, request_id: str) -> dict[str, Any]:
    del request_id
    time.sleep(0.05)
    return {
        "status": "ok",
        "data": {
            "failed_payment_rate": 0.031,
            "chargeback_alerts": 4,
            "incident_severity": "P1",
            "eta_minutes": 50,
            "stale_minutes": 18,
            "source": f"payments_cache:{report_date}:{region.upper()}",
        },
    }


def demand_primary_api(report_date: str, region: str, request_id: str) -> dict[str, Any]:
    del request_id
    time.sleep(0.15)
    return {
        "status": "ok",
        "data": {
            "affected_checkout_share": 0.27,
            "avg_orders_per_minute": 182,
            "priority_segment": f"{region.upper()}_enterprise",
            "source": f"demand_primary_api:{report_date}",
        },
    }


def demand_cached_snapshot(report_date: str, region: str, request_id: str) -> dict[str, Any]:
    del request_id
    time.sleep(0.03)
    return {
        "status": "ok",
        "data": {
            "affected_checkout_share": 0.25,
            "avg_orders_per_minute": 176,
            "priority_segment": f"{region.upper()}_enterprise",
            "stale_minutes": 22,
            "source": f"demand_cache:{report_date}:{region.upper()}",
        },
    }

