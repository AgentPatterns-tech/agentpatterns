from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class StopRun(Exception):
    def __init__(self, reason: str, *, details: dict[str, Any] | None = None):
        super().__init__(reason)
        self.reason = reason
        self.details = details or {}


@dataclass(frozen=True)
class Budget:
    max_seconds: int = 25
    max_code_chars: int = 2400
    exec_timeout_seconds: float = 2.0
    max_stdout_bytes: int = 4096
    max_stderr_bytes: int = 4096


@dataclass(frozen=True)
class Decision:
    kind: str
    reason: str


ALLOWED_IMPORTS = {"json", "statistics"}
DENIED_CALL_NAMES = {"exec", "eval", "compile", "__import__", "open"}
# NOTE: heuristic hardening — blocks suspicious attribute names regardless of receiver type.
DENIED_CALL_ATTRS = {"system", "popen", "fork", "spawn", "connect", "request", "urlopen"}
DENIED_NAME_REFERENCES = {
    "builtins",
    "getattr",
    "setattr",
    "delattr",
    "globals",
    "locals",
    "vars",
    "dir",
}
# Blocked identifier references in generated code (belt-and-suspenders hardening).
DENIED_GLOBAL_NAMES = {"os", "sys", "subprocess", "socket", "pathlib", "importlib"}


