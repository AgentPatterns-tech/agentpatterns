from typing import Any

CUSTOMERS = {
    101: {"id": 101, "name": "Iryna", "tier": "free", "email": "iryna@gmail.com"},
    202: {"id": 202, "name": "Taras", "tier": "pro", "email": "taras@company.local"},
}


def customer_db(action: str, customer_id: int, new_tier: str | None = None) -> dict[str, Any]:
    customer = CUSTOMERS.get(customer_id)
    if not customer:
        return {"ok": False, "error": f"customer {customer_id} not found"}

    if action == "read":
        return {"ok": True, "customer": customer}

    if action == "update_tier":
        if not new_tier:
            return {"ok": False, "error": "new_tier is required"}
        customer["tier"] = new_tier
        return {"ok": True, "customer": customer}

    return {"ok": False, "error": f"unknown action '{action}'"}


def email_service(to: str, subject: str, body: str) -> dict[str, Any]:
    return {
        "ok": True,
        "status": "queued",
        "to": to,
        "subject": subject,
        "preview": body[:80],
    }
