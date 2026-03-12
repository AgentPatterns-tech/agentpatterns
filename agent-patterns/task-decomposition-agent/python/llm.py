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
You are a task decomposition planner.
Return only one JSON object in this exact shape:
{
  "kind": "plan",
  "steps": [
    {"id": "step_1", "title": "...", "tool": "...", "args": {...}}
  ]
}

Rules:
- Create 3 to 6 steps.
- Use only tools from available_tools.
- Keep args minimal and valid.
- Do not add extra keys.
- Do not output markdown.
""".strip()

FINAL_SYSTEM_PROMPT = """
You are a reporting assistant.
Write a short final summary in English for a US business audience.
Include: manager name, month, gross sales (USD), refunds (USD), net sales (USD), refund rate (%), and key risk note.
""".strip()

TOOL_CATALOG = [
    {
        "name": "get_manager_profile",
        "description": "Get manager profile by manager_id",
        "args": {"manager_id": "integer"},
    },
    {
        "name": "fetch_sales_data",
        "description": "Get daily gross sales for a month",
        "args": {"month": "string in YYYY-MM"},
    },
    {
        "name": "fetch_refund_data",
        "description": "Get daily refund values for a month",
        "args": {"month": "string in YYYY-MM"},
    },
    {
        "name": "calculate_monthly_kpis",
        "description": "Calculate gross/refunds/net/order KPIs for a month",
        "args": {"month": "string in YYYY-MM"},
    },
    {
        "name": "detect_risk_signals",
        "description": "Detect risk warnings for a month",
        "args": {"month": "string in YYYY-MM"},
    },
]


def _get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY is not set. Run: export OPENAI_API_KEY='sk-...'"
        )
    return OpenAI(api_key=api_key)


def create_plan(goal: str, max_plan_steps: int) -> dict[str, Any]:
    payload = {
        "goal": goal,
        "max_plan_steps": max_plan_steps,
        "available_tools": TOOL_CATALOG,
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


def compose_final_answer(goal: str, history: list[dict[str, Any]]) -> str:
    payload = {
        "goal": goal,
        "history": history,
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
