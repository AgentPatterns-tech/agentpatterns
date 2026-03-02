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
You are a support drafting assistant.
Return only one JSON object with exactly these keys:
- customer_reply: string
- internal_note: string
- claims: array of {"kind": string, "text": string, "citation_id": string}
- citations: array of {"id": string, "title": string}

Rules:
- Keep customer_reply concise and professional.
- Do not promise refunds, credits, or guaranteed timelines.
- If any policy claim is made, add citation_id.
- Use only citation IDs present in provided policy/kb context.
- Never include secrets.
""".strip()


def _get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY is not set. Run: export OPENAI_API_KEY='sk-...'"
        )
    return OpenAI(api_key=api_key)


def _as_claims(value: Any) -> list[dict[str, str]]:
    claims: list[dict[str, str]] = []
    if not isinstance(value, list):
        return claims
    for item in value:
        if not isinstance(item, dict):
            continue
        claim = {
            "kind": str(item.get("kind", "")).strip().lower(),
            "text": str(item.get("text", "")).strip(),
            "citation_id": str(item.get("citation_id", "")).strip(),
        }
        claims.append(claim)
    return claims


def _as_citations(value: Any) -> list[dict[str, str]]:
    citations: list[dict[str, str]] = []
    if not isinstance(value, list):
        return citations
    for item in value:
        if not isinstance(item, dict):
            continue
        citation = {
            "id": str(item.get("id", "")).strip(),
            "title": str(item.get("title", "")).strip(),
        }
        if citation["id"]:
            citations.append(citation)
    return citations


def generate_support_draft(
    *,
    ticket: dict[str, Any],
    customer: dict[str, Any],
    kb_matches: list[dict[str, Any]],
    policy_matches: list[dict[str, Any]],
) -> dict[str, Any]:
    payload = {
        "ticket": ticket,
        "customer": customer,
        "kb_matches": kb_matches,
        "policy_matches": policy_matches,
        "output_language": ticket.get("language", "en"),
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
        data = json.loads(text)
    except json.JSONDecodeError:
        data = {}

    customer_reply = str(data.get("customer_reply", "")).strip()
    internal_note = str(data.get("internal_note", "")).strip()
    claims = _as_claims(data.get("claims", []))
    citations = _as_citations(data.get("citations", []))

    if not customer_reply:
        customer_reply = (
            "Thanks for your message. We are reviewing your request with the support team "
            "and will follow up shortly."
        )
    if not internal_note:
        internal_note = "Draft created. Please verify policy claims before approval."

    return {
        "customer_reply": customer_reply,
        "internal_note": internal_note,
        "claims": claims,
        "citations": citations,
    }
