from typing import Any

KB = [
    {
        "id": "KB-101",
        "title": "Refund Policy",
        "text": "Refunds are available within 14 days after payment. "
                "After 14 days, refunds are not available.",
    },
    {
        "id": "KB-102",
        "title": "Pro Plan",
        "text": "Pro customers have priority support and a 4-hour SLA.",
    },
    {
        "id": "KB-103",
        "title": "Free Plan",
        "text": "Free customers get business-hours support with no SLA.",
    },
]


def search_kb(question: str, limit: int = 2) -> list[dict[str, Any]]:
    q = question.lower()
    scored: list[tuple[int, dict[str, Any]]] = []
    for item in KB:
        score = 0
        text = f"{item['title']} {item['text']}".lower()
        for token in ("refund", "pro", "free", "sla", "support"):
            if token in q and token in text:
                score += 1
        scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:limit]]


def build_context(snippets: list[dict[str, Any]], max_chars: int = 700) -> str:
    parts: list[str] = []
    total = 0
    for s in snippets:
        line = f"[{s['id']}] {s['title']}: {s['text']}\n"
        if total + len(line) > max_chars:
            break
        parts.append(line)
        total += len(line)
    return "".join(parts).strip()
