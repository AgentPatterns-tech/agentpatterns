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


ROUTER_SYSTEM_PROMPT = """
You are a routing decision engine.
Return only one JSON object in this exact shape:
{"kind":"route","target":"<route_name>","args":{"ticket":"..."}}

Rules:
- Choose exactly one target from available_routes.
- Never choose targets from forbidden_targets.
- Keep args minimal and valid for that target.
- If previous attempts failed with needs_reroute, choose a different target.
- Respect routing budgets and avoid unnecessary retries.
- Do not answer the user directly.
- Never output markdown or extra keys.
""".strip()

FINAL_SYSTEM_PROMPT = """
You are a support response assistant.
Write a short final answer in English for a US customer.
Use only evidence from delegated specialist observation.
Include: selected specialist, final decision, and one reason.
For billing refunds, include amount in USD when available.
""".strip()

ROUTE_CATALOG = [
    {
        "name": "billing_specialist",
        "description": "Handle refunds, charges, invoices, and billing policy",
        "args": {"ticket": "string"},
    },
    {
        "name": "technical_specialist",
        "description": "Handle errors, incidents, API issues, and outages",
        "args": {"ticket": "string"},
    },
    {
        "name": "sales_specialist",
        "description": "Handle pricing, plan recommendations, and quotes",
        "args": {"ticket": "string"},
    },
]


def _get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY is not set. Run: export OPENAI_API_KEY='sk-...'"
        )
    return OpenAI(api_key=api_key)


def _build_state_summary(history: list[dict[str, Any]]) -> dict[str, Any]:
    routes_used = [
        step.get("route", {}).get("target")
        for step in history
        if isinstance(step, dict)
        and isinstance(step.get("route"), dict)
        and step.get("route", {}).get("kind") == "route"
    ]
    routes_used_unique = list(dict.fromkeys(route for route in routes_used if route))
    last_route_target = routes_used[-1] if routes_used else None
    last_observation = history[-1].get("observation") if history else None
    last_observation_status = (
        last_observation.get("status") if isinstance(last_observation, dict) else None
    )
    return {
        "attempts_completed": len(history),
        "routes_used_unique": routes_used_unique,
        "last_route_target": last_route_target,
        "last_observation_status": last_observation_status,
        "last_observation": last_observation,
    }


def decide_route(
    goal: str,
    history: list[dict[str, Any]],
    *,
    max_route_attempts: int,
    remaining_attempts: int,
    forbidden_targets: list[str],
) -> dict[str, Any]:
    recent_history = history[-3:]
    payload = {
        "goal": goal,
        "budgets": {
            "max_route_attempts": max_route_attempts,
            "remaining_attempts": remaining_attempts,
        },
        "forbidden_targets": forbidden_targets,
        "state_summary": _build_state_summary(history),
        "recent_history": recent_history,
        "available_routes": ROUTE_CATALOG,
    }

    client = _get_client()
    try:
        completion = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            timeout=LLM_TIMEOUT_SECONDS,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
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


def compose_final_answer(
    goal: str, selected_route: str, history: list[dict[str, Any]]
) -> str:
    payload = {
        "goal": goal,
        "selected_route": selected_route,
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
