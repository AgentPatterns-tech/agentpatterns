from __future__ import annotations

import json
import time
import uuid
from typing import Any

from audit import build_audit_log
from context import build_incident_context
from gateway import Budget, SelfCritiqueGateway, StopRun, text_hash, validate_critique, validate_draft
from llm import LLMEmpty, LLMInvalid, LLMTimeout, critique_draft, generate_draft, revise_once, shorten_draft

GOAL = (
    "Draft a customer-facing payment incident update for US enterprise customers. "
    "Use precise language, avoid guarantees, and keep next actions concrete."
)
INCIDENT_CONTEXT = build_incident_context(report_date="2026-03-06", region="US")

BUDGET = Budget(
    max_seconds=120,
    max_draft_chars=900,
    max_risks=5,
    max_required_changes=5,
    max_answer_chars=980,
    max_length_increase_pct=20.0,
    min_patch_similarity=0.4,
)

ALLOWED_CRITIQUE_DECISIONS_POLICY = {"approve", "revise", "escalate"}
AUTO_REVISION_ENABLED = True
ALLOWED_CRITIQUE_DECISIONS_EXECUTION = (
    ALLOWED_CRITIQUE_DECISIONS_POLICY if AUTO_REVISION_ENABLED else {"approve", "escalate"}
)

ALLOWED_RISK_TYPES_POLICY = {
    "overconfidence",
    "missing_uncertainty",
    "contradiction",
    "scope_leak",
    "policy_violation",
    "legal_risk",
}



