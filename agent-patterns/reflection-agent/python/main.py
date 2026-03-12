from __future__ import annotations

import json
import time
import uuid
from typing import Any

from context import build_incident_context
from gateway import Budget, ReflectionGateway, StopRun, text_hash, validate_draft, validate_review
from llm import LLMEmpty, LLMInvalid, LLMTimeout, generate_draft, review_draft, revise_once

GOAL = (
    "Draft a customer-facing payment incident update for US enterprise customers. "
    "Keep it accurate, avoid overconfident language, and include next actions."
)
INCIDENT_CONTEXT = build_incident_context(report_date="2026-03-05", region="US")

BUDGET = Budget(
    max_seconds=30,
    max_draft_chars=900,
    max_review_issues=4,
    max_fix_items=4,
    max_answer_chars=900,
    min_patch_similarity=0.45,
)

ALLOWED_REVIEW_DECISIONS_POLICY = {"approve", "revise", "escalate"}
AUTO_REVISION_ENABLED = True
ALLOWED_REVIEW_DECISIONS_EXECUTION = (
    ALLOWED_REVIEW_DECISIONS_POLICY if AUTO_REVISION_ENABLED else {"approve", "escalate"}
)

ALLOWED_ISSUE_TYPES_POLICY = {
    "overconfidence",
    "missing_uncertainty",
    "contradiction",
    "scope_leak",
    "policy_violation",
    "legal_risk",
}



def run_reflection_agent(*, goal: str, incident_context: dict[str, Any]) -> dict[str, Any]:
    run_id = str(uuid.uuid4())
    started = time.monotonic()
    trace: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []

    gateway = ReflectionGateway(
        allow_execution_decisions=ALLOWED_REVIEW_DECISIONS_EXECUTION,
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

    try:
        draft_raw = generate_draft(goal=goal, incident_context=incident_context)
        draft = validate_draft(draft_raw, max_chars=BUDGET.max_draft_chars)
    except LLMTimeout:
        return stopped("llm_timeout", phase="draft")
    except LLMInvalid as exc:
        return stopped(exc.args[0], phase="draft")
    except LLMEmpty:
        return stopped("llm_empty", phase="draft")
    except StopRun as exc:
        return stopped(exc.reason, phase="draft")

    trace.append(
        {
            "step": 1,
            "phase": "draft",
            "draft_hash": text_hash(draft),
            "chars": len(draft),
            "ok": True,
        }
    )
    history.append(
        {
            "step": 1,
            "action": "draft_once",
            "draft": draft,
        }
    )

    if (time.monotonic() - started) > BUDGET.max_seconds:
        return stopped("max_seconds", phase="review")

    try:
        raw_review = review_draft(
            goal=goal,
            incident_context=incident_context,
            draft=draft,
            allowed_issue_types=sorted(ALLOWED_ISSUE_TYPES_POLICY),
        )
    except LLMTimeout:
        return stopped("llm_timeout", phase="review")
    except LLMInvalid as exc:
        return stopped(exc.args[0], phase="review")

    try:
        review = validate_review(
            raw_review,
            allowed_decisions_policy=ALLOWED_REVIEW_DECISIONS_POLICY,
            allowed_issue_types_policy=ALLOWED_ISSUE_TYPES_POLICY,
            max_review_issues=BUDGET.max_review_issues,
            max_fix_items=BUDGET.max_fix_items,
        )
        gateway.enforce_execution_decision(review["decision"])
    except StopRun as exc:
        return stopped(exc.reason, phase="review", raw_review=raw_review)

    trace.append(
        {
            "step": 2,
            "phase": "review",
            "decision": review["decision"],
            "issues": len(review["issues"]),
            "fix_items": len(review["fix_plan"]),
            "ok": True,
        }
    )
    history.append(
        {
            "step": 2,
            "action": "review_once",
            "review": review,
        }
    )

    if review["decision"] == "escalate":
        escalation_reason = str(review.get("reason", "")).strip()
        return {
            "run_id": run_id,
            "status": "stopped",
            "stop_reason": "policy_escalation",
            "escalation_reason": escalation_reason[:120],
            "phase": "review",
            "review": review,
            "trace": trace,
            "history": history,
        }

    final_answer = draft
    revised = False

    if review["decision"] == "revise":
        if (time.monotonic() - started) > BUDGET.max_seconds:
            return stopped("max_seconds", phase="revise")

        try:
            revised_raw = revise_once(
                goal=goal,
                incident_context=incident_context,
                draft=draft,
                fix_plan=review["fix_plan"],
            )
            revised_payload = gateway.validate_revision(
                original=draft,
                revised=revised_raw,
                context=incident_context,
                fix_plan=review["fix_plan"],
            )
        except LLMTimeout:
            return stopped("llm_timeout", phase="revise")
        except LLMInvalid as exc:
            return stopped(exc.args[0], phase="revise")
        except LLMEmpty:
            return stopped("llm_empty", phase="revise")
        except StopRun as exc:
            return stopped(exc.reason, phase="revise")

        final_answer = revised_payload["answer"]
        revised = True

        trace.append(
            {
                "step": 3,
                "phase": "revise",
                "patch_similarity": revised_payload["patch_similarity"],
                "fix_plan_quoted_checks": revised_payload["fix_plan_quoted_checks"],
                "revised_hash": text_hash(final_answer),
                "ok": True,
            }
        )
        history.append(
            {
                "step": 3,
                "action": "revise_once",
                "fix_plan": review["fix_plan"],
                "revised_answer": final_answer,
            }
        )

    try:
        final_answer = gateway.validate_final(final_answer)
    except StopRun as exc:
        return stopped(exc.reason, phase="finalize")

    trace.append(
        {
            "step": 4 if revised else 3,
            "phase": "finalize",
            "final_hash": text_hash(final_answer),
            "ok": True,
        }
    )
    history.append(
        {
            "step": 4 if revised else 3,
            "action": "finalize",
            "status": "final",
        }
    )

    return {
        "run_id": run_id,
        "status": "ok",
        "stop_reason": "success",
        "outcome": "revised_once" if revised else "approved_direct",
        "answer": final_answer,
        "review_decision": review["decision"],
        "issues": review["issues"],
        "fix_plan": review["fix_plan"],
        "trace": trace,
        "history": history,
    }



def main() -> None:
    result = run_reflection_agent(goal=GOAL, incident_context=INCIDENT_CONTEXT)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
