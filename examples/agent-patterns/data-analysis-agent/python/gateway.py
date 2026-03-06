from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class StopRun(Exception):
    def __init__(self, reason: str, *, details: dict[str, Any] | None = None):
        super().__init__(reason)
        self.reason = reason
        self.details = details or {}


@dataclass(frozen=True)
class Budget:
    max_seconds: int = 25
    max_steps: int = 8
    max_rows: int = 5000


@dataclass(frozen=True)
class Decision:
    kind: str
    reason: str


EXPECTED_ACTION_SEQUENCE = [
    "ingest_sales",
    "profile_sales",
    "transform_sales",
    "analyze_sales",
    "validate_analysis",
]


def validate_plan(raw_steps: Any, *, max_steps: int) -> list[dict[str, Any]]:
    if not isinstance(raw_steps, list) or not raw_steps:
        raise StopRun("invalid_plan:steps")
    if len(raw_steps) > max_steps:
        raise StopRun("invalid_plan:too_many_steps")

    steps: list[dict[str, Any]] = []
    actions: list[str] = []
    for raw in raw_steps:
        if not isinstance(raw, dict):
            raise StopRun("invalid_step:not_object")
        step_id = raw.get("id")
        action = raw.get("action")
        args = raw.get("args")
        if not isinstance(step_id, str) or not step_id.strip():
            raise StopRun("invalid_step:id")
        if not isinstance(action, str) or not action.strip():
            raise StopRun("invalid_step:action")
        if not isinstance(args, dict):
            raise StopRun("invalid_step:args")

        normalized = {
            "id": step_id.strip(),
            "action": action.strip(),
            "args": dict(args),
        }
        steps.append(normalized)
        actions.append(normalized["action"])

    if actions != EXPECTED_ACTION_SEQUENCE:
        raise StopRun(
            "invalid_plan:step_sequence",
            details={"expected": EXPECTED_ACTION_SEQUENCE, "received": actions},
        )

    return steps


class DataAnalysisGateway:
    def __init__(
        self,
        *,
        allowed_sources_policy: set[str],
        allowed_sources_execution: set[str],
        allowed_regions_policy: set[str],
        budget: Budget,
    ):
        self.allowed_sources_policy = set(allowed_sources_policy)
        self.allowed_sources_execution = set(allowed_sources_execution)
        self.allowed_regions_policy = {x.upper() for x in allowed_regions_policy}
        self.budget = budget

    def evaluate_ingest(self, *, source: str, region: str) -> Decision:
        if source not in self.allowed_sources_policy:
            return Decision(kind="deny", reason="source_denied_policy")
        if region.upper() not in self.allowed_regions_policy:
            return Decision(kind="deny", reason="region_denied_policy")
        if source not in self.allowed_sources_execution:
            return Decision(kind="deny", reason="source_denied_execution")
        return Decision(kind="allow", reason="policy_pass")

    def ensure_rows_budget(self, *, rows: list[dict[str, Any]]) -> None:
        if len(rows) > self.budget.max_rows:
            raise StopRun("dataset_too_large")

    def validate_profile(self, *, profile: dict[str, Any], max_missing_channel_pct: float) -> None:
        if not bool(profile.get("schema_ok")):
            raise StopRun("invalid_profile:schema")
        if not bool(profile.get("row_validity_ok")):
            raise StopRun("invalid_profile:row_values")

        missing_pct = float(profile.get("missing_channel_pct", 0.0))
        if missing_pct > max_missing_channel_pct:
            raise StopRun("invalid_profile:missing_channel_too_high")

    def validate_metrics(self, *, metrics: dict[str, Any]) -> None:
        sample_size = int(metrics.get("sample_size", 0))
        if sample_size <= 0:
            raise StopRun("invalid_metrics:sample_size")

        conversion = float(metrics.get("conversion_rate", 0.0))
        if not (0.0 <= conversion <= 1.0):
            raise StopRun("invalid_metrics:conversion_rate")

        failed_rate = float(metrics.get("failed_payment_rate", 0.0))
        if not (0.0 <= failed_rate <= 1.0):
            raise StopRun("invalid_metrics:failed_payment_rate")

        refund_rate = float(metrics.get("refund_rate", 0.0))
        if not (0.0 <= refund_rate <= 1.0):
            raise StopRun("invalid_metrics:refund_rate")

        gross_revenue = float(metrics.get("gross_revenue", 0.0))
        refund_amount_total = float(metrics.get("refund_amount_total", 0.0))
        net_revenue = float(metrics.get("net_revenue", 0.0))

        if net_revenue < 0:
            raise StopRun("invalid_metrics:net_revenue")
        if gross_revenue < net_revenue:
            raise StopRun("invalid_metrics:gross_less_than_net")
        if abs((gross_revenue - refund_amount_total) - net_revenue) > 0.01:
            raise StopRun("invalid_metrics:revenue_consistency")
