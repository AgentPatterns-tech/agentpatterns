from __future__ import annotations

import time
from typing import Any


def fetch_incident_snapshot(report_date: str, region: str, incident_id: str) -> dict[str, Any]:
    time.sleep(0.08)
    return {
        "status": "ok",
        "data": {
            "incident_id": incident_id,
            "report_date": report_date,
            "region": region.upper(),
            "severity": "P1",
            "failed_payment_rate": 0.034,
            "chargeback_alerts": 5,
            "affected_checkout_share": 0.27,
            "eta_minutes": 45,
        },
    }


def send_status_update(
    channel: str,
    template_id: str,
    audience_segment: str,
    max_recipients: int,
) -> dict[str, Any]:
    time.sleep(0.05)
    return {
        "status": "ok",
        "data": {
            "channel": channel,
            "template_id": template_id,
            "audience_segment": audience_segment,
            "queued_recipients": int(max_recipients),
            "delivery_id": "upd_20260306_001",
        },
    }


def export_customer_data(fields: list[str], destination: str) -> dict[str, Any]:
    del fields, destination
    time.sleep(0.03)
    return {
        "status": "ok",
        "data": {
            "export_id": "exp_20260306_001",
            "rows": 18240,
        },
    }


def create_manual_review_ticket(reason: str, payload: dict[str, Any]) -> dict[str, Any]:
    time.sleep(0.03)
    return {
        "status": "ok",
        "data": {
            "ticket_id": "pol_20260306_001",
            "reason": reason,
            "payload_keys": sorted(payload.keys()),
        },
    }

