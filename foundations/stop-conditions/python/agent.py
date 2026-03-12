from dataclasses import dataclass
from typing import Any

from llm import choose_next_action
from tools import build_summary, fetch_orders, make_initial_state

TOOLS = {
    "fetch_orders": fetch_orders,
    "build_summary": build_summary,
}


@dataclass
class StopPolicy:
    max_steps: int
    max_errors: int
    max_no_progress: int


def evaluate_stop_conditions(
    state: dict[str, Any],
    steps: int,
    errors: int,
    no_progress: int,
    policy: StopPolicy,
) -> str | None:
    if "summary" in state:
        return "goal_reached"
    if steps >= policy.max_steps:
        return "step_limit"
    if errors >= policy.max_errors:
        return "too_many_errors"
    if no_progress >= policy.max_no_progress:
        return "no_progress"
    return None


def run_agent(task: str, user_id: int, fail_fetch_times: int, policy: StopPolicy) -> dict[str, Any]:
    state = make_initial_state(user_id=user_id, fail_fetch_times=fail_fetch_times)
    history: list[dict[str, Any]] = []

    steps = 0
    errors = 0
    no_progress = 0
    stop_reason: str | None = None

    while True:
        stop_reason = evaluate_stop_conditions(
            state=state,
            steps=steps,
            errors=errors,
            no_progress=no_progress,
            policy=policy,
        )
        if stop_reason is not None:
            break

        steps += 1

        call = choose_next_action(task, state)
        action = call["action"]
        history.append({"step": steps, "action": action, "status": "requested"})

        tool = TOOLS.get(action)
        if not tool:
            errors += 1
            no_progress += 1
            state["last_error"] = f"unknown_action:{action}"
            history.append({"step": steps, "action": action, "status": "error"})
        else:
            before_keys = set(state.keys())
            result = tool(state)

            if result.get("ok"):
                after_keys = set(state.keys())
                progress = len(after_keys - before_keys) > 0
                no_progress = 0 if progress else no_progress + 1
                state.pop("last_error", None)
                history.append({"step": steps, "action": action, "status": "ok"})
            else:
                errors += 1
                no_progress += 1
                state["last_error"] = result.get("error", "unknown_error")
                history.append({"step": steps, "action": action, "status": "error"})

    return {
        "done": stop_reason == "goal_reached",
        "stop_reason": stop_reason,
        "steps": steps,
        "errors": errors,
        "no_progress": no_progress,
        "summary": state.get("summary"),
        "history": history,
    }
