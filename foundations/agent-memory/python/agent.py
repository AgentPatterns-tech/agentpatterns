from memory import LongMemoryStore, ShortMemory
from tools import get_orders_count, get_sales_total, render_report

DEFAULT_PREFS = {
    "report_format": "default",
    "currency": "USD",
}


def save_user_preferences(
    *,
    user_key: str,
    prefs: dict[str, str],
    short_memory: ShortMemory,
    long_memory: LongMemoryStore,
) -> None:
    short_memory.add("user", f"Save prefs: {prefs}")
    long_memory.save_prefs(user_key, prefs)
    short_memory.add("assistant", "Preferences saved to long-term memory")


def parse_prefs_from_short_memory(short_memory: ShortMemory) -> dict[str, str]:
    # Simplified parser for learning: looks for lines like "pref:key=value".
    parsed: dict[str, str] = {}
    for item in short_memory.snapshot():
        content = item["content"]
        if "pref:" not in content:
            continue
        payload = content.split("pref:", 1)[1]
        if "=" not in payload:
            continue
        key, value = payload.split("=", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def build_weekly_report(
    *,
    user_id: int,
    user_key: str,
    request: str,
    short_memory: ShortMemory,
    long_memory: LongMemoryStore,
    use_long_memory: bool,
) -> dict:
    trace: list[str] = []

    short_memory.add("user", request)
    trace.append(f"request={request}")

    short_prefs = parse_prefs_from_short_memory(short_memory)
    trace.append(f"short_prefs={short_prefs}")

    long_prefs = long_memory.load_prefs(user_key) if use_long_memory else {}
    trace.append(f"long_prefs={long_prefs}")

    prefs = {**DEFAULT_PREFS, **short_prefs, **long_prefs}
    trace.append(f"resolved_prefs={prefs}")

    total = get_sales_total(user_id)
    orders = get_orders_count(user_id)

    report = render_report(
        total=total,
        orders=orders,
        currency=prefs["currency"],
        report_format=prefs["report_format"],
    )

    short_memory.add("assistant", f"Report generated with prefs={prefs}")

    return {
        "prefs": prefs,
        "report": report,
        "trace": trace,
        "short_memory_snapshot": short_memory.snapshot(),
    }