def run_self_critique_agent(*, goal: str, incident_context: dict[str, Any]) -> dict[str, Any]:
    run_id = str(uuid.uuid4())
    started = time.monotonic()
    trace: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []

    gateway = SelfCritiqueGateway(
        allow_execution_decisions=ALLOWED_CRITIQUE_DECISIONS_EXECUTION,
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

    draft_attempts = 0
    draft_retried = False
    try:
        draft_attempts += 1
        draft_raw = generate_draft(goal=goal, incident_context=incident_context)
        try:
            draft = validate_draft(draft_raw, max_chars=BUDGET.max_draft_chars)
        except StopRun as exc:
            if exc.reason != "invalid_draft:too_long":
                raise
            # One bounded recovery attempt: shorten draft within policy budget.
            draft_attempts += 1
            draft_retried = True
            shortened_raw = shorten_draft(draft=draft_raw, max_chars=BUDGET.max_draft_chars)
            draft = validate_draft(shortened_raw, max_chars=BUDGET.max_draft_chars)
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
            "attempts_used": draft_attempts,
            "retried": draft_retried,
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
        return stopped("max_seconds", phase="critique")

    try:
        raw_critique = critique_draft(
            goal=goal,
            incident_context=incident_context,
            draft=draft,
            allowed_risk_types=sorted(ALLOWED_RISK_TYPES_POLICY),
        )
    except LLMTimeout:
        return stopped("llm_timeout", phase="critique")
    except LLMInvalid as exc:
        return stopped(exc.args[0], phase="critique")

    try:
        critique = validate_critique(
            raw_critique,
            allowed_decisions_policy=ALLOWED_CRITIQUE_DECISIONS_POLICY,
            allowed_risk_types_policy=ALLOWED_RISK_TYPES_POLICY,
            max_risks=BUDGET.max_risks,
            max_required_changes=BUDGET.max_required_changes,
        )
        gateway.enforce_execution_decision(critique["decision"])
    except StopRun as exc:
        return stopped(exc.reason, phase="critique", raw_critique=raw_critique)

    trace.append(
        {
            "step": 2,
            "phase": "critique",
            "decision": critique["decision"],
            "severity": critique["severity"],
            "risks": len(critique["risks"]),
            "required_changes": len(critique["required_changes"]),
            "ok": True,
        }
    )
    history.append(
        {
            "step": 2,
            "action": "critique_once",
            "critique": critique,
        }
    )

    if critique["decision"] == "escalate":
        escalation_reason = str(critique.get("reason", "")).strip()
        return {
            "run_id": run_id,
            "status": "stopped",
            "stop_reason": "policy_escalation",
            "escalation_reason": escalation_reason[:120],
            "phase": "critique",
            "critique": critique,
            "trace": trace,
            "history": history,
        }

    final_answer = draft
    revised = False

    if critique["decision"] == "revise":
        revise_attempts = 0
        revise_retried = False
        revised_payload: dict[str, Any] | None = None
        last_revised_candidate = draft
        for attempt in range(1, 4):
            if (time.monotonic() - started) > BUDGET.max_seconds:
                return stopped("max_seconds", phase="revise")

            revise_attempts = attempt
            strict_mode = attempt > 1
            try:
                revised_raw = revise_once(
                    goal=goal,
                    incident_context=incident_context,
                    draft=draft,
                    required_changes=critique["required_changes"],
                    strict_mode=strict_mode,
                )
                last_revised_candidate = revised_raw
                revised_payload = gateway.validate_revision(
                    original=draft,
                    revised=revised_raw,
                    context=incident_context,
                    required_changes=critique["required_changes"],
                )
                break
            except LLMTimeout:
                return stopped("llm_timeout", phase="revise")
            except LLMInvalid as exc:
                return stopped(exc.args[0], phase="revise")
            except LLMEmpty:
                return stopped("llm_empty", phase="revise")
            except StopRun as exc:
                if exc.reason == "patch_violation:required_changes_not_applied" and attempt < 3:
                    revise_retried = True
                    continue
                if exc.reason == "patch_violation:required_changes_not_applied":
                    # Final fallback: enforce required phrase edits deterministically.
                    try:
                        fallback_revised = gateway.apply_required_changes_fallback(
                            text=last_revised_candidate,
                            required_changes=critique["required_changes"],
                        )
                        revised_payload = gateway.validate_revision(
                            original=draft,
                            revised=fallback_revised,
                            context=incident_context,
                            required_changes=critique["required_changes"],
                        )
                        revise_attempts = attempt + 1
                        revise_retried = True
                        break
                    except StopRun as fallback_exc:
                        return stopped(fallback_exc.reason, phase="revise")
                return stopped(exc.reason, phase="revise")

        if revised_payload is None:
            return stopped("patch_violation:required_changes_not_applied", phase="revise")

        final_answer = revised_payload["answer"]
        revised = True

        trace.append(
            {
                "step": 3,
                "phase": "revise",
                "patch_similarity": revised_payload["patch_similarity"],
                "length_increase_pct": revised_payload["length_increase_pct"],
                "required_changes_total": revised_payload["required_changes_total"],
                "required_changes_enforced": revised_payload["required_changes_enforced"],
                "required_changes_unenforced": revised_payload["required_changes_unenforced"],
                "attempts_used": revise_attempts,
                "retried": revise_retried,
                "revised_hash": text_hash(final_answer),
                "ok": True,
            }
        )
        history.append(
            {
                "step": 3,
                "action": "revise_once",
                "required_changes": critique["required_changes"],
                "revised_answer": final_answer,
            }
        )

    try:
        final_answer = gateway.validate_final(final_answer)
    except StopRun as exc:
        return stopped(exc.reason, phase="finalize")

    audit_log = build_audit_log(
        before=draft,
        after=final_answer,
        risks=critique["risks"],
        required_changes=critique["required_changes"],
    )

    trace.append(
        {
            "step": 4 if revised else 3,
            "phase": "audit_finalize",
            "final_hash": text_hash(final_answer),
            "changed": audit_log["changed"],
            "diff_lines": len(audit_log["diff_excerpt"]),
            "ok": True,
        }
    )
    history.append(
        {
            "step": 4 if revised else 3,
            "action": "audit_finalize",
            "status": "final",
            "changed": audit_log["changed"],
        }
    )

    return {
        "run_id": run_id,
        "status": "ok",
        "stop_reason": "success",
        "outcome": "revised_once" if revised else "approved_direct",
        "answer": final_answer,
        "critique_decision": critique["decision"],
        "severity": critique["severity"],
        "risks": critique["risks"],
        "required_changes": critique["required_changes"],
        "audit": audit_log,
        "trace": trace,
        "history": history,
    }



def main() -> None:
    result = run_self_critique_agent(goal=GOAL, incident_context=INCIDENT_CONTEXT)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
