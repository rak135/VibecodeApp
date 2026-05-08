"""File indexer for vibecode."""

from __future__ import annotations

import sys
from pathlib import Path

from vibecode.indexer.classifier import FileRecord, classify
from vibecode.indexer.inventory import build_inventory, write_inventory
from vibecode.indexer.scanner import (
    DEFAULT_SIZE_LIMIT,
    FileStatus,
    IndexedFile,
    scan,
)

__all__ = [
    "scan",
    "IndexedFile",
    "FileStatus",
    "DEFAULT_SIZE_LIMIT",
    "classify",
    "FileRecord",
    "build_inventory",
    "write_inventory",
]


def cmd_index(args) -> int:
    repo_root = Path(args.repo_root).resolve()

    include: list[str] = []
    exclude: list[str] = []
    project_id = repo_root.name.lower().replace(" ", "_")
    vibecode_dir = repo_root / ".vibecode"
    if (vibecode_dir / "project.yaml").exists():
        try:
            from vibecode.config import load_config

            cfg = load_config(vibecode_dir)
            include = cfg.include
            exclude = cfg.exclude
            project_id = cfg.project_id
        except Exception as exc:  # noqa: BLE001
            print(f"Warning: could not load project.yaml: {exc}", file=sys.stderr)

    print(f"Indexing {repo_root}", file=sys.stderr)
    files = scan(repo_root, include=include, exclude=exclude)

    for f in files:
        print(f.path)

    inventory_path = vibecode_dir / "index" / "file_inventory.json"
    write_inventory(project_id, repo_root, files, inventory_path)
    print(f"  {len(files)} file(s) indexed", file=sys.stderr)
    print(f"  inventory written to {inventory_path.relative_to(repo_root).as_posix()}", file=sys.stderr)
    return 0
