"""Tests for vibecode config and project modules."""

from __future__ import annotations

import pytest
from pathlib import Path

from vibecode.config import ProjectConfig, load_config


def test_project_config_defaults():
    cfg = ProjectConfig(project_id="myapp", project_name="MyApp", root=Path("/tmp/myapp"))
    assert cfg.include == []
    assert cfg.exclude == []
    assert cfg.protected_paths == []
    assert cfg.risk_rules == []
    assert cfg.required_checks == []


def test_load_config_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="project.yaml not found"):
        load_config(tmp_path / ".vibecode")


def test_load_config_not_implemented(tmp_path):
    vibecode_dir = tmp_path / ".vibecode"
    vibecode_dir.mkdir()
    (vibecode_dir / "project.yaml").write_text("project:\n  id: test\n")
    with pytest.raises(NotImplementedError):
        load_config(vibecode_dir)
