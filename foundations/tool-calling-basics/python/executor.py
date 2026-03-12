import json
from typing import Any

from tools import get_user_balance, get_user_profile

TOOL_REGISTRY = {
    "get_user_profile": get_user_profile,
    "get_user_balance": get_user_balance,
}

ALLOWED_TOOLS = {"get_user_profile", "get_user_balance"}


def execute_tool_call(tool_name: str, arguments_json: str) -> dict[str, Any]:
    if tool_name not in ALLOWED_TOOLS:
        return {"error": f"tool '{tool_name}' is not allowed"}

    tool = TOOL_REGISTRY.get(tool_name)
    if tool is None:
        return {"error": f"tool '{tool_name}' not found"}

    try:
        args = json.loads(arguments_json or "{}")
    except json.JSONDecodeError:
        return {"error": "invalid JSON arguments"}

    try:
        result = tool(**args)
    except TypeError as exc:
        return {"error": f"invalid arguments: {exc}"}

    return {"tool": tool_name, "result": result}
