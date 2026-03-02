from typing import Any


def make_initial_state(user_id: int) -> dict[str, Any]:
    # Deterministic flake config for teaching: orders fails once, then succeeds.
    return {
        "user_id": user_id,
        "_flaky": {
            "orders_failures_left": 1,
            "balance_failures_left": 0,
        },
    }


def fetch_profile(state: dict[str, Any]) -> dict[str, Any]:
    user_id = state["user_id"]
    return {
        "profile": {
            "user_id": user_id,
            "name": "Anna",
            "tier": "pro",
        }
    }


def fetch_orders(state: dict[str, Any]) -> dict[str, Any]:
    flaky = state["_flaky"]
    if flaky["orders_failures_left"] > 0:
        flaky["orders_failures_left"] -= 1
        return {"error": "orders_api_timeout"}

    return {
        "orders": [
            {"id": "ord-1001", "total": 49.9, "status": "paid"},
            {"id": "ord-1002", "total": 19.0, "status": "shipped"},
        ]
    }


def fetch_balance(state: dict[str, Any]) -> dict[str, Any]:
    flaky = state["_flaky"]
    if flaky["balance_failures_left"] > 0:
        flaky["balance_failures_left"] -= 1
        return {"error": "billing_api_unavailable"}

    return {"balance": {"currency": "USD", "value": 128.4}}


def build_summary(state: dict[str, Any]) -> dict[str, Any]:
    profile = state.get("profile")
    orders = state.get("orders")
    balance = state.get("balance")

    if not profile or not orders or not balance:
        return {"error": "not_enough_data_for_summary"}

    text = (
        f"User {profile['name']} ({profile['tier']}) has "
        f"{len(orders)} recent orders and balance {balance['value']} {balance['currency']}."
    )
    return {"summary": text}
