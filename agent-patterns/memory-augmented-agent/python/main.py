from __future__ import annotations

import json
import re
import time
import uuid
from typing import Any

from gateway import (
    Budget,
    MemoryGateway,
    StopRun,
    validate_memory_candidates,
    validate_retrieval_intent,
)
from llm import (
    LLMEmpty,
    LLMInvalid,
    LLMTimeout,
    compose_memory_augmented_answer,
    extract_memory_candidates,
    plan_retrieval_intent,
)
from memory_store import MemoryStore

USER_ID = 42
SESSION_1_USER_MESSAGE = (
    "For future incident updates, write in English, keep replies concise, "
    "use email as the primary channel, and remember that I am enterprise tier."
)
SESSION_2_GOAL = "Draft today's payment incident update and next actions."

INCIDENT_CONTEXT = {
    "date": "2026-03-04",
    "region": "US",
    "incident_id": "inc_payments_20260304",
    "severity": "P1",
    "gateway_status": "degraded",
    "failed_payment_rate": 0.034,
    "chargeback_alerts": 5,
    "eta_minutes": 45,
}

BUDGET = Budget(
    max_capture_items=6,
    max_retrieve_top_k=6,
    max_query_chars=240,
    max_answer_chars=700,
    max_value_chars=120,
    max_seconds=25,
)

ALLOWED_MEMORY_KEYS_POLICY = {
    "language",
    "response_style",
    "update_channel",
    "declared_tier",
}
# Runtime can block high-risk keys even if policy allows them.
TRUST_DECLARED_TIER_FROM_CHAT = False
ALLOWED_MEMORY_KEYS_EXECUTION = (
    ALLOWED_MEMORY_KEYS_POLICY
    if TRUST_DECLARED_TIER_FROM_CHAT
    else {"language", "response_style", "update_channel"}
)

ALLOWED_SCOPES_POLICY = {"user", "workspace"}
WORKSPACE_MEMORY_RUNTIME_ENABLED = False
ALLOWED_SCOPES_EXECUTION = (
    ALLOWED_SCOPES_POLICY if WORKSPACE_MEMORY_RUNTIME_ENABLED else {"user"}
)
# Runtime policy: include default preferences for this incident-update flow.
ENABLE_PREFERENCE_BIAS = True



def _shorten(text: str, *, limit: int = 240) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."



def _pick_applied_memory(
    memory_items: list[dict[str, Any]],
    used_keys: list[str],
) -> list[dict[str, Any]]:
    used = set(used_keys)
    out: list[dict[str, Any]] = []
    for item in memory_items:
        key = item.get("key")
        if key not in used:
            continue
        out.append(
            {
                "key": item["key"],
                "value": item["value"],
                "scope": item["scope"],
                "confidence": item["confidence"],
                "score": item["score"],
            }
        )
    return out



def _has_declared_memory_application(*, answer: str, applied_memory: list[dict[str, Any]]) -> bool:
    """
    Conservative audit check:
    - update_channel: value should appear in answer text.
    - response_style=concise: short-response format compliance.
    - language=english: answer should use a stable prefix "Incident update:".
    If no verifiable key exists, do not block.
    """
    if not applied_memory:
        return False

    normalized_answer = " ".join((answer or "").lower().split())
    evidenced_any = False
    has_verifiable_key = False

    def _is_concise(text: str) -> bool:
        words = re.findall(r"[a-zA-Z0-9_]+", text)
        sentence_count = len(re.findall(r"[.!?]+", text))
        return len(words) <= 80 and sentence_count <= 3

    for item in applied_memory:
        key = str(item.get("key") or "").strip().lower()
        value = str(item.get("value", "")).strip().lower()
        if not key or not value:
            continue

        if key == "update_channel":
            has_verifiable_key = True
            if value in normalized_answer:
                evidenced_any = True
        elif key == "response_style":
            has_verifiable_key = True
            if value == "concise" and _is_concise(answer):
                evidenced_any = True
        elif key == "language":
            if value in {"english", "en"}:
                has_verifiable_key = True
                if normalized_answer.startswith("incident update:"):
                    evidenced_any = True
            continue
        else:
            continue

    if not has_verifiable_key:
        return True
    return evidenced_any



