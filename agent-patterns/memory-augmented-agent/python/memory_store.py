from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any


DEFAULT_BOOST_KEYS = {"language", "response_style", "update_channel"}


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9_]+", (text or "").lower()))


@dataclass
class MemoryRecord:
    user_id: int
    key: str
    value: str
    scope: str
    source: str
    confidence: float
    updated_at: float
    expires_at: float


class MemoryStore:
    def __init__(self, *, max_items: int):
        self.max_items = max_items
        self._records: dict[tuple[int, str, str], MemoryRecord] = {}

    def _evict_if_needed(self) -> None:
        if len(self._records) <= self.max_items:
            return
        oldest_key = min(self._records.items(), key=lambda item: item[1].updated_at)[0]
        self._records.pop(oldest_key, None)

    def upsert_items(
        self,
        *,
        user_id: int,
        items: list[dict[str, Any]],
        source: str,
    ) -> list[dict[str, Any]]:
        now = time.time()
        written: list[dict[str, Any]] = []

        for item in items:
            key = str(item["key"]).strip()
            value = str(item["value"]).strip()
            scope = str(item.get("scope", "user")).strip() or "user"
            ttl_days = float(item.get("ttl_days", 180))
            ttl_days = max(1.0, min(365.0, ttl_days))
            confidence = float(item.get("confidence", 0.8))
            confidence = max(0.0, min(1.0, confidence))
            expires_at = now + ttl_days * 86400.0

            record_key = (user_id, scope, key)
            existing = self._records.get(record_key)
            if existing and existing.value == value:
                # Stable value: refresh metadata without creating noisy rewrites.
                existing.source = source
                existing.confidence = confidence
                existing.updated_at = now
                existing.expires_at = expires_at

                written.append(
                    {
                        "key": key,
                        "value": value,
                        "scope": scope,
                        "source": source,
                        "confidence": round(confidence, 3),
                        "ttl_days": int(ttl_days),
                        "refreshed": True,
                    }
                )
                continue

            row = MemoryRecord(
                user_id=user_id,
                key=key,
                value=value,
                scope=scope,
                source=source,
                confidence=confidence,
                updated_at=now,
                expires_at=expires_at,
            )
            self._records[record_key] = row
            self._evict_if_needed()

            written.append(
                {
                    "key": key,
                    "value": value,
                    "scope": scope,
                    "source": source,
                    "confidence": round(confidence, 3),
                    "ttl_days": int(ttl_days),
                    "refreshed": False,
                }
            )

        return written

    def search(
        self,
        *,
        user_id: int,
        query: str,
        top_k: int,
        scopes: set[str],
        include_preference_keys: bool = False,
    ) -> list[dict[str, Any]]:
        now = time.time()
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        hits: list[tuple[float, MemoryRecord]] = []
        for row in list(self._records.values()):
            if row.user_id != user_id:
                continue
            if row.scope not in scopes:
                continue
            if row.expires_at <= now:
                self._records.pop((row.user_id, row.scope, row.key), None)
                continue

            text_tokens = _tokenize(f"{row.key} {row.value}")
            overlap = len(query_tokens & text_tokens)
            if overlap == 0 and not (include_preference_keys and row.key in DEFAULT_BOOST_KEYS):
                continue

            score = overlap + (row.confidence * 0.3)

            if include_preference_keys and row.key in DEFAULT_BOOST_KEYS:
                score += 0.4

            if score <= 0:
                continue
            hits.append((score, row))

        hits.sort(key=lambda item: (item[0], item[1].updated_at), reverse=True)

        result: list[dict[str, Any]] = []
        for score, row in hits[:top_k]:
            result.append(
                {
                    "key": row.key,
                    "value": row.value,
                    "scope": row.scope,
                    "source": row.source,
                    "confidence": round(row.confidence, 3),
                    "score": round(score, 3),
                }
            )
        return result

    def dump_user_records(self, *, user_id: int) -> list[dict[str, Any]]:
        now = time.time()
        rows: list[MemoryRecord] = []

        for row in list(self._records.values()):
            if row.user_id != user_id:
                continue
            if row.expires_at <= now:
                self._records.pop((row.user_id, row.scope, row.key), None)
                continue
            rows.append(row)

        rows.sort(key=lambda item: item.updated_at, reverse=True)

        snapshot: list[dict[str, Any]] = []
        for row in rows:
            ttl_left_days = max(0.0, (row.expires_at - now) / 86400.0)
            snapshot.append(
                {
                    "key": row.key,
                    "value": row.value,
                    "scope": row.scope,
                    "source": row.source,
                    "confidence": round(row.confidence, 3),
                    "ttl_left_days": round(ttl_left_days, 1),
                }
            )
        return snapshot
