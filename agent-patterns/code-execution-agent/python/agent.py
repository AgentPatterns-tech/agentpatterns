from __future__ import annotations

from typing import Any


def propose_code_execution_plan(*, goal: str, request: dict[str, Any]) -> dict[str, Any]:
    req = request["request"]
    del goal

    code = """
import json
import statistics

payload = json.loads(input())
rows = payload["transactions"]

total = len(rows)
failed = sum(1 for row in rows if row["status"] != "paid")
chargeback_alerts = sum(1 for row in rows if row.get("chargeback") is True)
failed_rate = (failed / total) if total else 0.0

latencies = [float(row["latency_ms"]) for row in rows]
avg_latency = statistics.fmean(latencies) if latencies else 0.0

if latencies:
    sorted_latencies = sorted(latencies)
    p95_idx = int(round((len(sorted_latencies) - 1) * 0.95))
    p95_latency = sorted_latencies[p95_idx]
else:
    p95_latency = 0.0

severity = "P1" if failed_rate >= 0.03 else "P2"
eta_minutes = 45 if severity == "P1" else 20

print(
    json.dumps(
        {
            "failed_payment_rate": failed_rate,
            "chargeback_alerts": chargeback_alerts,
            "incident_severity": severity,
            "eta_minutes": eta_minutes,
            "affected_checkout_share": failed_rate,
            "avg_latency_ms": avg_latency,
            "p95_latency_ms": p95_latency,
            "sample_size": total,
            "incident_id": payload["incident_id"],
            "region": payload["region"],
        },
        separators=(",", ":"),
    )
)
""".strip()

    return {
        "action": {
            "id": "c1",
            "language": "python",
            "entrypoint": "main.py",
            "code": code,
            "input_payload": {
                "incident_id": req["incident_id"],
                "region": req["region"],
                "transactions": req["transactions"],
            },
        }
    }


def compose_final_answer(
    *,
    request: dict[str, Any],
    aggregate: dict[str, Any],
    execution_summary: dict[str, Any],
) -> str:
    req = request["request"]
    metrics = aggregate["metrics"]

    return (
        f"Code execution brief ({req['region']}, {req['report_date']}): incident {req['incident_id']} is "
        f"{metrics['incident_severity']} with failed payments at {metrics['failed_payment_rate_pct']}% and "
        f"{metrics['chargeback_alerts']} chargeback alerts. Affected checkout share is "
        f"{metrics['affected_checkout_share_pct']}%, average latency is {metrics['avg_latency_ms']} ms "
        f"(p95 {metrics['p95_latency_ms']} ms), and ETA is ~{metrics['eta_minutes']} minutes. "
        f"Executed in a separate subprocess boundary (best-effort, not a security sandbox) "
        f"({execution_summary['exec_ms']} ms, {execution_summary['stdout_bytes']} stdout bytes, "
        f"{execution_summary['stderr_bytes']} stderr bytes)."
    )
