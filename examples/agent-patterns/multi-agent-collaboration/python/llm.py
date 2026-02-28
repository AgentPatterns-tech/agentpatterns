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


COMMON_RULES = """
Return exactly one JSON object with this shape:
{
  "agent": "<role_name>",
  "stance": "go|caution|block",
  "summary": "one short paragraph",
  "confidence": 0.0,
  "actions": ["action 1", "action 2"]
}

Rules:
- Use only the provided facts.
- Keep actions concrete and operational.
- Do not output markdown or extra keys.
""".strip()

AGENT_PROMPTS = {
    "demand_analyst": (
        "You are Demand Analyst. Focus on demand capacity, conversion, and traffic risks. "
        "Decide whether launch is feasible from growth and operational demand perspective."
    ),
    "finance_analyst": (
        "You are Finance Analyst. Focus on revenue, margin, campaign cost, and downside exposure. "
        "Decide if launch economics are acceptable."
    ),
    "risk_analyst": (
        "You are Risk Analyst. Focus on payment reliability, chargebacks, and incidents. "
        "Prioritize safety and compliance risk containment."
    ),
    "legal_analyst": (
        "You are Legal Analyst. Focus on regulatory, compliance, consumer protection, and policy constraints. "
        "Flag launch blockers and required mitigations."
    ),
}

FINAL_SYSTEM_PROMPT = """
You are a launch readiness editor.
Write a short operations brief in English.
Include:
- final decision (go/go_with_caution/no_go)
- why the team agreed
- top 2 immediate actions
Use only evidence from collaboration history.
""".strip()



def _get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY is not set. Run: export OPENAI_API_KEY='sk-...'"
        )
    return OpenAI(api_key=api_key)



def _round_summaries(history: list[dict[str, Any]], limit: int = 2) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for row in history[-limit:]:
        summaries.append(
            {
                "round": row.get("round"),
                "decision": row.get("decision"),
                "conflicts": row.get("conflicts", []),
                "stances": [
                    {
                        "agent": item.get("agent"),
                        "stance": item.get("stance"),
                        "confidence": item.get("confidence"),
                    }
                    for item in row.get("contributions", [])
                ],
            }
        )
    return summaries



def propose_contribution(
    *,
    role: str,
    goal: str,
    shared_context: dict[str, Any],
    history: list[dict[str, Any]],
    open_conflicts: list[str],
) -> dict[str, Any]:
    system = AGENT_PROMPTS.get(role)
    if not system:
        raise ValueError(f"unknown_role:{role}")

    payload = {
        "goal": goal,
        "role": role,
        "shared_context": shared_context,
        "recent_rounds": _round_summaries(history, limit=2),
        "open_conflicts": open_conflicts,
    }

    client = _get_client()
    try:
        completion = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            timeout=LLM_TIMEOUT_SECONDS,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": f"{system}\n\n{COMMON_RULES}"},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=True)},
            ],
        )
    except (APITimeoutError, APIConnectionError) as exc:
        raise LLMTimeout("llm_timeout") from exc

    text = completion.choices[0].message.content or "{}"
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"invalid": True, "raw": text}



def compose_final_answer(
    *,
    goal: str,
    final_decision: str,
    history: list[dict[str, Any]],
) -> str:
    payload = {
        "goal": goal,
        "final_decision": final_decision,
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
