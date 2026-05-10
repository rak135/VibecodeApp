"""File indexer for vibecode."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from vibecode.indexer.classifier import FileRecord, classify
from vibecode.git_state import current_git_commit
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
    "check_index_freshness",
]




def check_index_freshness(
    repo_root: Path,
    max_age_seconds: float = 300.0,
) -> tuple[bool, str]:
    """Check whether the existing index is fresh enough to use.

    The index is considered stale if it does not exist, if it was
    built more than *max_age_seconds* ago, or if the git HEAD changed
    since the index was built.

    Returns
    -------
    (fresh, detail_message)
        *fresh* is True when the index looks current; False otherwise.
        *detail_message* explains why it is stale (or "fresh").

    """
    index_path = repo_root / ".vibecode" / "current" / "last_index.json"

    if not index_path.exists():
        return False, "No index found -- run 'vibecode index' first."

    try:
        record = json.loads(index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return False, "Cannot parse last index record: {exc}".format(exc=exc)

    # Check age.
    started_at = record.get("started_at", "")
    if started_at:
        from datetime import datetime as _dt, timezone as _tz
        started_dt = _dt.fromisoformat(started_at)
        age = (_dt.now(tz=_tz.utc) - started_dt).total_seconds()
        if age > max_age_seconds:
            return False, (
                "Index is {age:.0f}s old (>{max_age_seconds:.0f}s) "
                "-- run 'vibecode index' to refresh."
            ).format(age=age, max_age_seconds=max_age_seconds)

    # Check git commit.
    recorded_commit = record.get("git_commit")
    if recorded_commit and recorded_commit != "unknown":
        current_commit = current_git_commit(repo_root)
        if current_commit != "unknown" and current_commit != recorded_commit:
            return False, (
                "Index was built for commit {recorded_commit}, "
                "but HEAD is now {current_commit} -- re-index."
            ).format(recorded_commit=recorded_commit, current_commit=current_commit)

    # Check file-set fingerprint against current disk scan.
    recorded_fingerprint = record.get("file_set_fingerprint")
    if recorded_fingerprint:
        include = None
        exclude = None
        try:
            from vibecode.config import load_config as _load_cfg
            cfg = _load_cfg(repo_root / ".vibecode")
            include = cfg.include
            exclude = cfg.exclude
        except Exception:
            pass
        current_fingerprint = compute_current_file_set_fingerprint(
            repo_root, include=include, exclude=exclude
        )
        if current_fingerprint is not None and current_fingerprint != recorded_fingerprint:
            return False, (
                "Indexed file set has changed since the last index "
                "-- run 'vibecode index' to refresh."
            )

    return True, "fresh"
def cmd_index(args) -> int:
    repo_root = Path(args.repo_root).resolve()
    started_at = datetime.now(tz=timezone.utc)

    vibecode_dir = repo_root / ".vibecode"
    if not (vibecode_dir / "project.yaml").exists():
        print(
            f"Error: No project.yaml found in {vibecode_dir}.\n"
            "       Run 'vibecode init' to initialize the project.",
            file=sys.stderr,
        )
        return 1

    from vibecode.config import load_config

    cfg = load_config(vibecode_dir)
    include = cfg.include
    exclude = cfg.exclude
    project_id = cfg.project_id
    protected_paths = cfg.protected_paths
    risk_rules = [r for r in cfg.risk_rules if isinstance(r, dict)]

    _guard_index_paths(vibecode_dir, repo_root)

    print(f"Indexing {repo_root}", file=sys.stderr)
    files = scan(repo_root, include=include, exclude=exclude)

    for f in files:
        print(f.path)

    run_log: list[str] = []

    # Build risk index (warns if protected_paths is empty)
    records = [classify(f.path, f.size) for f in files]
    risk_index = build_risk_index(records, protected_paths, risk_rules, run_log=run_log)

    # Apply risk engine results to records so the repo tree reflects enriched risk levels.
    from dataclasses import replace as _replace
    records = [
        _replace(r, risk_level=risk_index[r.path].risk_level) if r.path in risk_index else r
        for r in records
    ]

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

    required_checks: list[str] | None = cfg.required_checks or None

    test_map_path = vibecode_dir / "index" / "test_map.json"
    test_map_data = build_test_map(repo_root, files, required_checks=required_checks)
    test_map_path.parent.mkdir(parents=True, exist_ok=True)
    test_map_path.write_text(json.dumps(test_map_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  test map written to {test_map_path.relative_to(repo_root).as_posix()}", file=sys.stderr)

    entrypoints_path = vibecode_dir / "index" / "entrypoints.md"
    entrypoints_data = detect_entrypoints(repo_root)
    write_entrypoints(repo_root, entrypoints_path)
    print(f"  entrypoints written to {entrypoints_path.relative_to(repo_root).as_posix()}", file=sys.stderr)

    repo_tree_path = vibecode_dir / "index" / "repo_tree.generated.md"
    write_repo_tree(
        repo_root,
        records,
        repo_tree_path,
        generated_at=started_at,
        git_commit=_git_commit(repo_root),
        entrypoints_data=entrypoints_data,
        test_map_data=test_map_data,
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
    # Compute file-set fingerprint for stale-index detection.
    file_set_fingerprint = _compute_file_set_fingerprint(files)
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
        git_commit=_git_commit(repo_root),
        file_set_fingerprint=file_set_fingerprint,
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


_FINGERPRINT_EXCLUDED_PREFIXES: tuple[str, ...] = (
    ".vibecode/current/",
    ".vibecode/generated/",
    ".vibecode/index/",
    ".vibecode/logs/",
    ".vibecode/runs/",
    ".vibecode/tmp/",
    ".vibecode/cache/",
    ".ralphy/",
    ".ralph/",
)
_FINGERPRINT_EXCLUDED_PARTS: frozenset[str] = frozenset({
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".pytest_cache", ".mypy_cache", ".ruff_cache",
})


def _compute_file_set_fingerprint(files: list[IndexedFile]) -> str:
    """Deterministic hash of indexed file paths for stale-index detection.

    Excludes generated/runtime and vendor paths so they don't change
    the fingerprint.
    """
    paths: list[str] = []
    for f in files:
        p = f.path.replace("\\", "/")
        if any(p.startswith(prefix) for prefix in _FINGERPRINT_EXCLUDED_PREFIXES):
            continue
        parts = set(p.split("/"))
        if parts & _FINGERPRINT_EXCLUDED_PARTS:
            continue
        paths.append(p)
    paths.sort()
    h = hashlib.sha256()
    for p in paths:
        h.update(p.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def compute_current_file_set_fingerprint(
    repo_root: Path,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
) -> str | None:
    """Compute a lightweight fingerprint of the current relevant file set.

    Scans the current repository file set (same include/exclude as the
    indexer) and hashes paths excluding generated/runtime directories.
    Returns None when the fingerprint cannot be determined (e.g. scan
    failure).
    """
    try:
        files = scan(repo_root, include=include, exclude=exclude)
    except Exception:
        return None
    return _compute_file_set_fingerprint(files)


_INVENTORY_REL_PATH = ".vibecode/index/file_inventory.json"


def check_inventory_health(repo_root: Path) -> str | None:
    """Return an error message if the file inventory is missing/invalid/empty.

    Returns ``None`` when the inventory is healthy (exists, valid JSON,
    contains at least one file entry).
    """
    inventory_path = repo_root / _INVENTORY_REL_PATH
    if not inventory_path.is_file():
        return (
            f"File inventory not found at {_INVENTORY_REL_PATH}. "
            "Run 'vibecode index <repo>' to generate it."
        )
    try:
        data = json.loads(inventory_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return f"File inventory is not valid JSON: {exc}"
    files = data.get("files") if isinstance(data, dict) else None
    if not isinstance(files, list):
        return "File inventory has no 'files' list."
    if not files:
        return (
            "File inventory is empty. "
            "Check include/exclude patterns in .vibecode/project.yaml "
            "and run 'vibecode index' again."
        )
    return None


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
