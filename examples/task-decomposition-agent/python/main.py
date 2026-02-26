from __future__ import annotations

import json
import time
from typing import Any

from gateway import Budget, StopRun, ToolGateway, args_hash, validate_plan_action
from llm import LLMEmpty, LLMTimeout, compose_final_answer, create_plan
from tools import (
    calculate_monthly_kpis,
    detect_risk_signals,
    fetch_refund_data,
    fetch_sales_data,
    get_manager_profile,
)

GOAL = (
    "Prepare an April 2026 monthly sales summary for manager_id=42 in USD. "
    "Use step-by-step decomposition. Include gross sales, refunds, net sales, refund rate, and one risk note."
)

# max_execute_steps here limits plan length (number of planned steps), not runtime loop iterations.
BUDGET = Budget(max_plan_steps=6, max_execute_steps=8, max_tool_calls=8, max_seconds=60)

TOOL_REGISTRY = {
    "get_manager_profile": get_manager_profile,
    "fetch_sales_data": fetch_sales_data,
    "fetch_refund_data": fetch_refund_data,
    "calculate_monthly_kpis": calculate_monthly_kpis,
    "detect_risk_signals": detect_risk_signals,
}

ALLOWED_TOOLS = {
    "get_manager_profile",
    "fetch_sales_data",
    "fetch_refund_data",
    "calculate_monthly_kpis",
    "detect_risk_signals",
}


def run_task_decomposition(goal: str) -> dict[str, Any]:
    started = time.monotonic()
    trace: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []

    gateway = ToolGateway(allow=ALLOWED_TOOLS, registry=TOOL_REGISTRY, budget=BUDGET)

    try:
        raw_plan = create_plan(goal=goal, max_plan_steps=BUDGET.max_plan_steps)
    except LLMTimeout:
        return {
            "status": "stopped",
            "stop_reason": "llm_timeout",
            "llm_phase": "plan",
            "trace": trace,
            "history": history,
        }

    try:
        steps = validate_plan_action(
            raw_plan,
            max_plan_steps=BUDGET.max_plan_steps,
            allowed_tools=ALLOWED_TOOLS,
        )
    except StopRun as exc:
        return {
            "status": "stopped",
            "stop_reason": exc.reason,
            "raw_plan": raw_plan,
            "trace": trace,
            "history": history,
        }

    if len(steps) > BUDGET.max_execute_steps:
        return {
            "status": "stopped",
            "stop_reason": "max_execute_steps",
            "plan": steps,
            "trace": trace,
            "history": history,
        }

    for step_no, step in enumerate(steps, start=1):
        elapsed = time.monotonic() - started
        if elapsed > BUDGET.max_seconds:
            return {
                "status": "stopped",
                "stop_reason": "max_seconds",
                "plan": steps,
                "trace": trace,
                "history": history,
            }

        tool_name = step["tool"]
        tool_args = step["args"]

        try:
            observation = gateway.call(tool_name, tool_args)
            trace.append(
                {
                    "step_no": step_no,
                    "step_id": step["id"],
                    "tool": tool_name,
                    "args_hash": args_hash(tool_args),
                    "ok": True,
                }
            )
        except StopRun as exc:
            trace.append(
                {
                    "step_no": step_no,
                    "step_id": step["id"],
                    "tool": tool_name,
                    "args_hash": args_hash(tool_args),
                    "ok": False,
                    "stop_reason": exc.reason,
                }
            )
            return {
                "status": "stopped",
                "stop_reason": exc.reason,
                "plan": steps,
                "trace": trace,
                "history": history,
            }

        history.append(
            {
                "step_no": step_no,
                "plan_step": step,
                "observation": observation,
            }
        )

    try:
        answer = compose_final_answer(goal=goal, history=history)
    except LLMTimeout:
        return {
            "status": "stopped",
            "stop_reason": "llm_timeout",
            "llm_phase": "finalize",
            "plan": steps,
            "trace": trace,
            "history": history,
        }
    except LLMEmpty:
        return {
            "status": "stopped",
            "stop_reason": "llm_empty",
            "llm_phase": "finalize",
            "plan": steps,
            "trace": trace,
            "history": history,
        }

    return {
        "status": "ok",
        "stop_reason": "success",
        "answer": answer,
        "plan": steps,
        "trace": trace,
        "history": history,
    }


def main() -> None:
    result = run_task_decomposition(GOAL)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