def code_hash(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()[:16]


def validate_code_action(raw: Any, *, max_code_chars: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise StopRun("invalid_action:not_object")

    action_id = raw.get("id")
    language = raw.get("language")
    entrypoint = raw.get("entrypoint")
    code = raw.get("code")
    input_payload = raw.get("input_payload")

    if not isinstance(action_id, str) or not action_id.strip():
        raise StopRun("invalid_action:id")
    if not isinstance(language, str) or not language.strip():
        raise StopRun("invalid_action:language")
    if not isinstance(entrypoint, str) or not entrypoint.strip():
        raise StopRun("invalid_action:entrypoint")
    if not isinstance(code, str) or not code.strip():
        raise StopRun("invalid_action:code")
    if len(code) > max_code_chars:
        raise StopRun("invalid_action:code_too_long")
    if not isinstance(input_payload, dict):
        raise StopRun("invalid_action:input_payload")

    normalized_entrypoint = entrypoint.strip()
    if "/" in normalized_entrypoint or "\\" in normalized_entrypoint:
        raise StopRun("invalid_action:entrypoint_path")
    if normalized_entrypoint != "main.py":
        raise StopRun("invalid_action:entrypoint_denied")

    return {
        "id": action_id.strip(),
        "language": language.strip().lower(),
        "entrypoint": normalized_entrypoint,
        "code": code,
        "input_payload": input_payload,
    }


def validate_execution_output(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise StopRun("invalid_code_output:not_object")

    required = {
        "failed_payment_rate",
        "chargeback_alerts",
        "incident_severity",
        "eta_minutes",
        "affected_checkout_share",
        "avg_latency_ms",
        "p95_latency_ms",
        "sample_size",
        "incident_id",
        "region",
    }
    if not required.issubset(set(raw.keys())):
        raise StopRun("invalid_code_output:missing_required")

    failed_rate = raw["failed_payment_rate"]
    if not isinstance(failed_rate, (int, float)) or not (0 <= float(failed_rate) <= 1):
        raise StopRun("invalid_code_output:failed_payment_rate")

    share = raw["affected_checkout_share"]
    if not isinstance(share, (int, float)) or not (0 <= float(share) <= 1):
        raise StopRun("invalid_code_output:affected_checkout_share")

    chargeback_alerts = raw["chargeback_alerts"]
    if not isinstance(chargeback_alerts, int) or chargeback_alerts < 0:
        raise StopRun("invalid_code_output:chargeback_alerts")

    severity = raw["incident_severity"]
    if severity not in {"P1", "P2", "P3"}:
        raise StopRun("invalid_code_output:incident_severity")

    eta = raw["eta_minutes"]
    if not isinstance(eta, int) or eta < 0 or eta > 240:
        raise StopRun("invalid_code_output:eta_minutes")

    sample_size = raw["sample_size"]
    if not isinstance(sample_size, int) or sample_size <= 0:
        raise StopRun("invalid_code_output:sample_size")

    try:
        avg_latency = round(float(raw["avg_latency_ms"]), 2)
    except (TypeError, ValueError):
        raise StopRun("invalid_code_output:avg_latency_ms")
    try:
        p95_latency = round(float(raw["p95_latency_ms"]), 2)
    except (TypeError, ValueError):
        raise StopRun("invalid_code_output:p95_latency_ms")

    return {
        "failed_payment_rate": float(failed_rate),
        "chargeback_alerts": chargeback_alerts,
        "incident_severity": severity,
        "eta_minutes": eta,
        "affected_checkout_share": float(share),
        "avg_latency_ms": avg_latency,
        "p95_latency_ms": p95_latency,
        "sample_size": sample_size,
        "incident_id": str(raw["incident_id"]),
        "region": str(raw["region"]).upper(),
    }


def _static_policy_violations(code: str) -> list[str]:
    lower = code.lower()
    violations: list[str] = []
    input_calls = 0

    if "http://" in lower or "https://" in lower:
        violations.append("network_literal_blocked")

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return ["syntax_error"]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name.split(".")[0]
                if module not in ALLOWED_IMPORTS:
                    violations.append(f"import_not_allowed:{module}")
        elif isinstance(node, ast.ImportFrom):
            module = (node.module or "").split(".")[0]
            if module not in ALLOWED_IMPORTS:
                violations.append(f"import_not_allowed:{module or 'relative'}")
        elif isinstance(node, ast.Name):
            if node.id.startswith("__"):
                violations.append(f"name_not_allowed:{node.id}")
            elif node.id in DENIED_NAME_REFERENCES:
                violations.append(f"name_not_allowed:{node.id}")
            elif node.id in DENIED_GLOBAL_NAMES:
                violations.append(f"name_not_allowed:{node.id}")
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__"):
                violations.append(f"attr_not_allowed:{node.attr}")
            elif node.attr in DENIED_CALL_ATTRS:
                violations.append(f"attr_not_allowed:{node.attr}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in DENIED_CALL_NAMES:
                violations.append(f"call_not_allowed:{node.func.id}")
            elif isinstance(node.func, ast.Name) and node.func.id in {"getattr", "setattr", "delattr"}:
                violations.append(f"call_not_allowed:{node.func.id}")
            elif isinstance(node.func, ast.Name) and node.func.id == "input":
                input_calls += 1
            elif isinstance(node.func, ast.Attribute) and node.func.attr in DENIED_CALL_ATTRS:
                violations.append(f"call_not_allowed:{node.func.attr}")

    if input_calls > 1:
        violations.append("too_many_input_reads")

    return sorted(set(violations))


class CodeExecutionGateway:
    def __init__(
        self,
        *,
        allowed_languages_policy: set[str],
        allowed_languages_execution: set[str],
        budget: Budget,
    ):
        self.allowed_languages_policy = {item.lower() for item in allowed_languages_policy}
        self.allowed_languages_execution = {item.lower() for item in allowed_languages_execution}
        self.budget = budget

    def evaluate(self, *, action: dict[str, Any]) -> Decision:
        language = action["language"]
        if language not in self.allowed_languages_policy:
            return Decision(kind="deny", reason="language_denied_policy")
        if language not in self.allowed_languages_execution:
            return Decision(kind="deny", reason="language_denied_execution")

        violations = _static_policy_violations(action["code"])
        if violations:
            return Decision(kind="deny", reason=f"static_policy_violation:{','.join(violations[:3])}")
        return Decision(kind="allow", reason="policy_pass")

    def execute_python(self, *, code: str, entrypoint: str, input_payload: dict[str, Any]) -> dict[str, Any]:
        if entrypoint != "main.py":
            raise StopRun("invalid_action:entrypoint_denied")

        with tempfile.TemporaryDirectory(prefix="code_exec_agent_") as temp_dir:
            script_path = Path(temp_dir) / entrypoint
            script_path.write_text(code, encoding="utf-8")

            # Minimal hardening for interpreter behavior in this demo boundary.
            proc_env = os.environ.copy()
            proc_env["PYTHONNOUSERSITE"] = "1"
            proc_env["PYTHONDONTWRITEBYTECODE"] = "1"

            started = time.monotonic()
            try:
                proc = subprocess.run(
                    [sys.executable, str(script_path)],
                    input=json.dumps(input_payload),
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    capture_output=True,
                    timeout=self.budget.exec_timeout_seconds,
                    cwd=temp_dir,
                    env=proc_env,
                )
            except subprocess.TimeoutExpired as exc:
                raise StopRun("code_timeout") from exc

            exec_ms = int((time.monotonic() - started) * 1000)
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
            # Demo limitation: size caps are checked after process completion.
            stdout_bytes = len(stdout.encode("utf-8"))
            stderr_bytes = len(stderr.encode("utf-8"))
            if stdout_bytes > self.budget.max_stdout_bytes:
                raise StopRun("code_output_too_large")
            if stderr_bytes > self.budget.max_stderr_bytes:
                raise StopRun("code_stderr_too_large")
            if proc.returncode != 0:
                stderr_snippet = stderr.strip().replace("\n", " ")[:200]
                stdout_snippet = stdout.strip().replace("\n", " ")[:200]
                details: dict[str, str] = {}
                if stderr_snippet:
                    details["stderr_snippet"] = stderr_snippet
                if stdout_snippet:
                    details["stdout_snippet"] = stdout_snippet
                raise StopRun(
                    f"code_runtime_error:{proc.returncode}",
                    details=details,
                )

            stdout = stdout.strip()
            if not stdout:
                raise StopRun("invalid_code_output:empty_stdout")

            try:
                payload = json.loads(stdout)
            except json.JSONDecodeError as exc:
                raise StopRun("invalid_code_output:non_json") from exc

            if not isinstance(payload, dict):
                raise StopRun("invalid_code_output:not_object")

            return {
                "payload": payload,
                "exec_ms": exec_ms,
                "stdout_bytes": stdout_bytes,
                "stderr_bytes": stderr_bytes,
            }
