from __future__ import annotations

import time
from typing import Any

SALES_METRICS = {
    "2026-02-26:US": {
        "gross_sales_usd": 182_450.0,
        "orders": 4_820,
        "aov_usd": 37.85,
    }
}

PAYMENT_ALERTS = {
    "2026-02-26:US": {
        "failed_payment_rate": 0.023,
        "chargeback_alerts": 3,
        "gateway_incident": "none",
    }
}

INVENTORY_ALERTS = {
    "2026-02-26:US": {
        "low_stock_skus": ["SKU-4411", "SKU-8820"],
        "out_of_stock_skus": ["SKU-9033"],
        "restock_eta_days": 2,
    }
}

_ATTEMPT_STATE: dict[str, int] = {}


def _key(report_date: str, region: str) -> str:
    return f"{report_date}:{region.upper()}"


def sales_worker(report_date: str, region: str, request_id: str) -> dict[str, Any]:
    del request_id
    time.sleep(0.4)
    metrics = SALES_METRICS.get(_key(report_date, region))
    if not metrics:
        return {
            "status": "done",
            "worker": "sales_worker",
            "result": {"warning": "sales_data_missing"},
        }
    return {"status": "done", "worker": "sales_worker", "result": metrics}


def payments_worker(report_date: str, region: str, request_id: str) -> dict[str, Any]:
    # Simulate a transient timeout on the first attempt within one request_id.
    attempt_key = f"{request_id}:{_key(report_date, region)}:payments"
    _ATTEMPT_STATE[attempt_key] = _ATTEMPT_STATE.get(attempt_key, 0) + 1
    attempt = _ATTEMPT_STATE[attempt_key]

    if attempt == 1:
        time.sleep(2.6)  # Exceeds gateway timeout on purpose.
    else:
        time.sleep(0.3)

    alerts = PAYMENT_ALERTS.get(_key(report_date, region))
    if not alerts:
        return {
            "status": "done",
            "worker": "payments_worker",
            "result": {"warning": "payments_data_missing"},
        }
    return {"status": "done", "worker": "payments_worker", "result": alerts}


def inventory_worker(report_date: str, region: str, request_id: str) -> dict[str, Any]:
    del request_id
    time.sleep(0.5)
    alerts = INVENTORY_ALERTS.get(_key(report_date, region))
    if not alerts:
        return {
            "status": "done",
            "worker": "inventory_worker",
            "result": {"warning": "inventory_data_missing"},
        }
    return {"status": "done", "worker": "inventory_worker", "result": alerts}
