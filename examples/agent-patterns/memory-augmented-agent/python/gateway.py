from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from memory_store import MemoryStore


class StopRun(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Budget:
    max_capture_items: int = 6
    max_retrieve_top_k: int = 6
    max_query_chars: int = 240
    max_answer_chars: int = 700
    max_value_chars: int = 120
    max_seconds: int = 25


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_memory_candidates(
    raw: Any,
    *,
    allowed_keys_policy: set[str],
    allowed_scopes_policy: set[str],
    max_items: int,
    max_value_chars: int,
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise StopRun("invalid_memory_candidates:not_object")

    items = raw.get("items")
    if not isinstance(items, list):
        raise StopRun("invalid_memory_candidates:items")

    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            raise StopRun("invalid_memory_candidates:item")

        required_keys = {"key", "value"}
        if not required_keys.issubset(item.keys()):
            raise StopRun("invalid_memory_candidates:missing_keys")

        key = item.get("key")
        value = item.get("value")
        scope = item.get("scope", "user")
        ttl_days = item.get("ttl_days", 180)
        confidence = item.get("confidence", 0.8)

        if not isinstance(key, str) or not key.strip():
            raise StopRun("invalid_memory_candidates:key")
        key = key.strip()
        if key not in allowed_keys_policy:
            raise StopRun(f"memory_key_not_allowed_policy:{key}")

        if not isinstance(value, str) or not value.strip():
            raise StopRun("invalid_memory_candidates:value")
        value = value.strip()
        if len(value) > max_value_chars:
            raise StopRun("invalid_memory_candidates:value_too_long")

        if not isinstance(scope, str) or not scope.strip():
            raise StopRun("invalid_memory_candidates:scope")
        scope = scope.strip()
        if scope not in allowed_scopes_policy:
            raise StopRun(f"memory_scope_not_allowed_policy:{scope}")

        if not _is_number(ttl_days):
            raise StopRun("invalid_memory_candidates:ttl_days")
        ttl_days = int(float(ttl_days))
        ttl_days = max(1, min(365, ttl_days))

        if not _is_number(confidence):
            raise StopRun("invalid_memory_candidates:confidence")
        confidence = float(confidence)
        confidence = max(0.0, min(1.0, confidence))

        normalized.append(
            {
                "key": key,
                "value": value,
                "scope": scope,
                "ttl_days": ttl_days,
                "confidence": round(confidence, 3),
            }
        )

    if len(normalized) > max_items:
        raise StopRun("invalid_memory_candidates:too_many_items")

    return {"items": normalized}


def validate_retrieval_intent(
    raw: Any,
    *,
    allowed_scopes_policy: set[str],
    max_top_k: int,
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise StopRun("invalid_retrieval_intent:not_object")

    if raw.get("kind") != "retrieve_memory":
        raise StopRun("invalid_retrieval_intent:kind")

    query = raw.get("query")
    if not isinstance(query, str) or not query.strip():
        raise StopRun("invalid_retrieval_intent:query")

    top_k = raw.get("top_k", 4)
    if not isinstance(top_k, int) or not (1 <= top_k <= max_top_k):
        raise StopRun("invalid_retrieval_intent:top_k")

    scopes_raw = raw.get("scopes")
    normalized_scopes: list[str] = []
    if scopes_raw is not None:
        if not isinstance(scopes_raw, list) or not scopes_raw:
            raise StopRun("invalid_retrieval_intent:scopes")
        for scope in scopes_raw:
            if not isinstance(scope, str) or not scope.strip():
                raise StopRun("invalid_retrieval_intent:scope_item")
            normalized_scope = scope.strip()
            if normalized_scope not in allowed_scopes_policy:
                raise StopRun(f"invalid_retrieval_intent:scope_not_allowed:{normalized_scope}")
            normalized_scopes.append(normalized_scope)

    payload = {
        "kind": "retrieve_memory",
        "query": query.strip(),
        "top_k": top_k,
    }
    if normalized_scopes:
        payload["scopes"] = normalized_scopes
    return payload


class MemoryGateway:
    def __init__(
        self,
        *,
        store: MemoryStore,
        budget: Budget,
        allow_execution_keys: set[str],
        allow_execution_scopes: set[str],
    ):
        self.store = store
        self.budget = budget
        self.allow_execution_keys = set(allow_execution_keys)
        self.allow_execution_scopes = set(allow_execution_scopes)

    def write(
        self,
        *,
        user_id: int,
        items: list[dict[str, Any]],
        source: str,
    ) -> dict[str, Any]:
        if len(items) > self.budget.max_capture_items:
            raise StopRun("max_capture_items")

        writable: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []

        for item in items:
            key = item["key"]
            scope = item["scope"]

            if key not in self.allow_execution_keys:
                blocked.append({"key": key, "reason": "key_denied_execution"})
                continue
            if scope not in self.allow_execution_scopes:
                blocked.append(
                    {
                        "key": key,
                        "scope": scope,
                        "reason": "scope_denied_execution",
                    }
                )
                continue

            writable.append(item)

        written = []
        if writable:
            written = self.store.upsert_items(user_id=user_id, items=writable, source=source)

        return {
            "written": written,
            "blocked": blocked,
        }

    def retrieve(
        self,
        *,
        user_id: int,
        intent: dict[str, Any],
        include_preference_keys: bool = False,
    ) -> dict[str, Any]:
        query = intent["query"]
        if len(query) > self.budget.max_query_chars:
            raise StopRun("invalid_retrieval_intent:query_too_long")

        requested_scopes = set(intent.get("scopes") or self.allow_execution_scopes)
        denied = sorted(requested_scopes - self.allow_execution_scopes)
        if denied:
            raise StopRun(f"scope_denied:{denied[0]}")

        items = self.store.search(
            user_id=user_id,
            query=query,
            top_k=intent["top_k"],
            scopes=requested_scopes,
            include_preference_keys=include_preference_keys,
        )

        return {
            "query": query,
            "requested_scopes": sorted(requested_scopes),
            "include_preference_keys": include_preference_keys,
            "items": items,
        }
