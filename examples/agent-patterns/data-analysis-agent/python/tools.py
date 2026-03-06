from __future__ import annotations

import math
from datetime import datetime
from collections import defaultdict
from typing import Any

ALLOWED_STATUSES = {"paid", "failed", "refunded"}


def _safe_float(value: Any) -> tuple[bool, float]:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False, 0.0
    if not math.isfinite(v):
        return False, 0.0
    return True, v


def _is_valid_event_ts(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    ts = value.strip()
    if len(ts) != 20 or not ts.endswith("Z"):
        return False
    try:
        datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return True


def read_sales_snapshot(*, source: str, region: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "status": "ok",
        "data": {
            "source": source,
            "region": region.upper(),
            "rows": rows,
            "snapshot_at": "2026-03-07T10:00:00Z",
        },
    }


def profile_sales_rows(*, rows: list[dict[str, Any]]) -> dict[str, Any]:
    required_fields = {"order_id", "event_ts", "status", "amount", "channel", "latency_ms"}
    schema_ok = True
    missing_fields_count = 0

    missing_channel_count = 0
    duplicate_rows = 0
    by_order_id: dict[str, int] = {}

    invalid_order_id_count = 0
    invalid_event_ts_count = 0
    invalid_status_count = 0
    invalid_amount_count = 0
    invalid_latency_count = 0

    for row in rows:
        keys = set(row.keys())
        if not required_fields.issubset(keys):
            schema_ok = False
            missing_fields_count += 1

        order_id = row.get("order_id")
        order_id_norm = str(order_id).strip() if isinstance(order_id, str) else ""
        if not order_id_norm:
            invalid_order_id_count += 1
        else:
            by_order_id[order_id_norm] = by_order_id.get(order_id_norm, 0) + 1
            if by_order_id[order_id_norm] > 1:
                duplicate_rows += 1

        event_ts = row.get("event_ts")
        if not _is_valid_event_ts(event_ts):
            invalid_event_ts_count += 1

        status = str(row.get("status", "")).strip().lower()
        if status not in ALLOWED_STATUSES:
            invalid_status_count += 1

        ok_amount, amount = _safe_float(row.get("amount"))
        if not ok_amount or amount < 0.0:
            invalid_amount_count += 1

        ok_latency, latency = _safe_float(row.get("latency_ms"))
        if not ok_latency or latency < 0.0:
            invalid_latency_count += 1

        channel = row.get("channel")
        if not isinstance(channel, str) or not channel.strip():
            missing_channel_count += 1

    total = len(rows)
    missing_channel_pct = (missing_channel_count / total) if total else 0.0

    row_validity_ok = (
        invalid_order_id_count == 0
        and invalid_event_ts_count == 0
        and invalid_status_count == 0
        and invalid_amount_count == 0
        and invalid_latency_count == 0
    )

    return {
        "status": "ok",
        "data": {
            "row_count_raw": total,
            "duplicate_rows": duplicate_rows,
            "missing_channel_count": missing_channel_count,
            "missing_channel_pct": missing_channel_pct,
            "schema_ok": schema_ok,
            "missing_fields_count": missing_fields_count,
            "row_validity_ok": row_validity_ok,
            "invalid_order_id_count": invalid_order_id_count,
            "invalid_event_ts_count": invalid_event_ts_count,
            "invalid_status_count": invalid_status_count,
            "invalid_amount_count": invalid_amount_count,
            "invalid_latency_count": invalid_latency_count,
        },
    }


def transform_sales_rows(
    *,
    rows: list[dict[str, Any]],
    dedupe_key: str,
    dedupe_ts_key: str,
    fill_missing_channel: str,
    normalize_status: str,
) -> dict[str, Any]:
    latest_by_key: dict[str, dict[str, Any]] = {}
    ts_by_key: dict[str, str] = {}
    skipped_rows_missing_key = 0
    skipped_rows_invalid_ts = 0

    for row in rows:
        key = str(row.get(dedupe_key, "")).strip()
        if not key:
            skipped_rows_missing_key += 1
            continue

        event_ts_raw = row.get(dedupe_ts_key)
        if not _is_valid_event_ts(event_ts_raw):
            skipped_rows_invalid_ts += 1
            continue
        event_ts = str(event_ts_raw).strip()
        previous_ts = ts_by_key.get(key, "")
        if key not in latest_by_key or event_ts >= previous_ts:
            latest_by_key[key] = dict(row)
            ts_by_key[key] = event_ts

    cleaned_rows = [latest_by_key[k] for k in sorted(latest_by_key.keys())]

    filled_missing_channel = 0
    for row in cleaned_rows:
        channel = row.get("channel")
        if not isinstance(channel, str) or not channel.strip():
            row["channel"] = fill_missing_channel
            filled_missing_channel += 1

        if normalize_status == "lower_strip":
            row["status"] = str(row.get("status", "")).strip().lower()

        row[dedupe_key] = str(row.get(dedupe_key, "")).strip()
        row[dedupe_ts_key] = str(row.get(dedupe_ts_key, "")).strip()
        ok_amount, amount = _safe_float(row.get("amount"))
        ok_latency, latency = _safe_float(row.get("latency_ms"))
        row["amount"] = amount if ok_amount else 0.0
        row["latency_ms"] = latency if ok_latency else 0.0

    return {
        "status": "ok",
        "data": {
            "rows": cleaned_rows,
            "row_count_clean": len(cleaned_rows),
            "deduped_rows": max(0, len(rows) - len(cleaned_rows)),
            "filled_missing_channel": filled_missing_channel,
            "skipped_rows_missing_key": skipped_rows_missing_key,
            "skipped_rows_invalid_ts": skipped_rows_invalid_ts,
            "dedupe_strategy": "latest_by_event_ts",
            "dedupe_key": dedupe_key,
            "dedupe_ts_key": dedupe_ts_key,
        },
    }


def analyze_sales_rows(*, rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    paid_count = 0
    failed_count = 0
    refunded_count = 0

    gross_revenue = 0.0
    refund_amount_total = 0.0
    latency_values: list[float] = []
    channel_net_revenue: dict[str, float] = defaultdict(float)

    for row in rows:
        status = str(row.get("status", "")).lower()
        amount = float(row.get("amount", 0.0))
        channel = str(row.get("channel", "unknown")).strip().lower() or "unknown"
        latency = float(row.get("latency_ms", 0.0))
        latency_values.append(latency)

        if status == "paid":
            paid_count += 1
            gross_revenue += amount
            channel_net_revenue[channel] += amount
        elif status == "failed":
            failed_count += 1
        elif status == "refunded":
            refunded_count += 1
            refund_amount_total += amount
            channel_net_revenue[channel] -= amount

    net_revenue = gross_revenue - refund_amount_total
    conversion_rate = (paid_count / total) if total else 0.0
    failed_payment_rate = (failed_count / total) if total else 0.0
    refund_rate = (refunded_count / total) if total else 0.0

    avg_latency_ms = (sum(latency_values) / len(latency_values)) if latency_values else 0.0
    sorted_latency = sorted(latency_values)
    if sorted_latency:
        p95_idx = int((len(sorted_latency) - 1) * 0.95)
        p95_latency_ms = sorted_latency[p95_idx]
    else:
        p95_latency_ms = 0.0

    top_channel = "unknown"
    top_channel_value = float("-inf")
    for channel, value in channel_net_revenue.items():
        if value > top_channel_value:
            top_channel = channel
            top_channel_value = value

    eta_minutes = 45 if failed_payment_rate >= 0.15 else 20

    return {
        "status": "ok",
        "data": {
            "sample_size": total,
            "paid_count": paid_count,
            "failed_count": failed_count,
            "refunded_count": refunded_count,
            "gross_revenue": gross_revenue,
            "refund_amount_total": refund_amount_total,
            "net_revenue": net_revenue,
            "conversion_rate": conversion_rate,
            "failed_payment_rate": failed_payment_rate,
            "refund_rate": refund_rate,
            "avg_latency_ms": avg_latency_ms,
            "p95_latency_ms": p95_latency_ms,
            "top_channel": top_channel,
            "eta_minutes": eta_minutes,
        },
    }


def validate_analysis(
    *,
    metrics: dict[str, Any],
    profile: dict[str, Any],
    max_missing_channel_pct: float,
) -> dict[str, Any]:
    passed_checks: list[str] = []
    failed_checks: list[str] = []

    conversion_rate = float(metrics.get("conversion_rate", 0.0))
    failed_payment_rate = float(metrics.get("failed_payment_rate", 0.0))
    refund_rate = float(metrics.get("refund_rate", 0.0))

    gross_revenue = float(metrics.get("gross_revenue", 0.0))
    refund_amount_total = float(metrics.get("refund_amount_total", 0.0))
    net_revenue = float(metrics.get("net_revenue", 0.0))

    sample_size = int(metrics.get("sample_size", 0))
    p95_latency_ms = float(metrics.get("p95_latency_ms", 0.0))
    missing_channel_pct = float(profile.get("missing_channel_pct", 0.0))
    row_validity_ok = bool(profile.get("row_validity_ok"))

    if 0.0 <= conversion_rate <= 1.0:
        passed_checks.append("conversion_between_0_1")
    else:
        failed_checks.append("conversion_out_of_range")

    if 0.0 <= refund_rate <= 1.0:
        passed_checks.append("refund_rate_between_0_1")
    else:
        failed_checks.append("refund_rate_out_of_range")

    if gross_revenue >= 0.0:
        passed_checks.append("gross_revenue_non_negative")
    else:
        failed_checks.append("gross_revenue_negative")

    if refund_amount_total >= 0.0:
        passed_checks.append("refund_amount_non_negative")
    else:
        failed_checks.append("refund_amount_negative")

    if net_revenue >= 0.0:
        passed_checks.append("net_revenue_non_negative")
    else:
        failed_checks.append("net_revenue_negative")

    if failed_payment_rate <= 0.35:
        passed_checks.append("failed_rate_reasonable")
    else:
        failed_checks.append("failed_rate_too_high")

    if sample_size >= 10:
        passed_checks.append("sample_size_min_10")
    else:
        failed_checks.append("sample_size_too_low")

    if p95_latency_ms <= 400.0:
        passed_checks.append("p95_latency_under_400")
    else:
        failed_checks.append("p95_latency_too_high")

    if missing_channel_pct <= max_missing_channel_pct:
        passed_checks.append("missing_channel_within_policy")
    else:
        failed_checks.append("missing_channel_policy_violation")

    if gross_revenue >= net_revenue:
        passed_checks.append("gross_ge_net")
    else:
        failed_checks.append("gross_less_than_net")

    if abs((gross_revenue - refund_amount_total) - net_revenue) <= 0.01:
        passed_checks.append("gross_minus_refunds_equals_net")
    else:
        failed_checks.append("gross_refund_net_mismatch")

    if row_validity_ok:
        passed_checks.append("profile_row_values_valid")
    else:
        failed_checks.append("profile_row_values_invalid")

    return {
        "status": "ok",
        "data": {
            "ok": len(failed_checks) == 0,
            "passed_checks": passed_checks,
            "failed_checks": failed_checks,
        },
    }
