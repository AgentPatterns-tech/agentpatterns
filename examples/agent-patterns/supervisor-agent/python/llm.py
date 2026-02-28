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


WORKER_SYSTEM_PROMPT = """
You are a support worker agent.
Return exactly one JSON object in one of these shapes:
1) {"kind":"tool","name":"<tool_name>","args":{...}}
2) {"kind":"final","answer":"<short final answer>"}

Rules:
- First, collect facts with get_refund_context.
- Then propose issue_refund when facts are sufficient.
- Use send_refund_email only after refund success is visible in history.
- Use only tools from available_tools.
- Do not output markdown or extra keys.
""".strip()

FINAL_SYSTEM_PROMPT = """
You are a customer support assistant.
Write a short final answer in English.
Include:
- final refund amount in USD
- whether human approval was required
- one reason based on policy
""".strip()

TOOL_CATALOG = [
    {
        "name": "get_refund_context",
        "description": "Get user profile, billing facts, and policy hints",
        "args": {"user_id": "integer"},
    },
    {
        "name": "issue_refund",
        "description": "Issue refund in USD",
        "args": {"user_id": "integer", "amount_usd": "number", "reason": "optional string"},
    },
    {
        "name": "send_refund_email",
        "description": "Send refund confirmation email",
        "args": {"user_id": "integer", "amount_usd": "number", "message": "string"},
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

    supervisor_decisions = [
        step.get("supervisor", {}).get("decision")
        for step in history
        if isinstance(step, dict) and isinstance(step.get("supervisor"), dict)
    ]

    return {
        "steps_completed": len(history),
        "tools_used": [t for t in tools_used if t],
        "supervisor_decisions": [d for d in supervisor_decisions if d],
        "last_step": history[-1] if history else None,
    }


def _recent_step_summaries(history: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for step in history[-limit:]:
        out.append(
            {
                "step": step.get("step"),
                "proposed_tool": step.get("action", {}).get("name"),
                "supervisor_decision": step.get("supervisor", {}).get("decision"),
                "executed_tool": step.get("executed_action", {}).get("name"),
                "executed_from": step.get("executed_from"),
                "observation_status": step.get("observation", {}).get("status"),
            }
        )
    return out


def decide_next_action(
    goal: str,
    history: list[dict[str, Any]],
) -> dict[str, Any]:
    payload = {
        "goal": goal,
        "state_summary": _build_state_summary(history),
        "recent_step_summaries": _recent_step_summaries(history, limit=3),
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
                {"role": "system", "content": WORKER_SYSTEM_PROMPT},
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

    text = (completion.choices[0].message.content or "").strip()
    if not text:
        raise LLMEmpty("llm_empty")
    return text
