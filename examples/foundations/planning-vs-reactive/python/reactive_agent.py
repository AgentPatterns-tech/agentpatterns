from typing import Any

from llm import choose_next_action
from tools import build_summary, fetch_balance, fetch_orders, fetch_profile, make_initial_state

TOOLS = {
    "fetch_profile": fetch_profile,
    "fetch_orders": fetch_orders,
    "fetch_balance": fetch_balance,
    "build_summary": build_summary,
}


def run_reactive_agent(task: str, user_id: int, max_steps: int = 8) -> dict[str, Any]:
    state = make_initial_state(user_id)
    trace: list[str] = []

    for step in range(1, max_steps + 1):
        if "summary" in state:
            return {"mode": "reactive", "done": True, "steps": step - 1, "state": state, "trace": trace}

        action = choose_next_action(task, state)
        trace.append(f"[{step}] action={action}")

        tool = TOOLS.get(action)
        if not tool:
            trace.append(f"unknown_action={action}")
            state["last_error"] = f"unknown_action:{action}"
            continue

        result = tool(state)
        trace.append(f"result={result}")

        if "error" in result:
            state["last_error"] = result["error"]
            continue

        state.update(result)
        state.pop("last_error", None)

    return {"mode": "reactive", "done": False, "steps": max_steps, "state": state, "trace": trace}
