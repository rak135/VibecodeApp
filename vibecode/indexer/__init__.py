"""File indexer for vibecode."""

from __future__ import annotations

import sys
import json
import subprocess
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
from vibecode.indexer.run_record import write_run_record
from vibecode.validation import validate_project, write_validation_report

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
    started_at = datetime.now(tz=timezone.utc)

    if not repo_root.exists():
        print(f"Error: repository root does not exist: {repo_root}", file=sys.stderr)
        return 1

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

    _guard_index_paths(vibecode_dir, repo_root)

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

    repo_tree_path = vibecode_dir / "index" / "repo_tree.generated.md"
    write_repo_tree(
        repo_root,
        records,
        repo_tree_path,
        generated_at=started_at,
        git_commit=_git_commit(repo_root),
    )
    print(f"  repo tree written to {repo_tree_path.relative_to(repo_root).as_posix()}", file=sys.stderr)

    _warn_unfilled_architecture_templates(repo_root, run_log)

    timestamp = started_at.strftime("%Y%m%dT%H%M%S%fZ")

    if run_log:
        log_path = vibecode_dir / "logs" / "index_runs" / f"{timestamp}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("\n".join(run_log) + "\n", encoding="utf-8")
        print(
            f"  {len(run_log)} warning(s) logged to"
            f" {log_path.relative_to(repo_root).as_posix()}",
            file=sys.stderr,
        )

    validation_report = validate_project(repo_root)
    write_validation_report(validation_report, vibecode_dir)
    _print_validation_summary(validation_report)

    errors = [
        item["message"]
        for item in validation_report.get("items", [])
        if item.get("level") == "ERROR"
    ]
    validation_warnings = [
        item["message"]
        for item in validation_report.get("items", [])
        if item.get("level") == "WARN"
    ]
    warnings = [*run_log, *validation_warnings]
    counts = _index_counts(
        files=files,
        symbol_map_path=symbol_map_path,
        dependency_map_path=dependency_map_path,
        test_map_path=test_map_path,
        warnings=warnings,
        errors=errors,
    )
    finished_at = datetime.now(tz=timezone.utc)

    current_path, run_path = write_run_record(
        project_id=project_id,
        root=repo_root,
        started_at=started_at,
        finished_at=finished_at,
        counts=counts,
        warnings=warnings,
        errors=errors,
        vibecode_dir=vibecode_dir,
        timestamp=timestamp,
        validation=validation_report,
    )
    print(f"  last index written to {current_path.relative_to(repo_root).as_posix()}", file=sys.stderr)
    print(f"  run record written to {run_path.relative_to(repo_root).as_posix()}", file=sys.stderr)

    return 1 if errors else 0


def _guard_index_paths(vibecode_dir: Path, repo_root: Path) -> None:
    """Raise RuntimeError if any index output path would overwrite a human-maintained file.

    This guard makes the write rules explicit and prevents accidental regressions
    if output paths are ever changed.
    """
    from vibecode.write_rules import is_human_maintained

    output_paths = [
        vibecode_dir / "index" / "file_inventory.json",
        vibecode_dir / "index" / "risky_files.md",
        vibecode_dir / "index" / "symbol_map.json",
        vibecode_dir / "index" / "dependency_map.json",
        vibecode_dir / "index" / "test_map.json",
        vibecode_dir / "index" / "entrypoints.md",
        vibecode_dir / "index" / "repo_tree.generated.md",
        vibecode_dir / "current" / "last_index.json",
        vibecode_dir / "current" / "validation.json",
    ]
    for path in output_paths:
        if is_human_maintained(path, repo_root):
            raise RuntimeError(
                f"BUG: index output path overlaps with human-maintained file: {path}"
            )


def _warn_unfilled_architecture_templates(repo_root: Path, run_log: list[str]) -> None:
    from vibecode.project import ARCHITECTURE_FILES, TEMPLATE_UNFILLED_MARKER

    for rel in ARCHITECTURE_FILES:
        path = repo_root / Path(rel)
        if path.exists() and TEMPLATE_UNFILLED_MARKER in path.read_text(encoding="utf-8"):
            msg = f"Warning: {rel} still contains unfilled template content."
            print(f"  {msg}", file=sys.stderr)
            run_log.append(msg)


def _index_counts(
    *,
    files: list[IndexedFile],
    symbol_map_path: Path,
    dependency_map_path: Path,
    test_map_path: Path,
    warnings: list[str],
    errors: list[str],
) -> dict:
    symbol_map = _read_json(symbol_map_path)
    dependency_map = _read_json(dependency_map_path)
    test_map = _read_json(test_map_path)
    symbols = 0
    for entry in symbol_map.get("files", []):
        if isinstance(entry, dict):
            symbols += len(entry.get("symbols") or [])
    return {
        "files": len(files),
        "symbols": symbols,
        "tests": len(test_map.get("tests") or []),
        "dependency_edges": len(dependency_map.get("edges") or []),
        "warnings": len(warnings),
        "errors": len(errors),
    }


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _print_validation_summary(report: dict) -> None:
    summary = report.get("summary", {})
    print(
        "  validation:"
        f" {summary.get('ok', 0)} OK,"
        f" {summary.get('warnings', 0)} WARN,"
        f" {summary.get('errors', 0)} ERROR",
        file=sys.stderr,
    )


def _git_commit(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    if result.returncode != 0:
        return "unknown"
    return result.stdout.strip() or "unknown"
