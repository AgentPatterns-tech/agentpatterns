from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class StopRun(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Budget:
    max_rounds: int = 3
    max_messages: int = 12
    max_seconds: int = 40
    min_go_votes: int = 2


ALLOWED_STANCES = {"go", "caution", "block"}



def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)



def validate_contribution(raw: Any, *, allowed_agents: set[str]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise StopRun("invalid_contribution:not_object")

    required = {"agent", "stance", "summary", "confidence", "actions"}
    if not required.issubset(raw.keys()):
        raise StopRun("invalid_contribution:missing_keys")

    agent = raw["agent"]
    stance = raw["stance"]
    summary = raw["summary"]
    confidence = raw["confidence"]
    actions = raw["actions"]

    if not isinstance(agent, str) or not agent.strip():
        raise StopRun("invalid_contribution:agent")
    agent = agent.strip()
    if agent not in allowed_agents:
        raise StopRun(f"invalid_contribution:agent_not_allowed:{agent}")

    if not isinstance(stance, str) or stance.strip() not in ALLOWED_STANCES:
        raise StopRun("invalid_contribution:stance")
    stance = stance.strip()

    if not isinstance(summary, str) or not summary.strip():
        raise StopRun("invalid_contribution:summary")

    if not _is_number(confidence):
        raise StopRun("invalid_contribution:confidence_type")
    confidence = float(confidence)
    if not (0.0 <= confidence <= 1.0):
        raise StopRun("invalid_contribution:confidence_range")

    if not isinstance(actions, list) or not actions:
        raise StopRun("invalid_contribution:actions")

    normalized_actions: list[str] = []
    for item in actions:
        if not isinstance(item, str) or not item.strip():
            raise StopRun("invalid_contribution:action_item")
        normalized_actions.append(item.strip())

    # Ignore unknown keys to tolerate extra LLM fields.
    return {
        "agent": agent,
        "stance": stance,
        "summary": summary.strip(),
        "confidence": round(confidence, 3),
        "actions": normalized_actions[:3],
    }



def detect_conflicts(contributions: list[dict[str, Any]]) -> list[str]:
    if not contributions:
        return ["no_contributions"]

    stances = {item["stance"] for item in contributions}
    conflicts: list[str] = []

    if "go" in stances and "caution" in stances and "block" not in stances:
        conflicts.append("go_vs_caution")
    if "block" in stances and len(stances) > 1:
        conflicts.append("blocking_vs_non_block")
    if len(stances) == 3:
        conflicts.append("high_divergence")

    return conflicts



def decide_round_outcome(
    contributions: list[dict[str, Any]],
    *,
    min_go_votes: int,
) -> str | None:
    go_votes = sum(1 for item in contributions if item["stance"] == "go")
    caution_votes = sum(1 for item in contributions if item["stance"] == "caution")
    block_votes = sum(1 for item in contributions if item["stance"] == "block")

    if block_votes >= 2:
        return "no_go"

    if block_votes > 0:
        return None
    if go_votes >= min_go_votes and caution_votes == 0:
        return "go"
    if go_votes >= min_go_votes and caution_votes > 0:
        return "go_with_caution"
    return None


class CollaborationGateway:
    def __init__(self, *, allow: set[str], budget: Budget):
        self.allow = set(allow)
        self.budget = budget
        self.message_count = 0

    def _consume_message_budget(self) -> None:
        self.message_count += 1
        if self.message_count > self.budget.max_messages:
            raise StopRun("max_messages")

    def accept(self, raw: Any, *, expected_agent: str) -> dict[str, Any]:
        if expected_agent not in self.allow:
            raise StopRun(f"agent_denied:{expected_agent}")

        self._consume_message_budget()
        contribution = validate_contribution(raw, allowed_agents=self.allow)

        if contribution["agent"] != expected_agent:
            raise StopRun(f"invalid_contribution:agent_mismatch:{expected_agent}")

        return contribution
