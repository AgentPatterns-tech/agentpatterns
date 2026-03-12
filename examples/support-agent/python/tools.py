from __future__ import annotations

import uuid
from typing import Any

CUSTOMERS = {
    42: {
        "id": 42,
        "name": "Anna",
        "email": "anna@example.com",
        "tier": "pro",
        "country": "US",
        "api_token": "tok_live_anna_123",  # must be redacted before LLM usage
    },
    7: {
        "id": 7,
        "name": "Max",
        "email": "max@example.com",
        "tier": "enterprise",
        "country": "DE",
        "api_token": "tok_live_max_987",  # must be redacted before LLM usage
    },
}

TICKETS = {
    "T-1001": {
        "id": "T-1001",
        "customer_id": 42,
        "subject": "Charged twice this month, can I get a refund?",
        "body": "I see two charges for the Pro plan this month. Please refund one charge.",
        "language": "en",
        "customer_tier": "pro",
    },
    "T-1002": {
        "id": "T-1002",
        "customer_id": 42,
        "subject": "How to change invoice email",
        "body": "Can you show me where to update the invoice email in settings?",
        "language": "en",
        "customer_tier": "pro",
    },
    "T-1003": {
        "id": "T-1003",
        "customer_id": 7,
        "subject": "My account may be hacked",
        "body": "I got a password reset email that I did not request. Is my account compromised?",
        "language": "en",
        "customer_tier": "enterprise",
    },
}

KB_DOCS = [
    {
        "id": "kb-invoice-email-v2",
        "title": "Update invoice email",
        "snippet": "Go to Settings > Billing > Invoice Contact to update the invoice email.",
    },
    {
        "id": "kb-refund-process-v1",
        "title": "Refund processing",
        "snippet": "Refund requests are reviewed by billing specialists. Approved refunds are returned to the original payment method.",
    },
    {
        "id": "kb-security-reset-v3",
        "title": "Compromised account steps",
        "snippet": "Force password reset, verify 2FA status, and review recent login events before replying.",
    },
]

POLICY_DOCS = [
    {
        "id": "policy-refund-v3",
        "title": "Refund Policy",
        "snippet": "Monthly Pro subscriptions may be eligible for a refund within 14 days from first payment after manual review.",
    },
    {
        "id": "policy-sla-v2",
        "title": "SLA Policy",
        "snippet": "Response targets are not guaranteed and may vary during incidents.",
    },
    {
        "id": "policy-security-v1",
        "title": "Security Escalation",
        "snippet": "Potential account compromise must be escalated to the security queue for manual handling.",
    },
]

ARTIFACTS: dict[str, dict[str, Any]] = {}
AUDIT_LOG: list[dict[str, Any]] = []
INTERNAL_NOTES: list[dict[str, Any]] = []


def _search_docs(query: str, docs: list[dict[str, str]], k: int) -> list[dict[str, str]]:
    words = [word for word in query.lower().split() if word]

    def score(doc: dict[str, str]) -> int:
        haystack = f"{doc['title']} {doc['snippet']}".lower()
        return sum(1 for word in words if word in haystack)

    ranked = sorted(docs, key=score, reverse=True)
    hits = [doc for doc in ranked if score(doc) > 0]
    if not hits:
        hits = docs[:]
    return hits[: max(1, k)]


def tickets_get(ticket_id: str) -> dict[str, Any]:
    ticket = TICKETS.get(ticket_id)
    if not ticket:
        return {"error": f"ticket {ticket_id} not found"}
    return {"ticket": ticket}


def customers_get(customer_id: int) -> dict[str, Any]:
    customer = CUSTOMERS.get(customer_id)
    if not customer:
        return {"error": f"customer {customer_id} not found"}
    return {"customer": customer}


def kb_search(query: str, k: int = 3) -> dict[str, Any]:
    return {"matches": _search_docs(query, KB_DOCS, k)}


def policy_search(query: str, k: int = 3) -> dict[str, Any]:
    return {"matches": _search_docs(query, POLICY_DOCS, k)}


def tickets_add_internal_note(ticket_id: str, note: dict[str, Any]) -> dict[str, Any]:
    entry = {"ticket_id": ticket_id, "note": note}
    INTERNAL_NOTES.append(entry)
    return {"ok": True, "internal_note_id": len(INTERNAL_NOTES)}


def artifacts_put(ticket_id: str, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    artifact_id = f"art_{uuid.uuid4().hex[:12]}"
    artifact = {
        "artifact_id": artifact_id,
        "ticket_id": ticket_id,
        "kind": kind,
        "payload": payload,
    }
    ARTIFACTS[artifact_id] = artifact
    return {"artifact_id": artifact_id}


def audit_emit(event_type: str, details: dict[str, Any]) -> dict[str, Any]:
    AUDIT_LOG.append({"event_type": event_type, "details": details})
    return {"ok": True, "audit_event_id": len(AUDIT_LOG)}


def get_demo_state() -> dict[str, Any]:
    return {
        "artifacts": ARTIFACTS,
        "audit_log": AUDIT_LOG,
        "internal_notes": INTERNAL_NOTES,
    }
