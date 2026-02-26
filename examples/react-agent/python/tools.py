from __future__ import annotations

from typing import Any

USERS = {
    42: {"id": 42, "name": "Anna", "country": "US", "tier": "pro"},
    7: {"id": 7, "name": "Max", "country": "US", "tier": "free"},
}

BILLING = {
    42: {
        "currency": "USD",
        "plan": "pro_monthly",
        "price_usd": 49.0,
        "days_since_first_payment": 10,
    },
    7: {
        "currency": "USD",
        "plan": "free",
        "price_usd": 0.0,
        "days_since_first_payment": 120,
    },
}

POLICY_DOCS = [
    {
        "id": "refund-v3",
        "title": "Refund Policy",
        "snippet": "Pro monthly subscriptions are refundable within 14 days from the first payment.",
    },
    {
        "id": "free-v1",
        "title": "Free Plan Policy",
        "snippet": "Free plan has no billable payments and cannot be refunded.",
    },
    {
        "id": "billing-v2",
        "title": "Billing Rules",
        "snippet": "All refunds are returned to the original payment method in USD.",
    },
]


def get_user_profile(user_id: int) -> dict[str, Any]:
    user = USERS.get(user_id)
    if not user:
        return {"error": f"user {user_id} not found"}
    return {"user": user}


def get_user_billing(user_id: int) -> dict[str, Any]:
    billing = BILLING.get(user_id)
    if not billing:
        return {"error": f"billing record for user {user_id} not found"}
    return {"billing": billing}


def search_policy(query: str) -> dict[str, Any]:
    words = [w for w in query.lower().split() if w]

    def score(doc: dict[str, str]) -> int:
        haystack = f"{doc['title']} {doc['snippet']}".lower()
        return sum(1 for word in words if word in haystack)

    ranked = sorted(POLICY_DOCS, key=score, reverse=True)
    top = [doc for doc in ranked if score(doc) > 0][:2]
    if not top:
        top = POLICY_DOCS[:1]

    return {"matches": top}
