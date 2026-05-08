"""File inventory JSON writer for vibecode."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from vibecode.indexer.classifier import classify
from vibecode.indexer.scanner import FileStatus, IndexedFile

_SCHEMA = "vibecode/file-inventory/v1"


def build_inventory(
    project_id: str,
    root: Path,
    indexed_files: list[IndexedFile],
) -> dict:
    """Return the inventory dict from a list of scanned :class:`IndexedFile` objects."""
    records = []
    for f in indexed_files:
        rec = classify(f.path, f.size)
        entry: dict = {
            "path": rec.path,
            "language": rec.language,
            "size_bytes": rec.size_bytes,
            "role_guess": rec.role_guess,
            "is_test": rec.is_test,
            "is_config": rec.is_config,
            "is_doc": rec.is_doc,
            "risk_level": rec.risk_level,
        }
        if f.status != FileStatus.UNKNOWN:
            entry["tracked"] = f.status.value
        records.append(entry)

    return {
        "$schema": _SCHEMA,
        "project_id": project_id,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "root": root.as_posix(),
        "files": records,
    }


def write_inventory(
    project_id: str,
    root: Path,
    indexed_files: list[IndexedFile],
    output_path: Path,
) -> None:
    """Write the inventory JSON to *output_path*, creating parent dirs as needed."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    inventory = build_inventory(project_id, root, indexed_files)
    output_path.write_text(
        json.dumps(inventory, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
