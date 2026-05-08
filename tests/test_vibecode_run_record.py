"""Tests for auditable index run records."""

from __future__ import annotations

import json
from pathlib import Path

from vibecode.cli import main


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_index_writes_last_index_and_json_run_record(tmp_path):
    assert main(["init", str(tmp_path), "--id", "runproj", "--name", "Run Project"]) == 0
    _write(tmp_path / "good.py", "def ok():\n    return 1\n")
    _write(tmp_path / "broken.py", "def nope(:\n    pass\n")
    _write(tmp_path / "tests" / "test_good.py", "from good import ok\n\ndef test_ok():\n    assert ok() == 1\n")

    assert main(["index", str(tmp_path)]) == 0

    last_index = tmp_path / ".vibecode" / "current" / "last_index.json"
    assert last_index.exists()
    data = json.loads(last_index.read_text(encoding="utf-8"))

    assert data["project_id"] == "runproj"
    assert data["root"] == tmp_path.resolve().as_posix()
    assert data["started_at"]
    assert data["finished_at"]
    assert data["generator"]
    assert set(data["counts"]) == {
        "files",
        "symbols",
        "tests",
        "dependency_edges",
        "warnings",
        "errors",
    }
    assert data["counts"]["files"] >= 3
    assert data["counts"]["symbols"] >= 1
    assert data["counts"]["tests"] >= 1
    assert data["counts"]["warnings"] == len(data["warnings"])
    assert data["counts"]["errors"] == len(data["errors"])
    assert any("broken.py" in warning for warning in data["warnings"])

    run_logs = sorted((tmp_path / ".vibecode" / "logs" / "index_runs").glob("*.json"))
    assert run_logs
    run_data = json.loads(run_logs[-1].read_text(encoding="utf-8"))
    assert run_data["project_id"] == "runproj"
