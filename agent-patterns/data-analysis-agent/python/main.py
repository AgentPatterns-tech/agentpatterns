from __future__ import annotations

import json
import time
import uuid
from typing import Any

from agent import compose_final_answer, propose_analysis_plan
from context import build_request
from gateway import Budget, DataAnalysisGateway, StopRun, validate_plan
from tools import (
    analyze_sales_rows,
    profile_sales_rows,
    read_sales_snapshot,
    transform_sales_rows,
    validate_analysis,
)

GOAL = (
    "Prepare a validated weekly data-analysis brief for US payments with revenue, "
    "conversion, failed payment rate, and quality checks."
)
REQUEST = build_request(
    report_date="2026-03-07",
    region="US",
    source="warehouse_sales_daily",
)

DEFAULT_BUDGET = Budget(
    max_seconds=25,
    max_steps=8,
    max_rows=5000,
)

DEFAULT_ALLOWED_SOURCES_POLICY = {"warehouse_sales_daily", "warehouse_refunds_daily"}
ALLOWED_SOURCES_EXECUTION = {"warehouse_sales_daily"}
DEFAULT_ALLOWED_REGIONS_POLICY = {"US", "CA"}


DEFAULT_ANALYSIS_RULES = {
    "dedupe_key": "order_id",
    "dedupe_ts_key": "event_ts",
    "dedupe_strategy": "latest_by_event_ts",
    "fill_missing_channel": "unknown",
    "normalize_status": "lower_strip",
}


