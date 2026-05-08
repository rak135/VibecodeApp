"""Tests for vibecode validation."""

from __future__ import annotations

import json
from pathlib import Path

from vibecode.cli import main


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_validate_valid_indexed_fixture_exits_zero(tmp_path, capsys):
    assert main(["init", str(tmp_path), "--id", "validproj", "--name", "Valid Project"]) == 0
    _write(tmp_path / "app.py", "def hello():\n    return 'hi'\n")
    assert main(["index", str(tmp_path)]) == 0

    rc = main(["validate", str(tmp_path)])
    captured = capsys.readouterr()

    assert rc == 0
    assert "OK:" in captured.out
    assert "ERROR:" not in captured.out
    report_path = tmp_path / ".vibecode" / "current" / "validation.json"
    assert report_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "ok"


def test_validate_missing_project_yaml_exits_nonzero(tmp_path, capsys):
    rc = main(["validate", str(tmp_path)])
    captured = capsys.readouterr()

    assert rc == 1
    assert "ERROR:" in captured.out
    assert ".vibecode/project.yaml is missing" in captured.out


def test_empty_invariants_warns_but_does_not_fail(tmp_path):
    assert main(["init", str(tmp_path), "--id", "weakproj", "--name", "Weak Project"]) == 0
    _write(tmp_path / ".vibecode" / "architecture" / "INVARIANTS.md", "\n")
    _write(tmp_path / "app.py", "def hello():\n    return 'hi'\n")

    assert main(["index", str(tmp_path)]) == 0

    last_index = json.loads(
        (tmp_path / ".vibecode" / "current" / "last_index.json").read_text(encoding="utf-8")
    )
    validation = last_index["validation"]
    assert validation["summary"]["errors"] == 0
    assert validation["summary"]["warnings"] >= 1
    assert any(
        item["level"] == "WARN" and "no confirmed invariants" in item["message"]
        for item in validation["items"]
    )
