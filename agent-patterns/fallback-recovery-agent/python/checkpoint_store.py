from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass
class CheckpointRow:
    run_id: str
    step_id: str
    source: str
    tool: str
    result: dict[str, Any]
    saved_at: float
    ttl_seconds: float | None = None


class CheckpointStore:
    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], CheckpointRow] = {}

    def get_step(self, *, run_id: str, step_id: str, now: float | None = None) -> CheckpointRow | None:
        row = self._rows.get((run_id, step_id))
        if row is None:
            return None
        if row.ttl_seconds is None:
            return row
        now_ts = time.time() if now is None else float(now)
        if (now_ts - row.saved_at) > float(row.ttl_seconds):
            # Expired checkpoint: treat as missing.
            self._rows.pop((run_id, step_id), None)
            return None
        return row

    def save_step(
        self,
        *,
        run_id: str,
        step_id: str,
        source: str,
        tool: str,
        result: dict[str, Any],
    ) -> None:
        self._rows[(run_id, step_id)] = CheckpointRow(
            run_id=run_id,
            step_id=step_id,
            source=source,
            tool=tool,
            result=result,
            saved_at=time.time(),
            ttl_seconds=None,
        )

    def save_step_with_ttl(
        self,
        *,
        run_id: str,
        step_id: str,
        source: str,
        tool: str,
        result: dict[str, Any],
        ttl_seconds: float,
    ) -> None:
        self._rows[(run_id, step_id)] = CheckpointRow(
            run_id=run_id,
            step_id=step_id,
            source=source,
            tool=tool,
            result=result,
            saved_at=time.time(),
            ttl_seconds=float(ttl_seconds),
        )

    def dump_run(self, *, run_id: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in self._rows.values():
            if row.run_id != run_id:
                continue
            out.append(
                {
                    "step_id": row.step_id,
                    "source": row.source,
                    "tool": row.tool,
                    "result_keys": sorted(row.result.keys()),
                    "saved_at": row.saved_at,
                }
            )
        out.sort(key=lambda item: item["saved_at"])
        return out
