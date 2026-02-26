from __future__ import annotations

import json
import time
from typing import Any

from gateway import Budget, StopRun, ToolGateway, args_hash, validate_action
from llm import LLMTimeout, decide_next_action
from tools import get_user_billing, get_user_profile, search_policy

GOAL = (
    "User 42 asked: Can I get a refund now? "
    "Use tools to verify profile, billing state, and policy. "
    "Return a short final answer in English with USD amount and reason."
)

BUDGET = Budget(max_steps=8, max_tool_calls=5, max_seconds=20)

TOOL_REGISTRY = {
    "get_user_profile": get_user_profile,
    "get_user_billing": get_user_billing,
    "search_policy": search_policy,
}

ALLOWED_TOOLS = {"get_user_profile", "get_user_billing", "search_policy"}


def run_react(goal: str) -> dict[str, Any]:
    started = time.monotonic()
    history: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = []

    gateway = ToolGateway(allow=ALLOWED_TOOLS, registry=TOOL_REGISTRY, budget=BUDGET)

    for step in range(1, BUDGET.max_steps + 1):
        elapsed = time.monotonic() - started
        if elapsed > BUDGET.max_seconds:
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
                "trace": trace,
                "history": history,
            }

        try:
            action = validate_action(raw_action)
        except StopRun as exc:
            return {
                "status": "stopped",
                "stop_reason": exc.reason,
                "raw_action": raw_action,
                "trace": trace,
                "history": history,
            }

        if action["kind"] == "final":
            return {
                "status": "ok",
                "stop_reason": "success",
                "answer": action["answer"],
                "trace": trace,
                "history": history,
            }

        tool_name = action["name"]
        tool_args = action["args"]

        try:
            observation = gateway.call(tool_name, tool_args)
            trace.append(
                {
                    "step": step,
                    "tool": tool_name,
                    "args_hash": args_hash(tool_args),
                    "ok": True,
                }
            )
        except StopRun as exc:
            trace.append(
                {
                    "step": step,
                    "tool": tool_name,
                    "args_hash": args_hash(tool_args),
                    "ok": False,
                    "stop_reason": exc.reason,
                }
            )
            return {
                "status": "stopped",
                "stop_reason": exc.reason,
                "trace": trace,
                "history": history,
            }

        history.append(
            {
                "step": step,
                "action": action,
                "observation": observation,
            }
        )

    return {
        "status": "stopped",
        "stop_reason": "max_steps",
        "trace": trace,
        "history": history,
    }


def main() -> None:
    result = run_react(GOAL)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
