from __future__ import annotations

import re
from typing import Any

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "what",
    "which",
    "when",
    "where",
    "have",
    "has",
    "plan",
    "does",
}



def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z0-9_]+", text.lower())
    return [token for token in tokens if len(token) > 2 and token not in STOPWORDS]



def _score_document(query_tokens: list[str], doc_text: str) -> float:
    if not query_tokens:
        return 0.0

    haystack = doc_text.lower()
    overlap = sum(1 for token in query_tokens if token in haystack)
    base = overlap / len(query_tokens)

    # Boost explicit SLA intent to prefer policy-grade docs.
    phrase_boost = 0.0
    if "sla" in haystack:
        phrase_boost += 0.15
    if "p1" in haystack and "response" in haystack:
        phrase_boost += 0.1

    return round(min(base + phrase_boost, 1.0), 4)



def retrieve_candidates(
    *,
    query: str,
    documents: list[dict[str, Any]],
    top_k: int,
    allowed_sources: set[str],
) -> list[dict[str, Any]]:
    query_tokens = _tokenize(query)
    scored: list[dict[str, Any]] = []

    for doc in documents:
        if doc.get("source") not in allowed_sources:
            continue

        text = str(doc.get("text", ""))
        score = _score_document(query_tokens, text)
        if score <= 0:
            continue

        scored.append(
            {
                "doc_id": doc["id"],
                "source": doc["source"],
                "title": doc["title"],
                "section": doc["section"],
                "updated_at": doc["updated_at"],
                "score": score,
                "text": text,
            }
        )

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:top_k]



def build_context_pack(
    *,
    candidates: list[dict[str, Any]],
    min_score: float,
    max_chunks: int,
    max_chars: int,
) -> dict[str, Any]:
    selected: list[dict[str, Any]] = []
    total_chars = 0
    rejected_low_score = 0

    for item in candidates:
        if item["score"] < min_score:
            rejected_low_score += 1
            continue

        text = item["text"].strip()
        next_size = len(text)
        if len(selected) >= max_chunks:
            break
        if total_chars + next_size > max_chars:
            continue

        selected.append(item)
        total_chars += next_size

    return {
        "chunks": selected,
        "total_chars": total_chars,
        "rejected_low_score": rejected_low_score,
    }
