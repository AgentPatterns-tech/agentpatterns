from __future__ import annotations

from typing import Any


def build_request(*, report_date: str, region: str, incident_id: str) -> dict[str, Any]:
    return {
        "request": {
            "report_date": report_date,
            "region": region.upper(),
            "incident_id": incident_id,
        },
        "policy_hints": {
            "status_update_template": "incident_p1_v2",
            "max_recipients_per_send": 50000,
        },
    }

