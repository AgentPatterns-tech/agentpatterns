from __future__ import annotations

from typing import Any


def build_incident_context(*, report_date: str, region: str) -> dict[str, Any]:
    return {
        "report_date": report_date,
        "region": region,
        "incident": {
            "incident_id": "inc_payments_20260305",
            "severity": "P1",
            "status": "degraded",
            "affected_checkout_pct": 27,
            "failed_payment_rate": 0.034,
            "chargeback_alerts": 5,
            "eta_minutes": 45,
        },
        "policy_hints": {
            "avoid_absolute_guarantees": True,
            "required_sections": ["current_status", "customer_impact", "next_actions"],
        },
        "approved_actions": [
            "monitor payment failures every 15 minutes",
            "publish customer update via status page",
            "prepare support macro with workaround guidance",
        ],
    }
