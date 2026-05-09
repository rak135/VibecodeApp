"""Tests for vibecode config and project modules."""

from __future__ import annotations

import pytest
from pathlib import Path

from vibecode.config import (
    _GENERIC_COMMANDS,
    _load_required_check_records,
    ProtectedPathRule,
    ProjectConfig,
    load_config,
    load_protected_path_records,
)


_VALID_YAML = """\
project:
  id: myapp
  name: MyApp
  root: .

indexing:
  include:
    - "**/*.py"
    - "**/*.md"
  exclude:
    - ".git/**"
    - "__pycache__/**"

protected_paths:
  - ".vibecode/architecture/**"

risk_rules: []

required_checks:
  - lint
  - tests
"""

_CHECKS_YAML = """\
checks:
  - name: unit tests
    command: python -m pytest
    required: true

  - name: optional docs
    command: python -m markdownlint README.md
    required: false
"""


def test_project_config_defaults():
    cfg = ProjectConfig(project_id="myapp", project_name="MyApp", root=Path("/tmp/myapp"))
    assert cfg.include == []
    assert cfg.exclude == []
    assert cfg.protected_paths == []
    assert cfg.protected_path_records == []
    assert cfg.risk_rules == []
    assert cfg.required_checks == []


def test_load_config_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="project.yaml not found"):
        load_config(tmp_path / ".vibecode")


def test_load_config_valid(tmp_path):
    vibecode_dir = tmp_path / ".vibecode"
    vibecode_dir.mkdir()
    (vibecode_dir / "project.yaml").write_text(_VALID_YAML, encoding="utf-8")

    cfg = load_config(vibecode_dir)

    assert cfg.project_id == "myapp"
    assert cfg.project_name == "MyApp"
    assert cfg.root == tmp_path.resolve()
    assert "**/*.py" in cfg.include
    assert ".git/**" in cfg.exclude
    assert ".vibecode/architecture/**" in cfg.protected_paths
    assert cfg.risk_rules == []
    assert cfg.required_checks == ["lint", "tests"]


def test_load_config_prefers_required_checks_yaml(tmp_path):
    vibecode_dir = tmp_path / ".vibecode"
    vibecode_dir.mkdir()
    (vibecode_dir / "project.yaml").write_text(_VALID_YAML, encoding="utf-8")
    (vibecode_dir / "checks").mkdir()
    (vibecode_dir / "checks" / "required_checks.yaml").write_text(
        _CHECKS_YAML,
        encoding="utf-8",
    )

    cfg = load_config(vibecode_dir)

    assert cfg.required_checks == ["python -m pytest"]
    assert cfg.required_check_records == [
        {
            "name": "unit tests",
            "command": "python -m pytest",
            "required": True,
        },
        {
            "name": "optional docs",
            "command": "python -m markdownlint README.md",
            "required": False,
        },
    ]


def test_load_config_prefers_protected_paths_yaml(tmp_path):
    vibecode_dir = tmp_path / ".vibecode"
    vibecode_dir.mkdir()
    (vibecode_dir / "project.yaml").write_text(_VALID_YAML, encoding="utf-8")
    (vibecode_dir / "checks").mkdir()
    (vibecode_dir / "checks" / "protected_paths.yaml").write_text(
        """\
protected_paths:
  - path: ".vibecode/architecture/"
    rule: "Architecture truth requires explicit task scope."
  - path: "vibecode/context/renderer.py"
    rule: "Context rendering changes require tests."
""",
        encoding="utf-8",
    )

    cfg = load_config(vibecode_dir)

    assert cfg.protected_path_records == [
        ProtectedPathRule(
            path=".vibecode/architecture/",
            rule="Architecture truth requires explicit task scope.",
        ),
        ProtectedPathRule(
            path="vibecode/context/renderer.py",
            rule="Context rendering changes require tests.",
        ),
    ]
    assert cfg.protected_paths == [
        ".vibecode/architecture/**",
        "vibecode/context/renderer.py",
    ]