def _unwrap_tool_data(raw: Any, *, tool_name: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or raw.get("status") != "ok" or not isinstance(raw.get("data"), dict):
        raise StopRun(f"tool_invalid_output:{tool_name}")
    return dict(raw["data"])


def run_data_analysis_agent(*, goal: str, request: dict[str, Any]) -> dict[str, Any]:
    run_id = str(uuid.uuid4())
    started = time.monotonic()
    trace: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []

    artifact_ids = {
        "snapshot_id": f"snap_{run_id[:8]}",
        "profile_id": f"profile_{run_id[:8]}",
        "transform_id": f"transform_{run_id[:8]}",
        "metrics_id": f"metrics_{run_id[:8]}",
        "quality_id": f"quality_{run_id[:8]}",
    }

    def elapsed_ms() -> int:
        return max(1, int((time.monotonic() - started) * 1000))

    hints_raw = request.get("policy_hints")
    hints: dict[str, Any] = hints_raw if isinstance(hints_raw, dict) else {}

    allowed_sources_raw = hints.get("allowed_sources")
    if isinstance(allowed_sources_raw, list):
        allowed_sources_policy = {
            str(item).strip()
            for item in allowed_sources_raw
            if isinstance(item, str) and item.strip()
        }
    else:
        allowed_sources_policy = set(DEFAULT_ALLOWED_SOURCES_POLICY)
    if not allowed_sources_policy:
        allowed_sources_policy = set(DEFAULT_ALLOWED_SOURCES_POLICY)

    allowed_regions_raw = hints.get("allowed_regions")
    if isinstance(allowed_regions_raw, list):
        allowed_regions_policy = {
            str(item).strip().upper()
            for item in allowed_regions_raw
            if isinstance(item, str) and item.strip()
        }
    else:
        allowed_regions_policy = set(DEFAULT_ALLOWED_REGIONS_POLICY)
    if not allowed_regions_policy:
        allowed_regions_policy = set(DEFAULT_ALLOWED_REGIONS_POLICY)

    max_rows_raw = hints.get("max_rows", DEFAULT_BUDGET.max_rows)
    max_missing_channel_pct_raw = hints.get("max_missing_channel_pct", 0.25)

    analysis_rules_raw = hints.get("analysis_rules")
    analysis_rules = dict(DEFAULT_ANALYSIS_RULES)
    if isinstance(analysis_rules_raw, dict):
        for key, value in analysis_rules_raw.items():
            if isinstance(key, str):
                analysis_rules[key] = value

    dedupe_key = str(analysis_rules.get("dedupe_key", DEFAULT_ANALYSIS_RULES["dedupe_key"])).strip() or "order_id"
    dedupe_ts_key = str(analysis_rules.get("dedupe_ts_key", DEFAULT_ANALYSIS_RULES["dedupe_ts_key"])).strip() or "event_ts"
    dedupe_strategy = str(
        analysis_rules.get("dedupe_strategy", DEFAULT_ANALYSIS_RULES["dedupe_strategy"])
    ).strip() or "latest_by_event_ts"
    fill_missing_channel = str(
        analysis_rules.get("fill_missing_channel", DEFAULT_ANALYSIS_RULES["fill_missing_channel"])
    ).strip() or "unknown"
    normalize_status = str(
        analysis_rules.get("normalize_status", DEFAULT_ANALYSIS_RULES["normalize_status"])
    ).strip() or "lower_strip"

    if dedupe_strategy != "latest_by_event_ts":
        return {
            "run_id": run_id,
            "status": "stopped",
            "stop_reason": "invalid_request:dedupe_strategy",
            "phase": "plan",
            "trace": trace,
            "history": history,
        }

    try:
        max_rows = int(max_rows_raw)
    except (TypeError, ValueError):
        max_rows = DEFAULT_BUDGET.max_rows
    if max_rows <= 0:
        return {
            "run_id": run_id,
            "status": "stopped",
            "stop_reason": "invalid_request:max_rows",
            "phase": "plan",
            "trace": trace,
            "history": history,
        }

    try:
        max_missing_channel_pct = float(max_missing_channel_pct_raw)
    except (TypeError, ValueError):
        max_missing_channel_pct = 0.25
    if not (0.0 <= max_missing_channel_pct <= 1.0):
        return {
            "run_id": run_id,
            "status": "stopped",
            "stop_reason": "invalid_request:max_missing_channel_pct",
            "phase": "plan",
            "trace": trace,
            "history": history,
        }

    budget = Budget(
        max_seconds=DEFAULT_BUDGET.max_seconds,
        max_steps=DEFAULT_BUDGET.max_steps,
        max_rows=max(10, min(200000, max_rows)),
    )

    gateway = DataAnalysisGateway(
        allowed_sources_policy=allowed_sources_policy,
        allowed_sources_execution=ALLOWED_SOURCES_EXECUTION,
        allowed_regions_policy=allowed_regions_policy,
        budget=budget,
    )

    def stopped(stop_reason: str, *, phase: str, **extra: Any) -> dict[str, Any]:
        payload = {
            "run_id": run_id,
            "status": "stopped",
            "stop_reason": stop_reason,
            "phase": phase,
            "trace": trace,
            "history": history,
        }
        payload.update(extra)
        return payload

    phase = "plan"
    try:
        if (time.monotonic() - started) > budget.max_seconds:
            return stopped("max_seconds", phase=phase)

        raw_plan = propose_analysis_plan(goal=goal, request=request)
        steps = validate_plan(raw_plan.get("steps"), max_steps=budget.max_steps)

        trace.append(
            {
                "step": 1,
                "phase": "plan",
                "steps": len(steps),
                "elapsed_ms": elapsed_ms(),
                "ok": True,
            }
        )
        history.append(
            {
                "step": 1,
                "action": "propose_analysis_plan",
                "step_ids": [item["id"] for item in steps],
            }
        )

        phase = "policy_check"
        ingest_args = steps[0]["args"]
        source = str(ingest_args.get("source", "")).strip()
        region = str(ingest_args.get("region", "")).strip().upper()
        decision = gateway.evaluate_ingest(source=source, region=region)

        trace.append(
            {
                "step": 2,
                "phase": "policy_check",
                "source": source,
                "region": region,
                "decision": decision.kind,
                "reason": decision.reason,
                "allowed_sources_policy": sorted(allowed_sources_policy),
                "allowed_sources_execution": sorted(ALLOWED_SOURCES_EXECUTION),
                "elapsed_ms": elapsed_ms(),
                "ok": decision.kind == "allow",
            }
        )
        history.append(
            {
                "step": 2,
                "action": "policy_check",
                "decision": {"kind": decision.kind, "reason": decision.reason},
            }
        )
        if decision.kind != "allow":
            return stopped(f"policy_block:{decision.reason}", phase=phase)

        if (time.monotonic() - started) > budget.max_seconds:
            return stopped("max_seconds", phase="ingest_profile")

        phase = "ingest_profile"
        req = request["request"]
        snapshot = _unwrap_tool_data(
            read_sales_snapshot(
                source=source,
                region=region,
                rows=list(req["rows"]),
            ),
            tool_name="read_sales_snapshot",
        )
        rows_raw = list(snapshot["rows"])
        gateway.ensure_rows_budget(rows=rows_raw)

        profile = _unwrap_tool_data(
            profile_sales_rows(rows=rows_raw),
            tool_name="profile_sales_rows",
        )
        gateway.validate_profile(profile=profile, max_missing_channel_pct=max_missing_channel_pct)

        trace.append(
            {
                "step": 3,
                "phase": "ingest_profile",
                "row_count_raw": profile["row_count_raw"],
                "duplicate_rows": profile["duplicate_rows"],
                "missing_channel_pct": round(float(profile["missing_channel_pct"]) * 100, 2),
                "artifact_refs": {
                    "snapshot_id": artifact_ids["snapshot_id"],
                    "profile_id": artifact_ids["profile_id"],
                },
                "elapsed_ms": elapsed_ms(),
                "ok": True,
            }
        )
        history.append(
            {
                "step": 3,
                "action": "ingest_profile",
                "source": source,
                "row_count_raw": profile["row_count_raw"],
                "artifact_refs": {
                    "snapshot_id": artifact_ids["snapshot_id"],
                    "profile_id": artifact_ids["profile_id"],
                },
            }
        )

        if (time.monotonic() - started) > budget.max_seconds:
            return stopped("max_seconds", phase="transform_analyze")

        phase = "transform_analyze"
        transformed = _unwrap_tool_data(
            transform_sales_rows(
                rows=rows_raw,
                dedupe_key=dedupe_key,
                dedupe_ts_key=dedupe_ts_key,
                fill_missing_channel=fill_missing_channel,
                normalize_status=normalize_status,
            ),
            tool_name="transform_sales_rows",
        )
        rows_clean = list(transformed["rows"])

        metrics = _unwrap_tool_data(
            analyze_sales_rows(rows=rows_clean),
            tool_name="analyze_sales_rows",
        )
        gateway.validate_metrics(metrics=metrics)

        trace.append(
            {
                "step": 4,
                "phase": "transform_analyze",
                "row_count_clean": transformed["row_count_clean"],
                "deduped_rows": transformed["deduped_rows"],
                "filled_missing_channel": transformed["filled_missing_channel"],
                "skipped_rows_missing_key": transformed.get("skipped_rows_missing_key", 0),
                "skipped_rows_invalid_ts": transformed.get("skipped_rows_invalid_ts", 0),
                "net_revenue": round(float(metrics["net_revenue"]), 2),
                "conversion_rate_pct": round(float(metrics["conversion_rate"]) * 100, 2),
                "failed_payment_rate_pct": round(float(metrics["failed_payment_rate"]) * 100, 2),
                "artifact_refs": {
                    "transform_id": artifact_ids["transform_id"],
                    "metrics_id": artifact_ids["metrics_id"],
                },
                "elapsed_ms": elapsed_ms(),
                "ok": True,
            }
        )
        history.append(
            {
                "step": 4,
                "action": "transform_analyze",
                "row_count_clean": transformed["row_count_clean"],
                "net_revenue": round(float(metrics["net_revenue"]), 2),
                "applied_rules": {
                    "dedupe_strategy": dedupe_strategy,
                    "dedupe_key": dedupe_key,
                    "dedupe_ts_key": dedupe_ts_key,
                    "fill_missing_channel": fill_missing_channel,
                    "normalize_status": normalize_status,
                },
                "artifact_refs": {
                    "transform_id": artifact_ids["transform_id"],
                    "metrics_id": artifact_ids["metrics_id"],
                },
            }
        )

        if (time.monotonic() - started) > budget.max_seconds:
            return stopped("max_seconds", phase="validate")

        phase = "validate"
        quality = _unwrap_tool_data(
            validate_analysis(
                metrics=metrics,
                profile=profile,
                max_missing_channel_pct=max_missing_channel_pct,
            ),
            tool_name="validate_analysis",
        )
        if not bool(quality.get("ok")):
            failed = quality.get("failed_checks") or []
            first = str(failed[0]) if failed else "unknown"
            return stopped(f"validation_failed:{first}", phase=phase, quality=quality)

        trace.append(
            {
                "step": 5,
                "phase": "validate",
                "passed_checks": len(quality.get("passed_checks", [])),
                "failed_checks": len(quality.get("failed_checks", [])),
                "artifact_refs": {"quality_id": artifact_ids["quality_id"]},
                "elapsed_ms": elapsed_ms(),
                "ok": True,
            }
        )
        history.append(
            {
                "step": 5,
                "action": "validate_analysis",
                "passed_checks": len(quality.get("passed_checks", [])),
                "artifact_refs": {"quality_id": artifact_ids["quality_id"]},
            }
        )

        aggregate = {
            "report_date": req["report_date"],
            "region": req["region"],
            "source": source,
            "metrics": {
                "sample_size": int(metrics["sample_size"]),
                "gross_revenue": round(float(metrics["gross_revenue"]), 2),
                "refund_amount_total": round(float(metrics["refund_amount_total"]), 2),
                "net_revenue": round(float(metrics["net_revenue"]), 2),
                "conversion_rate": round(float(metrics["conversion_rate"]), 6),
                "conversion_rate_pct": round(float(metrics["conversion_rate"]) * 100, 2),
                "failed_payment_rate": round(float(metrics["failed_payment_rate"]), 6),
                "failed_payment_rate_pct": round(float(metrics["failed_payment_rate"]) * 100, 2),
                "refund_rate": round(float(metrics["refund_rate"]), 6),
                "refund_rate_pct": round(float(metrics["refund_rate"]) * 100, 2),
                "top_channel": str(metrics["top_channel"]),
                "avg_latency_ms": round(float(metrics["avg_latency_ms"]), 2),
                "p95_latency_ms": round(float(metrics["p95_latency_ms"]), 2),
                "eta_minutes": int(metrics["eta_minutes"]),
            },
            "data_quality": {
                "row_count_raw": int(profile["row_count_raw"]),
                "row_count_clean": int(transformed["row_count_clean"]),
                "deduped_rows": int(transformed["deduped_rows"]),
                "missing_channel_pct_raw": round(float(profile["missing_channel_pct"]) * 100, 2),
                "row_validity_ok": bool(profile["row_validity_ok"]),
                "invalid_order_id_count": int(profile["invalid_order_id_count"]),
                "invalid_event_ts_count": int(profile["invalid_event_ts_count"]),
                "invalid_status_count": int(profile["invalid_status_count"]),
                "invalid_amount_count": int(profile["invalid_amount_count"]),
                "invalid_latency_count": int(profile["invalid_latency_count"]),
                "skipped_rows_missing_key": int(transformed.get("skipped_rows_missing_key", 0)),
                "skipped_rows_invalid_ts": int(transformed.get("skipped_rows_invalid_ts", 0)),
            },
        }

        answer = compose_final_answer(
            request=request,
            aggregate=aggregate,
            quality=quality,
        )

        trace.append(
            {
                "step": 6,
                "phase": "finalize",
                "elapsed_ms": elapsed_ms(),
                "ok": True,
            }
        )
        history.append(
            {
                "step": 6,
                "action": "finalize",
            }
        )

        return {
            "run_id": run_id,
            "status": "ok",
            "stop_reason": "success",
            "outcome": "validated_analysis",
            "answer": answer,
            "aggregate": aggregate,
            "quality": quality,
            "trace": trace,
            "history": history,
        }
    except StopRun as exc:
        return stopped(
            exc.reason,
            phase=phase,
            **({"details": exc.details} if isinstance(exc.details, dict) and exc.details else {}),
        )


def main() -> None:
    result = run_data_analysis_agent(goal=GOAL, request=REQUEST)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
