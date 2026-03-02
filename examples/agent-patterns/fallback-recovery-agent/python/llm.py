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


FINAL_SYSTEM_PROMPT = """
You are an operations editor.
Return exactly one JSON object:
{
  "answer": "short operations brief"
}

Rules:
- Use only provided aggregate facts.
- Mention if fallback recovery was used.
- Keep it concise and actionable.
- If ETA is present, phrase it as an estimate that may change. Never guarantee timelines.
- Do not output markdown or extra keys.
""".strip()


def _get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY is not set. Run: export OPENAI_API_KEY='sk-...'"
        )
    return OpenAI(api_key=api_key)


def _chat_json(*, system_prompt: str, payload: dict[str, Any]) -> dict[str, Any]:
    client = _get_client()
    try:
        completion = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            timeout=LLM_TIMEOUT_SECONDS,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
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
    return data


def compose_operations_brief(
    *,
    goal: str,
    aggregate: dict[str, Any],
    recovery_summary: dict[str, Any],
) -> str:
    payload = {
        "goal": goal,
        "aggregate": aggregate,
        "recovery_summary": recovery_summary,
    }
    data = _chat_json(system_prompt=FINAL_SYSTEM_PROMPT, payload=payload)
    answer = data.get("answer")
    if not isinstance(answer, str):
        raise LLMInvalid("llm_invalid_schema")
    answer = answer.strip()
    if not answer:
        raise LLMEmpty("llm_empty")
    return answer
