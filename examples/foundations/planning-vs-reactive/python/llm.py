from typing import Any


DEFAULT_PLAN = ["fetch_profile", "fetch_orders", "fetch_balance", "build_summary"]


def create_plan(task: str) -> list[str]:
    # Learning version: fixed starter plan keeps behavior easy to reason about.
    _ = task
    return DEFAULT_PLAN.copy()


def replan(task: str, state: dict[str, Any], failed_step: str, error: str) -> list[str]:
    # Learning version: rebuild plan from missing data in state.
    _ = task, failed_step, error
    remaining: list[str] = []

    if "profile" not in state:
        remaining.append("fetch_profile")
    if "orders" not in state:
        remaining.append("fetch_orders")
    if "balance" not in state:
        remaining.append("fetch_balance")
    if "summary" not in state:
        remaining.append("build_summary")

    return remaining


def choose_next_action(task: str, state: dict[str, Any]) -> str:
    # Learning version: one-step-at-a-time policy driven by current state.
    _ = task

    if "profile" not in state:
        return "fetch_profile"

    # If orders just failed, fetch other missing data first.
    if state.get("last_error") == "orders_api_timeout" and "balance" not in state:
        return "fetch_balance"

    if "orders" not in state:
        return "fetch_orders"
    if "balance" not in state:
        return "fetch_balance"
    return "build_summary"
