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


MEMORY_CAPTURE_SYSTEM_PROMPT = """
You are a memory extraction assistant.
Return exactly one JSON object in this shape:
{
  "items": [
    {
      "key": "language",
      "value": "english",
      "scope": "user",
      "ttl_days": 180,
      "confidence": 0.9
    }
  ]
}

Rules:
- Extract only stable preferences or durable constraints useful in future sessions.
- Use only keys from available_keys.
- scope must be "user" or "workspace".
- ttl_days must be between 1 and 365.
- confidence must be between 0 and 1.
- If nothing should be stored, return {"items": []}.
- Do not output markdown or extra keys.
""".strip()

RETRIEVAL_INTENT_SYSTEM_PROMPT = """
You are a memory retrieval planner.
Return exactly one JSON object in this shape:
{
  "kind": "retrieve_memory",
  "query": "short memory query",
  "top_k": 4
}

Optional key:
- "scopes": ["user", "workspace"]

Rules:
- Keep query compact and factual.
- top_k must be between 1 and 6.
- Use only scopes from available_scopes.
- Prefer omitting "scopes" unless the goal explicitly requires a specific scope.
- Do not output markdown or extra keys.
""".strip()

ANSWER_SYSTEM_PROMPT = """
You are an incident response assistant.
Return exactly one JSON object in this shape:
{
  "answer": "final answer in English",
  "used_memory_keys": ["language", "response_style"]
}

Rules:
- Use only incident_context and memory_items.
- Keep the answer concise, actionable, and suitable for an operations update.
- used_memory_keys must reference only keys present in memory_items.
- If "update_channel" is used, explicitly mention it in answer text (for example, "via email").
- If "language" is used with value "english", start answer with "Incident update:".
- If no memory was used, return an empty array.
- Do not output markdown or extra keys.
""".strip()


def _get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY is not set. Run: export OPENAI_API_KEY='sk-...'"
        )
    return OpenAI(api_key=api_key)


def extract_memory_candidates(
    *,
    user_message: str,
    available_keys: list[str],
) -> dict[str, Any]:
    payload = {
        "user_message": user_message,
        "available_keys": available_keys,
    }

    client = _get_client()
    try:
        completion = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            timeout=LLM_TIMEOUT_SECONDS,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": MEMORY_CAPTURE_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        )
    except (APITimeoutError, APIConnectionError) as exc:
        raise LLMTimeout("llm_timeout") from exc

    text = completion.choices[0].message.content or "{}"
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"invalid": True, "raw": text}


def plan_retrieval_intent(*, goal: str, available_scopes: list[str]) -> dict[str, Any]:
    payload = {
        "goal": goal,
        "available_scopes": available_scopes,
    }

    client = _get_client()
    try:
        completion = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            timeout=LLM_TIMEOUT_SECONDS,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": RETRIEVAL_INTENT_SYSTEM_PROMPT},
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


def compose_memory_augmented_answer(
    *,
    goal: str,
    incident_context: dict[str, Any],
    memory_items: list[dict[str, Any]],
) -> dict[str, Any]:
    payload = {
        "goal": goal,
        "incident_context": incident_context,
        "memory_items": [
            {
                "key": item.get("key"),
                "value": item.get("value"),
                "scope": item.get("scope"),
                "confidence": item.get("confidence"),
            }
            for item in memory_items
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
    used_memory_keys = data.get("used_memory_keys")

    if not isinstance(answer, str):
        raise LLMInvalid("llm_invalid_schema")
    if not answer.strip():
        raise LLMEmpty("llm_empty")

    if not isinstance(used_memory_keys, list):
        raise LLMInvalid("llm_invalid_schema")

    normalized_keys: list[str] = []
    for value in used_memory_keys:
        if not isinstance(value, str):
            raise LLMInvalid("llm_invalid_schema")
        item = value.strip()
        if item and item not in normalized_keys:
            normalized_keys.append(item)

    return {
        "answer": answer.strip(),
        "used_memory_keys": normalized_keys,
    }
