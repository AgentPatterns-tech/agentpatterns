from __future__ import annotations

from typing import Any


def propose_research_plan(*, goal: str, request: dict[str, Any]) -> dict[str, Any]:
    del goal
    query = request["request"]["question"]
    return {
        "steps": [
            {
                "id": "r1",
                "action": "search_sources",
                "args": {
                    "query": query,
                },
            },
            {"id": "r2", "action": "dedupe_urls", "args": {}},
            {"id": "r3", "action": "read_extract_notes", "args": {}},
            {"id": "r4", "action": "verify_notes", "args": {}},
            {"id": "r5", "action": "synthesize_answer", "args": {}},
        ]
    }


def synthesize_from_notes(*, goal: str, notes: list[dict[str, Any]]) -> dict[str, Any]:
    del goal
    if not notes:
        return {
            "answer": "",
            "citations": [],
        }

    selected = notes[:3]
    citations = [str(item["id"]) for item in selected]

    claims = [str(item["claim"]).strip() for item in selected]
    answer = (
        "Research brief: "
        + " ".join(claims)
        + " Timeline values are estimates and may change."
    )

    return {
        "answer": answer,
        "citations": citations,
    }
