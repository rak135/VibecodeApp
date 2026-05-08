"""Project configuration loading and validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import yaml


@dataclass
class ProjectConfig:
    project_id: str
    project_name: str
    root: Path
    include: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)
    protected_paths: List[str] = field(default_factory=list)
    risk_rules: List[str] = field(default_factory=list)
    required_checks: List[str] = field(default_factory=list)
    required_check_records: List[dict] = field(default_factory=list)


def load_config(vibecode_dir: Path) -> ProjectConfig:
    """Load and validate .vibecode/project.yaml.

    Raises FileNotFoundError if project.yaml is absent or the resolved root
    does not exist on disk.
    Raises ValueError for invalid or incomplete configuration.
    """
    config_path = vibecode_dir / "project.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"project.yaml not found: {config_path}")

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"project.yaml is not valid YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError("project.yaml must be a YAML mapping at the top level")

    project_section = raw.get("project") or {}
    project_id = project_section.get("id")
    if not project_id:
        raise ValueError("project.yaml: missing required field 'project.id'")

    project_name = str(project_section.get("name") or project_id)

    # Normalize root path — accept both forward and back slashes.
    raw_root = str(project_section.get("root") or ".").replace("\\", "/")
    root_path = Path(raw_root)
    if not root_path.is_absolute():
        root_path = (vibecode_dir.parent / root_path).resolve()
    else:
        root_path = root_path.resolve()

    if not root_path.exists():
        raise FileNotFoundError(f"project root does not exist: {root_path}")

    indexing = raw.get("indexing") or {}
    check_records = _load_required_check_records(vibecode_dir)
    legacy_checks = _legacy_required_checks(raw.get("required_checks") or [])
    required_checks = [str(check["command"]) for check in check_records if check.get("required")]
    if not required_checks:
        required_checks = legacy_checks
    return ProjectConfig(
        project_id=str(project_id),
        project_name=project_name,
        root=root_path,
        include=list(indexing.get("include") or []),
        exclude=list(indexing.get("exclude") or []),
        protected_paths=list(raw.get("protected_paths") or []),
        risk_rules=list(raw.get("risk_rules") or []),
        required_checks=required_checks,
        required_check_records=check_records,
    )


def _legacy_required_checks(raw_checks: list) -> list[str]:
    checks: list[str] = []
    for item in raw_checks:
        if isinstance(item, str):
            checks.append(item)
        elif isinstance(item, dict) and item.get("command"):
            checks.append(str(item["command"]))
    return checks


def _load_required_check_records(vibecode_dir: Path) -> list[dict]:
    path = vibecode_dir / "checks" / "required_checks.yaml"
    if not path.exists():
        return []
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"required_checks.yaml is not valid YAML: {exc}") from exc
    if raw is None:
        return []
    if not isinstance(raw, dict):
        raise ValueError("required_checks.yaml must be a YAML mapping at the top level")
    records = raw.get("checks") or []
    if not isinstance(records, list):
        raise ValueError("required_checks.yaml: 'checks' must be a list")

    normalized: list[dict] = []
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise ValueError(f"required_checks.yaml: check #{index} must be a mapping")
        name = record.get("name")
        command = record.get("command")
        if not name or not command:
            raise ValueError(f"required_checks.yaml: check #{index} requires name and command")
        normalized.append({
            "name": str(name),
            "command": str(command),
            "required": bool(record.get("required", True)),
        })
    return normalized
