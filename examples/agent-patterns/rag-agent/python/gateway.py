from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from retriever import build_context_pack, retrieve_candidates


class StopRun(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Budget:
    max_query_chars: int = 240
    max_top_k: int = 6
    max_context_chunks: int = 3
    max_context_chars: int = 2200
    min_chunk_score: float = 0.2
    max_seconds: int = 20



def validate_retrieval_intent(
    raw: Any,
    *,
    allowed_sources_policy: set[str],
    max_top_k: int,
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise StopRun("invalid_intent:not_object")

    if raw.get("kind") != "retrieve":
        raise StopRun("invalid_intent:kind")

    query = raw.get("query")
    if not isinstance(query, str) or not query.strip():
        raise StopRun("invalid_intent:query")

    top_k = raw.get("top_k", 4)
    if not isinstance(top_k, int) or not (1 <= top_k <= max_top_k):
        raise StopRun("invalid_intent:top_k")

    sources_raw = raw.get("sources")
    normalized_sources: list[str] = []
    if sources_raw is not None:
        if not isinstance(sources_raw, list) or not sources_raw:
            raise StopRun("invalid_intent:sources")
        for source in sources_raw:
            if not isinstance(source, str) or not source.strip():
                raise StopRun("invalid_intent:source_item")
            source_name = source.strip()
            if source_name not in allowed_sources_policy:
                raise StopRun(f"invalid_intent:source_not_allowed:{source_name}")
            normalized_sources.append(source_name)

    # Ignore unknown keys and keep only contract fields.
    payload = {
        "kind": "retrieve",
        "query": query.strip(),
        "top_k": top_k,
    }
    if normalized_sources:
        payload["sources"] = normalized_sources
    return payload


class RetrievalGateway:
    def __init__(
        self,
        *,
        documents: list[dict[str, Any]],
        budget: Budget,
        allow_execution_sources: set[str],
    ):
        self.documents = documents
        self.budget = budget
        self.allow_execution_sources = set(allow_execution_sources)

    def run(self, intent: dict[str, Any]) -> dict[str, Any]:
        query = intent["query"]
        if len(query) > self.budget.max_query_chars:
            raise StopRun("invalid_intent:query_too_long")

        requested_sources = set(intent.get("sources") or self.allow_execution_sources)
        denied = sorted(requested_sources - self.allow_execution_sources)
        if denied:
            raise StopRun(f"source_denied:{denied[0]}")

        candidates = retrieve_candidates(
            query=query,
            documents=self.documents,
            top_k=intent["top_k"],
            allowed_sources=requested_sources,
        )

        context_pack = build_context_pack(
            candidates=candidates,
            min_score=self.budget.min_chunk_score,
            max_chunks=self.budget.max_context_chunks,
            max_chars=self.budget.max_context_chars,
        )

        return {
            "query": query,
            "requested_sources": sorted(requested_sources),
            "candidates": candidates,
            "context_chunks": context_pack["chunks"],
            "context_total_chars": context_pack["total_chars"],
            "rejected_low_score": context_pack["rejected_low_score"],
        }
