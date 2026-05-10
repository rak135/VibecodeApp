"""Auditable run record written after every ``vibecode index`` invocation."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

_SCHEMA = "vibecode/index-run/v1"
_GENERATOR = "vibecode 0.1.0"


def write_run_record(
    *,
    project_id: str,
    root: Path,
    started_at: datetime,
    finished_at: datetime,
    counts: dict,
    warnings: list[str],
    errors: list[str],
    vibecode_dir: Path,
    timestamp: str,
    validation: dict | None = None,
    git_commit: str | None = None,
) -> tuple[Path, Path]:
    """Persist the run record to ``current/last_index.json`` and ``logs/index_runs/<timestamp>.json``.

    Returns the two paths written (current, log).
    """
    record = {
        "$schema": _SCHEMA,
        "project_id": project_id,
        "root": root.as_posix(),
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "counts": counts,
        "warnings": warnings,
        "errors": errors,
        "generator": _GENERATOR,
    }
    if validation is not None:
        record["validation"] = validation
    if git_commit is not None:
        record["git_commit"] = git_commit
    serialized = json.dumps(record, indent=2, ensure_ascii=False) + "\n"

    current_path = vibecode_dir / "current" / "last_index.json"
    current_path.parent.mkdir(parents=True, exist_ok=True)
    current_path.write_text(serialized, encoding="utf-8")

    log_path = vibecode_dir / "logs" / "index_runs" / f"{timestamp}.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(serialized, encoding="utf-8")

    return current_path, log_path
