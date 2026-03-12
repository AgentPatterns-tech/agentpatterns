from __future__ import annotations

from typing import Any



def build_shared_context(*, report_date: str, region: str) -> dict[str, Any]:
    return {
        "report_date": report_date,
        "region": region,
        "campaign": {
            "name": "Checkout v2 Launch",
            "window": "2026-03-02",
            "channel": "US paid + lifecycle",
        },
        "demand_signals": {
            "projected_orders": 15200,
            "conversion_lift_pct": 12.4,
            "traffic_risk": "medium",
        },
        "finance_signals": {
            "projected_revenue_usd": 684000.0,
            "expected_margin_pct": 19.2,
            "promo_cost_usd": 94000.0,
        },
        "risk_signals": {
            "failed_payment_rate": 0.028,
            "chargeback_alerts": 4,
            "critical_incidents": 0,
        },
        "policy_limits": {
            "payment_failure_block_threshold": 0.03,
            "max_chargeback_alerts_for_go": 5,
        },
    }
