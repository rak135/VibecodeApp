"""Project configuration loading and validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import yaml

from vibecode.paths import strip_to_posix

# Commands that are too vague to be actionable as required checks.
_GENERIC_COMMANDS = frozenset({
    "build",
    "check",
    "ci",
    "lint",
    "run checks",
    "test",
    "tests",
    "validate",
    "verify",
})


@dataclass
class ProjectConfig:
    project_id: str
    project_name: str
    root: Path
    include: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)
    protected_paths: List[str] = field(default_factory=list)
    protected_path_records: List["ProtectedPathRule"] = field(default_factory=list)
    risk_rules: List[str] = field(default_factory=list)
    required_checks: List[str] = field(default_factory=list)
    required_check_records: List[dict] = field(default_factory=list)


@dataclass(frozen=True)
class ProtectedPathRule:
    path: str
    rule: str
    required_tests: tuple[str, ...] = ()
    explicit_task_scope_required: bool | None = None


DEFAULT_PROTECTED_PATH_RULES = (
    ProtectedPathRule(
        path=".vibecode/architecture/",
        rule=(
            "Edit only when the task explicitly changes architecture truth; "
            "preserve human-maintained docs."
        ),
    ),
    ProtectedPathRule(
        path=".vibecode/checks/",
        rule=(
            "Edit only for check or policy tasks; keep human-maintained policies "
            "separate from generated artifacts."
        ),
    ),
    ProtectedPathRule(
        path=".vibecode/handoff/",
        rule=(
            "Edit only to record current scope or handoff state; do not treat it "
            "as generated output."
        ),
    ),
    ProtectedPathRule(
        path=".vibecode/history/README.md",
        rule=(
            "Durable history policy; edit only when the project memory workflow "
            "itself changes."
        ),
    ),
    ProtectedPathRule(
        path=".vibecode/agents/",
        rule=(
            "Agent permission/profile definitions; edit only when changing how "
            "agents are allowed to operate."
        ),
    ),
    ProtectedPathRule(
        path=".vibecode/index/*",
        rule=(
            "Generated index output; regenerate through index commands instead "
            "of manual edits. Only .vibecode/index/README.md and "
            ".vibecode/index/schema.json are human-maintained source truth."
        ),
    ),
    ProtectedPathRule(
        path=".vibecode/current/*",
        rule="Runtime/session state; do not commit or treat as source truth.",
    ),
    ProtectedPathRule(
        path=".vibecode/generated/*",
        rule="Generated output; regenerate instead of manual edits.",
    ),
    ProtectedPathRule(
        path=".vibecode/logs/*",
        rule="Runtime logs; do not commit or treat as source truth.",
    ),
    ProtectedPathRule(
        path=".vibecode/runs/*",
        rule="Agent run metadata; do not commit or treat as source truth.",
    ),
    ProtectedPathRule(
        path=".vibecode/tmp/*",
        rule="Temporary runtime state; do not commit or treat as source truth.",
    ),
    ProtectedPathRule(
        path=".vibecode/cache/*",
        rule="Runtime cache; do not commit or treat as source truth.",
    ),
    ProtectedPathRule(
        path="README.md",
        rule=(
            "Manual-only until generated block markers are introduced; only "
            "README/docs tasks may change it."
        ),
        explicit_task_scope_required=False,
    ),
)


def render_protected_paths_yaml() -> str:
    lines = [
        "# vibecode protected paths policy",
        "# schema: vibecode/protected-paths/v1",
        "",
        "protected_paths:",
    ]
    for record in DEFAULT_PROTECTED_PATH_RULES:
        lines.extend([
            f'  - path: "{record.path}"',
            f'    rule: "{record.rule}"',
        ])
        if record.required_tests:
            lines.append("    required_tests:")
            lines.extend(f'      - "{test}"' for test in record.required_tests)
        if record.explicit_task_scope_required is not None:
            value = str(record.explicit_task_scope_required).lower()
            lines.append(f"    explicit_task_scope_required: {value}")
        lines.append("")
    return "\n".join(lines)


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
        raise ValueError(f"Invalid YAML in {config_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError("project.yaml must be a YAML mapping at the top level")

    project_section = raw.get("project") or {}
    project_id = project_section.get("id")
    if not project_id:
        raise ValueError("project.yaml: missing required field 'project.id'")

    project_name = str(project_section.get("name") or project_id)

    # Normalize root path — accept both forward and back slashes.
    raw_root = strip_to_posix(str(project_section.get("root") or "."))
    root_path = Path(raw_root)
    if not root_path.is_absolute():
        root_path = (vibecode_dir.parent / root_path).resolve()
    else:
        root_path = root_path.resolve()

    if not root_path.exists():
        raise FileNotFoundError(f"project root does not exist: {root_path}")

    indexing = raw.get("indexing") or {}
    check_records = _load_required_check_records(vibecode_dir)
    protected_path_records = load_protected_path_records(vibecode_dir)
    legacy_protected_paths = list(raw.get("protected_paths") or [])
    protected_paths = (
        [_protected_path_pattern(record.path) for record in protected_path_records]
        if protected_path_records
        else legacy_protected_paths
    )
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
        protected_paths=protected_paths,
        protected_path_records=protected_path_records,
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


def load_protected_path_records(vibecode_dir: Path) -> list[ProtectedPathRule]:
    path = vibecode_dir / "checks" / "protected_paths.yaml"
    if not path.exists():
        return []
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"protected_paths.yaml is not valid YAML: {exc}") from exc
    if raw is None:
        raise ValueError("protected_paths.yaml: missing required field 'protected_paths'")
    if not isinstance(raw, dict):
        raise ValueError("protected_paths.yaml must be a YAML mapping at the top level")
    if "protected_paths" not in raw:
        raise ValueError("protected_paths.yaml: missing required field 'protected_paths'")
    records = raw["protected_paths"]
    if not isinstance(records, list):
        raise ValueError("protected_paths.yaml: 'protected_paths' must be a list")

    normalized: list[ProtectedPathRule] = []
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise ValueError(f"protected_paths.yaml: entry #{index} must be a mapping")
        path_value = record.get("path")
        rule = record.get("rule")
        if not isinstance(path_value, str) or not path_value.strip():
            raise ValueError(
                f"protected_paths.yaml: entry #{index} requires non-empty string field 'path'"
            )
        if not isinstance(rule, str) or not rule.strip():
            raise ValueError(
                f"protected_paths.yaml: entry #{index} requires non-empty string field 'rule'"
            )
        required_tests = record.get("required_tests")
        if required_tests is None:
            required_tests = ()
        elif isinstance(required_tests, str):
            required_tests = (required_tests.strip(),)
        elif isinstance(required_tests, list):
            required_tests = tuple(
                str(item).strip() for item in required_tests if str(item).strip()
            )
        else:
            raise ValueError(
                f"protected_paths.yaml: entry #{index} field 'required_tests' "
                "must be a string or list"
            )
        explicit_scope = record.get("explicit_task_scope_required")
        if explicit_scope is not None and not isinstance(explicit_scope, bool):
            raise ValueError(
                f"protected_paths.yaml: entry #{index} field "
                "'explicit_task_scope_required' must be a boolean"
            )
        normalized.append(
            ProtectedPathRule(
                path=path_value.strip(),
                rule=rule.strip(),
                required_tests=tuple(required_tests),
                explicit_task_scope_required=explicit_scope,
            )
        )
    return normalized


def _protected_path_pattern(path: str) -> str:
    if path.endswith("/"):
        return f"{path}**"
    return path


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
    seen_command_strings: set[str] = set()
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise ValueError(f"required_checks.yaml: check #{index} must be a mapping")
        name = record.get("name")
        command = record.get("command")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                f"required_checks.yaml: check #{index} requires a non-empty name"
            )
        name = name.strip()

        # Accept both string and list-form commands.
        if isinstance(command, list):
            str_command = command
            if not command:
                raise ValueError(
                    f"required_checks.yaml: check #{index} ({name!r}) has an empty command list"
                )
            for i, elem in enumerate(command):
                if not isinstance(elem, str) or not elem.strip():
                    raise ValueError(
                        f"required_checks.yaml: check #{index} ({name!r}) "
                        f"command element #{i + 1} must be a non-empty string"
                    )
            command_str = " ".join(command)
        elif isinstance(command, str) and command.strip():
            str_command = command.strip()
            command_str = str_command
        else:
            raise ValueError(
                f"required_checks.yaml: check #{index} requires a non-empty "
                "command (string or list of strings)"
            )

        if command_str.lower() in _GENERIC_COMMANDS:
            raise ValueError(
                f"required_checks.yaml: check #{index} ({name!r}) has a "
                f"generic command {command_str!r}; use a concrete command "
                f"(e.g. 'python -m pytest' instead of 'tests')"
            )
        if command_str in seen_command_strings:
            raise ValueError(
                f"required_checks.yaml: duplicate command {command_str!r} "
                f"(first seen in check #{index})"
            )
        seen_command_strings.add(command_str)
        normalized.append({
            "name": name,
            "command": str_command,
            "required": bool(record.get("required", True)),
        })
    return normalized
