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
    max_plan_steps: int = 6
    max_execute_steps: int = 8
    max_tool_calls: int = 8
    max_seconds: int = 60


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


def validate_plan_action(
    action: Any, *, max_plan_steps: int, allowed_tools: set[str]
) -> list[dict[str, Any]]:
    if not isinstance(action, dict):
        raise StopRun("invalid_plan:not_object")

    kind = action.get("kind")
    if kind == "invalid":
        raise StopRun("invalid_plan:non_json")
    if kind != "plan":
        raise StopRun("invalid_plan:bad_kind")

    allowed_top_keys = {"kind", "steps"}
    if set(action.keys()) - allowed_top_keys:
        raise StopRun("invalid_plan:extra_keys")

    steps = action.get("steps")
    if not isinstance(steps, list) or not steps:
        raise StopRun("invalid_plan:missing_steps")
    if len(steps) < 3:
        raise StopRun("invalid_plan:min_steps")
    if len(steps) > max_plan_steps:
        raise StopRun("invalid_plan:max_steps")

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            raise StopRun(f"invalid_plan:step_{index}_not_object")

        allowed_step_keys = {"id", "title", "tool", "args"}
        if set(step.keys()) - allowed_step_keys:
            raise StopRun(f"invalid_plan:step_{index}_extra_keys")

        step_id = step.get("id")
        if not isinstance(step_id, str) or not step_id.strip():
            raise StopRun(f"invalid_plan:step_{index}_missing_id")
        if step_id in seen_ids:
            raise StopRun("invalid_plan:duplicate_step_id")
        seen_ids.add(step_id)

        title = step.get("title")
        if not isinstance(title, str) or not title.strip():
            raise StopRun(f"invalid_plan:step_{index}_missing_title")

        tool = step.get("tool")
        if not isinstance(tool, str) or not tool.strip():
            raise StopRun(f"invalid_plan:step_{index}_missing_tool")
        tool = tool.strip()
        if tool not in allowed_tools:
            raise StopRun(f"invalid_plan:tool_not_allowed:{tool}")

        args = step.get("args", {})
        if args is None:
            args = {}
        if not isinstance(args, dict):
            raise StopRun(f"invalid_plan:step_{index}_bad_args")

        normalized.append(
            {
                "id": step_id.strip(),
                "title": title.strip(),
                "tool": tool,
                "args": args,
            }
        )

    return normalized


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
