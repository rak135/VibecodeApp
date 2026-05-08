"""Validation checks for vibecode project artifacts."""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from vibecode.project import TEMPLATE_UNFILLED_MARKER

_SCHEMA = "vibecode/validation-report/v1"

_GENERATED_JSON = (
    ".vibecode/index/file_inventory.json",
    ".vibecode/index/symbol_map.json",
    ".vibecode/index/dependency_map.json",
    ".vibecode/index/test_map.json",
)

_OPTIONAL_GENERATED_JSON = (
    ".vibecode/current/last_index.json",
    ".vibecode/current/validation.json",
)

_GENERATED_PREFIXES = (
    ".vibecode/index/",
    ".vibecode/current/",
    ".vibecode/logs/index_runs/",
)

_HUMAN_MAINTAINED = (
    ".vibecode/project.yaml",
    ".vibecode/architecture/OVERVIEW.md",
    ".vibecode/architecture/INVARIANTS.md",
    ".vibecode/architecture/STRUCTURE.md",
    ".vibecode/architecture/MODULE_BOUNDARIES.md",
    ".vibecode/architecture/PROTECTED_AREAS.md",
    ".vibecode/architecture/DATA_FLOW.md",
    ".vibecode/checks/required_checks.yaml",
    ".vibecode/handoff/NOW.md",
    ".vibecode/handoff/NEXT.md",
    ".vibecode/handoff/BLOCKERS.md",
    ".vibecode/history/README.md",
)

_FORBIDDEN_INVENTORY_PARTS = {".git", "node_modules", ".venv", "venv"}


@dataclass(frozen=True)
class ValidationItem:
    level: str
    message: str
    path: str | None = None

    def as_dict(self) -> dict:
        data = {"level": self.level, "message": self.message}
        if self.path is not None:
            data["path"] = self.path
        return data


def validate_project(repo_root: Path) -> dict:
    """Return a validation report for *repo_root*."""
    root = repo_root.resolve()
    items: list[ValidationItem] = []
    vibecode_dir = root / ".vibecode"

    if root.exists():
        items.append(_ok("repository root exists", str(root)))
    else:
        items.append(_error("repository root does not exist", str(root)))
        return _report(root, items)

    config = None
    project_yaml = vibecode_dir / "project.yaml"
    if project_yaml.exists():
        items.append(_ok(".vibecode/project.yaml exists", ".vibecode/project.yaml"))
        try:
            from vibecode.config import load_config

            config = load_config(vibecode_dir)
            items.append(_ok("project root from project.yaml exists", str(config.root)))
        except Exception as exc:  # noqa: BLE001
            items.append(_error(f"project.yaml is invalid: {exc}", ".vibecode/project.yaml"))
    else:
        items.append(_error(".vibecode/project.yaml is missing", ".vibecode/project.yaml"))

    _validate_generated_json(root, items)
    _validate_inventory(root, items)
    _validate_invariants(root, items)
    _validate_protected_paths(config, items)
    _validate_context_smoke(root, items)
    _validate_write_rules(root, items)

    return _report(root, items)


def write_validation_report(report: dict, vibecode_dir: Path) -> Path:
    """Write *report* to ``.vibecode/current/validation.json``."""
    path = vibecode_dir / "current" / "validation.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def print_validation_report(report: dict, stream=None) -> None:
    """Print validation items as OK/WARN/ERROR lines."""
    out = stream or sys.stdout
    for item in report.get("items", []):
        path = item.get("path")
        suffix = f" [{path}]" if path else ""
        print(f"{item['level']}: {item['message']}{suffix}", file=out)


def cmd_validate(args) -> int:
    repo_root = Path(args.repo_root)
    report = validate_project(repo_root)
    vibecode_dir = repo_root.resolve() / ".vibecode"
    if repo_root.exists() and vibecode_dir.exists():
        write_validation_report(report, vibecode_dir)
    print_validation_report(report)
    return 1 if report["summary"]["errors"] else 0


def _validate_generated_json(root: Path, items: list[ValidationItem]) -> None:
    for rel in _GENERATED_JSON:
        path = root / Path(rel)
        if not path.exists():
            items.append(_error("generated JSON file is missing", rel))
            continue
        _append_json_validity(path, rel, items)

    for rel in _OPTIONAL_GENERATED_JSON:
        path = root / Path(rel)
        if path.exists():
            _append_json_validity(path, rel, items)


def _append_json_validity(path: Path, rel: str, items: list[ValidationItem]) -> None:
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        items.append(_error(f"generated JSON is invalid: {exc}", rel))
    except OSError as exc:
        items.append(_error(f"generated JSON cannot be read: {exc}", rel))
    else:
        items.append(_ok("generated JSON is valid", rel))


