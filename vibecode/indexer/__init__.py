"""File indexer for vibecode."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

from vibecode.indexer.classifier import FileRecord, classify
from vibecode.indexer.inventory import build_inventory, write_inventory
from vibecode.indexer.risk_engine import RiskResult, build_risk_index
from vibecode.indexer.risky_files import write_risky_files
from vibecode.indexer.scanner import (
    DEFAULT_SIZE_LIMIT,
    FileStatus,
    IndexedFile,
    scan,
)

from vibecode.indexer.dependency_map import build_dependency_map, write_dependency_map
from vibecode.indexer.entrypoints import detect_entrypoints, render_entrypoints, write_entrypoints
from vibecode.indexer.repo_tree import render_repo_tree, write_repo_tree
from vibecode.indexer.symbol_map import build_symbol_map, write_symbol_map
from vibecode.indexer.test_map import build_test_map, write_test_map

__all__ = [
    "scan",
    "IndexedFile",
    "FileStatus",
    "DEFAULT_SIZE_LIMIT",
    "classify",
    "FileRecord",
    "build_inventory",
    "write_inventory",
    "RiskResult",
    "build_risk_index",
    "write_risky_files",
    "render_repo_tree",
    "write_repo_tree",
    "build_symbol_map",
    "write_symbol_map",
    "build_dependency_map",
    "write_dependency_map",
    "build_test_map",
    "write_test_map",
    "detect_entrypoints",
    "render_entrypoints",
    "write_entrypoints",
]


def cmd_index(args) -> int:
    repo_root = Path(args.repo_root).resolve()

    include: list[str] = []
    exclude: list[str] = []
    project_id = repo_root.name.lower().replace(" ", "_")
    protected_paths: list[str] = []
    risk_rules: list[dict] = []
    vibecode_dir = repo_root / ".vibecode"
    if (vibecode_dir / "project.yaml").exists():
        try:
            from vibecode.config import load_config

            cfg = load_config(vibecode_dir)
            include = cfg.include
            exclude = cfg.exclude
            project_id = cfg.project_id
            protected_paths = cfg.protected_paths
            risk_rules = [r for r in cfg.risk_rules if isinstance(r, dict)]
        except Exception as exc:  # noqa: BLE001
            print(f"Warning: could not load project.yaml: {exc}", file=sys.stderr)

    print(f"Indexing {repo_root}", file=sys.stderr)
    files = scan(repo_root, include=include, exclude=exclude)

    for f in files:
        print(f.path)

    run_log: list[str] = []

    # Build risk index (warns if protected_paths is empty)
    records = [classify(f.path, f.size) for f in files]
    risk_index = build_risk_index(records, protected_paths, risk_rules, run_log=run_log)

    inventory_path = vibecode_dir / "index" / "file_inventory.json"
    write_inventory(project_id, repo_root, files, inventory_path, risk_index=risk_index)
    print(f"  {len(files)} file(s) indexed", file=sys.stderr)
    print(f"  inventory written to {inventory_path.relative_to(repo_root).as_posix()}", file=sys.stderr)

    risky_files_path = vibecode_dir / "index" / "risky_files.md"
    write_risky_files(risk_index, risky_files_path)
    print(
        f"  risky files written to {risky_files_path.relative_to(repo_root).as_posix()}",
        file=sys.stderr,
    )

    symbol_map_path = vibecode_dir / "index" / "symbol_map.json"
    write_symbol_map(repo_root, files, symbol_map_path, run_log=run_log)
    print(f"  symbol map written to {symbol_map_path.relative_to(repo_root).as_posix()}", file=sys.stderr)

    dependency_map_path = vibecode_dir / "index" / "dependency_map.json"
    write_dependency_map(repo_root, files, dependency_map_path, run_log=run_log)
    print(f"  dependency map written to {dependency_map_path.relative_to(repo_root).as_posix()}", file=sys.stderr)

    required_checks: list[str] | None = None
    if (vibecode_dir / "project.yaml").exists():
        try:
            from vibecode.config import load_config as _load_config

            required_checks = _load_config(vibecode_dir).required_checks or None
        except Exception:  # noqa: BLE001
            pass

    test_map_path = vibecode_dir / "index" / "test_map.json"
    write_test_map(repo_root, files, test_map_path, required_checks=required_checks)
    print(f"  test map written to {test_map_path.relative_to(repo_root).as_posix()}", file=sys.stderr)

    entrypoints_path = vibecode_dir / "index" / "entrypoints.md"
    write_entrypoints(repo_root, entrypoints_path)
    print(f"  entrypoints written to {entrypoints_path.relative_to(repo_root).as_posix()}", file=sys.stderr)

    if run_log:
        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        log_path = vibecode_dir / "logs" / "index_runs" / f"{ts}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("\n".join(run_log) + "\n", encoding="utf-8")
        print(
            f"  {len(run_log)} warning(s) logged to"
            f" {log_path.relative_to(repo_root).as_posix()}",
            file=sys.stderr,
        )

    return 0
