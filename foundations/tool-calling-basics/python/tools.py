from typing import Any

USERS = {
    42: {"id": 42, "name": "Anna", "tier": "pro"},
    7: {"id": 7, "name": "Max", "tier": "free"},
}

BALANCES = {
    42: {"currency": "USD", "value": 128.40},
    7: {"currency": "USD", "value": 0.0},
}


def get_user_profile(user_id: int) -> dict[str, Any]:
    user = USERS.get(user_id)
    if not user:
        return {"error": f"user {user_id} not found"}
    return {"user": user}


def get_user_balance(user_id: int) -> dict[str, Any]:
    balance = BALANCES.get(user_id)
    if not balance:
        return {"error": f"balance for user {user_id} not found"}
    return {"balance": balance}
