from __future__ import annotations

import difflib
import hashlib
import re
from typing import Any


SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _hash_text(text: str) -> str:
    normalized = " ".join((text or "").split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]


def _split_for_diff(text: str) -> list[str]:
    lines = (text or "").splitlines()
    if len(lines) > 1:
        return lines

    normalized = (text or "").strip()
    if not normalized:
        return [""]

    sentences = [item.strip() for item in SENTENCE_SPLIT_RE.split(normalized) if item.strip()]
    if len(sentences) > 1:
        return sentences

    chunk_size = 80
    return [normalized[i : i + chunk_size] for i in range(0, len(normalized), chunk_size)]


def build_audit_log(
    *,
    before: str,
    after: str,
    risks: list[dict[str, Any]],
    required_changes: list[str],
) -> dict[str, Any]:
    before_text = (before or "").strip()
    after_text = (after or "").strip()

    before_chars = len(before_text)
    after_chars = len(after_text)
    delta_chars = after_chars - before_chars

    if before_chars <= 0:
        increase_pct = 0.0
    else:
        increase_pct = (delta_chars / float(before_chars)) * 100.0

    raw_diff = list(
        difflib.unified_diff(
            _split_for_diff(before_text),
            _split_for_diff(after_text),
            fromfile="before",
            tofile="after",
            lineterm="",
        )
    )

    diff_excerpt: list[str] = []
    for line in raw_diff:
        if line.startswith(("---", "+++", "@@")):
            continue
        if line.startswith(("+", "-")):
            diff_excerpt.append(line)
        if len(diff_excerpt) >= 6:
            break

    return {
        "changed": before_text != after_text,
        "before_hash": _hash_text(before_text),
        "after_hash": _hash_text(after_text),
        "before_chars": before_chars,
        "after_chars": after_chars,
        "delta_chars": delta_chars,
        "length_increase_pct": round(increase_pct, 2),
        "risks_count": len(risks),
        "required_changes_count": len(required_changes),
        "diff_excerpt": diff_excerpt,
    }
