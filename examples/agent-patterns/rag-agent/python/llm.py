from __future__ import annotations

import json
import os
from typing import Any

from openai import APIConnectionError, APITimeoutError, OpenAI

MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
LLM_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "60"))


class LLMTimeout(Exception):
    pass


class LLMEmpty(Exception):
    pass


class LLMInvalid(Exception):
    pass


RETRIEVAL_SYSTEM_PROMPT = """
You are a retrieval planner for a RAG system.
Return exactly one JSON object in this shape:
{
  "kind": "retrieve",
  "query": "short retrieval query",
  "top_k": 4
}

Optional key:
- "sources": ["support_policy", "security_policy"]

Rules:
- Use only sources from available_sources.
- Keep query compact and factual.
- top_k must be between 1 and 6.
- Prefer omitting "sources" unless the question explicitly requires a specific policy domain.
- Do not output markdown or extra keys.
""".strip()

ANSWER_SYSTEM_PROMPT = """
You are a support assistant.
Return exactly one JSON object with this shape:
{
  "answer": "grounded answer in English",
  "citations": ["doc_id_1", "doc_id_2"]
}

Rules:
- Use only facts from provided context_chunks.
- Keep the answer concise and actionable.
- Include at least one citation.
- All citations must be doc_ids from context_chunks.
- Do not output markdown or extra keys.
""".strip()



def _get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY is not set. Run: export OPENAI_API_KEY='sk-...'"
        )
    return OpenAI(api_key=api_key)



def plan_retrieval_intent(*, question: str, available_sources: list[str]) -> dict[str, Any]:
    payload = {
        "question": question,
        "available_sources": available_sources,
    }

    client = _get_client()
    try:
        completion = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            timeout=LLM_TIMEOUT_SECONDS,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": RETRIEVAL_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        )
    except (APITimeoutError, APIConnectionError) as exc:
        raise LLMTimeout("llm_timeout") from exc

    text = completion.choices[0].message.content or "{}"
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"kind": "invalid", "raw": text}



def compose_grounded_answer(
    *,
    question: str,
    context_chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    payload = {
        "question": question,
        "context_chunks": [
            {
                "doc_id": item.get("doc_id"),
                "title": item.get("title"),
                "section": item.get("section"),
                "updated_at": item.get("updated_at"),
                "text": item.get("text"),
            }
            for item in context_chunks
        ],
    }

    client = _get_client()
    try:
        completion = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            timeout=LLM_TIMEOUT_SECONDS,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        )
    except (APITimeoutError, APIConnectionError) as exc:
        raise LLMTimeout("llm_timeout") from exc

    text = completion.choices[0].message.content or "{}"
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMInvalid("llm_invalid_json") from exc

    if not isinstance(data, dict):
        raise LLMInvalid("llm_invalid_json")

    answer = data.get("answer")
    citations = data.get("citations")

    if not isinstance(answer, str):
        raise LLMInvalid("llm_invalid_schema")
    if not answer.strip():
        raise LLMEmpty("llm_empty")

    if not isinstance(citations, list):
        raise LLMInvalid("llm_invalid_schema")

    normalized_citations: list[str] = []
    for item in citations:
        if not isinstance(item, str):
            raise LLMInvalid("llm_invalid_schema")
        value = item.strip()
        if value:
            normalized_citations.append(value)

    return {
        "answer": answer.strip(),
        "citations": normalized_citations,
    }
