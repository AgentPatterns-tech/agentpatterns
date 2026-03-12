def get_sales_total(user_id: int) -> float:
    _ = user_id
    return 12400.0


def get_orders_count(user_id: int) -> int:
    _ = user_id
    return 31


def render_report(*, total: float, orders: int, currency: str, report_format: str) -> str:
    if report_format == "short-bullets":
        return (
            f"- Total sales: {total:.2f} {currency}\n"
            f"- Orders: {orders}\n"
            "- Status: stable"
        )

    return (
        f"Sales report: total={total:.2f} {currency}, "
        f"orders={orders}, status=stable"
    )