def test_load_protected_path_records_rejects_missing_top_level_field(tmp_path):
    vibecode_dir = tmp_path / ".vibecode"
    (vibecode_dir / "checks").mkdir(parents=True)
    (vibecode_dir / "checks" / "protected_paths.yaml").write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="missing required field 'protected_paths'"):
        load_protected_path_records(vibecode_dir)


def test_load_protected_path_records_rejects_non_mapping(tmp_path):
    vibecode_dir = tmp_path / ".vibecode"
    (vibecode_dir / "checks").mkdir(parents=True)
    (vibecode_dir / "checks" / "protected_paths.yaml").write_text("[]\n", encoding="utf-8")

    with pytest.raises(ValueError, match="YAML mapping"):
        load_protected_path_records(vibecode_dir)


def test_load_protected_path_records_rejects_missing_path(tmp_path):
    vibecode_dir = tmp_path / ".vibecode"
    (vibecode_dir / "checks").mkdir(parents=True)
    (vibecode_dir / "checks" / "protected_paths.yaml").write_text(
        "protected_paths:\n  - rule: Must have a path.\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="entry #1.*field 'path'"):
        load_protected_path_records(vibecode_dir)


def test_load_protected_path_records_rejects_missing_rule(tmp_path):
    vibecode_dir = tmp_path / ".vibecode"
    (vibecode_dir / "checks").mkdir(parents=True)
    (vibecode_dir / "checks" / "protected_paths.yaml").write_text(
        "protected_paths:\n  - path: .vibecode/checks/\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="entry #1.*field 'rule'"):
        load_protected_path_records(vibecode_dir)


def test_load_config_missing_project_id(tmp_path):
    vibecode_dir = tmp_path / ".vibecode"
    vibecode_dir.mkdir()
    (vibecode_dir / "project.yaml").write_text("project:\n  name: NoId\n  root: .\n")

    with pytest.raises(ValueError, match="project.id"):
        load_config(vibecode_dir)


def test_load_config_nonexistent_root(tmp_path):
    vibecode_dir = tmp_path / ".vibecode"
    vibecode_dir.mkdir()
    (vibecode_dir / "project.yaml").write_text(
        "project:\n  id: myapp\n  name: MyApp\n  root: nonexistent_subdir\n"
    )

    with pytest.raises(FileNotFoundError, match="project root does not exist"):
        load_config(vibecode_dir)


def test_load_config_windows_style_path(tmp_path):
    """A root expressed with Windows backslashes should be normalised safely."""
    subdir = tmp_path / "src"
    subdir.mkdir()
    vibecode_dir = tmp_path / ".vibecode"
    vibecode_dir.mkdir()
    # Write root using backslash notation
    (vibecode_dir / "project.yaml").write_text(
        "project:\n  id: myapp\n  name: MyApp\n  root: .\\src\n"
    )

    cfg = load_config(vibecode_dir)

    assert cfg.root == subdir.resolve()


# ---------------------------------------------------------------------------
# Required checks validation tests
# ---------------------------------------------------------------------------


def test_required_check_rejects_missing_name(tmp_path):
    """A check entry without a name must raise ValueError."""
    checks_yaml = """\
checks:
  - command: python -m pytest
"""
    (tmp_path / ".vibecode" / "checks").mkdir(parents=True)
    (tmp_path / ".vibecode" / "checks" / "required_checks.yaml").write_text(
        checks_yaml, encoding="utf-8"
    )

    with pytest.raises(ValueError, match="non-empty name"):
        _load_required_check_records(tmp_path / ".vibecode")


def test_required_check_rejects_missing_command(tmp_path):
    """A check entry without a command must raise ValueError."""
    checks_yaml = """\
checks:
  - name: unit tests
"""
    (tmp_path / ".vibecode" / "checks").mkdir(parents=True)
    (tmp_path / ".vibecode" / "checks" / "required_checks.yaml").write_text(
        checks_yaml, encoding="utf-8"
    )

    with pytest.raises(ValueError, match="non-empty command"):
        _load_required_check_records(tmp_path / ".vibecode")


def test_required_check_rejects_generic_command(tmp_path):
    """Generic commands like 'tests' or 'lint' must be rejected."""
    for generic_cmd in sorted(_GENERIC_COMMANDS):
        checks_yaml = f"""\
checks:
  - name: run {generic_cmd}
    command: {generic_cmd}
"""
        vibecode_dir = tmp_path / f".vibecode_{generic_cmd}"
        (vibecode_dir / "checks").mkdir(parents=True)
        (vibecode_dir / "checks" / "required_checks.yaml").write_text(
            checks_yaml, encoding="utf-8"
        )

        with pytest.raises(ValueError, match=f"generic command {generic_cmd!r}"):
            _load_required_check_records(vibecode_dir)


def test_required_check_rejects_duplicate_commands(tmp_path):
    """Duplicate commands must be rejected."""
    checks_yaml = """\
checks:
  - name: unit tests
    command: python -m pytest
  - name: integration tests
    command: python -m pytest
"""
    (tmp_path / ".vibecode" / "checks").mkdir(parents=True)
    (tmp_path / ".vibecode" / "checks" / "required_checks.yaml").write_text(
        checks_yaml, encoding="utf-8"
    )

    with pytest.raises(ValueError, match="duplicate command"):
        _load_required_check_records(tmp_path / ".vibecode")


def test_required_check_accepts_concrete_commands(tmp_path):
    """Concrete commands with full paths/invocations are accepted."""
    checks_yaml = """\
checks:
  - name: unit tests
    command: python -m pytest
  - name: lint
    command: ruff check .
  - name: optional docs
    command: python -m markdownlint README.md
    required: false
"""
    (tmp_path / ".vibecode" / "checks").mkdir(parents=True)
    (tmp_path / ".vibecode" / "checks" / "required_checks.yaml").write_text(
        checks_yaml, encoding="utf-8"
    )

    records = _load_required_check_records(tmp_path / ".vibecode")

    assert len(records) == 3
    assert records[0] == {"name": "unit tests", "command": "python -m pytest", "required": True}
    assert records[1] == {"name": "lint", "command": "ruff check .", "required": True}
    assert records[2] == {"name": "optional docs", "command": "python -m markdownlint README.md", "required": False}


def test_required_check_defaults_required_true(tmp_path):
    """The 'required' field defaults to True when omitted."""
    checks_yaml = """\
checks:
  - name: unit tests
    command: python -m pytest
"""
    (tmp_path / ".vibecode" / "checks").mkdir(parents=True)
    (tmp_path / ".vibecode" / "checks" / "required_checks.yaml").write_text(
        checks_yaml, encoding="utf-8"
    )

    records = _load_required_check_records(tmp_path / ".vibecode")

    assert records[0]["required"] is True


def test_required_check_empty_name_rejected(tmp_path):
    """An empty name string must be rejected."""
    checks_yaml = """\
checks:
  - name: ""
    command: python -m pytest
"""
    vibecode_dir = tmp_path / ".vibecode_empty_name"
    (vibecode_dir / "checks").mkdir(parents=True)
    (vibecode_dir / "checks" / "required_checks.yaml").write_text(
        checks_yaml, encoding="utf-8"
    )

    with pytest.raises(ValueError, match="non-empty name"):
        _load_required_check_records(vibecode_dir)


def test_required_check_empty_command_rejected(tmp_path):
    """An empty command string must be rejected."""
    checks_yaml = """\
checks:
  - name: unit tests
    command: ""
"""
    vibecode_dir = tmp_path / ".vibecode_empty_cmd"
    (vibecode_dir / "checks").mkdir(parents=True)
    (vibecode_dir / "checks" / "required_checks.yaml").write_text(
        checks_yaml, encoding="utf-8"
    )

    with pytest.raises(ValueError, match="non-empty command"):
        _load_required_check_records(vibecode_dir)

