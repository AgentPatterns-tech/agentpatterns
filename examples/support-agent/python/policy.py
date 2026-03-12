from __future__ import annotations

from typing import Any

HIGH_RISK_CATEGORIES = {"security", "billing_refund", "legal", "outage"}
REQUIRED_CITATION_KINDS = {"refund", "credit", "sla", "timeline"}

# These phrases are intentionally simple lexical checks.
# Teams should adapt this list to their own policy language.
NO_COMMITMENT_PHRASES = [
    "we refunded",
    "refund is guaranteed",
    "we guarantee",
    "you will definitely",
    "credit has been applied",
]


def classify_ticket_risk(ticket: dict[str, Any]) -> tuple[str, str]:
    text = f"{ticket.get('subject', '')} {ticket.get('body', '')}".lower()

    if any(word in text for word in ["refund", "charged", "chargeback"]):
        return "billing_refund", "contains_refund_or_chargeback"
    if any(word in text for word in ["hacked", "2fa", "compromised", "password reset"]):
        return "security", "contains_security_signal"
    if any(word in text for word in ["gdpr", "legal", "lawyer", "contract"]):
        return "legal", "contains_legal_signal"
    if any(word in text for word in ["outage", "down", "incident", "500"]):
        return "outage", "contains_incident_signal"

    return "general", "no_high_risk_signals"


def should_force_manual_review(*, risk_category: str, customer: dict[str, Any]) -> bool:
    if risk_category in HIGH_RISK_CATEGORIES:
        return True
    # Conservative rule for enterprise billing topics.
    if customer.get("tier") == "enterprise" and risk_category.startswith("billing"):
        return True
    return False


def redact_customer(customer: dict[str, Any]) -> dict[str, Any]:
    blocked_keys = {"api_token", "password_hash", "secret", "ssn"}
    safe: dict[str, Any] = {}
    for key, value in customer.items():
        if key in blocked_keys:
            safe[key] = "[REDACTED]"
        else:
            safe[key] = value
    return safe


def validate_no_commitments(customer_reply: str) -> list[str]:
    text = customer_reply.lower()
    return [
        f"forbidden_commitment_phrase:{phrase}"
        for phrase in NO_COMMITMENT_PHRASES
        if phrase in text
    ]


def validate_citations(
    *,
    claims: list[dict[str, Any]],
    citations: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []

    citation_ids = {
        str(item.get("id", "")).strip()
        for item in citations
        if isinstance(item, dict) and str(item.get("id", "")).strip()
    }

    for claim in claims:
        if not isinstance(claim, dict):
            errors.append("bad_claim_object")
            continue

        kind = str(claim.get("kind", "")).strip().lower()
        citation_id = str(claim.get("citation_id", "")).strip()

        if kind in REQUIRED_CITATION_KINDS and not citation_id:
            errors.append(f"missing_citation:{kind}")
            continue

        if citation_id and citation_id not in citation_ids:
            errors.append(f"unknown_citation:{citation_id}")

    return errors


def build_handoff_note(
    *,
    ticket: dict[str, Any],
    risk_category: str,
    risk_reason: str,
) -> dict[str, Any]:
    return {
        "ticket_id": ticket.get("id"),
        "summary": (
            f"Ticket requires manual handling due to {risk_category}. "
            f"Reason: {risk_reason}."
        ),
        "risk_category": risk_category,
        "risk_reason": risk_reason,
        "suggested_team": "security" if risk_category == "security" else "billing",
    }
