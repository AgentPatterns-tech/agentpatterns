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
    max_seconds: int = 120
    max_draft_chars: int = 900
    max_risks: int = 5
    max_required_changes: int = 5
    max_answer_chars: int = 980
    max_length_increase_pct: float = 20.0
    min_patch_similarity: float = 0.4


NUMBER_TOKEN_RE = re.compile(r"\b\d+(?:\.\d+)?%?\b")
INCIDENT_ID_RE = re.compile(r"\binc_[a-z0-9_]+\b", re.IGNORECASE)
SEVERITY_RE = re.compile(r"\bp[0-5]\b", re.IGNORECASE)
REGION_RE = re.compile(r"\b(us|eu|uk|ua|apac|global|emea|latam)\b", re.IGNORECASE)
QUOTED_PHRASE_RE = re.compile(r"['\"]([^'\"]{3,160})['\"]")

RESTRICTED_CLAIMS_RE = [
    re.compile(r"\bresolved\b", re.IGNORECASE),
    re.compile(r"\bfully[-\s]+recovered\b", re.IGNORECASE),
    re.compile(r"\bincident\s+closed\b", re.IGNORECASE),
    re.compile(r"\ball payments (?:are|is)\s+stable\b", re.IGNORECASE),
]

ALLOWED_SEVERITY = {"low", "medium", "high"}



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
    return set(NUMBER_TOKEN_RE.findall(_normalize_space(text).lower()))



def _extract_incident_ids(text: str) -> set[str]:
    return set(INCIDENT_ID_RE.findall(_normalize_space(text).lower()))



def _extract_severity_labels(text: str) -> set[str]:
    normalized = _normalize_space(text).upper()
    return {match.upper() for match in SEVERITY_RE.findall(normalized)}



def _extract_regions(text: str) -> set[str]:
    normalized = _normalize_space(text).upper()
    return {value.upper() for value in REGION_RE.findall(normalized)}



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
        for key in sorted(value):
            item = value[key]
            parts.append(str(key))
            parts.append(_context_claim_text(item))
        return " ".join(parts)
    return str(value)



def _extract_required_change_rules(required_changes: list[str]) -> dict[str, list[str]]:
    must_include: list[str] = []
    must_remove: list[str] = []

    def _append_unique(target: list[str], value: str) -> None:
        if value and value not in target:
            target.append(value)

    for item in required_changes:
        item_norm = _normalize_space(item).lower()
        quoted = [_normalize_space(match).lower() for match in QUOTED_PHRASE_RE.findall(item)]
        quoted = [value for value in quoted if value]
        if not quoted:
            continue

        # Keep extraction deterministic and explicit:
        # - REMOVE/MUST_REMOVE => must_remove
        # - ADD/MUST_INCLUDE   => must_include
        # - otherwise          => must_include
        is_remove_rule = ("must_remove" in item_norm) or item_norm.startswith(
            ("remove ", "remove:", "remove-")
        )
        is_add_rule = ("must_include" in item_norm) or item_norm.startswith(
            ("add ", "add:", "add-")
        )

        if is_remove_rule:
            for phrase in quoted:
                _append_unique(must_remove, phrase)
            continue
        if is_add_rule:
            for phrase in quoted:
                _append_unique(must_include, phrase)
            continue

        for phrase in quoted:
            _append_unique(must_include, phrase)

    return {
        "must_include": must_include,
        "must_remove": must_remove,
    }



def _is_high_risk_risk_type(risk_type: str) -> bool:
    return risk_type in {"legal_risk", "policy_violation"}


def _is_enforceable_required_change(item: str) -> bool:
    item_norm = _normalize_space(item).lower()
    prefixes = (
        "add ",
        "add:",
        "add-",
        "remove ",
        "remove:",
        "remove-",
        "must_include ",
        "must_include:",
        "must_include-",
        "must_remove ",
        "must_remove:",
        "must_remove-",
    )
    if not item_norm.startswith(prefixes):
        return False

    # Contract: one enforceable phrase per instruction.
    quoted_count = len(QUOTED_PHRASE_RE.findall(item))
    return quoted_count == 1


def _contains_normalized_phrase(*, text: str, phrase: str) -> bool:
    # Compare using token-like normalization so punctuation differences
    # (e.g. trailing dots/commas) do not cause false negatives.
    normalized_text = re.sub(r"[^a-z0-9% ]+", " ", _normalize_space(text).lower())
    normalized_phrase = re.sub(r"[^a-z0-9% ]+", " ", _normalize_space(phrase).lower())
    normalized_text = " ".join(normalized_text.split())
    normalized_phrase = " ".join(normalized_phrase.split())
    return normalized_phrase in normalized_text


