from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse


class StopRun(Exception):
    def __init__(self, reason: str, *, details: dict[str, Any] | None = None):
        super().__init__(reason)
        self.reason = reason
        self.details = details or {}


@dataclass(frozen=True)
class Budget:
    max_seconds: int = 25
    max_steps: int = 8
    max_urls: int = 6
    max_read_pages: int = 3
    max_notes: int = 6
    max_answer_chars: int = 850


@dataclass(frozen=True)
class Decision:
    kind: str
    reason: str


EXPECTED_ACTION_SEQUENCE = [
    "search_sources",
    "dedupe_urls",
    "read_extract_notes",
    "verify_notes",
    "synthesize_answer",
]


def normalize_url(url: str) -> str:
    parsed = urlparse(str(url).strip())
    scheme = (parsed.scheme or "https").lower()
    host = parsed.netloc.lower()
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return f"{scheme}://{host}{path}"


def get_domain(url: str) -> str:
    return urlparse(str(url).strip()).netloc.lower()


def validate_plan(raw_steps: Any, *, max_steps: int) -> list[dict[str, Any]]:
    if not isinstance(raw_steps, list) or not raw_steps:
        raise StopRun("invalid_plan:steps")
    if len(raw_steps) > max_steps:
        raise StopRun("invalid_plan:too_many_steps")

    out: list[dict[str, Any]] = []
    actions: list[str] = []

    for raw in raw_steps:
        if not isinstance(raw, dict):
            raise StopRun("invalid_step:not_object")
        step_id = raw.get("id")
        action = raw.get("action")
        args = raw.get("args")

        if not isinstance(step_id, str) or not step_id.strip():
            raise StopRun("invalid_step:id")
        if not isinstance(action, str) or not action.strip():
            raise StopRun("invalid_step:action")
        if not isinstance(args, dict):
            raise StopRun("invalid_step:args")

        normalized = {
            "id": step_id.strip(),
            "action": action.strip(),
            "args": dict(args),
        }
        out.append(normalized)
        actions.append(normalized["action"])

    if actions != EXPECTED_ACTION_SEQUENCE:
        raise StopRun(
            "invalid_plan:step_sequence",
            details={"expected": EXPECTED_ACTION_SEQUENCE, "received": actions},
        )

    return out


def dedupe_urls(*, raw_urls: list[str], max_urls: int) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in raw_urls:
        normalized = normalize_url(raw)
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
        if len(out) >= max_urls:
            break
    return out


class ResearchGateway:
    def __init__(
        self,
        *,
        allowed_domains_policy: set[str],
        allowed_domains_execution: set[str],
        budget: Budget,
    ):
        self.allowed_domains_policy = {d.lower() for d in allowed_domains_policy}
        self.allowed_domains_execution = {d.lower() for d in allowed_domains_execution}
        self.budget = budget

    def evaluate_source(self, *, url: str) -> Decision:
        domain = get_domain(url)
        if domain not in self.allowed_domains_policy:
            return Decision(kind="deny", reason="source_denied_policy")
        if domain not in self.allowed_domains_execution:
            return Decision(kind="deny", reason="source_denied_execution")
        return Decision(kind="allow", reason="policy_pass")

    def validate_notes(self, *, notes: list[dict[str, Any]]) -> None:
        if not isinstance(notes, list) or not notes:
            raise StopRun("invalid_notes:empty")
        if len(notes) > self.budget.max_notes:
            raise StopRun("invalid_notes:too_many")

        for note in notes:
            if not isinstance(note, dict):
                raise StopRun("invalid_notes:item")
            if not isinstance(note.get("id"), str) or not note["id"].strip():
                raise StopRun("invalid_notes:id")
            if not isinstance(note.get("url"), str) or not note["url"].strip():
                raise StopRun("invalid_notes:url")
            if not isinstance(note.get("claim"), str) or not note["claim"].strip():
                raise StopRun("invalid_notes:claim")
            quote = note.get("quote")
            if not isinstance(quote, str) or len(quote.strip()) < 20:
                raise StopRun("invalid_notes:quote")

    def validate_synthesis(self, *, answer: str, citations: list[str], notes: list[dict[str, Any]]) -> None:
        if not isinstance(answer, str) or not answer.strip():
            raise StopRun("invalid_answer:empty")
        if len(answer) > self.budget.max_answer_chars:
            raise StopRun("invalid_answer:too_long")

        if not isinstance(citations, list) or not citations:
            raise StopRun("invalid_answer:citations")

        note_ids = {str(item["id"]) for item in notes}
        for citation in citations:
            if str(citation) not in note_ids:
                raise StopRun("invalid_answer:citation_unknown")
