from typing import Any

USERS: dict[int, dict[str, Any]] = {
    42: {"id": 42, "name": "Anna", "status": "active"},
}


def read_user(user_id: int) -> dict[str, Any]:
    user = USERS.get(user_id)
    if not user:
        return {"ok": False, "error": f"user {user_id} not found"}
    return {"ok": True, "user": dict(user)}


def update_user_status(user_id: int, status: str) -> dict[str, Any]:
    user = USERS.get(user_id)
    if not user:
        return {"ok": False, "error": f"user {user_id} not found"}
    user["status"] = status
    return {"ok": True, "user": dict(user)}


def send_webhook(event: str) -> dict[str, Any]:
    return {"ok": True, "sent": event}


def delete_user(user_id: int) -> dict[str, Any]:
    if user_id not in USERS:
        return {"ok": False, "error": f"user {user_id} not found"}
    del USERS[user_id]
    return {"ok": True, "deleted": user_id}
