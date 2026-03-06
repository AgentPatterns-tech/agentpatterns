from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


RAW_SEARCH_RESULTS = [
    {
        "url": "https://official-status.example.com/incidents/payments-2026-03-07",
        "title": "Payments Incident Update",
        "snippet": "P1 incident, failed payment rate and ETA updates.",
        "score": 0.98,
    },
    {
        "url": "https://vendor.example.com/policies/enterprise-sla",
        "title": "Enterprise SLA",
        "snippet": "Uptime SLA and response targets by severity.",
        "score": 0.94,
    },
    {
        "url": "https://regulator.example.org/guidance/customer-communications",
        "title": "Customer Communication Guidance",
        "snippet": "Expectations for incident disclosures.",
        "score": 0.81,
    },
    {
        "url": "https://official-status.example.com/incidents/payments-2026-03-07#latest",
        "title": "Payments Incident Update (duplicate URL form)",
        "snippet": "Duplicate page with fragment.",
        "score": 0.73,
    },
    {
        "url": "https://vendor.example.com/policies/enterprise-sla?ref=search",
        "title": "Enterprise SLA (duplicate URL form)",
        "snippet": "Duplicate page with query string.",
        "score": 0.71,
    },
    {
        "url": "https://community-rumors.example.net/thread/payment-outage",
        "title": "Community Thread",
        "snippet": "Unverified forum claims.",
        "score": 0.42,
    },
]

PAGES: dict[str, dict[str, Any]] = {
    "https://official-status.example.com/incidents/payments-2026-03-07": {
        "title": "Payments Incident Update",
        "published_at": "2026-03-07",
        "body": (
            "US payment gateway is in P1 degraded mode. Failed payment rate is 3.4%. "
            "Chargeback alerts observed: 5. Estimated time to recovery: 45 minutes, subject to change."
        ),
    },
    "https://vendor.example.com/policies/enterprise-sla": {
        "title": "Enterprise SLA",
        "published_at": "2026-01-15",
        "body": (
            "Enterprise monthly uptime SLA is 99.95%. "
            "For P1 incidents, first response target is 15 minutes, available 24/7."
        ),
    },
    "https://regulator.example.org/guidance/customer-communications": {
        "title": "Customer Communication Guidance",
        "published_at": "2025-11-04",
        "body": (
            "Service providers should publish regular incident updates with known impact and recovery status."
        ),
    },
}


def normalize_url(url: str) -> str:
    parsed = urlparse(str(url).strip())
    scheme = (parsed.scheme or "https").lower()
    host = parsed.netloc.lower()
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return f"{scheme}://{host}{path}"


def search_sources(*, query: str, k: int) -> dict[str, Any]:
    del query
    return {
        "status": "ok",
        "data": {
            "results": [dict(item) for item in RAW_SEARCH_RESULTS[: max(1, int(k))]],
        },
    }


def read_source(*, url: str) -> dict[str, Any]:
    normalized = normalize_url(url)
    page = PAGES.get(normalized)
    if page is None:
        return {
            "status": "error",
            "error": "not_found",
        }
    return {
        "status": "ok",
        "data": {
            "url": normalized,
            "title": str(page["title"]),
            "published_at": str(page["published_at"]),
            "body": str(page["body"]),
        },
    }


def extract_notes_from_page(*, url: str, page: dict[str, Any]) -> list[dict[str, Any]]:
    normalized = normalize_url(url)

    if normalized == "https://official-status.example.com/incidents/payments-2026-03-07":
        return [
            {
                "claim": "US payments incident is P1 with failed payment rate 3.4%, 5 chargeback alerts, and ETA about 45 minutes.",
                "quote": "US payment gateway is in P1 degraded mode. Failed payment rate is 3.4%. Chargeback alerts observed: 5. Estimated time to recovery: 45 minutes, subject to change.",
                "url": normalized,
                "title": page["title"],
                "published_at": page["published_at"],
            }
        ]

    if normalized == "https://vendor.example.com/policies/enterprise-sla":
        return [
            {
                "claim": "Enterprise SLA includes 99.95% monthly uptime and a 15-minute first response target for P1 incidents (24/7).",
                "quote": "Enterprise monthly uptime SLA is 99.95%. For P1 incidents, first response target is 15 minutes, available 24/7.",
                "url": normalized,
                "title": page["title"],
                "published_at": page["published_at"],
            }
        ]

    return []


def verify_notes(*, notes: list[dict[str, Any]]) -> dict[str, Any]:
    checked = 0
    issues: list[str] = []

    for note in notes:
        checked += 1
        quote = str(note.get("quote", "")).strip()
        claim = str(note.get("claim", "")).strip()
        if len(quote) < 20:
            issues.append("quote_too_short")
        if not claim:
            issues.append("claim_missing")

    return {
        "status": "ok",
        "data": {
            "ok": len(issues) == 0,
            "checked_notes": checked,
            "issues": issues,
        },
    }
