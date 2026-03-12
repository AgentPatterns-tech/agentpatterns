from __future__ import annotations

import json
import time
import uuid
from typing import Any

from agent import propose_research_plan, synthesize_from_notes
from context import build_request
from gateway import Budget, ResearchGateway, StopRun, dedupe_urls, validate_plan
from tools import extract_notes_from_page, read_source, search_sources, verify_notes

GOAL = (
    "Research current US payments incident status and enterprise SLA commitments, "
    "then return a concise grounded summary with citations."
)
REQUEST = build_request(
    report_date="2026-03-07",
    region="US",
)

DEFAULT_BUDGET = Budget(
    max_seconds=25,
    max_steps=8,
    max_urls=6,
    max_read_pages=3,
    max_notes=6,
    max_answer_chars=850,
)


def _unwrap_tool_data(raw: Any, *, tool_name: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or raw.get("status") != "ok" or not isinstance(raw.get("data"), dict):
        raise StopRun(f"tool_invalid_output:{tool_name}")
    return dict(raw["data"])


def _safe_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def run_research_agent(*, goal: str, request: dict[str, Any]) -> dict[str, Any]:
    run_id = str(uuid.uuid4())
    started = time.monotonic()
    trace: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []

    hints_raw = request.get("policy_hints")
    hints: dict[str, Any] = hints_raw if isinstance(hints_raw, dict) else {}

    allowed_domains_policy_raw = hints.get("allowed_domains_policy")
    if isinstance(allowed_domains_policy_raw, list):
        allowed_domains_policy = {
            str(item).strip().lower()
            for item in allowed_domains_policy_raw
            if isinstance(item, str) and item.strip()
        }
    else:
        allowed_domains_policy = {
            "official-status.example.com",
            "vendor.example.com",
            "regulator.example.org",
        }

    allowed_domains_execution_raw = hints.get("allowed_domains_execution")
    if isinstance(allowed_domains_execution_raw, list):
        allowed_domains_execution = {
            str(item).strip().lower()
            for item in allowed_domains_execution_raw
            if isinstance(item, str) and item.strip()
        }
    else:
        allowed_domains_execution = {
            "official-status.example.com",
            "vendor.example.com",
        }

    max_urls = _safe_int(hints.get("max_urls", DEFAULT_BUDGET.max_urls), default=DEFAULT_BUDGET.max_urls)
    max_read_pages = _safe_int(hints.get("max_read_pages", DEFAULT_BUDGET.max_read_pages), default=DEFAULT_BUDGET.max_read_pages)
    max_notes = _safe_int(hints.get("max_notes", DEFAULT_BUDGET.max_notes), default=DEFAULT_BUDGET.max_notes)
    max_answer_chars = _safe_int(hints.get("max_answer_chars", DEFAULT_BUDGET.max_answer_chars), default=DEFAULT_BUDGET.max_answer_chars)

    budget = Budget(
        max_seconds=DEFAULT_BUDGET.max_seconds,
        max_steps=DEFAULT_BUDGET.max_steps,
        max_urls=max(1, min(20, max_urls)),
        max_read_pages=max(1, min(10, max_read_pages)),
        max_notes=max(1, min(20, max_notes)),
        max_answer_chars=max(120, min(2000, max_answer_chars)),
    )

    gateway = ResearchGateway(
        allowed_domains_policy=allowed_domains_policy,
        allowed_domains_execution=allowed_domains_execution,
        budget=budget,
    )

    def elapsed_ms() -> int:
        return max(1, int((time.monotonic() - started) * 1000))

    def stopped(stop_reason: str, *, phase: str, **extra: Any) -> dict[str, Any]:
        payload = {
            "run_id": run_id,
            "status": "stopped",
            "stop_reason": stop_reason,
            "phase": phase,
            "trace": trace,
            "history": history,
        }
        payload.update(extra)
        return payload

    phase = "plan"
    try:
        if (time.monotonic() - started) > budget.max_seconds:
            return stopped("max_seconds", phase=phase)

        raw_plan = propose_research_plan(goal=goal, request=request)
        steps = validate_plan(raw_plan.get("steps"), max_steps=budget.max_steps)

        trace.append(
            {
                "step": 1,
                "phase": "plan",
                "steps": len(steps),
                "elapsed_ms": elapsed_ms(),
                "ok": True,
            }
        )
        history.append(
            {
                "step": 1,
                "action": "propose_research_plan",
                "step_ids": [step["id"] for step in steps],
            }
        )

        phase = "search"
        query = str(steps[0]["args"].get("query", "")).strip()
        if not query:
            return stopped("invalid_search:query", phase=phase)

        search_data = _unwrap_tool_data(
            search_sources(query=query, k=budget.max_urls * 2),
            tool_name="search_sources",
        )
        search_results = list(search_data.get("results", []))
        candidate_urls = [str(item.get("url", "")).strip() for item in search_results if isinstance(item, dict)]

        trace.append(
            {
                "step": 2,
                "phase": "search",
                "query": query,
                "candidates": len(candidate_urls),
                "elapsed_ms": elapsed_ms(),
                "ok": True,
            }
        )
        history.append(
            {
                "step": 2,
                "action": "search_sources",
                "query": query,
                "candidates": len(candidate_urls),
            }
        )

        phase = "dedupe"
        deduped_urls = dedupe_urls(raw_urls=candidate_urls, max_urls=budget.max_urls)
        if not deduped_urls:
            return stopped("no_sources_after_dedupe", phase=phase)

        trace.append(
            {
                "step": 3,
                "phase": "dedupe",
                "urls_after_dedupe": len(deduped_urls),
                "elapsed_ms": elapsed_ms(),
                "ok": True,
            }
        )
        history.append(
            {
                "step": 3,
                "action": "dedupe_urls",
                "urls_after_dedupe": len(deduped_urls),
            }
        )

        phase = "read_extract"
        notes: list[dict[str, Any]] = []
        read_urls: list[str] = []
        denied_sources: list[dict[str, str]] = []

        for url in deduped_urls:
            if (time.monotonic() - started) > budget.max_seconds:
                return stopped("max_seconds", phase=phase)

            decision = gateway.evaluate_source(url=url)
            if decision.kind != "allow":
                denied_sources.append({"url": url, "reason": decision.reason})
                continue

            if len(read_urls) >= budget.max_read_pages:
                break

            page = _unwrap_tool_data(
                read_source(url=url),
                tool_name="read_source",
            )

            extracted = extract_notes_from_page(url=url, page=page)
            for item in extracted:
                note = dict(item)
                note["id"] = f"n{len(notes) + 1}"
                notes.append(note)
                if len(notes) >= budget.max_notes:
                    break

            read_urls.append(url)
            if len(notes) >= budget.max_notes:
                break

        if not notes:
            return stopped(
                "no_reliable_sources",
                phase=phase,
                denied_sources=denied_sources,
            )

        gateway.validate_notes(notes=notes)

        trace.append(
            {
                "step": 4,
                "phase": "read_extract",
                "pages_read": len(read_urls),
                "notes": len(notes),
                "denied_sources": len(denied_sources),
                "elapsed_ms": elapsed_ms(),
                "ok": True,
            }
        )
        history.append(
            {
                "step": 4,
                "action": "read_extract_notes",
                "pages_read": len(read_urls),
                "denied_sources": denied_sources,
            }
        )

        phase = "verify"
        verification = _unwrap_tool_data(
            verify_notes(notes=notes),
            tool_name="verify_notes",
        )
        if not bool(verification.get("ok")):
            issues = verification.get("issues") or []
            first = str(issues[0]) if issues else "unknown"
            return stopped(f"verification_failed:{first}", phase=phase, verification=verification)

        trace.append(
            {
                "step": 5,
                "phase": "verify",
                "checked_notes": int(verification.get("checked_notes", 0)),
                "issues": len(verification.get("issues", [])),
                "elapsed_ms": elapsed_ms(),
                "ok": True,
            }
        )
        history.append(
            {
                "step": 5,
                "action": "verify_notes",
                "checked_notes": int(verification.get("checked_notes", 0)),
            }
        )

        phase = "synthesize"
        synthesis = synthesize_from_notes(goal=goal, notes=notes)
        answer = str(synthesis.get("answer", "")).strip()
        citations = [str(item).strip() for item in synthesis.get("citations", []) if str(item).strip()]

        gateway.validate_synthesis(answer=answer, citations=citations, notes=notes)

        aggregate = {
            "query": query,
            "urls_found": len(candidate_urls),
            "urls_after_dedupe": len(deduped_urls),
            "pages_read": len(read_urls),
            "notes_count": len(notes),
            "citations_count": len(citations),
            "denied_sources": denied_sources,
            "verified_notes": int(verification.get("checked_notes", 0)),
        }

        trace.append(
            {
                "step": 6,
                "phase": "synthesize",
                "answer_chars": len(answer),
                "citations": len(citations),
                "elapsed_ms": elapsed_ms(),
                "ok": True,
            }
        )
        history.append(
            {
                "step": 6,
                "action": "synthesize_answer",
                "citations": citations,
            }
        )

        return {
            "run_id": run_id,
            "status": "ok",
            "stop_reason": "success",
            "outcome": "grounded_research_answer",
            "answer": answer,
            "citations": citations,
            "citation_details": [
                {
                    "id": str(note["id"]),
                    "url": str(note["url"]),
                    "title": str(note["title"]),
                    "published_at": str(note["published_at"]),
                }
                for note in notes
                if str(note["id"]) in set(citations)
            ],
            "aggregate": aggregate,
            "trace": trace,
            "history": history,
        }

    except StopRun as exc:
        return stopped(
            exc.reason,
            phase=phase,
            **({"details": exc.details} if isinstance(exc.details, dict) and exc.details else {}),
        )


def main() -> None:
    result = run_research_agent(goal=GOAL, request=REQUEST)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
