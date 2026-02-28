from __future__ import annotations

from typing import Any

USERS = {
    42: {"id": 42, "name": "Anna", "country": "US", "tier": "enterprise"},
    7: {"id": 7, "name": "Max", "country": "US", "tier": "pro"},
}

BILLING = {
    42: {
        "plan": "annual_enterprise",
        "currency": "USD",
        "last_charge_usd": 1200.0,
        "days_since_payment": 10,
    },
    7: {
        "plan": "pro_monthly",
        "currency": "USD",
        "last_charge_usd": 49.0,
        "days_since_payment": 35,
    },
}


def get_refund_context(user_id: int) -> dict[str, Any]:
    user = USERS.get(user_id)
    billing = BILLING.get(user_id)
    if not user or not billing:
        return {"error": f"context_not_found_for_user:{user_id}"}

    return {
        "user": user,
        "billing": billing,
        "policy_hint": {
            "auto_refund_limit_usd": 1000.0,
            "refund_window_days": 14,
        },
    }


def issue_refund(
    user_id: int,
    amount_usd: float,
    reason: str,
) -> dict[str, Any]:
    user = USERS.get(user_id)
    billing = BILLING.get(user_id)
    if not user or not billing:
        return {"status": "error", "error": f"refund_user_not_found:{user_id}"}

    if amount_usd <= 0:
        return {"status": "error", "error": "refund_amount_must_be_positive"}

    paid = float(billing["last_charge_usd"])
    if amount_usd > paid:
        return {
            "status": "error",
            "error": "refund_exceeds_last_charge",
            "max_refund_usd": paid,
        }

    return {
        "status": "ok",
        "refund": {
            "user_id": user_id,
            "currency": "USD",
            "amount_usd": round(float(amount_usd), 2),
            "reason": reason.strip(),
            "transaction_id": f"rf_{user_id}_20260226",
        },
    }


def send_refund_email(user_id: int, amount_usd: float, message: str) -> dict[str, Any]:
    user = USERS.get(user_id)
    if not user:
        return {"status": "error", "error": f"email_user_not_found:{user_id}"}

    return {
        "status": "ok",
        "email": {
            "to": f"{user['name'].lower()}@example.com",
            "template": "refund_confirmation_v2",
            "amount_usd": round(float(amount_usd), 2),
            "message": message,
            "email_id": f"em_{user_id}_20260226",
        },
    }
