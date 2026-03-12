from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Callable


class StopRun(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Budget:
    max_tool_calls: int = 12
    max_seconds: int = 30


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
    payload = _stable_json(args or {})
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


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
        self.started = time.monotonic()
        self.seen_signatures: dict[str, int] = {}

    def call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        elapsed = time.monotonic() - self.started
        if elapsed > self.budget.max_seconds:
            raise StopRun("max_seconds")

        self.tool_calls += 1
        if self.tool_calls > self.budget.max_tool_calls:
            raise StopRun("max_tool_calls")

        if name not in self.allow:
            raise StopRun(f"tool_denied:{name}")

        signature = f"{name}:{args_hash(args)}"
        seen = self.seen_signatures.get(signature, 0) + 1
        self.seen_signatures[signature] = seen
        if seen > 2:
            raise StopRun("loop_detected")

        tool = self.registry.get(name)
        if tool is None:
            raise StopRun(f"tool_missing:{name}")

        try:
            result = tool(**args)
        except TypeError as exc:
            raise StopRun(f"tool_bad_args:{name}") from exc
        except Exception as exc:
            raise StopRun(f"tool_error:{name}") from exc

        if isinstance(result, dict) and "error" in result:
            raise StopRun(f"tool_result_error:{name}")

        return result
