from __future__ import annotations

from dataclasses import dataclass
from typing import Any

HUMAN_APPROVAL_CAP_USD = 800.0


@dataclass(frozen=True)
class Policy:
    auto_refund_limit_usd: float = 1000.0
    max_refund_per_run_usd: float = 2000.0


@dataclass
class RuntimeState:
    executed_refund_total_usd: float = 0.0
    refund_executed: bool = False
    has_context: bool = False


@dataclass
class Decision:
    kind: str  # approve | revise | block | escalate
    reason: str
    revised_action: dict[str, Any] | None = None


def review_action(action: dict[str, Any], state: RuntimeState, policy: Policy) -> Decision:
    kind = action.get("kind")
    if kind == "final":
        if not state.has_context:
            return Decision(kind="block", reason="final_requires_context")
        return Decision(kind="approve", reason="final_with_context")
    if kind != "tool":
        return Decision(kind="block", reason="unknown_action_kind")

    name = action.get("name")
    args = dict(action.get("args") or {})

    if name == "get_refund_context":
        return Decision(kind="approve", reason="read_only_context")

    if name == "issue_refund":
        try:
            amount = float(args.get("amount_usd", 0.0))
        except (TypeError, ValueError):
            return Decision(kind="block", reason="invalid_refund_amount_type")
        if amount <= 0:
            return Decision(kind="block", reason="invalid_refund_amount")

        remaining = policy.max_refund_per_run_usd - state.executed_refund_total_usd
        if remaining <= 0:
            return Decision(kind="block", reason="refund_budget_exhausted")

        if amount > remaining:
            revised = {
                "kind": "tool",
                "name": name,
                "args": {**args, "amount_usd": round(remaining, 2)},
            }
            return Decision(
                kind="revise",
                reason="cap_to_remaining_run_budget",
                revised_action=revised,
            )

        reason = str(args.get("reason", "")).strip()
        if not reason:
            revised = {
                "kind": "tool",
                "name": name,
                "args": {**args, "reason": "Customer requested refund within policy review"},
            }
            return Decision(
                kind="revise",
                reason="refund_reason_required",
                revised_action=revised,
            )

        if amount > policy.auto_refund_limit_usd:
            return Decision(kind="escalate", reason="high_refund_requires_human")

        return Decision(kind="approve", reason="refund_within_auto_limit")

    if name == "send_refund_email":
        if not state.refund_executed:
            return Decision(kind="block", reason="email_before_refund")
        return Decision(kind="approve", reason="email_after_refund")

    return Decision(kind="block", reason=f"unknown_tool_for_supervisor:{name}")


def simulate_human_approval(action: dict[str, Any]) -> dict[str, Any]:
    name = action.get("name")
    args = dict(action.get("args") or {})

    if name != "issue_refund":
        return {"approved": True, "revised_action": action, "comment": "approved_by_human"}

    try:
        requested = float(args.get("amount_usd", 0.0))
    except (TypeError, ValueError):
        return {"approved": False, "comment": "invalid_requested_amount_type"}
    approved_amount = min(requested, HUMAN_APPROVAL_CAP_USD)

    if approved_amount <= 0:
        return {"approved": False, "comment": "invalid_requested_amount"}

    revised_action = {
        "kind": "tool",
        "name": "issue_refund",
        "args": {**args, "amount_usd": round(approved_amount, 2)},
    }
    return {
        "approved": True,
        "revised_action": revised_action,
        "comment": f"approved_with_cap:{approved_amount}",
    }
