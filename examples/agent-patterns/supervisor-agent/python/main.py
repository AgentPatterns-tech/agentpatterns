from __future__ import annotations

import json
import time
from typing import Any

from gateway import Budget, StopRun, ToolGateway, args_hash, validate_worker_action
from llm import LLMEmpty, LLMTimeout, compose_final_answer, decide_next_action
from supervisor import Decision, Policy, RuntimeState, review_action, simulate_human_approval
from tools import get_refund_context, issue_refund, send_refund_email

GOAL = (
    "User Anna (user_id=42) requests a refund for a recent annual plan charge of 1200 USD. "
    "Apply supervisor policy before any refund execution and provide a short final response."
)

BUDGET = Budget(max_steps=8, max_tool_calls=5, max_seconds=30)
POLICY = Policy(
    auto_refund_limit_usd=1000.0,
    max_refund_per_run_usd=2000.0,
)

TOOL_REGISTRY = {
    "get_refund_context": get_refund_context,
    "issue_refund": issue_refund,
    "send_refund_email": send_refund_email,
}

ALLOWED_TOOLS = {"get_refund_context", "issue_refund", "send_refund_email"}


def _decision_payload(decision: Decision) -> dict[str, Any]:
    payload = {
        "decision": decision.kind,
        "reason": decision.reason,
    }
    if decision.revised_action:
        payload["revised_action"] = decision.revised_action
    return payload


def run_supervised_flow(goal: str) -> dict[str, Any]:
    started = time.monotonic()
    history: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = []

    state = RuntimeState()
    gateway = ToolGateway(allow=ALLOWED_TOOLS, registry=TOOL_REGISTRY, budget=BUDGET)

    for step in range(1, BUDGET.max_steps + 1):
        if (time.monotonic() - started) > BUDGET.max_seconds:
            return {
                "status": "stopped",
                "stop_reason": "max_seconds",
                "trace": trace,
                "history": history,
            }

        try:
            raw_action = decide_next_action(goal=goal, history=history)
        except LLMTimeout:
            return {
                "status": "stopped",
                "stop_reason": "llm_timeout",
                "phase": "worker",
                "trace": trace,
                "history": history,
            }

        try:
            action = validate_worker_action(raw_action)
        except StopRun as exc:
            return {
                "status": "stopped",
                "stop_reason": exc.reason,
                "phase": "worker",
                "raw_action": raw_action,
                "trace": trace,
                "history": history,
            }

        decision = review_action(action=action, state=state, policy=POLICY)
        supervisor_info = _decision_payload(decision)

        action_to_execute = action
        human_info: dict[str, Any] | None = None
        executed_from = "original"

        if decision.kind == "block":
            trace_row = {
                "step": step,
                "tool": action.get("name", "final"),
                "supervisor_decision": "block",
                "executed_from": executed_from,
                "stop_reason": f"supervisor_block:{decision.reason}",
                "ok": False,
            }
            if action.get("kind") == "tool":
                trace_row["args_hash"] = args_hash(action.get("args", {}))
            trace.append(trace_row)
            return {
                "status": "stopped",
                "stop_reason": f"supervisor_block:{decision.reason}",
                "phase": "supervisor",
                "action": action,
                "trace": trace,
                "history": history,
            }

        if decision.kind == "revise" and decision.revised_action:
            action_to_execute = decision.revised_action
            executed_from = "supervisor_revised"

        if decision.kind == "escalate":
            human = simulate_human_approval(action)
            human_info = human
            if not human.get("approved"):
                trace.append(
                    {
                        "step": step,
                        "tool": action["name"],
                        "args_hash": args_hash(action["args"]),
                        "supervisor_decision": "escalate",
                        "executed_from": executed_from,
                        "human_approved": False,
                        "stop_reason": "human_rejected",
                        "ok": False,
                    }
                )
                return {
                    "status": "stopped",
                    "stop_reason": "human_rejected",
                    "phase": "human_approval",
                    "action": action,
                    "trace": trace,
                    "history": history,
                }
            revised = human.get("revised_action")
            if isinstance(revised, dict):
                action_to_execute = revised
                executed_from = "human_revised"

        if action_to_execute["kind"] == "final":
            trace.append(
                {
                    "step": step,
                    "tool": "final",
                    "supervisor_decision": decision.kind,
                    "executed_from": executed_from,
                    "ok": True,
                }
            )
            history.append(
                {
                    "step": step,
                    "action": action,
                    "supervisor": supervisor_info,
                    "executed_action": action_to_execute,
                    "executed_from": executed_from,
                    "observation": {"status": "final"},
                }
            )
            return {
                "status": "ok",
                "stop_reason": "success",
                "answer": action_to_execute["answer"],
                "trace": trace,
                "history": history,
            }

        tool_name = action_to_execute["name"]
        tool_args = action_to_execute["args"]

        try:
            observation = gateway.call(tool_name, tool_args)
            trace_row = {
                "step": step,
                "tool": tool_name,
                "args_hash": args_hash(tool_args),
                "supervisor_decision": decision.kind,
                "executed_from": executed_from,
                "ok": True,
            }
            if human_info is not None:
                trace_row["human_approved"] = bool(human_info.get("approved"))
            trace.append(trace_row)
        except StopRun as exc:
            trace_row = {
                "step": step,
                "tool": tool_name,
                "args_hash": args_hash(tool_args),
                "supervisor_decision": decision.kind,
                "executed_from": executed_from,
                "ok": False,
                "stop_reason": exc.reason,
            }
            if human_info is not None:
                trace_row["human_approved"] = bool(human_info.get("approved"))
            trace.append(trace_row)
            return {
                "status": "stopped",
                "stop_reason": exc.reason,
                "phase": "execution",
                "action": action_to_execute,
                "trace": trace,
                "history": history,
            }

        if tool_name == "get_refund_context" and "error" not in observation:
            state.has_context = True

        if tool_name == "issue_refund" and observation.get("status") == "ok":
            amount = float(observation.get("refund", {}).get("amount_usd", 0.0))
            state.executed_refund_total_usd += amount
            state.refund_executed = True

        history_entry = {
            "step": step,
            "action": action,
            "supervisor": supervisor_info,
            "executed_action": action_to_execute,
            "executed_from": executed_from,
            "observation": observation,
        }
        if human_info is not None:
            history_entry["human_approval"] = human_info
        history.append(history_entry)

    try:
        answer = compose_final_answer(goal=goal, history=history)
    except LLMTimeout:
        return {
            "status": "stopped",
            "stop_reason": "llm_timeout",
            "phase": "finalize",
            "trace": trace,
            "history": history,
        }
    except LLMEmpty:
        return {
            "status": "stopped",
            "stop_reason": "llm_empty",
            "phase": "finalize",
            "trace": trace,
            "history": history,
        }

    return {
        "status": "ok",
        "stop_reason": "success",
        "answer": answer,
        "trace": trace,
        "history": history,
    }


def main() -> None:
    result = run_supervised_flow(GOAL)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
