from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable


class StopRun(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Budget:
    max_steps: int = 8
    max_tool_calls: int = 6
    max_seconds: int = 20


def _stable_json(value: Any) -> str:
    if value is None or isinstance(value, (bool, int, float, str)):
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    if isinstance(value, list):
        return "[" + ",".join(_stable_json(item) for item in value) + "]"
    if isinstance(value, dict):
        parts = []
        for key in sorted(value):
            parts.append(
                json.dumps(str(key), ensure_ascii=True) + ":" + _stable_json(value[key])
            )
        return "{" + ",".join(parts) + "}"
    return json.dumps(str(value), ensure_ascii=True)


def args_hash(args: dict[str, Any]) -> str:
    raw = _stable_json(args or {})
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def validate_action(action: Any) -> dict[str, Any]:
    if not isinstance(action, dict):
        raise StopRun("invalid_action:not_object")

    kind = action.get("kind")
    if kind == "invalid":
        raise StopRun("invalid_action:bad_json")
    if kind not in {"tool", "final"}:
        raise StopRun("invalid_action:bad_kind")

    if kind == "final":
        allowed = {"kind", "answer"}
        extra = set(action.keys()) - allowed
        if extra:
            raise StopRun("invalid_action:extra_keys")
        answer = action.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise StopRun("invalid_action:missing_answer")
        return {"kind": "final", "answer": answer.strip()}

    allowed = {"kind", "name", "args"}
    extra = set(action.keys()) - allowed
    if extra:
        raise StopRun("invalid_action:extra_keys")

    name = action.get("name")
    if not isinstance(name, str) or not name:
        raise StopRun("invalid_action:missing_tool_name")

    args = action.get("args", {})
    if args is None:
        args = {}
    if not isinstance(args, dict):
        raise StopRun("invalid_action:bad_args")

    return {"kind": "tool", "name": name, "args": args}


class ToolGateway:
    def __init__(
        self,
        *,
        allow: set[str],
        registry: dict[str, Callable[..., dict[str, Any]]],
        budget: Budget,
    ):
        self.allow = set(allow)
        self.registry = registry
        self.budget = budget
        self.tool_calls = 0
        self.seen_calls: set[str] = set()

    def call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        self.tool_calls += 1
        if self.tool_calls > self.budget.max_tool_calls:
            raise StopRun("max_tool_calls")

        if name not in self.allow:
            raise StopRun(f"tool_denied:{name}")

        tool = self.registry.get(name)
        if tool is None:
            raise StopRun(f"tool_missing:{name}")

        signature = f"{name}:{args_hash(args)}"
        if signature in self.seen_calls:
            raise StopRun("loop_detected")
        self.seen_calls.add(signature)

        try:
            return tool(**args)
        except TypeError as exc:
            raise StopRun(f"tool_bad_args:{name}") from exc
        except Exception as exc:
            raise StopRun(f"tool_error:{name}") from exc
