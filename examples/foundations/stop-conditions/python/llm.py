from typing import Any


def choose_next_action(task: str, state: dict[str, Any]) -> dict[str, Any]:
    # Learning version: fixed policy keeps behavior easy to reason about.
    _ = task

    if "orders" not in state:
        return {"action": "fetch_orders", "parameters": {}}
    return {"action": "build_summary", "parameters": {}}
