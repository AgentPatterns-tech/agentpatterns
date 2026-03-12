from __future__ import annotations

from typing import Any


def build_request(*, report_date: str, region: str) -> dict[str, Any]:
    return {
        "request": {
            "report_date": report_date,
            "region": region.upper(),
            "question": (
                "What is the current US payments incident status and what enterprise SLA "
                "commitments apply for uptime and P1 response time?"
            ),
        },
        "policy_hints": {
            "allowed_domains_policy": [
                "official-status.example.com",
                "vendor.example.com",
                "regulator.example.org",
            ],
            "allowed_domains_execution": [
                "official-status.example.com",
                "vendor.example.com",
            ],
            "max_urls": 6,
            "max_read_pages": 3,
            "max_notes": 6,
            "max_answer_chars": 850,
        },
    }
