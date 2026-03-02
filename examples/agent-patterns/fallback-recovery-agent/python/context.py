from __future__ import annotations

from typing import Any


def build_operations_context(*, report_date: str, region: str) -> dict[str, Any]:
    return {
        "goal": "Prepare a customer-safe operations update for the payments incident.",
        "request": {
            "report_date": report_date,
            "region": region.upper(),
        },
        "policy_hints": {
            "max_retries": 1,
            "max_fallbacks": 2,
            "allow_cached_fallback": True,
            "avoid_absolute_guarantees": True,
        },
    }

