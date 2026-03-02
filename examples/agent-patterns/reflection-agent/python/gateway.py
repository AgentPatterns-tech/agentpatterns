from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any


class StopRun(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Budget:
    max_seconds: int = 30
    max_draft_chars: int = 900
    max_review_issues: int = 4
    max_fix_items: int = 4
    max_answer_chars: int = 900
    min_patch_similarity: float = 0.45


NUMBER_TOKEN_RE = re.compile(r"\b\d+(?:\.\d+)?%?\b")
INCIDENT_ID_RE = re.compile(r"\binc_[a-z0-9_]+\b", re.IGNORECASE)
SEVERITY_RE = re.compile(r"\bp[0-5]\b", re.IGNORECASE)
REGION_RE = re.compile(r"\b(us|eu|uk|ua|apac|global|emea|latam)\b", re.IGNORECASE)
QUOTED_PHRASE_RE = re.compile(r"['\"]([^'\"]{3,120})['\"]")

RESTRICTED_CLAIMS_RE = [
    re.compile(r"\bresolved\b", re.IGNORECASE),
    re.compile(r"\bfully[-\s]+recovered\b", re.IGNORECASE),
    re.compile(r"\bincident\s+closed\b", re.IGNORECASE),
    re.compile(r"\ball payments (?:are|is)\s+stable\b", re.IGNORECASE),
]


def _stable_json(value: Any) -> str:
    if value is None or isinstance(value, (bool, int, float, str)):
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    if isinstance(value, list):
        return "[" + ",".join(_stable_json(v) for v in value) + "]"
    if isinstance(value, dict):
        parts = []
        for key in sorted(value):
            parts.append(json.dumps(str(key), ensure_ascii=True) + ":" + _stable_json(value[key]))
        return "{" + ",".join(parts) + "}"
    return json.dumps(str(value), ensure_ascii=True)


def _normalize_space(text: str) -> str:
    return " ".join((text or "").strip().split())


def text_hash(text: str) -> str:
    normalized = _normalize_space(text)
    raw = _stable_json(normalized)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _extract_number_tokens(text: str) -> set[str]:
    normalized = _normalize_space(text).lower()
    return set(NUMBER_TOKEN_RE.findall(normalized))


def _extract_incident_ids(text: str) -> set[str]:
    normalized = _normalize_space(text).lower()
    return set(INCIDENT_ID_RE.findall(normalized))


def _extract_severity_labels(text: str) -> set[str]:
    normalized = _normalize_space(text).upper()
    return {match.upper() for match in SEVERITY_RE.findall(normalized)}


def _extract_regions(text: str) -> set[str]:
    normalized = _normalize_space(text).upper()
    return {value.upper() for value in REGION_RE.findall(normalized)}


def _extract_fix_plan_phrase_rules(fix_plan: list[str]) -> dict[str, list[str]]:
    must_include: list[str] = []
    must_remove: list[str] = []

    def _append_unique(target: list[str], value: str) -> None:
        if value and value not in target:
            target.append(value)

    for item in fix_plan:
        item_norm = _normalize_space(item).lower()
        quoted = [_normalize_space(match).lower() for match in QUOTED_PHRASE_RE.findall(item)]
        quoted = [value for value in quoted if value]
        if not quoted:
            continue

        is_replace = "replace" in item_norm
        is_modify = any(word in item_norm for word in ("modify", "change", "update", "rewrite"))
        has_with = " with " in f" {item_norm} "
        has_example_marker = any(
            marker in item_norm for marker in ("such as", "for example", "e.g.", "e.g")
        )

        if is_replace or is_modify:
            _append_unique(must_remove, quoted[0])

            # Enforce phrase add only for strict replace-with instructions, not modify/example hints.
            if is_replace and len(quoted) >= 2 and has_with and not has_example_marker:
                _append_unique(must_include, quoted[1])
            continue

        for phrase in quoted:
            _append_unique(must_include, phrase)

    return {
        "must_include": must_include,
        "must_remove": must_remove,
    }


def _context_claim_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (bool, int, float)):
        return str(value)
    if isinstance(value, list):
        return " ".join(_context_claim_text(item) for item in value)
    if isinstance(value, dict):
        parts: list[str] = []
        for key, item in value.items():
            parts.append(str(key))
            parts.append(_context_claim_text(item))
        return " ".join(parts)
    return str(value)


def _is_high_risk_issue(issue_type: str) -> bool:
    return issue_type in {"legal_risk", "policy_violation"}


def validate_draft(draft: Any, *, max_chars: int) -> str:
    if not isinstance(draft, str) or not draft.strip():
        raise StopRun("invalid_draft:empty")
    normalized = draft.strip()
    if len(normalized) > max_chars:
        raise StopRun("invalid_draft:too_long")
    return normalized


