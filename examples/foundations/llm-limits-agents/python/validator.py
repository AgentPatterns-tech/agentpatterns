import json
from dataclasses import dataclass
from typing import Any


@dataclass
class ValidationResult:
    ok: bool
    data: dict[str, Any] | None
    errors: list[str]


def validate_model_output(raw: str, allowed_sources: set[str]) -> ValidationResult:
    errors: list[str] = []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return ValidationResult(False, None, ["invalid JSON"])

    if not isinstance(data, dict):
        return ValidationResult(False, None, ["output must be a JSON object"])

    answer = data.get("answer")
    citations = data.get("citations")
    confidence = data.get("confidence")
    needs_human = data.get("needs_human")

    if not isinstance(answer, str) or not answer.strip():
        errors.append("answer must be non-empty string")

    if not isinstance(citations, list) or not all(isinstance(x, str) for x in citations):
        errors.append("citations must be a list of strings")
    else:
        unknown = [x for x in citations if x not in allowed_sources]
        if unknown:
            errors.append(f"unknown citations: {unknown}")

    if not isinstance(confidence, (int, float)) or not (0 <= float(confidence) <= 1):
        errors.append("confidence must be a number in [0, 1]")

    if not isinstance(needs_human, bool):
        errors.append("needs_human must be boolean")

    return ValidationResult(len(errors) == 0, data if len(errors) == 0 else None, errors)
