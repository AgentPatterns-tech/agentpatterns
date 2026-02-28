from __future__ import annotations

import json
import time
import uuid
from typing import Any

from gateway import Budget, OrchestratorGateway, StopRun, validate_orchestration_plan
from llm import LLMEmpty, LLMTimeout, compose_final_answer, create_plan
from workers import inventory_worker, payments_worker, sales_worker

REPORT_DATE = "2026-02-26"
REGION = "US"
GOAL = (
    "Prepare a morning operations report for e-commerce region US on 2026-02-26. "
    "Include sales, payment risk, and inventory risk with one concrete action."
)

BUDGET = Budget(
    max_tasks=4,
    max_parallel=3,
    max_retries_per_task=1,
    max_dispatches=8,
    task_timeout_seconds=2.0,
    max_seconds=25,
)

WORKER_REGISTRY = {
    "sales_worker": sales_worker,
    "payments_worker": payments_worker,
    "inventory_worker": inventory_worker,
}

ALLOWED_WORKERS_POLICY = {"sales_worker", "payments_worker", "inventory_worker"}
INVENTORY_RUNTIME_ENABLED = True
ALLOWED_WORKERS_EXECUTION = (
    {"sales_worker", "payments_worker", "inventory_worker"}
    if INVENTORY_RUNTIME_ENABLED
    else {"sales_worker", "payments_worker"}
)
# Set INVENTORY_RUNTIME_ENABLED=False to get worker_denied:inventory_worker in trace.


def aggregate_results(task_results: list[dict[str, Any]]) -> dict[str, Any]:
    done_by_worker: dict[str, dict[str, Any]] = {}
    failed: list[dict[str, Any]] = []

    for item in task_results:
        if item["status"] == "done":
            done_by_worker[item["worker"]] = item["observation"]
        else:
            failed.append(
                {
                    "task_id": item["task_id"],
                    "worker": item["worker"],
                    "critical": item["critical"],
                    "stop_reason": item["stop_reason"],
                }
            )

    sales = done_by_worker.get("sales_worker", {}).get("result", {})
    payments = done_by_worker.get("payments_worker", {}).get("result", {})
    inventory = done_by_worker.get("inventory_worker", {}).get("result", {})

    health = "green"
    if payments.get("failed_payment_rate", 0) >= 0.03 or inventory.get("out_of_stock_skus"):
        health = "yellow"
    if payments.get("gateway_incident") not in (None, "none"):
        health = "red"

    return {
        "report_date": REPORT_DATE,
        "region": REGION,
        "health": health,
        "sales": sales,
        "payments": payments,
        "inventory": inventory,
        "failed_tasks": failed,
    }


def run_orchestrator(goal: str) -> dict[str, Any]:
    started = time.monotonic()
    deadline = started + BUDGET.max_seconds
    request_id = uuid.uuid4().hex[:10]

    trace: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []

    gateway = OrchestratorGateway(
        allow=ALLOWED_WORKERS_EXECUTION,
        registry=WORKER_REGISTRY,
        budget=BUDGET,
    )

    try:
        raw_plan = create_plan(
            goal=goal,
            report_date=REPORT_DATE,
            region=REGION,
            max_tasks=BUDGET.max_tasks,
        )
    except LLMTimeout:
        return {
            "status": "stopped",
            "stop_reason": "llm_timeout",
            "phase": "plan",
            "trace": trace,
            "history": history,
        }

    try:
        tasks = validate_orchestration_plan(
            raw_plan,
            allowed_workers=ALLOWED_WORKERS_POLICY,
            max_tasks=BUDGET.max_tasks,
        )
    except StopRun as exc:
        return {
            "status": "stopped",
            "stop_reason": exc.reason,
            "phase": "plan",
            "raw_plan": raw_plan,
            "trace": trace,
            "history": history,
        }

    if time.monotonic() > deadline:
        return {
            "status": "stopped",
            "stop_reason": "max_seconds",
            "phase": "dispatch",
            "plan": tasks,
            "trace": trace,
            "history": history,
        }

    try:
        task_results = gateway.dispatch_parallel(
            tasks,
            request_id=request_id,
            deadline_monotonic=deadline,
        )
    except StopRun as exc:
        return {
            "status": "stopped",
            "stop_reason": exc.reason,
            "phase": "dispatch",
            "plan": tasks,
            "trace": trace,
            "history": history,
        }

    for item in task_results:
        trace.append(
            {
                "task_id": item["task_id"],
                "worker": item["worker"],
                "status": item["status"],
                "attempts_used": item["attempts_used"],
                "retried": item["retried"],
                "args_hash": item["args_hash"],
                "stop_reason": item.get("stop_reason"),
                "critical": item["critical"],
            }
        )
        history.append(item)

    failed_critical = [
        item for item in task_results if item["status"] == "failed" and item["critical"]
    ]
    if failed_critical:
        return {
            "status": "stopped",
            "stop_reason": "critical_task_failed",
            "phase": "dispatch",
            "plan": tasks,
            "failed_critical": failed_critical,
            "trace": trace,
            "history": history,
        }

    aggregate = aggregate_results(task_results)

    if time.monotonic() > deadline:
        return {
            "status": "stopped",
            "stop_reason": "max_seconds",
            "phase": "finalize",
            "aggregate": aggregate,
            "trace": trace,
            "history": history,
        }

    try:
        answer = compose_final_answer(goal=goal, aggregate=aggregate)
    except LLMTimeout:
        return {
            "status": "stopped",
            "stop_reason": "llm_timeout",
            "phase": "finalize",
            "aggregate": aggregate,
            "trace": trace,
            "history": history,
        }
    except LLMEmpty:
        return {
            "status": "stopped",
            "stop_reason": "llm_empty",
            "phase": "finalize",
            "aggregate": aggregate,
            "trace": trace,
            "history": history,
        }

    return {
        "status": "ok",
        "stop_reason": "success",
        "answer": answer,
        "plan": tasks,
        "aggregate": aggregate,
        "trace": trace,
        "history": history,
    }


def main() -> None:
    result = run_orchestrator(GOAL)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
