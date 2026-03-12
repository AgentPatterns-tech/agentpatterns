from __future__ import annotations

import json
import time
from typing import Any

from gateway import (
    Budget,
    CollaborationGateway,
    StopRun,
    decide_round_outcome,
    detect_conflicts,
)
from llm import LLMEmpty, LLMTimeout, compose_final_answer, propose_contribution
from signals import build_shared_context

REPORT_DATE = "2026-03-02"
REGION = "US"
GOAL = (
    "Prepare a go/no-go launch brief for Checkout v2 campaign in US on 2026-03-02. "
    "Use collaboration across demand, finance, and risk analysts; return one aligned decision."
)

BUDGET = Budget(max_rounds=3, max_messages=12, max_seconds=40, min_go_votes=2)

TEAM_ROLES_POLICY = {
    "demand_analyst",
    "finance_analyst",
    "risk_analyst",
    "legal_analyst",
}
LEGAL_ANALYST_ENABLED = False
TEAM_ROLES_EXECUTION = (
    TEAM_ROLES_POLICY
    if LEGAL_ANALYST_ENABLED
    else {"demand_analyst", "finance_analyst", "risk_analyst"}
)

TEAM_SEQUENCE = ["demand_analyst", "finance_analyst", "risk_analyst"]
# Set LEGAL_ANALYST_ENABLED=True and append "legal_analyst" to TEAM_SEQUENCE to test runtime denial paths.



def _latest_stances(contributions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "agent": item["agent"],
            "stance": item["stance"],
            "confidence": item["confidence"],
        }
        for item in contributions
    ]



def run_collaboration(goal: str) -> dict[str, Any]:
    started = time.monotonic()
    shared_context = build_shared_context(report_date=REPORT_DATE, region=REGION)

    history: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = []
    open_conflicts: list[str] = []
    final_decision: str | None = None

    gateway = CollaborationGateway(allow=TEAM_ROLES_EXECUTION, budget=BUDGET)

    for round_no in range(1, BUDGET.max_rounds + 1):
        if (time.monotonic() - started) > BUDGET.max_seconds:
            return {
                "status": "stopped",
                "stop_reason": "max_seconds",
                "trace": trace,
                "history": history,
            }

        round_contributions: list[dict[str, Any]] = []

        for role in TEAM_SEQUENCE:
            try:
                raw = propose_contribution(
                    role=role,
                    goal=goal,
                    shared_context=shared_context,
                    history=history,
                    open_conflicts=open_conflicts,
                )
            except LLMTimeout:
                return {
                    "status": "stopped",
                    "stop_reason": "llm_timeout",
                    "phase": f"round_{round_no}:{role}",
                    "trace": trace,
                    "history": history,
                }

            try:
                contribution = gateway.accept(raw, expected_agent=role)
            except StopRun as exc:
                return {
                    "status": "stopped",
                    "stop_reason": exc.reason,
                    "phase": f"round_{round_no}:{role}",
                    "raw_contribution": raw,
                    "trace": trace,
                    "history": history,
                }

            round_contributions.append(contribution)
            trace.append(
                {
                    "round": round_no,
                    "agent": role,
                    "stance": contribution["stance"],
                    "confidence": contribution["confidence"],
                    "accepted": True,
                }
            )

        conflicts = detect_conflicts(round_contributions)
        round_decision = decide_round_outcome(
            round_contributions,
            min_go_votes=BUDGET.min_go_votes,
        )

        history_entry = {
            "round": round_no,
            "contributions": round_contributions,
            "conflicts": conflicts,
            "decision": round_decision,
        }
        history.append(history_entry)

        trace.append(
            {
                "round": round_no,
                "conflicts": conflicts,
                "decision": round_decision or "next_round",
            }
        )

        if round_decision:
            final_decision = round_decision
            break

        open_conflicts = conflicts

    if not final_decision:
        return {
            "status": "stopped",
            "stop_reason": "max_rounds_reached",
            "trace": trace,
            "history": history,
        }

    try:
        answer = compose_final_answer(
            goal=goal,
            final_decision=final_decision,
            history=history,
        )
    except LLMTimeout:
        return {
            "status": "stopped",
            "stop_reason": "llm_timeout",
            "phase": "finalize",
            "trace": trace,
            "history": history,
        }
    except LLMEmpty:
        return {
            "status": "stopped",
            "stop_reason": "llm_empty",
            "phase": "finalize",
            "trace": trace,
            "history": history,
        }

    last_round = history[-1]
    return {
        "status": "ok",
        "stop_reason": "success",
        "answer": answer,
        "final_decision": final_decision,
        "rounds_used": len(history),
        "team_summary": {
            "report_date": REPORT_DATE,
            "region": REGION,
            "stances": _latest_stances(last_round["contributions"]),
            "conflicts": last_round["conflicts"],
        },
        "trace": trace,
        "history": history,
    }



def main() -> None:
    result = run_collaboration(GOAL)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
