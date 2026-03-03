from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from typing import Any, Callable


class StopRun(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Budget:
    max_seconds: int = 25
    max_actions: int = 8
    action_timeout_seconds: float = 1.2
    max_recipients_per_send: int = 50000


@dataclass(frozen=True)
class Decision:
    kind: str
    reason: str
    enforced_action: dict[str, Any] | None = None


def _normalize_action(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise StopRun("invalid_action:not_object")

    action_id = raw.get("id")
    tool = raw.get("tool")
    args = raw.get("args")

    if not isinstance(action_id, str) or not action_id.strip():
        raise StopRun("invalid_action:id")
    if not isinstance(tool, str) or not tool.strip():
        raise StopRun("invalid_action:tool")
    if not isinstance(args, dict):
        raise StopRun("invalid_action:args")

    return {
        "id": action_id.strip(),
        "tool": tool.strip(),
        "args": dict(args),
    }


def validate_plan(raw_actions: Any, *, max_actions: int) -> list[dict[str, Any]]:
    if not isinstance(raw_actions, list) or not raw_actions:
        raise StopRun("invalid_plan:actions")
    if len(raw_actions) > max_actions:
        raise StopRun("invalid_plan:too_many_actions")
    return [_normalize_action(item) for item in raw_actions]


def validate_tool_observation(raw: Any, *, tool_name: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise StopRun(f"tool_invalid_output:{tool_name}")
    if raw.get("status") != "ok":
        raise StopRun(f"tool_status_not_ok:{tool_name}")
    data = raw.get("data")
    if not isinstance(data, dict):
        raise StopRun(f"tool_invalid_output:{tool_name}")
    return data


class PolicyGateway:
    def __init__(
        self,
        *,
        allowed_tools_policy: set[str],
        allowed_tools_execution: set[str],
        budget: Budget,
    ):
        self.allowed_tools_policy = set(allowed_tools_policy)
        self.allowed_tools_execution = set(allowed_tools_execution)
        self.budget = budget
        self.allowed_templates = {"incident_p1_v2", "incident_p2_v1"}
        self._pool = ThreadPoolExecutor(max_workers=4)

    def close(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)

    def evaluate(self, *, action: dict[str, Any], state: dict[str, Any]) -> Decision:
        del state
        normalized = _normalize_action(action)
        tool = normalized["tool"]
        args = dict(normalized["args"])

        if tool not in self.allowed_tools_policy:
            return Decision(kind="deny", reason="tool_denied_policy")
        if tool == "export_customer_data":
            return Decision(kind="deny", reason="pii_export_blocked")
        if tool not in self.allowed_tools_execution:
            return Decision(kind="deny", reason="tool_denied_execution")

        if tool != "send_status_update":
            return Decision(kind="allow", reason="policy_pass")

        rewrite_reasons: list[str] = []
        rewritten = dict(args)

        if rewritten.get("template_id") not in self.allowed_templates:
            rewritten["template_id"] = "incident_p1_v2"
            rewrite_reasons.append("template_allowlist")

        raw_recipients = rewritten.get("max_recipients", self.budget.max_recipients_per_send)
        try:
            recipients = int(raw_recipients)
        except (TypeError, ValueError):
            recipients = self.budget.max_recipients_per_send
        if recipients > self.budget.max_recipients_per_send:
            recipients = self.budget.max_recipients_per_send
            rewrite_reasons.append("recipient_cap")
        rewritten["max_recipients"] = recipients

        if "free_text" in rewritten:
            rewritten.pop("free_text", None)
            rewrite_reasons.append("free_text_removed")

        if (
            rewritten.get("channel") == "external_email"
            and rewritten.get("audience_segment") == "all_customers"
        ):
            rewritten["channel"] = "status_page"
            rewritten["audience_segment"] = "enterprise_active"
            enforced = {
                "id": normalized["id"],
                "tool": normalized["tool"],
                "args": rewritten,
            }
            return Decision(
                kind="escalate",
                reason="mass_external_broadcast",
                enforced_action=enforced,
            )

        if not rewrite_reasons:
            return Decision(kind="allow", reason="policy_pass")

        enforced = {
            "id": normalized["id"],
            "tool": normalized["tool"],
            "args": rewritten,
        }
        return Decision(
            kind="rewrite",
            reason=f"policy_rewrite:{','.join(rewrite_reasons)}",
            enforced_action=enforced,
        )

    def dispatch(
        self,
        *,
        tool_name: str,
        tool_fn: Callable[..., dict[str, Any]],
        args: dict[str, Any],
    ) -> dict[str, Any]:
        future = self._pool.submit(tool_fn, **args)
        try:
            raw = future.result(timeout=self.budget.action_timeout_seconds)
        except FuturesTimeoutError as exc:
            raise StopRun(f"tool_timeout:{tool_name}") from exc
        except Exception as exc:  # noqa: BLE001
            raise StopRun(f"tool_error:{tool_name}:{type(exc).__name__}") from exc

        return validate_tool_observation(raw, tool_name=tool_name)
