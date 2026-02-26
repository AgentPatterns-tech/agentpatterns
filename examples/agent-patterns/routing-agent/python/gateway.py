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
    max_route_attempts: int = 3
    max_delegations: int = 3
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


def validate_route_action(
    action: Any, *, allowed_routes: set[str]
) -> dict[str, Any]:
    if not isinstance(action, dict):
        raise StopRun("invalid_route:not_object")

    kind = action.get("kind")
    if kind == "invalid":
        raise StopRun("invalid_route:non_json")
    if kind != "route":
        raise StopRun("invalid_route:bad_kind")

    allowed_keys = {"kind", "target", "args"}
    if set(action.keys()) - allowed_keys:
        raise StopRun("invalid_route:extra_keys")

    target = action.get("target")
    if not isinstance(target, str) or not target.strip():
        raise StopRun("invalid_route:missing_target")
    target = target.strip()
    if target not in allowed_routes:
        raise StopRun(f"invalid_route:route_not_allowed:{target}")

    args = action.get("args", {})
    if args is None:
        args = {}
    if not isinstance(args, dict):
        raise StopRun("invalid_route:bad_args")
    ticket = args.get("ticket")
    if not isinstance(ticket, str) or not ticket.strip():
        raise StopRun("invalid_route:missing_ticket")

    return {"kind": "route", "target": target, "args": args}


class RouteGateway:
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
        self.delegations = 0
        self.seen_routes: set[str] = set()

    def call(self, target: str, args: dict[str, Any]) -> dict[str, Any]:
        self.delegations += 1
        if self.delegations > self.budget.max_delegations:
            raise StopRun("max_delegations")

        if target not in self.allow:
            raise StopRun(f"route_denied:{target}")

        worker = self.registry.get(target)
        if worker is None:
            raise StopRun(f"route_missing:{target}")

        signature = f"{target}:{args_hash(args)}"
        if signature in self.seen_routes:
            raise StopRun("loop_detected")
        self.seen_routes.add(signature)

        try:
            return worker(**args)
        except TypeError as exc:
            raise StopRun(f"route_bad_args:{target}") from exc
        except Exception as exc:
            raise StopRun(f"route_error:{target}") from exc
