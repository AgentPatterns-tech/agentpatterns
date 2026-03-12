from __future__ import annotations

from typing import Any


def build_request(*, report_date: str, region: str, incident_id: str) -> dict[str, Any]:
    transactions: list[dict[str, Any]] = []
    for idx in range(60):
        is_failed = idx in {7, 34}
        transactions.append(
            {
                "transaction_id": f"txn_{idx + 1:03d}",
                "status": "failed" if is_failed else "paid",
                "chargeback": idx == 34,
                "latency_ms": 150 + (idx % 40) + (25 if is_failed else 0),
            }
        )

    return {
        "request": {
            "report_date": report_date,
            "region": region.upper(),
            "incident_id": incident_id,
            "transactions": transactions,
        },
        "policy_hints": {
            "allowed_languages": ["python", "javascript"],
            "max_code_chars": 2400,
            "exec_timeout_seconds": 2.0,
            "network_access": "denied",
        },
    }
