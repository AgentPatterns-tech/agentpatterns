from __future__ import annotations

from typing import Any

MANAGERS = {
    42: {"id": 42, "name": "Anna", "region": "US", "team": "Retail East"},
    7: {"id": 7, "name": "Max", "region": "US", "team": "Retail West"},
}

SALES_DATA = {
    "2026-04": [
        {"day": "2026-04-01", "gross_usd": 5200.0, "orders": 120},
        {"day": "2026-04-02", "gross_usd": 4890.0, "orders": 113},
        {"day": "2026-04-03", "gross_usd": 6105.0, "orders": 141},
        {"day": "2026-04-04", "gross_usd": 5580.0, "orders": 127},
        {"day": "2026-04-05", "gross_usd": 6420.0, "orders": 149},
    ]
}

REFUND_DATA = {
    "2026-04": [
        {"day": "2026-04-01", "refunds_usd": 140.0},
        {"day": "2026-04-02", "refunds_usd": 260.0},
        {"day": "2026-04-03", "refunds_usd": 210.0},
        {"day": "2026-04-04", "refunds_usd": 590.0},
        {"day": "2026-04-05", "refunds_usd": 170.0},
    ]
}


def get_manager_profile(manager_id: int) -> dict[str, Any]:
    manager = MANAGERS.get(manager_id)
    if not manager:
        return {"error": f"manager {manager_id} not found"}
    return {"manager": manager}


def fetch_sales_data(month: str) -> dict[str, Any]:
    rows = SALES_DATA.get(month)
    if not rows:
        return {"error": f"sales data for {month} not found"}
    return {"month": month, "currency": "USD", "daily_sales": rows}


def fetch_refund_data(month: str) -> dict[str, Any]:
    rows = REFUND_DATA.get(month)
    if not rows:
        return {"error": f"refund data for {month} not found"}
    return {"month": month, "currency": "USD", "daily_refunds": rows}


def calculate_monthly_kpis(month: str) -> dict[str, Any]:
    sales_rows = SALES_DATA.get(month)
    refund_rows = REFUND_DATA.get(month)
    if not sales_rows or not refund_rows:
        return {"error": f"kpi inputs for {month} not found"}

    gross_sales = sum(row["gross_usd"] for row in sales_rows)
    total_refunds = sum(row["refunds_usd"] for row in refund_rows)
    total_orders = sum(row["orders"] for row in sales_rows)
    net_sales = gross_sales - total_refunds
    refund_rate = (total_refunds / gross_sales) if gross_sales else 0.0

    top_day = max(sales_rows, key=lambda row: row["gross_usd"])["day"]

    return {
        "month": month,
        "currency": "USD",
        "gross_sales_usd": round(gross_sales, 2),
        "refunds_usd": round(total_refunds, 2),
        "net_sales_usd": round(net_sales, 2),
        "orders": total_orders,
        "refund_rate": round(refund_rate, 4),
        "top_sales_day": top_day,
    }


def detect_risk_signals(month: str) -> dict[str, Any]:
    refund_rows = REFUND_DATA.get(month)
    if not refund_rows:
        return {"error": f"refund data for {month} not found"}

    high_refund_day = max(refund_rows, key=lambda row: row["refunds_usd"])
    warnings: list[str] = []

    if high_refund_day["refunds_usd"] >= 500:
        warnings.append(
            f"Refund spike detected on {high_refund_day['day']}: {high_refund_day['refunds_usd']} USD"
        )

    if not warnings:
        warnings.append("No critical risk signals detected for this month.")

    return {
        "month": month,
        "currency": "USD",
        "risk_warnings": warnings,
        "peak_refund_day": high_refund_day,
    }
