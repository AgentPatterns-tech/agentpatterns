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


def _extract_user_id(ticket: str) -> int:
    if "user_id=7" in ticket:
        return 7
    return 42


def _contains_any(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def billing_specialist(ticket: str) -> dict[str, Any]:
    if not _contains_any(ticket, ["refund", "charge", "billing", "invoice"]):
        return {
            "status": "needs_reroute",
            "reason": "ticket_not_billing",
            "domain": "billing",
        }

    user_id = _extract_user_id(ticket)
    user = USERS.get(user_id)
    billing = BILLING.get(user_id)
    if not user or not billing:
        return {"status": "done", "domain": "billing", "error": "user_not_found"}

    is_refundable = (
        billing["plan"] == "pro_monthly" and billing["days_since_first_payment"] <= 14
    )
    refund_amount = billing["price_usd"] if is_refundable else 0.0

    return {
        "status": "done",
        "domain": "billing",
        "result": {
            "user_name": user["name"],
            "plan": billing["plan"],
            "currency": billing["currency"],
            "refund_eligible": is_refundable,
            "refund_amount_usd": refund_amount,
            "reason": "Pro monthly subscriptions are refundable within 14 days.",
        },
    }


def technical_specialist(ticket: str) -> dict[str, Any]:
    if not _contains_any(ticket, ["error", "bug", "incident", "api", "latency"]):
        return {
            "status": "needs_reroute",
            "reason": "ticket_not_technical",
            "domain": "technical",
        }

    return {
        "status": "done",
        "domain": "technical",
        "result": {
            "incident_id": "INC-4021",
            "service": "public-api",
            "state": "mitigated",
            "next_update_in_minutes": 30,
        },
    }


def sales_specialist(ticket: str) -> dict[str, Any]:
    if not _contains_any(ticket, ["price", "pricing", "quote", "plan", "discount"]):
        return {
            "status": "needs_reroute",
            "reason": "ticket_not_sales",
            "domain": "sales",
        }

    return {
        "status": "done",
        "domain": "sales",
        "result": {
            "recommended_plan": "team_plus",
            "currency": "USD",
            "monthly_price_usd": 199.0,
            "reason": "Best fit for teams that need priority support and usage controls.",
        },
    }
