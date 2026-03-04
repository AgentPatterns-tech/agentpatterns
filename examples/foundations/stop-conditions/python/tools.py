from typing import Any


def make_initial_state(user_id: int, fail_fetch_times: int) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "fetch_calls": 0,
        "fail_fetch_times": fail_fetch_times,
    }


def fetch_orders(state: dict[str, Any]) -> dict[str, Any]:
    state["fetch_calls"] += 1

    if state["fetch_calls"] <= state["fail_fetch_times"]:
        return {"ok": False, "error": "orders_api_timeout"}

    orders = [
        {"id": "ord-2001", "total": 49.9, "status": "paid"},
        {"id": "ord-2002", "total": 19.0, "status": "shipped"},
    ]
    state["orders"] = orders
    return {"ok": True, "orders": orders}


def build_summary(state: dict[str, Any]) -> dict[str, Any]:
    orders = state.get("orders")
    if not orders:
        return {"ok": False, "error": "missing_orders"}

    summary = f"Prepared report for {len(orders)} recent orders."
    state["summary"] = summary
    return {"ok": True, "summary": summary}
