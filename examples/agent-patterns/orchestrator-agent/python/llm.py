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


PLAN_SYSTEM_PROMPT = """
You are an orchestration planner.
Return only one JSON object in this exact shape:
{
  "kind": "plan",
  "tasks": [
    {"id":"t1","worker":"sales_worker","args":{"report_date":"YYYY-MM-DD","region":"US"},"critical":true}
  ]
}

Rules:
- Create 2 to 4 independent tasks.
- Use only workers from available_workers.
- Keep args minimal and valid for the selected worker.
- Mark task as critical=true only if final brief is impossible without it.
- Do not output markdown or extra keys.
""".strip()

FINAL_SYSTEM_PROMPT = """
You are an operations assistant.
Write a short final briefing in English for an e-commerce operations manager.
Include:
- headline health status (green/yellow/red)
- key sales metrics
- payment risk note
- inventory risk note
- one concrete next action
Use only evidence from orchestrator output.
""".strip()

WORKER_CATALOG = [
    {
        "name": "sales_worker",
        "description": "Provides sales KPIs for a date and region",
        "args": {"report_date": "YYYY-MM-DD", "region": "US|EU|..."},
    },
    {
        "name": "payments_worker",
        "description": "Provides payment failure and chargeback signals",
        "args": {"report_date": "YYYY-MM-DD", "region": "US|EU|..."},
    },
    {
        "name": "inventory_worker",
        "description": "Provides low-stock and out-of-stock risk signals",
        "args": {"report_date": "YYYY-MM-DD", "region": "US|EU|..."},
    },
]


def _get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY is not set. Run: export OPENAI_API_KEY='sk-...'"
        )
    return OpenAI(api_key=api_key)


def create_plan(
    *,
    goal: str,
    report_date: str,
    region: str,
    max_tasks: int,
) -> dict[str, Any]:
    payload = {
        "goal": goal,
        "report_date": report_date,
        "region": region,
        "max_tasks": max_tasks,
        "available_workers": WORKER_CATALOG,
    }

    client = _get_client()
    try:
        completion = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            timeout=LLM_TIMEOUT_SECONDS,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": PLAN_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=True)},
            ],
        )
    except (APITimeoutError, APIConnectionError) as exc:
        raise LLMTimeout("llm_timeout") from exc

    text = completion.choices[0].message.content or "{}"
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"kind": "invalid", "raw": text}


def compose_final_answer(*, goal: str, aggregate: dict[str, Any]) -> str:
    payload = {
        "goal": goal,
        "aggregate": aggregate,
    }

    client = _get_client()
    try:
        completion = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            timeout=LLM_TIMEOUT_SECONDS,
            messages=[
                {"role": "system", "content": FINAL_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=True)},
            ],
        )
    except (APITimeoutError, APIConnectionError) as exc:
        raise LLMTimeout("llm_timeout") from exc

    text = completion.choices[0].message.content or ""
    text = text.strip()
    if not text:
        raise LLMEmpty("llm_empty")
    return text
