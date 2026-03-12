from __future__ import annotations

from typing import Any


def propose_analysis_plan(*, goal: str, request: dict[str, Any]) -> dict[str, Any]:
    del goal
    req = request["request"]
    return {
        "steps": [
            {
                "id": "s1",
                "action": "ingest_sales",
                "args": {
                    "source": req["source"],
                    "region": req["region"],
                },
            },
            {"id": "s2", "action": "profile_sales", "args": {}},
            {"id": "s3", "action": "transform_sales", "args": {}},
            {"id": "s4", "action": "analyze_sales", "args": {}},
            {"id": "s5", "action": "validate_analysis", "args": {}},
        ]
    }


def compose_final_answer(
    *,
    request: dict[str, Any],
    aggregate: dict[str, Any],
    quality: dict[str, Any],
) -> str:
    req = request["request"]
    m = aggregate["metrics"]
    checks = quality.get("passed_checks", [])

    return (
        f"Data analysis brief ({req['region']}, {req['report_date']}): source {req['source']} shows net revenue "
        f"{m['net_revenue']:.2f} (gross {m['gross_revenue']:.2f}, refunds {m['refund_amount_total']:.2f} subtracted), "
        f"conversion {m['conversion_rate_pct']:.2f}%, failed payment rate {m['failed_payment_rate_pct']:.2f}%, "
        f"refund rate {m['refund_rate_pct']:.2f}%, top channel {m['top_channel']}, "
        f"and p95 latency {m['p95_latency_ms']:.2f} ms. Quality checks passed: {len(checks)}."
    )