def validate_review(
    raw: Any,
    *,
    allowed_decisions_policy: set[str],
    allowed_issue_types_policy: set[str],
    max_review_issues: int,
    max_fix_items: int,
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise StopRun("invalid_review:not_object")

    decision = raw.get("decision")
    if not isinstance(decision, str) or not decision.strip():
        raise StopRun("invalid_review:decision")
    decision = decision.strip()
    if decision not in allowed_decisions_policy:
        raise StopRun(f"review_decision_not_allowed_policy:{decision}")

    issues_raw = raw.get("issues", [])
    if not isinstance(issues_raw, list):
        raise StopRun("invalid_review:issues")
    if len(issues_raw) > max_review_issues:
        raise StopRun("invalid_review:too_many_issues")

    issues: list[dict[str, str]] = []
    for item in issues_raw:
        if not isinstance(item, dict):
            raise StopRun("invalid_review:issue_item")

        issue_type = item.get("type")
        note = item.get("note")

        if not isinstance(issue_type, str) or not issue_type.strip():
            raise StopRun("invalid_review:issue_type")
        issue_type = issue_type.strip()
        if issue_type not in allowed_issue_types_policy:
            raise StopRun(f"review_issue_not_allowed_policy:{issue_type}")

        if not isinstance(note, str) or not note.strip():
            raise StopRun("invalid_review:issue_note")

        issues.append({"type": issue_type, "note": note.strip()})

    fix_plan_raw = raw.get("fix_plan", [])
    if not isinstance(fix_plan_raw, list):
        raise StopRun("invalid_review:fix_plan")
    if len(fix_plan_raw) > max_fix_items:
        raise StopRun("invalid_review:too_many_fix_items")

    fix_plan: list[str] = []
    for item in fix_plan_raw:
        if not isinstance(item, str) or not item.strip():
            raise StopRun("invalid_review:fix_item")
        fix_plan.append(item.strip())

    reason = raw.get("reason", "")
    if reason is None:
        reason = ""
    if not isinstance(reason, str):
        raise StopRun("invalid_review:reason")
    reason = reason.strip()

    if decision == "approve":
        if issues and any(_is_high_risk_issue(issue["type"]) for issue in issues):
            raise StopRun("invalid_review:approve_with_high_risk_issue")
        return {
            "decision": "approve",
            "issues": issues,
            "fix_plan": [],
            "reason": reason,
            "high_risk": False,
        }

    if decision == "revise":
        if not issues:
            raise StopRun("invalid_review:revise_without_issues")
        if not fix_plan:
            raise StopRun("invalid_review:revise_without_fix_plan")
        if any(_is_high_risk_issue(issue["type"]) for issue in issues):
            raise StopRun("invalid_review:high_risk_requires_escalate")
        return {
            "decision": "revise",
            "issues": issues,
            "fix_plan": fix_plan,
            "reason": reason,
            "high_risk": False,
        }

    if decision == "escalate":
        if not reason:
            raise StopRun("invalid_review:escalate_reason_required")
        return {
            "decision": "escalate",
            "issues": issues,
            "fix_plan": [],
            "reason": reason,
            "high_risk": True,
        }

    raise StopRun("invalid_review:unknown_decision")


class ReflectionGateway:
    def __init__(
        self,
        *,
        allow_execution_decisions: set[str],
        budget: Budget,
    ):
        self.allow_execution_decisions = set(allow_execution_decisions)
        self.budget = budget

    def enforce_execution_decision(self, decision: str) -> None:
        if decision not in self.allow_execution_decisions:
            raise StopRun(f"review_decision_denied_execution:{decision}")

    def validate_revision(
        self,
        *,
        original: str,
        revised: str,
        context: dict[str, Any],
        fix_plan: list[str] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(revised, str) or not revised.strip():
            raise StopRun("invalid_revised:empty")

        revised_clean = revised.strip()
        if len(revised_clean) > self.budget.max_answer_chars:
            raise StopRun("invalid_revised:too_long")

        normalized_original = _normalize_space(original)
        normalized_revised = _normalize_space(revised_clean)
        if normalized_original == normalized_revised:
            raise StopRun("invalid_revised:no_changes")

        similarity = SequenceMatcher(a=normalized_original, b=normalized_revised).ratio()
        if similarity < self.budget.min_patch_similarity:
            raise StopRun("patch_violation:too_large_edit")

        allowed_text_tokens = _stable_json(context) + " " + original
        allowed_text_claims = _normalize_space(_context_claim_text(context) + " " + original)
        revised_numbers = _extract_number_tokens(revised_clean)
        allowed_numbers = _extract_number_tokens(allowed_text_tokens)
        if revised_numbers - allowed_numbers:
            raise StopRun("patch_violation:no_new_facts")

        revised_ids = _extract_incident_ids(revised_clean)
        allowed_ids = _extract_incident_ids(allowed_text_tokens)
        if revised_ids - allowed_ids:
            raise StopRun("patch_violation:new_incident_id")

        revised_severity = _extract_severity_labels(revised_clean)
        allowed_severity = _extract_severity_labels(allowed_text_tokens)
        if revised_severity - allowed_severity:
            raise StopRun("patch_violation:new_severity_label")

        revised_regions = _extract_regions(revised_clean)
        allowed_regions = _extract_regions(allowed_text_tokens)
        if revised_regions - allowed_regions:
            raise StopRun("patch_violation:new_region")

        for claim_re in RESTRICTED_CLAIMS_RE:
            if claim_re.search(revised_clean) and not claim_re.search(allowed_text_claims):
                raise StopRun("patch_violation:restricted_claims")

        phrase_rules = _extract_fix_plan_phrase_rules(fix_plan or [])
        must_include = phrase_rules["must_include"]
        must_remove = phrase_rules["must_remove"]
        if must_include or must_remove:
            revised_lower = _normalize_space(revised_clean).lower()
            missing = [phrase for phrase in must_include if phrase not in revised_lower]
            if missing:
                raise StopRun("patch_violation:fix_plan_not_applied")
            still_present = [phrase for phrase in must_remove if phrase in revised_lower]
            if still_present:
                raise StopRun("patch_violation:fix_plan_not_applied")

        return {
            "answer": revised_clean,
            "patch_similarity": round(similarity, 3),
            "fix_plan_quoted_checks": len(must_include) + len(must_remove),
        }

    def validate_final(self, answer: str) -> str:
        if not isinstance(answer, str) or not answer.strip():
            raise StopRun("invalid_answer:empty")

        cleaned = answer.strip()
        if len(cleaned) > self.budget.max_answer_chars:
            raise StopRun("invalid_answer:too_long")
        return cleaned