def _remove_phrase_occurrences(*, text: str, phrase: str) -> str:
    cleaned = text
    normalized_phrase = _normalize_space(phrase).strip()
    if not normalized_phrase:
        return cleaned

    variants = {normalized_phrase, normalized_phrase.rstrip(".!?")}
    for variant in variants:
        if not variant:
            continue
        cleaned = re.sub(re.escape(variant), "", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"\s+\.", ".", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _append_phrase_sentence(*, text: str, phrase: str) -> str:
    sentence = _normalize_space(phrase).strip()
    if not sentence:
        return text

    out = text.rstrip()
    if out and out[-1] not in ".!?":
        out += "."
    separator = "\n\n" if "\n\n" in out else " "
    return (out + separator + sentence).strip()



def validate_draft(draft: Any, *, max_chars: int) -> str:
    if not isinstance(draft, str) or not draft.strip():
        raise StopRun("invalid_draft:empty")
    out = draft.strip()
    if len(out) > max_chars:
        raise StopRun("invalid_draft:too_long")
    return out



def validate_critique(
    raw: Any,
    *,
    allowed_decisions_policy: set[str],
    allowed_risk_types_policy: set[str],
    max_risks: int,
    max_required_changes: int,
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise StopRun("invalid_critique:not_object")

    decision = raw.get("decision")
    if not isinstance(decision, str) or not decision.strip():
        raise StopRun("invalid_critique:decision")
    decision = decision.strip()
    if decision not in allowed_decisions_policy:
        raise StopRun(f"critique_decision_not_allowed_policy:{decision}")

    severity = raw.get("severity", "medium")
    if not isinstance(severity, str) or not severity.strip():
        raise StopRun("invalid_critique:severity")
    severity = severity.strip().lower()
    if severity not in ALLOWED_SEVERITY:
        raise StopRun("invalid_critique:severity")

    risks_raw = raw.get("risks", [])
    if not isinstance(risks_raw, list):
        raise StopRun("invalid_critique:risks")
    if len(risks_raw) > max_risks:
        raise StopRun("invalid_critique:too_many_risks")

    risks: list[dict[str, str]] = []
    for item in risks_raw:
        if not isinstance(item, dict):
            raise StopRun("invalid_critique:risk_item")

        risk_type = item.get("type")
        note = item.get("note")

        if not isinstance(risk_type, str) or not risk_type.strip():
            raise StopRun("invalid_critique:risk_type")
        risk_type = risk_type.strip()
        if risk_type not in allowed_risk_types_policy:
            raise StopRun(f"critique_risk_not_allowed_policy:{risk_type}")

        if not isinstance(note, str) or not note.strip():
            raise StopRun("invalid_critique:risk_note")

        risks.append({"type": risk_type, "note": note.strip()})

    required_changes_raw = raw.get("required_changes", [])
    if not isinstance(required_changes_raw, list):
        raise StopRun("invalid_critique:required_changes")
    if len(required_changes_raw) > max_required_changes:
        raise StopRun("invalid_critique:too_many_required_changes")

    required_changes: list[str] = []
    for item in required_changes_raw:
        if not isinstance(item, str) or not item.strip():
            raise StopRun("invalid_critique:required_change_item")
        required_changes.append(item.strip())

    reason = raw.get("reason", "")
    if reason is None:
        reason = ""
    if not isinstance(reason, str):
        raise StopRun("invalid_critique:reason")
    reason = reason.strip()

    high_risk = severity == "high" or any(_is_high_risk_risk_type(r["type"]) for r in risks)

    if decision == "approve":
        if required_changes:
            raise StopRun("invalid_critique:approve_with_required_changes")
        if high_risk:
            raise StopRun("invalid_critique:approve_with_high_risk")

    if decision == "revise":
        if not required_changes:
            raise StopRun("invalid_critique:revise_without_required_changes")
        if not all(_is_enforceable_required_change(item) for item in required_changes):
            raise StopRun("invalid_critique:required_changes_not_enforceable")
        if high_risk:
            raise StopRun("invalid_critique:high_risk_requires_escalate")

    if decision == "escalate":
        if not reason:
            raise StopRun("invalid_critique:escalate_reason_required")

    return {
        "decision": decision,
        "severity": severity,
        "risks": risks,
        "required_changes": required_changes,
        "reason": reason,
        "high_risk": high_risk,
    }


class SelfCritiqueGateway:
    def __init__(self, *, allow_execution_decisions: set[str], budget: Budget):
        self.allow_execution_decisions = set(allow_execution_decisions)
        self.budget = budget

    def enforce_execution_decision(self, decision: str) -> None:
        if decision not in self.allow_execution_decisions:
            raise StopRun(f"critique_decision_denied_execution:{decision}")

    def apply_required_changes_fallback(self, *, text: str, required_changes: list[str]) -> str:
        """
        Deterministic fallback for enforceable required changes:
        remove MUST_REMOVE/REMOVE phrases and append missing MUST_INCLUDE/ADD phrases.
        """
        candidate = (text or "").strip()
        if not candidate:
            return candidate

        phrase_rules = _extract_required_change_rules(required_changes)
        must_include = phrase_rules["must_include"]
        must_remove = phrase_rules["must_remove"]

        for phrase in must_remove:
            candidate = _remove_phrase_occurrences(text=candidate, phrase=phrase)

        for phrase in must_include:
            if not _contains_normalized_phrase(text=candidate, phrase=phrase):
                candidate = _append_phrase_sentence(text=candidate, phrase=phrase)

        return candidate.strip()

    def validate_revision(
        self,
        *,
        original: str,
        revised: str,
        context: dict[str, Any],
        required_changes: list[str],
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

        original_len = max(1, len(normalized_original))
        revised_len = len(normalized_revised)
        increase_pct = ((revised_len - original_len) / float(original_len)) * 100.0
        policy_hint_raw = (
            context.get("policy_hints", {}).get("max_length_increase_pct")
            if isinstance(context, dict)
            else None
        )
        policy_hint_cap = self.budget.max_length_increase_pct
        if isinstance(policy_hint_raw, (int, float)) and not isinstance(policy_hint_raw, bool):
            policy_hint_cap = float(policy_hint_raw)

        effective_length_cap = min(self.budget.max_length_increase_pct, policy_hint_cap)
        if increase_pct > effective_length_cap:
            raise StopRun("patch_violation:length_increase_limit")

        allowed_text_tokens = _stable_json(context) + " " + original
        allowed_text_claims = _normalize_space(_context_claim_text(context) + " " + original)

        if _extract_number_tokens(revised_clean) - _extract_number_tokens(allowed_text_tokens):
            raise StopRun("patch_violation:no_new_facts")

        if _extract_incident_ids(revised_clean) - _extract_incident_ids(allowed_text_tokens):
            raise StopRun("patch_violation:new_incident_id")

        if _extract_severity_labels(revised_clean) - _extract_severity_labels(allowed_text_tokens):
            raise StopRun("patch_violation:new_severity_label")

        if _extract_regions(revised_clean) - _extract_regions(allowed_text_tokens):
            raise StopRun("patch_violation:new_region")

        avoid_absolute_guarantees = bool(
            context.get("policy_hints", {}).get("avoid_absolute_guarantees")
            if isinstance(context, dict)
            else False
        )
        for claim_re in RESTRICTED_CLAIMS_RE:
            if avoid_absolute_guarantees:
                if claim_re.search(revised_clean):
                    raise StopRun("patch_violation:restricted_claims")
                continue
            if claim_re.search(revised_clean) and not claim_re.search(allowed_text_claims):
                raise StopRun("patch_violation:restricted_claims")

        phrase_rules = _extract_required_change_rules(required_changes)
        must_include = phrase_rules["must_include"]
        must_remove = phrase_rules["must_remove"]

        if must_include or must_remove:
            revised_lower = normalized_revised.lower()
            if [value for value in must_include if not _contains_normalized_phrase(text=revised_lower, phrase=value)]:
                raise StopRun("patch_violation:required_changes_not_applied")
            if [value for value in must_remove if _contains_normalized_phrase(text=revised_lower, phrase=value)]:
                raise StopRun("patch_violation:required_changes_not_applied")

        return {
            "answer": revised_clean,
            "patch_similarity": round(similarity, 3),
            "length_increase_pct": round(increase_pct, 2),
            "required_changes_total": len(required_changes),
            "required_changes_enforced": len(must_include) + len(must_remove),
            "required_changes_unenforced": len(required_changes) - (len(must_include) + len(must_remove)),
        }

    def validate_final(self, answer: str) -> str:
        if not isinstance(answer, str) or not answer.strip():
            raise StopRun("invalid_answer:empty")

        out = answer.strip()
        if len(out) > self.budget.max_answer_chars:
            raise StopRun("invalid_answer:too_long")
        return out
