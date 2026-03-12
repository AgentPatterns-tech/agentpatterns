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


DRAFT_SYSTEM_PROMPT = """
You are an operations communications writer.
Return exactly one JSON object:
{
  "draft": "short customer-safe incident update"
}

Rules:
- Use only facts from provided incident_context.
- Include current status, customer impact, and next actions.
- Avoid absolute guarantees and overconfident claims.
- Keep draft concise and actionable.
- Do not output markdown or extra keys.
""".strip()

REVIEW_SYSTEM_PROMPT = """
You are a reflection reviewer.
Return exactly one JSON object:
{
  "decision": "approve|revise|escalate",
  "issues": [{"type":"overconfidence","note":"..."}],
  "fix_plan": ["patch instruction"],
  "reason": "for escalate only"
}

Rules:
- Review exactly once.
- decision=approve: fix_plan must be empty.
- decision=revise: provide 1-4 concrete patch-only instructions.
- For enforceable instructions, include quoted target phrases in fix_plan.
- decision=escalate: use only for high-risk or policy-unsafe content.
- Do not add new facts in fix_plan.
- Use only issue types from allowed_issue_types.
- Do not output markdown or extra keys.
""".strip()

REVISE_SYSTEM_PROMPT = """
You are an editor applying one controlled patch.
Return exactly one JSON object:
{
  "revised_answer": "updated answer"
}

Rules:
- Edit only what is needed to satisfy fix_plan.
- Keep scope and intent of original draft.
- Do not introduce new facts or numbers.
- Keep answer concise and customer-safe.
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



def generate_draft(*, goal: str, incident_context: dict[str, Any]) -> str:
    payload = {
        "goal": goal,
        "incident_context": incident_context,
    }
    data = _chat_json(system_prompt=DRAFT_SYSTEM_PROMPT, payload=payload)

    draft = data.get("draft")
    if not isinstance(draft, str):
        raise LLMInvalid("llm_invalid_schema")

    draft = draft.strip()
    if not draft:
        raise LLMEmpty("llm_empty")
    return draft



def review_draft(
    *,
    goal: str,
    incident_context: dict[str, Any],
    draft: str,
    allowed_issue_types: list[str],
) -> dict[str, Any]:
    payload = {
        "goal": goal,
        "incident_context": incident_context,
        "draft": draft,
        "allowed_issue_types": allowed_issue_types,
    }
    return _chat_json(system_prompt=REVIEW_SYSTEM_PROMPT, payload=payload)



def revise_once(
    *,
    goal: str,
    incident_context: dict[str, Any],
    draft: str,
    fix_plan: list[str],
) -> str:
    payload = {
        "goal": goal,
        "incident_context": incident_context,
        "draft": draft,
        "fix_plan": fix_plan,
    }
    data = _chat_json(system_prompt=REVISE_SYSTEM_PROMPT, payload=payload)

    revised = data.get("revised_answer")
    if not isinstance(revised, str):
        raise LLMInvalid("llm_invalid_schema")

    revised = revised.strip()
    if not revised:
        raise LLMEmpty("llm_empty")
    return revised
