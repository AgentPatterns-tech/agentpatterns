from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from typing import Any, Callable

from checkpoint_store import CheckpointStore


class StopRun(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Budget:
    max_seconds: int = 120
    step_timeout_seconds: float = 1.0
    max_retries: int = 1
    max_fallbacks: int = 2
    checkpoint_ttl_seconds: float = 900.0


def classify_exception(exc: Exception) -> str:
    if isinstance(exc, TimeoutError):
        msg = str(exc)[:80]
        return f"timeout:{msg}" if msg else "timeout"
    if isinstance(exc, ValueError):
        return "invalid_output"
    if isinstance(exc, RuntimeError):
        if "unavailable" in str(exc).lower():
            return "tool_unavailable"
        return "runtime_error"
    return "non_retriable"


def validate_tool_observation(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("tool_observation_not_object")
    if raw.get("status") != "ok":
        raise ValueError("tool_observation_status_not_ok")
    data = raw.get("data")
    if not isinstance(data, dict):
        raise ValueError("tool_observation_data_not_object")
    return data


class RecoveryGateway:
    def __init__(
        self,
        *,
        allowed_steps_policy: set[str],
        allowed_tools_policy: set[str],
        allowed_tools_execution: set[str],
        budget: Budget,
    ):
        self.allowed_steps_policy = set(allowed_steps_policy)
        self.allowed_tools_policy = set(allowed_tools_policy)
        self.allowed_tools_execution = set(allowed_tools_execution)
        self.budget = budget
        self._pool = ThreadPoolExecutor(max_workers=4)

    def close(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)

    def _ensure_run_budget(self, *, started_monotonic: float) -> None:
        elapsed = time.monotonic() - started_monotonic
        if elapsed > self.budget.max_seconds:
            raise StopRun("max_seconds")

    def _dispatch(
        self,
        *,
        tool_name: str,
        tool_fn: Callable[..., dict[str, Any]],
        args: dict[str, Any],
    ) -> dict[str, Any]:
        future = self._pool.submit(tool_fn, **args)
        try:
            raw = future.result(timeout=self.budget.step_timeout_seconds)
        except FuturesTimeoutError as exc:
            raise TimeoutError(f"tool_timeout:{tool_name}") from exc
        return validate_tool_observation(raw)

    def _save_checkpoint(
        self,
        *,
        checkpoint: CheckpointStore,
        run_id: str,
        step_id: str,
        source: str,
        tool: str,
        result: dict[str, Any],
        checkpoint_ttl_seconds: float | None = None,
    ) -> None:
        ttl_value = self.budget.checkpoint_ttl_seconds if checkpoint_ttl_seconds is None else checkpoint_ttl_seconds
        ttl = float(ttl_value)
        if ttl > 0:
            checkpoint.save_step_with_ttl(
                run_id=run_id,
                step_id=step_id,
                source=source,
                tool=tool,
                result=result,
                ttl_seconds=ttl,
            )
            return
        checkpoint.save_step(
            run_id=run_id,
            step_id=step_id,
            source=source,
            tool=tool,
            result=result,
        )

    def run_step_with_recovery(
        self,
        *,
        run_id: str,
        step_id: str,
        primary_tool_name: str,
        primary_tool_fn: Callable[..., dict[str, Any]],
        fallback_chain: list[tuple[str, Callable[..., dict[str, Any]]]],
        args: dict[str, Any],
        checkpoint: CheckpointStore,
        started_monotonic: float,
        critical: bool = True,
        checkpoint_ttl_seconds: float | None = None,
    ) -> dict[str, Any]:
        self._ensure_run_budget(started_monotonic=started_monotonic)
        if step_id not in self.allowed_steps_policy:
            raise StopRun(f"step_not_allowed_policy:{step_id}")

        cached = checkpoint.get_step(run_id=run_id, step_id=step_id)
        if cached is not None:
            return {
                "status": "done",
                "step_id": step_id,
                "source": "checkpoint",
                "tool": cached.tool,
                "result": cached.result,
                "attempts_used": 0,
                "primary_attempts": 0,
                "fallback_attempts": 0,
                "retried": False,
                "fallbacks_used": 0,
                "events": [{"kind": "checkpoint_resume", "step_id": step_id}],
            }

        events: list[dict[str, Any]] = []
        primary_attempts = 0
        fallback_attempts = 0
        last_reason = "unknown"

        if primary_tool_name not in self.allowed_tools_policy:
            events.append({"kind": "primary_denied_policy", "tool": primary_tool_name})
            last_reason = "tool_denied_policy"
        elif primary_tool_name not in self.allowed_tools_execution:
            events.append({"kind": "primary_denied", "tool": primary_tool_name})
            last_reason = "tool_denied"
        else:
            for retry_idx in range(self.budget.max_retries + 1):
                self._ensure_run_budget(started_monotonic=started_monotonic)
                primary_attempts += 1
                try:
                    data = self._dispatch(
                        tool_name=primary_tool_name,
                        tool_fn=primary_tool_fn,
                        args=args,
                    )
                    self._save_checkpoint(
                        checkpoint=checkpoint,
                        run_id=run_id,
                        step_id=step_id,
                        source="primary",
                        tool=primary_tool_name,
                        result=data,
                        checkpoint_ttl_seconds=checkpoint_ttl_seconds,
                    )
                    return {
                        "status": "done",
                        "step_id": step_id,
                        "source": "primary",
                        "tool": primary_tool_name,
                        "result": data,
                        "attempts_used": primary_attempts,
                        "primary_attempts": primary_attempts,
                        "fallback_attempts": 0,
                        "retried": retry_idx > 0,
                        "fallbacks_used": 0,
                        "events": events,
                    }
                except Exception as exc:  # noqa: BLE001
                    is_timeout = isinstance(exc, TimeoutError)
                    reason = classify_exception(exc)
                    last_reason = reason
                    events.append(
                        {
                            "kind": "primary_failure",
                            "tool": primary_tool_name,
                            "attempt": retry_idx + 1,
                            "reason": reason,
                            "message": str(exc)[:120],
                        }
                    )
                    if is_timeout and retry_idx < self.budget.max_retries:
                        backoff = 0.25 * float(retry_idx + 1)
                        events.append({"kind": "retry_backoff", "seconds": backoff})
                        time.sleep(backoff)
                        continue
                    break

        fallbacks_used = 0
        for fallback_name, fallback_fn in fallback_chain:
            if fallbacks_used >= self.budget.max_fallbacks:
                break
            fallbacks_used += 1
            self._ensure_run_budget(started_monotonic=started_monotonic)
            if fallback_name not in self.allowed_tools_policy:
                events.append({"kind": "fallback_denied_policy", "tool": fallback_name})
                continue
            if fallback_name not in self.allowed_tools_execution:
                events.append({"kind": "fallback_denied", "tool": fallback_name})
                continue
            try:
                fallback_attempts += 1
                data = self._dispatch(
                    tool_name=fallback_name,
                    tool_fn=fallback_fn,
                    args=args,
                )
                events.append({"kind": "fallback_success", "tool": fallback_name})
                self._save_checkpoint(
                    checkpoint=checkpoint,
                    run_id=run_id,
                    step_id=step_id,
                    source="fallback",
                    tool=fallback_name,
                    result=data,
                    checkpoint_ttl_seconds=checkpoint_ttl_seconds,
                )
                return {
                    "status": "done",
                    "step_id": step_id,
                    "source": "fallback",
                    "tool": fallback_name,
                    "result": data,
                    "attempts_used": primary_attempts + fallback_attempts,
                    "primary_attempts": primary_attempts,
                    "fallback_attempts": fallback_attempts,
                    "retried": primary_attempts > 1,
                    "fallbacks_used": fallbacks_used,
                    "events": events,
                }
            except Exception as exc:  # noqa: BLE001
                reason = classify_exception(exc)
                last_reason = reason
                events.append(
                    {
                        "kind": "fallback_failure",
                        "tool": fallback_name,
                        "reason": reason,
                        "message": str(exc)[:120],
                    }
                )

        if critical:
            if last_reason in {"tool_denied_policy", "tool_denied"}:
                raise StopRun(f"{last_reason}:{step_id}")
            raise StopRun(f"recovery_exhausted:{step_id}")
        return {
            "status": "failed",
            "step_id": step_id,
            "source": "none",
            "tool": "none",
            "error": last_reason,
            "attempts_used": primary_attempts + fallback_attempts,
            "primary_attempts": primary_attempts,
            "fallback_attempts": fallback_attempts,
            "retried": primary_attempts > 1,
            "fallbacks_used": fallbacks_used,
            "events": events,
        }
