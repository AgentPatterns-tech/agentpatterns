from __future__ import annotations

import json
import os
from typing import Any

from openai import APIConnectionError, APITimeoutError, OpenAI

MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
LLM_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "60"))


class LLMTimeout(Exception):
    pass

SYSTEM_PROMPT = """
You are a ReAct decision engine.
Return only one JSON object with one of these shapes:
1) {"kind":"tool","name":"<tool_name>","args":{...}}
2) {"kind":"final","answer":"<short final answer>"}

Rules:
- Use tools when you do not have enough facts.
- Do not invent tool outputs.
- Prefer the smallest next step.
- When evidence is sufficient, return "final".
- Never output markdown or extra keys.
""".strip()

TOOL_CATALOG = [
    {
        "name": "get_user_profile",
        "description": "Get user profile by user_id",
        "args": {"user_id": "integer"},
    },
    {
        "name": "get_user_billing",
        "description": "Get billing info by user_id",
        "args": {"user_id": "integer"},
    },
    {
        "name": "search_policy",
        "description": "Search refund and billing policy snippets",
        "args": {"query": "string"},
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
    tools_used = [
        step.get("action", {}).get("name")
        for step in history
        if isinstance(step, dict)
        and isinstance(step.get("action"), dict)
        and step.get("action", {}).get("kind") == "tool"
    ]
    last_observation = history[-1].get("observation") if history else None
    return {
        "steps_completed": len(history),
        "tools_used": tools_used,
        "last_observation": last_observation,
    }


def decide_next_action(goal: str, history: list[dict[str, Any]]) -> dict[str, Any]:
    # Keep full history in memory, but send summary + last N steps
    # so the prompt remains stable as runs get longer.
    recent_history = history[-3:]
    payload = {
        "goal": goal,
        "state_summary": _build_state_summary(history),
        "recent_history": recent_history,
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
                {"role": "system", "content": SYSTEM_PROMPT},
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