def _validate_inventory(root: Path, items: list[ValidationItem]) -> None:
    rel = ".vibecode/index/file_inventory.json"
    path = root / Path(rel)
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return

    files = data.get("files")
    if not isinstance(files, list):
        items.append(_error("inventory files field is missing or invalid", rel))
        return

    bad_paths: list[str] = []
    for entry in files:
        if not isinstance(entry, dict):
            continue
        posix = str(entry.get("path") or "")
        parts = posix.split("/")
        if any(part in _FORBIDDEN_INVENTORY_PARTS for part in parts[:-1]):
            bad_paths.append(posix)

    if bad_paths:
        items.append(_error("inventory contains excluded paths: " + ", ".join(bad_paths[:5]), rel))
    else:
        items.append(_ok("inventory excludes .git, node_modules, and virtualenv paths", rel))


def _validate_invariants(root: Path, items: list[ValidationItem]) -> None:
    rel = ".vibecode/architecture/INVARIANTS.md"
    path = root / Path(rel)
    if not path.exists():
        items.append(_error("architecture/INVARIANTS.md is missing", rel))
        return

    items.append(_ok("architecture/INVARIANTS.md exists", rel))
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        items.append(_error(f"architecture/INVARIANTS.md cannot be read: {exc}", rel))
        return

    stripped = content.strip()
    if not stripped or TEMPLATE_UNFILLED_MARKER in content or _has_only_weak_invariants(content):
        items.append(_warn("Project has no confirmed invariants. Agent gets technical map but weak project rules.", rel))


def _has_only_weak_invariants(content: str) -> bool:
    meaningful = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("<!--"):
            continue
        if stripped.startswith(">") or stripped.upper().startswith("TODO"):
            continue
        meaningful.append(stripped)
    return not meaningful


def _validate_protected_paths(config, items: list[ValidationItem]) -> None:
    if config is None:
        return
    if config.protected_paths:
        items.append(_ok("protected_paths is non-empty", ".vibecode/project.yaml"))
    else:
        items.append(_warn("protected_paths is empty; no paths are explicitly protected", ".vibecode/project.yaml"))


def _validate_context_smoke(root: Path, items: list[ValidationItem]) -> None:
    try:
        from vibecode.context import cmd_context

        args = SimpleNamespace(repo=str(root), task="validation smoke")
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            rc = cmd_context(args)
    except Exception as exc:  # noqa: BLE001
        items.append(_error(f"context pack smoke generation failed: {exc}"))
        return

    if rc == 0:
        items.append(_ok("dummy context pack command can be generated"))
    else:
        items.append(_error(f"dummy context pack command failed with exit code {rc}"))


def _validate_write_rules(root: Path, items: list[ValidationItem]) -> None:
    invalid_generated: list[str] = []
    for rel in [*_GENERATED_JSON, *_OPTIONAL_GENERATED_JSON, ".vibecode/index/entrypoints.md", ".vibecode/index/risky_files.md"]:
        path = root / Path(rel)
        if path.exists() and not rel.startswith(_GENERATED_PREFIXES):
            invalid_generated.append(rel)

    missing_human = [rel for rel in _HUMAN_MAINTAINED if not (root / Path(rel)).exists()]

    if invalid_generated:
        items.append(_error("generated artifacts are outside generated directories: " + ", ".join(invalid_generated)))
    else:
        items.append(_ok("generated artifacts are confined to generated directories"))

    if missing_human:
        items.append(_warn("some human-maintained files are missing: " + ", ".join(missing_human[:5])))
    else:
        items.append(_ok("human-maintained files are outside generated artifact set"))


def _report(root: Path, items: list[ValidationItem]) -> dict:
    errors = sum(1 for item in items if item.level == "ERROR")
    warnings = sum(1 for item in items if item.level == "WARN")
    return {
        "$schema": _SCHEMA,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "root": root.as_posix(),
        "summary": {
            "ok": sum(1 for item in items if item.level == "OK"),
            "warnings": warnings,
            "errors": errors,
        },
        "status": "error" if errors else "ok",
        "items": [item.as_dict() for item in items],
    }


def _ok(message: str, path: str | None = None) -> ValidationItem:
    return ValidationItem("OK", message, path)


def _warn(message: str, path: str | None = None) -> ValidationItem:
    return ValidationItem("WARN", message, path)


def _error(message: str, path: str | None = None) -> ValidationItem:
    return ValidationItem("ERROR", message, path)
