from __future__ import annotations

import json
import os
from typing import Any

from gateway import Budget, StopRun, ToolGateway, args_hash
from llm import LLMTimeout, generate_support_draft
from policy import (
    build_handoff_note,
    classify_ticket_risk,
    redact_customer,
    should_force_manual_review,
    validate_citations,
    validate_no_commitments,
)
from tools import (
    artifacts_put,
    audit_emit,
    customers_get,
    get_demo_state,
    kb_search,
    policy_search,
    tickets_add_internal_note,
    tickets_get,
)

BUDGET = Budget(max_tool_calls=12, max_seconds=30)

TOOL_REGISTRY = {
    "tickets_get": tickets_get,
    "customers_get": customers_get,
    "kb_search": kb_search,
    "policy_search": policy_search,
    "tickets_add_internal_note": tickets_add_internal_note,
    "artifacts_put": artifacts_put,
    "audit_emit": audit_emit,
}

ALLOWED_TOOLS = {
    "tickets_get",
    "customers_get",
    "kb_search",
    "policy_search",
    "tickets_add_internal_note",
    "artifacts_put",
    "audit_emit",
}


def _trace_call(trace: list[dict[str, Any]], *, step: int, name: str, args: dict[str, Any]) -> None:
    trace.append({"step": step, "tool": name, "args_hash": args_hash(args)})


def run_support_agent(ticket_id: str) -> dict[str, Any]:
    gateway = ToolGateway(allow=ALLOWED_TOOLS, registry=TOOL_REGISTRY, budget=BUDGET)
    trace: list[dict[str, Any]] = []
    step = 0

    try:
        step += 1
        args = {"ticket_id": ticket_id}
        ticket_payload = gateway.call("tickets_get", args)
        _trace_call(trace, step=step, name="tickets_get", args=args)

        ticket = ticket_payload["ticket"]

        step += 1
        args = {"customer_id": int(ticket["customer_id"])}
        customer_payload = gateway.call("customers_get", args)
        _trace_call(trace, step=step, name="customers_get", args=args)

        customer = customer_payload["customer"]

        risk_category, risk_reason = classify_ticket_risk(ticket)

        if should_force_manual_review(risk_category=risk_category, customer=customer):
            handoff = build_handoff_note(
                ticket=ticket,
                risk_category=risk_category,
                risk_reason=risk_reason,
            )

            step += 1
            args = {"ticket_id": ticket_id, "note": handoff}
            note_result = gateway.call("tickets_add_internal_note", args)
            _trace_call(trace, step=step, name="tickets_add_internal_note", args=args)

            step += 1
            args = {"ticket_id": ticket_id, "kind": "handoff", "payload": handoff}
            artifact_result = gateway.call("artifacts_put", args)
            _trace_call(trace, step=step, name="artifacts_put", args=args)

            step += 1
            args = {
                "event_type": "support.handoff.created",
                "details": {
                    "ticket_id": ticket_id,
                    "risk_category": risk_category,
                    "artifact_id": artifact_result["artifact_id"],
                    "internal_note_id": note_result["internal_note_id"],
                },
            }
            gateway.call("audit_emit", args)
            _trace_call(trace, step=step, name="audit_emit", args=args)

            return {
                "status": "success",
                "outcome": "handoff",
                "risk_category": risk_category,
                "risk_reason": risk_reason,
                "requires_human_approval": True,
                "send_allowed": False,
                "artifact_id": artifact_result["artifact_id"],
                "trace": trace,
            }

        step += 1
        args = {"query": ticket.get("subject", ""), "k": 3}
        kb_result = gateway.call("kb_search", args)
        _trace_call(trace, step=step, name="kb_search", args=args)

        step += 1
        args = {"query": "refund policy sla security", "k": 3}
        policy_result = gateway.call("policy_search", args)
        _trace_call(trace, step=step, name="policy_search", args=args)

        safe_customer = redact_customer(customer)

        draft = generate_support_draft(
            ticket=ticket,
            customer=safe_customer,
            kb_matches=kb_result["matches"],
            policy_matches=policy_result["matches"],
        )

        violations = []
        violations.extend(validate_no_commitments(draft["customer_reply"]))
        violations.extend(
            validate_citations(
                claims=draft.get("claims", []),
                citations=draft.get("citations", []),
            )
        )

        if violations:
            blocked_note = {
                "ticket_id": ticket_id,
                "reason": "unsafe_draft",
                "violations": violations,
            }

            step += 1
            args = {"ticket_id": ticket_id, "note": blocked_note}
            gateway.call("tickets_add_internal_note", args)
            _trace_call(trace, step=step, name="tickets_add_internal_note", args=args)

            step += 1
            args = {
                "event_type": "support.draft.blocked",
                "details": {"ticket_id": ticket_id, "violations": violations},
            }
            gateway.call("audit_emit", args)
            _trace_call(trace, step=step, name="audit_emit", args=args)

            return {
                "status": "blocked",
                "stop_reason": "unsafe_draft",
                "violations": violations,
                "requires_human_approval": True,
                "send_allowed": False,
                "trace": trace,
            }

        step += 1
        args = {"ticket_id": ticket_id, "kind": "draft", "payload": draft}
        artifact_result = gateway.call("artifacts_put", args)
        _trace_call(trace, step=step, name="artifacts_put", args=args)

        step += 1
        args = {
            "event_type": "support.draft.created",
            "details": {
                "ticket_id": ticket_id,
                "artifact_id": artifact_result["artifact_id"],
                "risk_category": risk_category,
            },
        }
        gateway.call("audit_emit", args)
        _trace_call(trace, step=step, name="audit_emit", args=args)

        return {
            "status": "success",
            "outcome": "draft_ready",
            "requires_human_approval": True,
            "send_allowed": False,
            "artifact_id": artifact_result["artifact_id"],
            "risk_category": risk_category,
            "draft_preview": draft["customer_reply"],
            "trace": trace,
        }

    except LLMTimeout:
        return {
            "status": "stopped",
            "stop_reason": "llm_timeout",
            "trace": trace,
        }
    except StopRun as exc:
        return {
            "status": "stopped",
            "stop_reason": exc.reason,
            "trace": trace,
        }


def main() -> None:
    ticket_id = os.getenv("TICKET_ID", "T-1001")
    result = run_support_agent(ticket_id)
    state = get_demo_state()
    print(json.dumps({"result": result, "state": state}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
