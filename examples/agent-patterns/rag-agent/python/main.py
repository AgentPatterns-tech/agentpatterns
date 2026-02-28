from __future__ import annotations

import json
import time
from typing import Any

from gateway import Budget, RetrievalGateway, StopRun, validate_retrieval_intent
from kb import KB_DOCUMENTS
from llm import LLMEmpty, LLMInvalid, LLMTimeout, compose_grounded_answer, plan_retrieval_intent

QUESTION = "What SLA applies to enterprise plan and what is P1 first response target?"

BUDGET = Budget(
    max_query_chars=240,
    max_top_k=6,
    max_context_chunks=3,
    max_context_chars=2200,
    min_chunk_score=0.2,
    max_seconds=20,
)

ALLOWED_SOURCES_POLICY = {
    "support_policy",
    "security_policy",
    "billing_policy",
}

SECURITY_SOURCE_RUNTIME_ENABLED = True
ALLOWED_SOURCES_EXECUTION = (
    {"support_policy", "security_policy", "billing_policy"}
    if SECURITY_SOURCE_RUNTIME_ENABLED
    else {"support_policy", "billing_policy"}
)
# Set SECURITY_SOURCE_RUNTIME_ENABLED=False to observe source_denied:security_policy.



def _shorten(text: str, *, limit: int = 280) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."



def _validate_citations_from_context(
    context_chunks: list[dict[str, Any]],
    citations: list[str],
) -> tuple[list[str], list[dict[str, Any]], list[str], list[str]]:
    by_id: dict[str, dict[str, Any]] = {
        str(chunk["doc_id"]): chunk
        for chunk in context_chunks
        if chunk.get("doc_id")
    }

    normalized: list[str] = []
    seen: set[str] = set()
    for citation in citations:
        value = str(citation).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)

    invalid = sorted([doc_id for doc_id in normalized if doc_id not in by_id])

    valid_doc_ids: list[str] = []
    citation_details: list[dict[str, Any]] = []
    for doc_id in normalized:
        chunk = by_id.get(doc_id)
        if not chunk:
            continue
        valid_doc_ids.append(doc_id)
        citation_details.append(
            {
                "doc_id": chunk["doc_id"],
                "title": chunk["title"],
                "section": chunk["section"],
                "updated_at": chunk["updated_at"],
                "source": chunk["source"],
                "score": chunk["score"],
            }
        )

    return valid_doc_ids, citation_details, invalid, sorted(by_id.keys())



def run_rag(question: str) -> dict[str, Any]:
    started = time.monotonic()
    trace: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []

    gateway = RetrievalGateway(
        documents=KB_DOCUMENTS,
        budget=BUDGET,
        allow_execution_sources=ALLOWED_SOURCES_EXECUTION,
    )

    try:
        raw_intent = plan_retrieval_intent(
            question=question,
            available_sources=sorted(ALLOWED_SOURCES_POLICY),
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
        intent = validate_retrieval_intent(
            raw_intent,
            allowed_sources_policy=ALLOWED_SOURCES_POLICY,
            max_top_k=BUDGET.max_top_k,
        )
    except StopRun as exc:
        return {
            "status": "stopped",
            "stop_reason": exc.reason,
            "phase": "plan",
            "raw_intent": raw_intent,
            "trace": trace,
            "history": history,
        }

    if (time.monotonic() - started) > BUDGET.max_seconds:
        return {
            "status": "stopped",
            "stop_reason": "max_seconds",
            "phase": "retrieve",
            "trace": trace,
            "history": history,
        }

    try:
        retrieval = gateway.run(intent)
    except StopRun as exc:
        return {
            "status": "stopped",
            "stop_reason": exc.reason,
            "phase": "retrieve",
            "intent": intent,
            "trace": trace,
            "history": history,
        }

    trace.append(
        {
            "step": 1,
            "phase": "retrieve",
            "query": retrieval["query"],
            "requested_sources": retrieval["requested_sources"],
            "candidates": len(retrieval["candidates"]),
            "context_chunks": len(retrieval["context_chunks"]),
            "rejected_low_score": retrieval["rejected_low_score"],
            "ok": True,
        }
    )

    history.append(
        {
            "step": 1,
            "intent": intent,
            "retrieval": {
                "candidates": [
                    {
                        "doc_id": item["doc_id"],
                        "source": item["source"],
                        "score": item["score"],
                    }
                    for item in retrieval["candidates"]
                ],
                "context_chunks": [item["doc_id"] for item in retrieval["context_chunks"]],
            },
        }
    )

    if not retrieval["context_chunks"]:
        fallback_answer = (
            "I could not find enough grounded evidence in approved sources. "
            "Please clarify the plan (enterprise/standard) or provide a policy document link."
        )
        trace.append(
            {
                "step": 2,
                "phase": "fallback",
                "reason": "no_grounded_context",
                "ok": True,
            }
        )
        history.append(
            {
                "step": 2,
                "action": "fallback",
                "answer": fallback_answer,
            }
        )
        return {
            "status": "ok",
            "stop_reason": "success",
            "outcome": "clarify",
            "answer": fallback_answer,
            "citations": [],
            "citation_details": [],
            "trace": trace,
            "history": history,
        }

    if (time.monotonic() - started) > BUDGET.max_seconds:
        return {
            "status": "stopped",
            "stop_reason": "max_seconds",
            "phase": "generate",
            "trace": trace,
            "history": history,
        }

    try:
        final = compose_grounded_answer(
            question=question,
            context_chunks=retrieval["context_chunks"],
        )
    except LLMTimeout:
        return {
            "status": "stopped",
            "stop_reason": "llm_timeout",
            "phase": "generate",
            "trace": trace,
            "history": history,
        }
    except LLMInvalid as exc:
        return {
            "status": "stopped",
            "stop_reason": exc.args[0],
            "phase": "generate",
            "trace": trace,
            "history": history,
        }
    except LLMEmpty:
        return {
            "status": "stopped",
            "stop_reason": "llm_empty",
            "phase": "generate",
            "trace": trace,
            "history": history,
        }

    citations, citation_details, invalid_citations, context_doc_ids = _validate_citations_from_context(
        retrieval["context_chunks"],
        final["citations"],
    )
    if invalid_citations:
        return {
            "status": "stopped",
            "stop_reason": "invalid_answer:citations_out_of_context",
            "phase": "generate",
            "invalid_citations": invalid_citations,
            "context_doc_ids": context_doc_ids,
            "trace": trace,
            "history": history,
        }
    if len(citations) < 1:
        return {
            "status": "stopped",
            "stop_reason": "invalid_answer:missing_citations",
            "phase": "generate",
            "trace": trace,
            "history": history,
        }

    trace.append(
        {
            "step": 2,
            "phase": "generate",
            "citation_count": len(citations),
            "ok": True,
        }
    )

    history.append(
        {
            "step": 2,
            "action": "compose_grounded_answer",
            "answer": _shorten(final["answer"]),
            "citations": citations,
        }
    )

    return {
        "status": "ok",
        "stop_reason": "success",
        "outcome": "grounded_answer",
        "answer": final["answer"],
        "citations": citations,
        "citation_details": citation_details,
        "trace": trace,
        "history": history,
    }



def main() -> None:
    result = run_rag(QUESTION)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
