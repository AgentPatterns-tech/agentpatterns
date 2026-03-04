from __future__ import annotations

import json
import math
import time
import uuid
from typing import Any

from agent import compose_final_answer, propose_code_execution_plan
from context import build_request
from gateway import (
    Budget,
    CodeExecutionGateway,
    StopRun,
    code_hash,
    validate_code_action,
    validate_execution_output,
)

GOAL = (
    "Run a safe code task to compute incident metrics from payment transactions "
    "and return an operations-ready summary."
)
REQUEST = build_request(
    report_date="2026-03-07",
    region="US",
    incident_id="inc_payments_20260307",
)

DEFAULT_BUDGET = Budget(
    max_seconds=25,
    max_code_chars=2400,
    exec_timeout_seconds=2.0,
    max_stdout_bytes=4096,
    max_stderr_bytes=4096,
)

DEFAULT_ALLOWED_LANGUAGES_POLICY = {"python", "javascript"}
ALLOWED_LANGUAGES_EXECUTION = {"python"}


def run_code_execution_agent(*, goal: str, request: dict[str, Any]) -> dict[str, Any]:
    run_id = str(uuid.uuid4())
    started = time.monotonic()
    trace: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []

    hints_raw = request.get("policy_hints")
    hints: dict[str, Any] = hints_raw if isinstance(hints_raw, dict) else {}
    network_access = str(hints.get("network_access", "denied")).strip().lower()
    if network_access not in {"denied", "none", "off"}:
        return {
            "run_id": run_id,
            "status": "stopped",
            "stop_reason": "invalid_request:network_access_must_be_denied",
            "phase": "plan",
            "trace": trace,
            "history": history,
        }

    allowed_policy_raw = hints.get("allowed_languages")
    if isinstance(allowed_policy_raw, list):
        allowed_policy = {
            str(item).strip().lower()
            for item in allowed_policy_raw
            if isinstance(item, str) and item.strip()
        }
    else:
        allowed_policy = set(DEFAULT_ALLOWED_LANGUAGES_POLICY)
    if not allowed_policy:
        allowed_policy = set(DEFAULT_ALLOWED_LANGUAGES_POLICY)

    max_code_chars_raw = hints.get("max_code_chars", DEFAULT_BUDGET.max_code_chars)
    exec_timeout_raw = hints.get("exec_timeout_seconds", DEFAULT_BUDGET.exec_timeout_seconds)
    try:
        max_code_chars = int(max_code_chars_raw)
    except (TypeError, ValueError):
        max_code_chars = DEFAULT_BUDGET.max_code_chars
    try:
        exec_timeout_seconds = float(exec_timeout_raw)
        if not math.isfinite(exec_timeout_seconds):
            raise ValueError
    except (TypeError, ValueError):
        exec_timeout_seconds = DEFAULT_BUDGET.exec_timeout_seconds

    budget = Budget(
        max_seconds=DEFAULT_BUDGET.max_seconds,
        max_code_chars=max(200, min(8000, max_code_chars)),
        exec_timeout_seconds=max(0.2, min(20.0, exec_timeout_seconds)),
        max_stdout_bytes=DEFAULT_BUDGET.max_stdout_bytes,
        max_stderr_bytes=DEFAULT_BUDGET.max_stderr_bytes,
    )

    gateway = CodeExecutionGateway(
        allowed_languages_policy=allowed_policy,
        allowed_languages_execution=ALLOWED_LANGUAGES_EXECUTION,
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

        raw_plan = propose_code_execution_plan(goal=goal, request=request)
        action = validate_code_action(raw_plan.get("action"), max_code_chars=budget.max_code_chars)
        generated_code_hash = code_hash(action["code"])

        trace.append(
            {
                "step": 1,
                "phase": "plan_code",
                "action_id": action["id"],
                "language": action["language"],
                "code_hash": generated_code_hash,
                "chars": len(action["code"]),
                "ok": True,
            }
        )
        history.append(
            {
                "step": 1,
                "action": "propose_code_execution_plan",
                "proposed_action": {
                    "id": action["id"],
                    "language": action["language"],
                    "entrypoint": action["entrypoint"],
                    "code_hash": generated_code_hash,
                },
            }
        )

        phase = "policy_check"
        decision = gateway.evaluate(action=action)
        trace.append(
            {
                "step": 2,
                "phase": "policy_check",
                "decision": decision.kind,
                "reason": decision.reason,
                "allowed_languages_policy": sorted(allowed_policy),
                "allowed_languages_execution": sorted(ALLOWED_LANGUAGES_EXECUTION),
                "ok": decision.kind == "allow",
            }
        )
        history.append(
            {
                "step": 2,
                "action": "policy_check",
                "decision": {
                    "kind": decision.kind,
                    "reason": decision.reason,
                },
            }
        )
        if decision.kind != "allow":
            return stopped(f"policy_block:{decision.reason}", phase=phase)

        if (time.monotonic() - started) > budget.max_seconds:
            return stopped("max_seconds", phase="execute")

        phase = "execute"
        execute_trace = {
            "step": 3,
            "phase": "execute_code",
            "language": action["language"],
            "code_hash": generated_code_hash,
            "ok": False,
        }
        trace.append(execute_trace)
        try:
            execution = gateway.execute_python(
                code=action["code"],
                entrypoint=action["entrypoint"],
                input_payload=action["input_payload"],
            )
            validated = validate_execution_output(execution["payload"])
        except StopRun as exc:
            execute_trace["error"] = exc.reason
            details = exc.details if isinstance(exc.details, dict) else {}
            stderr_snippet = str(details.get("stderr_snippet", "")).strip()
            stdout_snippet = str(details.get("stdout_snippet", "")).strip()
            if stderr_snippet:
                execute_trace["stderr_snippet"] = stderr_snippet
            if stdout_snippet:
                execute_trace["stdout_snippet"] = stdout_snippet
            history.append(
                {
                    "step": 3,
                    "action": "execute_code",
                    "status": "error",
                    "reason": exc.reason,
                    **({"stderr_snippet": stderr_snippet} if stderr_snippet else {}),
                    **({"stdout_snippet": stdout_snippet} if stdout_snippet else {}),
                }
            )
            raise

        execute_trace["stdout_bytes"] = execution["stdout_bytes"]
        execute_trace["stderr_bytes"] = execution["stderr_bytes"]
        execute_trace["exec_ms"] = execution["exec_ms"]
        execute_trace["ok"] = True
        history.append(
            {
                "step": 3,
                "action": "execute_code",
                "result": validated,
            }
        )

        aggregate = {
            "report_date": request["request"]["report_date"],
            "region": request["request"]["region"],
            "incident_id": request["request"]["incident_id"],
            "metrics": {
                "incident_severity": validated["incident_severity"],
                "failed_payment_rate": round(validated["failed_payment_rate"], 6),
                "failed_payment_rate_pct": round(validated["failed_payment_rate"] * 100, 2),
                "chargeback_alerts": validated["chargeback_alerts"],
                "eta_minutes": validated["eta_minutes"],
                "affected_checkout_share": round(validated["affected_checkout_share"], 6),
                "affected_checkout_share_pct": round(validated["affected_checkout_share"] * 100, 2),
                "avg_latency_ms": validated["avg_latency_ms"],
                "p95_latency_ms": validated["p95_latency_ms"],
                "sample_size": validated["sample_size"],
            },
        }
        execution_summary = {
            "language": action["language"],
            "code_hash": generated_code_hash,
            "exec_ms": execution["exec_ms"],
            "stdout_bytes": execution["stdout_bytes"],
            "stderr_bytes": execution["stderr_bytes"],
        }
        answer = compose_final_answer(
            request=request,
            aggregate=aggregate,
            execution_summary=execution_summary,
        )

        trace.append(
            {
                "step": 4,
                "phase": "finalize",
                "ok": True,
            }
        )
        history.append(
            {
                "step": 4,
                "action": "finalize",
            }
        )

        return {
            "run_id": run_id,
            "status": "ok",
            "stop_reason": "success",
            "outcome": "code_execution_success",
            "answer": answer,
            "proposed_action": {
                "id": action["id"],
                "language": action["language"],
                "entrypoint": action["entrypoint"],
                "code_hash": generated_code_hash,
            },
            "aggregate": aggregate,
            "execution": execution_summary,
            "trace": trace,
            "history": history,
        }
    except StopRun as exc:
        return stopped(exc.reason, phase=phase)


def main() -> None:
    result = run_code_execution_agent(goal=GOAL, request=REQUEST)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
