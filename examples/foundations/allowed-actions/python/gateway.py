from typing import Any

from tools import delete_user, read_user, send_webhook, update_user_status

TOOL_REGISTRY = {
    "read_user": read_user,
    "update_user_status": update_user_status,
    "send_webhook": send_webhook,
    "delete_user": delete_user,
}

TOOL_LEVEL = {
    "read_user": "read",
    "update_user_status": "write",
    "send_webhook": "execute",
    "delete_user": "delete",
}

# Least-privilege policy for this agent.
AGENT_ALLOWED_LEVELS = {"read", "write"}


def execute_action(call: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
    action = str(call.get("action") or "")
    params = call.get("parameters") or {}
    level = TOOL_LEVEL.get(action, "unknown")

    history.append({"action": action, "level": level, "status": "requested"})

    tool = TOOL_REGISTRY.get(action)
    if tool is None:
        history.append({"action": action, "level": level, "status": "blocked"})
        return {
            "ok": False,
            "action": action,
            "error": f"action '{action}' is not found",
            "history": list(history),
        }

    if level not in AGENT_ALLOWED_LEVELS:
        history.append({"action": action, "level": level, "status": "blocked"})
        return {
            "ok": False,
            "action": action,
            "error": f"action '{action}' is blocked by policy (level={level})",
            "history": list(history),
        }

    result = tool(**params)
    history.append({"action": action, "level": level, "status": "allowed"})

    return {
        "ok": True,
        "action": action,
        "result": result,
        "history": list(history),
    }