def run_memory_augmented(
    *,
    user_id: int,
    session_1_message: str,
    session_2_goal: str,
) -> dict[str, Any]:
    run_id = str(uuid.uuid4())
    started = time.monotonic()
    trace: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []

    def stopped(stop_reason: str, *, phase: str, **extra: Any) -> dict[str, Any]:
        payload = {
            "run_id": run_id,
            "status": "stopped",
            "stop_reason": stop_reason,
            "phase": phase,
            "trace": trace,
            "history": history,
        }
        payload.update(extra)
        return payload

    store = MemoryStore(max_items=100)
    gateway = MemoryGateway(
        store=store,
        budget=BUDGET,
        allow_execution_keys=ALLOWED_MEMORY_KEYS_EXECUTION,
        allow_execution_scopes=ALLOWED_SCOPES_EXECUTION,
    )

    try:
        raw_capture = extract_memory_candidates(
            user_message=session_1_message,
            available_keys=sorted(ALLOWED_MEMORY_KEYS_POLICY),
        )
    except LLMTimeout:
        return stopped("llm_timeout", phase="capture")

    try:
        capture_payload = validate_memory_candidates(
            raw_capture,
            allowed_keys_policy=ALLOWED_MEMORY_KEYS_POLICY,
            allowed_scopes_policy=ALLOWED_SCOPES_POLICY,
            max_items=BUDGET.max_capture_items,
            max_value_chars=BUDGET.max_value_chars,
        )
    except StopRun as exc:
        return stopped(
            exc.reason,
            phase="capture",
            raw_capture=raw_capture,
        )

    write_result = gateway.write(
        user_id=user_id,
        items=capture_payload["items"],
        source="session_1",
    )

    refreshed_items = [item for item in write_result["written"] if item.get("refreshed")]
    written_items = [item for item in write_result["written"] if not item.get("refreshed")]

    trace.append(
        {
            "step": 1,
            "phase": "capture_store",
            "candidates": len(capture_payload["items"]),
            "written": len(written_items),
            "refreshed": len(refreshed_items),
            "blocked": len(write_result["blocked"]),
            "ok": True,
        }
    )

    history.append(
        {
            "step": 1,
            "session": "session_1",
            "message": session_1_message,
            "written_keys": [item["key"] for item in written_items],
            "refreshed_keys": [item["key"] for item in refreshed_items],
            "blocked": write_result["blocked"],
        }
    )

    if (time.monotonic() - started) > BUDGET.max_seconds:
        return stopped("max_seconds", phase="retrieve_plan")

    try:
        raw_intent = plan_retrieval_intent(
            goal=session_2_goal,
            available_scopes=sorted(ALLOWED_SCOPES_POLICY),
        )
    except LLMTimeout:
        return stopped("llm_timeout", phase="retrieve_plan")

    try:
        intent = validate_retrieval_intent(
            raw_intent,
            allowed_scopes_policy=ALLOWED_SCOPES_POLICY,
            max_top_k=BUDGET.max_retrieve_top_k,
        )
    except StopRun as exc:
        return stopped(
            exc.reason,
            phase="retrieve_plan",
            raw_intent=raw_intent,
        )

    try:
        retrieval = gateway.retrieve(
            user_id=user_id,
            intent=intent,
            include_preference_keys=ENABLE_PREFERENCE_BIAS,
        )
    except StopRun as exc:
        return stopped(
            exc.reason,
            phase="retrieve",
            intent=intent,
        )

    trace.append(
        {
            "step": 2,
            "phase": "retrieve",
            "query": retrieval["query"],
            "requested_scopes": retrieval["requested_scopes"],
            "include_preference_keys": retrieval["include_preference_keys"],
            "memory_hits": len(retrieval["items"]),
            "ok": True,
        }
    )

    history.append(
        {
            "step": 2,
            "session": "session_2",
            "intent": intent,
            "resolved_scopes": retrieval["requested_scopes"],
            "include_preference_keys": retrieval["include_preference_keys"],
            "retrieved_keys": [item["key"] for item in retrieval["items"]],
        }
    )

    if (time.monotonic() - started) > BUDGET.max_seconds:
        return stopped("max_seconds", phase="apply")

    try:
        final = compose_memory_augmented_answer(
            goal=session_2_goal,
            incident_context=INCIDENT_CONTEXT,
            memory_items=retrieval["items"],
        )
    except LLMTimeout:
        return stopped("llm_timeout", phase="apply")
    except LLMInvalid as exc:
        return stopped(exc.args[0], phase="apply")
    except LLMEmpty:
        return stopped("llm_empty", phase="apply")

    retrieved_keys = {item["key"] for item in retrieval["items"]}
    invalid_used_keys = sorted(
        set(final["used_memory_keys"]) - retrieved_keys,
    )
    if invalid_used_keys:
        return stopped(
            "invalid_answer:memory_keys_out_of_context",
            phase="apply",
            invalid_used_memory_keys=invalid_used_keys,
            retrieved_keys=sorted(retrieved_keys),
        )

    if len(final["answer"]) > BUDGET.max_answer_chars:
        return stopped("invalid_answer:too_long", phase="apply")

    applied_memory = _pick_applied_memory(retrieval["items"], final["used_memory_keys"])
    if final["used_memory_keys"] and not _has_declared_memory_application(
        answer=final["answer"],
        applied_memory=applied_memory,
    ):
        return stopped(
            "invalid_answer:memory_declared_but_not_applied",
            phase="apply",
            used_memory_keys=final["used_memory_keys"],
            applied_memory=applied_memory,
        )

    trace.append(
        {
            "step": 3,
            "phase": "apply",
            "used_memory_keys": final["used_memory_keys"],
            "applied_memory_count": len(applied_memory),
            "ok": True,
        }
    )

    history.append(
        {
            "step": 3,
            "action": "compose_memory_augmented_answer",
            "used_memory_keys": final["used_memory_keys"],
            "answer": _shorten(final["answer"]),
        }
    )

    return {
        "run_id": run_id,
        "status": "ok",
        "stop_reason": "success",
        "outcome": "memory_applied" if final["used_memory_keys"] else "context_only",
        "answer": final["answer"],
        "used_memory_keys": final["used_memory_keys"],
        "applied_memory": applied_memory,
        "memory_state": store.dump_user_records(user_id=user_id),
        "trace": trace,
        "history": history,
    }



def main() -> None:
    result = run_memory_augmented(
        user_id=USER_ID,
        session_1_message=SESSION_1_USER_MESSAGE,
        session_2_goal=SESSION_2_GOAL,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
