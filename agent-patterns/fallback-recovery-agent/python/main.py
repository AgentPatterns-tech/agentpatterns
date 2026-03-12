from __future__ import annotations

import json
import time
import uuid
from typing import Any

from checkpoint_store import CheckpointStore
from context import build_operations_context
from gateway import Budget, RecoveryGateway, StopRun
from llm import LLMEmpty, LLMInvalid, LLMTimeout, compose_operations_brief
from tools import (
    demand_cached_snapshot,
    demand_primary_api,
    payments_cached_snapshot,
    payments_primary_api,
    payments_replica_api,
)

GOAL = (
    "Prepare a concise operations brief for the US payments incident. "
    "Recover from tool failures safely and keep the update customer-safe."
)
REQUEST = build_operations_context(report_date="2026-03-06", region="US")

BUDGET = Budget(
    max_seconds=120,
    step_timeout_seconds=1.0,
    max_retries=1,
    max_fallbacks=2,
    checkpoint_ttl_seconds=900.0,
)

ALLOWED_STEPS_POLICY = {"payments_health", "demand_signal"}
ALLOWED_TOOLS_POLICY = {
    "payments_primary_api",
    "payments_replica_api",
    "payments_cached_snapshot",
    "demand_primary_api",
    "demand_cached_snapshot",
}
# Runtime allowlist can differ from policy allowlist by tenant/feature-flags.
ALLOWED_TOOLS_EXECUTION = ALLOWED_TOOLS_POLICY


def run_fallback_recovery_agent(*, goal: str, request: dict[str, Any]) -> dict[str, Any]:
    run_id = str(uuid.uuid4())
    started = time.monotonic()
    checkpoint = CheckpointStore()
    trace: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []

    gateway = RecoveryGateway(
        allowed_steps_policy=ALLOWED_STEPS_POLICY,
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

    req = request["request"]
    common_args = {
        "report_date": req["report_date"],
        "region": req["region"],
        "request_id": run_id,
    }

    try:
        try:
            payments_step = gateway.run_step_with_recovery(
                run_id=run_id,
                step_id="payments_health",
                primary_tool_name="payments_primary_api",
                primary_tool_fn=payments_primary_api,
                fallback_chain=[
                    ("payments_replica_api", payments_replica_api),
                    ("payments_cached_snapshot", payments_cached_snapshot),
                ],
                args=common_args,
                checkpoint=checkpoint,
                started_monotonic=started,
                critical=True,
                checkpoint_ttl_seconds=300.0,
            )
        except StopRun as exc:
            return stopped(exc.reason, phase="payments_health")

        trace.append(
            {
                "step": 1,
                "phase": "payments_health",
                "source": payments_step["source"],
                "tool": payments_step["tool"],
                "attempts_used": payments_step["attempts_used"],
                "primary_attempts": payments_step["primary_attempts"],
                "fallback_attempts": payments_step["fallback_attempts"],
                "retried": payments_step["retried"],
                "fallbacks_used": payments_step["fallbacks_used"],
                "ok": payments_step["status"] == "done",
            }
        )
        history.append(
            {
                "step": 1,
                "action": "run_step_with_recovery",
                "step_id": "payments_health",
                "events": payments_step["events"],
                "result": payments_step.get("result"),
            }
        )

        try:
            demand_step = gateway.run_step_with_recovery(
                run_id=run_id,
                step_id="demand_signal",
                primary_tool_name="demand_primary_api",
                primary_tool_fn=demand_primary_api,
                fallback_chain=[("demand_cached_snapshot", demand_cached_snapshot)],
                args=common_args,
                checkpoint=checkpoint,
                started_monotonic=started,
                critical=True,
                checkpoint_ttl_seconds=900.0,
            )
        except StopRun as exc:
            return stopped(exc.reason, phase="demand_signal")

        trace.append(
            {
                "step": 2,
                "phase": "demand_signal",
                "source": demand_step["source"],
                "tool": demand_step["tool"],
                "attempts_used": demand_step["attempts_used"],
                "primary_attempts": demand_step["primary_attempts"],
                "fallback_attempts": demand_step["fallback_attempts"],
                "retried": demand_step["retried"],
                "fallbacks_used": demand_step["fallbacks_used"],
                "ok": demand_step["status"] == "done",
            }
        )
        history.append(
            {
                "step": 2,
                "action": "run_step_with_recovery",
                "step_id": "demand_signal",
                "events": demand_step["events"],
                "result": demand_step.get("result"),
            }
        )

        aggregate = {
            "report_date": req["report_date"],
            "region": req["region"],
            "payments": payments_step["result"],
            "demand": demand_step["result"],
        }
        fallback_steps = [
            step["step_id"]
            for step in (payments_step, demand_step)
            if step["source"] == "fallback"
        ]
        checkpoint_saved_steps = sorted(
            set(item["step_id"] for item in checkpoint.dump_run(run_id=run_id))
        )
        checkpoint_resumed_steps = []
        for h in history:
            for ev in (h.get("events") or []):
                if ev.get("kind") == "checkpoint_resume":
                    checkpoint_resumed_steps.append(ev.get("step_id"))

        recovery_summary = {
            "fallback_used": bool(fallback_steps),
            "fallback_steps": fallback_steps,
            "checkpoint_saved_steps": checkpoint_saved_steps,
            "checkpoint_resumed_steps": sorted(set(checkpoint_resumed_steps)),
        }

        if (time.monotonic() - started) > BUDGET.max_seconds:
            return stopped("max_seconds", phase="finalize")

        try:
            answer = compose_operations_brief(
                goal=goal,
                aggregate=aggregate,
                recovery_summary=recovery_summary,
            )
        except LLMTimeout:
            return stopped("llm_timeout", phase="finalize")
        except LLMInvalid as exc:
            return stopped(exc.args[0], phase="finalize")
        except LLMEmpty:
            return stopped("llm_empty", phase="finalize")

        trace.append(
            {
                "step": 3,
                "phase": "finalize",
                "fallback_used": recovery_summary["fallback_used"],
                "ok": True,
            }
        )
        history.append({"step": 3, "action": "compose_operations_brief"})

        return {
            "run_id": run_id,
            "status": "ok",
            "stop_reason": "success",
            "outcome": "recovered_with_fallback" if fallback_steps else "direct_success",
            "answer": answer,
            "aggregate": aggregate,
            "recovery": recovery_summary,
            "checkpoint": checkpoint.dump_run(run_id=run_id),
            "trace": trace,
            "history": history,
        }
    finally:
        gateway.close()


def main() -> None:
    result = run_fallback_recovery_agent(goal=GOAL, request=REQUEST)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
