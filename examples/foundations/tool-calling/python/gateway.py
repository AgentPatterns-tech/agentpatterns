import json
from typing import Any

from tools import customer_db, email_service

TOOL_REGISTRY = {
    "customer_db": customer_db,
    "email_service": email_service,
}

# Level 1: which tools are visible to the agent
ALLOWED_TOOLS = {"customer_db"}

# Level 2: which actions are allowed inside each tool
ALLOWED_ACTIONS = {
    "customer_db": {"read"},  # update_tier is blocked
}


def execute_tool_call(tool_name: str, arguments_json: str) -> dict[str, Any]:
    if tool_name not in ALLOWED_TOOLS:
        return {"ok": False, "error": f"tool '{tool_name}' is not allowed"}

    tool = TOOL_REGISTRY.get(tool_name)
    if tool is None:
        return {"ok": False, "error": f"tool '{tool_name}' not found"}

    try:
        args = json.loads(arguments_json or "{}")
    except json.JSONDecodeError:
        return {"ok": False, "error": "invalid JSON arguments"}

    if tool_name == "customer_db":
        action = args.get("action")
        if action not in ALLOWED_ACTIONS["customer_db"]:
            return {
                "ok": False,
                "error": f"action '{action}' is not allowed for tool '{tool_name}'",
            }

    try:
        result = tool(**args)
    except TypeError as exc:
        return {"ok": False, "error": f"invalid arguments: {exc}"}

    return {"ok": True, "tool": tool_name, "result": result}
