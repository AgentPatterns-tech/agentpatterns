from typing import Any

from llm import create_plan, replan
from tools import build_summary, fetch_balance, fetch_orders, fetch_profile, make_initial_state

TOOLS = {
    "fetch_profile": fetch_profile,
    "fetch_orders": fetch_orders,
    "fetch_balance": fetch_balance,
    "build_summary": build_summary,
}


def run_planning_agent(task: str, user_id: int, max_steps: int = 8) -> dict[str, Any]:
    state = make_initial_state(user_id)
    plan = create_plan(task)
    trace: list[str] = [f"Initial plan: {plan}"]

    step = 0
    while plan and step < max_steps:
        action = plan.pop(0)
        step += 1
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
            trace.append("planning: replan after failure")
            plan = replan(task, state, failed_step=action, error=result["error"])
            trace.append(f"new_plan={plan}")
            continue

        state.update(result)
        state.pop("last_error", None)

        if "summary" in state:
            return {"mode": "planning", "done": True, "steps": step, "state": state, "trace": trace}

    return {"mode": "planning", "done": False, "steps": step, "state": state, "trace": trace}
