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
  "draft": "customer-facing incident update"
}

Rules:
- Use only facts from provided incident_context.
- Include current status, customer impact, and next actions.
- Keep language clear and non-speculative.
- Avoid absolute guarantees.
- Do not output markdown or extra keys.
""".strip()

SHORTEN_DRAFT_SYSTEM_PROMPT = """
You are an operations editor.
Return exactly one JSON object:
{
  "draft": "shortened customer-facing incident update"
}

Rules:
- Rewrite the draft to be <= max_chars characters.
- Preserve original facts, numbers, and intent.
- Do not add new facts or speculative claims.
- Keep current status, customer impact, and next actions.
- Keep language clear and non-speculative.
- Avoid absolute guarantees.
- Do not output markdown or extra keys.
""".strip()

CRITIQUE_SYSTEM_PROMPT = """
You are a strict critique reviewer.
Return exactly one JSON object:
{
  "decision": "approve|revise|escalate",
  "severity": "low|medium|high",
  "risks": [{"type":"overconfidence","note":"..."}],
  "required_changes": ["concrete change"],
  "reason": "for escalate only"
}

Rules:
- Review exactly once.
- decision=approve: required_changes must be empty.
- decision=revise: provide 1-5 concrete required changes.
- decision=escalate: use only for high-risk content.
- Every required_changes item MUST start with ADD/REMOVE/MUST_INCLUDE/MUST_REMOVE.
- Every required_changes item MUST contain exactly one quoted phrase.
- If you cannot express required changes in enforceable ADD/REMOVE format, set decision=escalate and explain why in reason.
- Use explicit markers for enforceable phrase edits:
  - REMOVE "phrase to delete"
  - ADD "phrase to include"
  - MUST_REMOVE "phrase to delete" (equivalent)
  - MUST_INCLUDE "phrase to include" (equivalent)
- Do not add new facts in required_changes.
- Use only risk types from allowed_risk_types.
- Do not output markdown or extra keys.
""".strip()

REVISE_SYSTEM_PROMPT = """
You are an editor applying a constrained rewrite.
Return exactly one JSON object:
{
  "revised_answer": "updated answer"
}

Rules:
- Apply required_changes only.
- Keep original scope and customer intent.
- Do not add new facts or numbers.
- Keep the answer concise and actionable.
- Do not output markdown or extra keys.
""".strip()

REVISE_SYSTEM_PROMPT_STRICT = """
You are an editor applying a constrained rewrite.
Return exactly one JSON object:
{
  "revised_answer": "updated answer"
}

Rules:
- Apply required_changes only.
- Keep original scope and customer intent.
- Do not add new facts or numbers.
- Keep the answer concise and actionable.
- You MUST satisfy each required_changes item exactly.
- For ADD/MUST_INCLUDE: include the quoted phrase verbatim.
- For REMOVE/MUST_REMOVE: ensure the quoted phrase does not appear.
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


def shorten_draft(*, draft: str, max_chars: int) -> str:
    payload = {
        "draft": draft,
        "max_chars": int(max_chars),
    }
    data = _chat_json(system_prompt=SHORTEN_DRAFT_SYSTEM_PROMPT, payload=payload)

    shortened = data.get("draft")
    if not isinstance(shortened, str):
        raise LLMInvalid("llm_invalid_schema")

    shortened = shortened.strip()
    if not shortened:
        raise LLMEmpty("llm_empty")
    return shortened



def critique_draft(
    *,
    goal: str,
    incident_context: dict[str, Any],
    draft: str,
    allowed_risk_types: list[str],
) -> dict[str, Any]:
    payload = {
        "goal": goal,
        "incident_context": incident_context,
        "draft": draft,
        "allowed_risk_types": allowed_risk_types,
    }
    return _chat_json(system_prompt=CRITIQUE_SYSTEM_PROMPT, payload=payload)



def revise_once(
    *,
    goal: str,
    incident_context: dict[str, Any],
    draft: str,
    required_changes: list[str],
    strict_mode: bool = False,
) -> str:
    payload = {
        "goal": goal,
        "incident_context": incident_context,
        "draft": draft,
        "required_changes": required_changes,
    }
    system_prompt = REVISE_SYSTEM_PROMPT_STRICT if strict_mode else REVISE_SYSTEM_PROMPT
    data = _chat_json(system_prompt=system_prompt, payload=payload)

    revised = data.get("revised_answer")
    if not isinstance(revised, str):
        raise LLMInvalid("llm_invalid_schema")

    revised = revised.strip()
    if not revised:
        raise LLMEmpty("llm_empty")
    return revised
