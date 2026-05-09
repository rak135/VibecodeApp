"""Tests for vibecode config and project modules."""

from __future__ import annotations

import pytest
from pathlib import Path

from vibecode.config import (
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

