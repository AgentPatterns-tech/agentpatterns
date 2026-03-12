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
    max_tool_calls: int = 5
    max_seconds: int = 30


TOOL_ARG_TYPES: dict[str, dict[str, str]] = {
    "get_refund_context": {"user_id": "int"},
    "issue_refund": {"user_id": "int", "amount_usd": "number", "reason": "str?"},
    "send_refund_email": {"user_id": "int", "amount_usd": "number", "message": "str"},
}


def _stable_json(value: Any) -> str:
    if value is None or isinstance(value, (bool, int, float, str)):
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    if isinstance(value, list):
        return "[" + ",".join(_stable_json(v) for v in value) + "]"
    if isinstance(value, dict):
        parts = []
        for key in sorted(value):
            parts.append(json.dumps(str(key), ensure_ascii=True) + ":" + _stable_json(value[key]))
        return "{" + ",".join(parts) + "}"
    return json.dumps(str(value), ensure_ascii=True)


def _normalize_for_hash(value: Any) -> Any:
    if isinstance(value, str):
        return " ".join(value.strip().split())
    if isinstance(value, list):
        return [_normalize_for_hash(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalize_for_hash(value[key]) for key in sorted(value)}
    return value


def args_hash(args: dict[str, Any]) -> str:
    normalized = _normalize_for_hash(args or {})
    raw = _stable_json(normalized)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_tool_args(name: str, args: dict[str, Any]) -> dict[str, Any]:
    spec = TOOL_ARG_TYPES.get(name)
    if spec is None:
        raise StopRun(f"invalid_action:unknown_tool:{name}")

    extra = set(args.keys()) - set(spec.keys())
    if extra:
        raise StopRun(f"invalid_action:extra_tool_args:{name}")

    normalized: dict[str, Any] = {}
    for arg_name, expected in spec.items():
        is_optional = expected.endswith("?")
        expected_base = expected[:-1] if is_optional else expected

        if arg_name not in args:
            if is_optional:
                continue
            raise StopRun(f"invalid_action:missing_required_arg:{name}:{arg_name}")
        value = args[arg_name]

        if expected_base == "int":
            if not isinstance(value, int) or isinstance(value, bool):
                raise StopRun(f"invalid_action:bad_arg_type:{name}:{arg_name}")
            normalized[arg_name] = value
            continue

        if expected_base == "number":
            if not _is_number(value):
                raise StopRun(f"invalid_action:bad_arg_type:{name}:{arg_name}")
            normalized[arg_name] = float(value)
            continue

        if expected_base == "str":
            if not isinstance(value, str) or not value.strip():
                raise StopRun(f"invalid_action:bad_arg_type:{name}:{arg_name}")
            normalized[arg_name] = value.strip()
            continue

        raise StopRun(f"invalid_action:unknown_arg_spec:{name}:{arg_name}")

    return normalized


def validate_worker_action(action: Any) -> dict[str, Any]:
    if not isinstance(action, dict):
        raise StopRun("invalid_action:not_object")

    kind = action.get("kind")
    if kind == "invalid":
        raise StopRun("invalid_action:non_json")

    if kind == "final":
        allowed_keys = {"kind", "answer"}
        if set(action.keys()) - allowed_keys:
            raise StopRun("invalid_action:extra_keys_final")
        answer = action.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise StopRun("invalid_action:bad_final_answer")
        return {"kind": "final", "answer": answer.strip()}

    if kind == "tool":
        allowed_keys = {"kind", "name", "args"}
        if set(action.keys()) - allowed_keys:
            raise StopRun("invalid_action:extra_keys_tool")

        name = action.get("name")
        if not isinstance(name, str) or not name.strip():
            raise StopRun("invalid_action:bad_tool_name")

        args = action.get("args", {})
        if args is None:
            args = {}
        if not isinstance(args, dict):
            raise StopRun("invalid_action:bad_tool_args")

        normalized_args = _validate_tool_args(name.strip(), args)
        return {"kind": "tool", "name": name.strip(), "args": normalized_args}

    raise StopRun("invalid_action:bad_kind")


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
        self.seen_call_counts: dict[str, int] = {}
        self.per_tool_counts: dict[str, int] = {}
        self.read_only_repeat_limit: dict[str, int] = {
            "get_refund_context": 2,
        }
        self.per_tool_limit: dict[str, int] = {
            "get_refund_context": 3,
            "issue_refund": 2,
            "send_refund_email": 2,
        }

    def call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        self.tool_calls += 1
        if self.tool_calls > self.budget.max_tool_calls:
            raise StopRun("max_tool_calls")

        if name not in self.allow:
            raise StopRun(f"tool_denied:{name}")

        fn = self.registry.get(name)
        if fn is None:
            raise StopRun(f"tool_missing:{name}")

        count_for_tool = self.per_tool_counts.get(name, 0) + 1
        if count_for_tool > self.per_tool_limit.get(name, 2):
            raise StopRun("loop_detected:per_tool_limit")
        self.per_tool_counts[name] = count_for_tool

        signature = f"{name}:{args_hash(args)}"
        seen = self.seen_call_counts.get(signature, 0) + 1
        allowed_repeats = self.read_only_repeat_limit.get(name, 1)
        if seen > allowed_repeats:
            raise StopRun("loop_detected:signature_repeat")
        self.seen_call_counts[signature] = seen

        try:
            out = fn(**args)
        except TypeError as exc:
            raise StopRun(f"tool_bad_args:{name}") from exc
        except Exception as exc:
            raise StopRun(f"tool_error:{name}") from exc

        if not isinstance(out, dict):
            raise StopRun(f"tool_bad_result:{name}")
        return out
