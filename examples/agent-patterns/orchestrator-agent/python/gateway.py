from __future__ import annotations

import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from dataclasses import dataclass
from typing import Any, Callable


class StopRun(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Budget:
    max_tasks: int = 4
    max_parallel: int = 3
    max_retries_per_task: int = 1
    max_dispatches: int = 8
    task_timeout_seconds: float = 2.0
    max_seconds: int = 25


def args_hash(args: dict[str, Any]) -> str:
    stable = json.dumps(args, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()[:12]


def validate_orchestration_plan(
    raw_plan: dict[str, Any], *, allowed_workers: set[str], max_tasks: int
) -> list[dict[str, Any]]:
    if not isinstance(raw_plan, dict):
        raise StopRun("invalid_plan:non_json")
    if raw_plan.get("kind") != "plan":
        raise StopRun("invalid_plan:kind")

    tasks = raw_plan.get("tasks")
    if not isinstance(tasks, list):
        raise StopRun("invalid_plan:tasks")
    if not (1 <= len(tasks) <= max_tasks):
        raise StopRun("invalid_plan:max_tasks")

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    required_keys = {"id", "worker", "args", "critical"}

    for task in tasks:
        if not isinstance(task, dict):
            raise StopRun("invalid_plan:task_shape")
        if not required_keys.issubset(task.keys()):
            raise StopRun("invalid_plan:missing_keys")

        # Ignore unknown keys and keep only contract fields.
        task_id = task["id"]
        worker = task["worker"]
        args = task["args"]
        critical = task["critical"]

        if not isinstance(task_id, str) or not task_id.strip():
            raise StopRun("invalid_plan:task_id")
        if task_id in seen_ids:
            raise StopRun("invalid_plan:duplicate_task_id")
        seen_ids.add(task_id)

        if not isinstance(worker, str) or not worker.strip():
            raise StopRun("invalid_plan:worker")
        if worker not in allowed_workers:
            raise StopRun(f"invalid_plan:worker_not_allowed:{worker}")

        if not isinstance(args, dict):
            raise StopRun("invalid_plan:args")
        if not isinstance(critical, bool):
            raise StopRun("invalid_plan:critical")

        normalized.append(
            {
                "id": task_id.strip(),
                "worker": worker.strip(),
                "args": dict(args),
                "critical": critical,
            }
        )

    return normalized


class OrchestratorGateway:
    def __init__(
        self,
        *,
        allow: set[str],
        registry: dict[str, Callable[..., dict[str, Any]]],
        budget: Budget,
    ) -> None:
        self.allow = set(allow)
        self.registry = registry
        self.budget = budget
        self.dispatches = 0
        self._lock = threading.Lock()

    def _consume_dispatch_budget(self) -> None:
        with self._lock:
            self.dispatches += 1
            if self.dispatches > self.budget.max_dispatches:
                raise StopRun("max_dispatches")

    def _call_once(
        self, worker_name: str, args: dict[str, Any], *, deadline_monotonic: float
    ) -> dict[str, Any]:
        if worker_name not in self.allow:
            raise StopRun(f"worker_denied:{worker_name}")
        fn = self.registry.get(worker_name)
        if fn is None:
            raise StopRun(f"worker_missing:{worker_name}")

        remaining = deadline_monotonic - time.monotonic()
        if remaining <= 0:
            raise StopRun("max_seconds")
        task_timeout = min(self.budget.task_timeout_seconds, max(0.01, remaining))

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(fn, **args)
            try:
                result = future.result(timeout=task_timeout)
            except TimeoutError as exc:
                raise StopRun("task_timeout") from exc
            except TypeError as exc:
                raise StopRun(f"worker_bad_args:{worker_name}") from exc

        if not isinstance(result, dict):
            raise StopRun(f"worker_bad_result:{worker_name}")
        return result

    def _run_task_with_retry(
        self, task: dict[str, Any], request_id: str, deadline_monotonic: float
    ) -> dict[str, Any]:
        task_id = task["id"]
        worker_name = task["worker"]
        semantic_args = dict(task["args"])
        semantic_hash = args_hash(semantic_args)
        base_args = dict(semantic_args)
        base_args["request_id"] = request_id

        attempts_total = self.budget.max_retries_per_task + 1
        last_reason = "unknown"

        for attempt in range(1, attempts_total + 1):
            try:
                self._consume_dispatch_budget()
                observation = self._call_once(
                    worker_name, base_args, deadline_monotonic=deadline_monotonic
                )
                return {
                    "task_id": task_id,
                    "worker": worker_name,
                    "critical": task["critical"],
                    "status": "done",
                    "attempts_used": attempt,
                    "retried": attempt > 1,
                    "args_hash": semantic_hash,
                    "observation": observation,
                }
            except StopRun as exc:
                last_reason = exc.reason
                if exc.reason == "task_timeout" and attempt < attempts_total:
                    continue
                return {
                    "task_id": task_id,
                    "worker": worker_name,
                    "critical": task["critical"],
                    "status": "failed",
                    "attempts_used": attempt,
                    "retried": attempt > 1,
                    "args_hash": semantic_hash,
                    "stop_reason": last_reason,
                }

        return {
            "task_id": task_id,
            "worker": worker_name,
            "critical": task["critical"],
            "status": "failed",
            "attempts_used": attempts_total,
            "retried": True,
            "args_hash": semantic_hash,
            "stop_reason": last_reason,
        }

    def dispatch_parallel(
        self,
        tasks: list[dict[str, Any]],
        *,
        request_id: str,
        deadline_monotonic: float,
    ) -> list[dict[str, Any]]:
        if not tasks:
            return []

        indexed_tasks = list(enumerate(tasks))
        output: list[tuple[int, dict[str, Any]]] = []
        parallelism = min(self.budget.max_parallel, len(tasks))

        with ThreadPoolExecutor(max_workers=parallelism) as pool:
            future_to_idx = {
                pool.submit(
                    self._run_task_with_retry, task, request_id, deadline_monotonic
                ): idx
                for idx, task in indexed_tasks
            }
            remaining = deadline_monotonic - time.monotonic()
            if remaining <= 0:
                raise StopRun("max_seconds")
            try:
                for future in as_completed(future_to_idx, timeout=max(0.01, remaining)):
                    idx = future_to_idx[future]
                    output.append((idx, future.result()))
            except TimeoutError as exc:
                raise StopRun("max_seconds") from exc

        output.sort(key=lambda item: item[0])
        return [item[1] for item in output]
