from __future__ import annotations

import json
import time
import uuid
from typing import Any

from agent import compose_final_answer, propose_action_plan
from context import build_request
from gateway import Budget, PolicyGateway, StopRun, validate_plan
from tools import (
    create_manual_review_ticket,
    export_customer_data,
    fetch_incident_snapshot,
    send_status_update,
)

GOAL = (
    "Prepare a customer-safe operations update for a US payments incident. "
    "Use policy-gated execution and never expose customer PII."
)
REQUEST = build_request(
    report_date="2026-03-06",
    region="US",
    incident_id="inc_payments_20260306",
)

BUDGET = Budget(
    max_seconds=25,
    max_actions=8,
    action_timeout_seconds=1.2,
    max_recipients_per_send=50000,
)

ALLOWED_TOOLS_POLICY = {
    "fetch_incident_snapshot",
    "send_status_update",
    "export_customer_data",
    "create_manual_review_ticket",
}
ALLOWED_TOOLS_EXECUTION = {
    "fetch_incident_snapshot",
    "send_status_update",
    "create_manual_review_ticket",
}

TOOLS: dict[str, Any] = {
    "fetch_incident_snapshot": fetch_incident_snapshot,
    "send_status_update": send_status_update,
    "export_customer_data": export_customer_data,
    "create_manual_review_ticket": create_manual_review_ticket,
}


def simulate_human_approval(*, action: dict[str, Any], reason: str) -> dict[str, Any]:
    # Demo policy: approve only the broadcast-risk escalation after safe rewrite.
    if reason == "mass_external_broadcast":
        return {"approved": True, "action": action, "reason": "approved_with_safe_scope"}
    return {"approved": False, "action": action, "reason": "human_rejected"}


def run_guarded_policy_agent(*, goal: str, request: dict[str, Any]) -> dict[str, Any]:
    run_id = str(uuid.uuid4())
    started = time.monotonic()
    trace: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []
    state: dict[str, Any] = {"snapshot": None, "delivery": None}

    gateway = PolicyGateway(
        allowed_tools_policy=ALLOWED_TOOLS_POLICY,
        allowed_tools_execution=ALLOWED_TOOLS_EXECUTION,
        budget=BUDGET,
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

    decision_counts = {"allow": 0, "rewrite": 0, "deny": 0, "escalate": 0}
    denied_tools: list[str] = []
    rewritten_tools: list[str] = []
    escalated_tools: list[str] = []

    try:
        if (time.monotonic() - started) > BUDGET.max_seconds:
            return stopped("max_seconds", phase="plan")

        raw_plan = propose_action_plan(goal=goal, request=request)
        actions = validate_plan(raw_plan.get("actions"), max_actions=BUDGET.max_actions)

        for idx, action in enumerate(actions, start=1):
            if (time.monotonic() - started) > BUDGET.max_seconds:
                return stopped("max_seconds", phase="execute")

            decision = gateway.evaluate(action=action, state=state)
            decision_counts[decision.kind] += 1

            trace_item = {
                "step": idx,
                "action_id": action["id"],
                "tool": action["tool"],
                "policy_decision": decision.kind,
                "policy_reason": decision.reason,
                "executed_from": "none",
                "ok": decision.kind != "deny",
            }
            history_item: dict[str, Any] = {
                "step": idx,
                "proposed_action": action,
                "policy": {"decision": decision.kind, "reason": decision.reason},
            }

            if decision.kind == "deny":
                denied_tools.append(action["tool"])
                trace.append(trace_item)
                history.append(history_item)
                continue

            executed_action = action
            executed_from = "original"
            if decision.kind == "rewrite":
                executed_action = decision.enforced_action or action
                rewritten_tools.append(action["tool"])
                executed_from = "policy_rewrite"
            elif decision.kind == "escalate":
                escalated_tools.append(action["tool"])
                escalation_ticket = gateway.dispatch(
                    tool_name="create_manual_review_ticket",
                    tool_fn=TOOLS["create_manual_review_ticket"],
                    args={"reason": decision.reason, "payload": (decision.enforced_action or action)},
                )
                history_item["escalation_ticket"] = escalation_ticket
                human = simulate_human_approval(
                    action=(decision.enforced_action or action),
                    reason=decision.reason,
                )
                if not human["approved"]:
                    return stopped("policy_escalation_rejected", phase="execute")
                executed_action = human["action"]
                executed_from = "human_approved"
                history_item["human"] = {
                    "approved": True,
                    "reason": human["reason"],
                }

            tool_name = executed_action["tool"]
            tool_fn = TOOLS.get(tool_name)
            if tool_fn is None:
                return stopped(f"tool_unmapped:{tool_name}", phase="execute")

            observation = gateway.dispatch(
                tool_name=tool_name,
                tool_fn=tool_fn,
                args=executed_action["args"],
            )
            if tool_name == "fetch_incident_snapshot":
                state["snapshot"] = observation
            elif tool_name == "send_status_update":
                state["delivery"] = observation

            trace_item["executed_from"] = executed_from
            trace_item["ok"] = True
            trace.append(trace_item)

            history_item["executed_action"] = executed_action
            history_item["executed_from"] = executed_from
            history_item["observation"] = observation
            history.append(history_item)

        if not isinstance(state["snapshot"], dict):
            return stopped("missing_required_observation:snapshot", phase="finalize")
        if not isinstance(state["delivery"], dict):
            return stopped("missing_required_observation:send_status_update", phase="finalize")

        aggregate = {
            "report_date": request["request"]["report_date"],
            "region": request["request"]["region"],
            "incident": state["snapshot"],
            "delivery": state["delivery"],
        }
        policy_summary = {
            "decisions": decision_counts,
            "denied_tools": sorted(set(denied_tools)),
            "rewritten_tools": sorted(set(rewritten_tools)),
            "escalated_tools": sorted(set(escalated_tools)),
        }
        answer = compose_final_answer(
            request=request,
            state=state,
            policy_summary=policy_summary,
        )

        trace.append(
            {
                "step": len(actions) + 1,
                "phase": "finalize",
                "ok": True,
            }
        )
        history.append({"step": len(actions) + 1, "action": "finalize"})

        return {
            "run_id": run_id,
            "status": "ok",
            "stop_reason": "success",
            "outcome": "policy_guarded_success",
            "answer": answer,
            "proposed_plan": actions,
            "executed_plan": [
                step["executed_action"]
                for step in history
                if isinstance(step, dict) and isinstance(step.get("executed_action"), dict)
            ],
            "aggregate": aggregate,
            "policy_summary": policy_summary,
            "trace": trace,
            "history": history,
        }
    except StopRun as exc:
        return stopped(exc.reason, phase="execute")
    finally:
        gateway.close()


def main() -> None:
    result = run_guarded_policy_agent(goal=GOAL, request=REQUEST)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
