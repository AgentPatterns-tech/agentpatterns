from __future__ import annotations

import json
import time
from typing import Any

from gateway import Budget, RouteGateway, StopRun, args_hash, validate_route_action
from llm import LLMEmpty, LLMTimeout, compose_final_answer, decide_route
from tools import billing_specialist, sales_specialist, technical_specialist

GOAL = (
    "User Anna (user_id=42) asks: Can I get a refund for my pro_monthly subscription "
    "charged 10 days ago? Route to the correct specialist and provide a short final answer."
)

BUDGET = Budget(max_route_attempts=3, max_delegations=3, max_seconds=60)

ROUTE_REGISTRY = {
    "billing_specialist": billing_specialist,
    "technical_specialist": technical_specialist,
    "sales_specialist": sales_specialist,
}

ALLOWED_ROUTE_TARGETS_POLICY = {
    "billing_specialist",
    "technical_specialist",
    "sales_specialist",
}

ALLOWED_ROUTE_TARGETS_EXECUTION = {
    "billing_specialist",
    "technical_specialist",
    "sales_specialist",
}


def run_routing(goal: str) -> dict[str, Any]:
    started = time.monotonic()
    trace: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []

    gateway = RouteGateway(
        allow=ALLOWED_ROUTE_TARGETS_EXECUTION,
        registry=ROUTE_REGISTRY,
        budget=BUDGET,
    )

    for attempt in range(1, BUDGET.max_route_attempts + 1):
        elapsed = time.monotonic() - started
        if elapsed > BUDGET.max_seconds:
            return {
                "status": "stopped",
                "stop_reason": "max_seconds",
                "trace": trace,
                "history": history,
            }

        previous_step = history[-1] if history else None
        previous_observation = (
            previous_step.get("observation")
            if isinstance(previous_step, dict)
            else None
        )
        previous_route = previous_step.get("route") if isinstance(previous_step, dict) else None
        previous_status = (
            previous_observation.get("status")
            if isinstance(previous_observation, dict)
            else None
        )
        previous_target = (
            previous_route.get("target")
            if isinstance(previous_route, dict)
            else None
        )
        forbidden_targets = (
            [previous_target]
            if previous_status == "needs_reroute" and isinstance(previous_target, str)
            else []
        )

        try:
            raw_route = decide_route(
                goal=goal,
                history=history,
                max_route_attempts=BUDGET.max_route_attempts,
                remaining_attempts=(BUDGET.max_route_attempts - attempt + 1),
                forbidden_targets=forbidden_targets,
            )
        except LLMTimeout:
            return {
                "status": "stopped",
                "stop_reason": "llm_timeout",
                "phase": "route",
                "trace": trace,
                "history": history,
            }

        try:
            route_action = validate_route_action(
                raw_route,
                allowed_routes=ALLOWED_ROUTE_TARGETS_POLICY,
                previous_target=previous_target,
                previous_status=previous_status,
            )
        except StopRun as exc:
            return {
                "status": "stopped",
                "stop_reason": exc.reason,
                "phase": "route",
                "raw_route": raw_route,
                "trace": trace,
                "history": history,
            }

        target = route_action["target"]
        route_args = route_action["args"]

        try:
            observation = gateway.call(target, route_args)
            trace.append(
                {
                    "attempt": attempt,
                    "target": target,
                    "args_hash": args_hash(route_args),
                    "ok": True,
                }
            )
        except StopRun as exc:
            trace.append(
                {
                    "attempt": attempt,
                    "target": target,
                    "args_hash": args_hash(route_args),
                    "ok": False,
                    "stop_reason": exc.reason,
                }
            )
            return {
                "status": "stopped",
                "stop_reason": exc.reason,
                "phase": "delegate",
                "route": route_action,
                "trace": trace,
                "history": history,
            }

        history.append(
            {
                "attempt": attempt,
                "route": route_action,
                "observation": observation,
            }
        )

        observation_status = observation.get("status")
        if trace:
            trace[-1]["observation_status"] = observation_status
            if isinstance(observation, dict) and observation.get("domain"):
                trace[-1]["domain"] = observation.get("domain")
        if observation_status == "needs_reroute":
            continue
        if observation_status != "done":
            return {
                "status": "stopped",
                "stop_reason": "route_bad_observation",
                "phase": "delegate",
                "route": route_action,
                "expected_statuses": ["needs_reroute", "done"],
                "received_status": observation_status,
                "bad_observation": observation,
                "trace": trace,
                "history": history,
            }

        try:
            answer = compose_final_answer(
                goal=goal,
                selected_route=target,
                history=history,
            )
        except LLMTimeout:
            return {
                "status": "stopped",
                "stop_reason": "llm_timeout",
                "phase": "finalize",
                "route": route_action,
                "trace": trace,
                "history": history,
            }
        except LLMEmpty:
            return {
                "status": "stopped",
                "stop_reason": "llm_empty",
                "phase": "finalize",
                "route": route_action,
                "trace": trace,
                "history": history,
            }

        return {
            "status": "ok",
            "stop_reason": "success",
            "selected_route": target,
            "answer": answer,
            "trace": trace,
            "history": history,
        }

    return {
        "status": "stopped",
        "stop_reason": "max_route_attempts",
        "trace": trace,
        "history": history,
    }


def main() -> None:
    result = run_routing(GOAL)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
