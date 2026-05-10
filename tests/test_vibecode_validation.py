"""Tests for vibecode validation."""

from __future__ import annotations

import json
import subprocess
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


def test_validate_does_not_mutate_context_pack(tmp_path):
    """validate must not overwrite .vibecode/current/context_pack.md."""
    _init_repo(tmp_path)
    assert main(["init", str(tmp_path), "--id", "ctxproj", "--name", "Context Project"]) == 0
    _write(tmp_path / "app.py", "def hello():\n    return 'hi'\n")
    _commit_all(tmp_path)

    assert main(["index", str(tmp_path)]) == 0

    real_task = "real application task"
    assert main(["context", str(tmp_path), "--task", real_task]) == 0

    context_pack_path = tmp_path / ".vibecode" / "current" / "context_pack.md"
    assert context_pack_path.exists()
    original_content = context_pack_path.read_text(encoding="utf-8")
    assert real_task in original_content

    assert main(["validate", str(tmp_path)]) == 0

    assert context_pack_path.exists()
    restored_content = context_pack_path.read_text(encoding="utf-8")
    assert restored_content == original_content, "context_pack.md was mutated by validate"
    assert real_task in restored_content
    assert "validation smoke" not in restored_content

    report_path = tmp_path / ".vibecode" / "current" / "validation.json"
    assert report_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "ok"


def _init_repo(repo: Path) -> None:
    result = subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        subprocess.run(["git", "init"], cwd=repo, capture_output=True, text=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo, capture_output=True, text=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo, capture_output=True, text=True,
    )


def _commit_all(repo: Path) -> None:
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True, text=True)


def test_validate_warns_when_gitignore_hides_source_truth_files(tmp_path):
    """Validate should warn when .gitignore hides human-maintained .vibecode files."""
    _init_repo(tmp_path)
    assert main(["init", str(tmp_path), "--id", "hproj", "--name", "Hidden Project"]) == 0
    _write(tmp_path / "app.py", "def hello():\n    return 'hi'\n")
    _commit_all(tmp_path)

    # Add a broad .gitignore that hides .vibecode
    _write(tmp_path / ".gitignore", ".vibecode/\n")
    _commit_all(tmp_path)

    assert main(["index", str(tmp_path)]) == 0

    rc = main(["validate", str(tmp_path)])
    report_path = tmp_path / ".vibecode" / "current" / "validation.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert any(
        "human-maintained .vibecode source-truth files are git-ignored" in item.get("message", "")
        for item in report["items"]
    )


def test_validate_no_warning_when_gitignore_is_correct(tmp_path):
    """Validate should not warn when .gitignore only ignores generated paths."""
    _init_repo(tmp_path)
    assert main(["init", str(tmp_path), "--id", "gproj", "--name", "Good Project"]) == 0
    _write(tmp_path / "app.py", "def hello():\n    return 'hi'\n")
    _commit_all(tmp_path)

    # Write correct .gitignore that only ignores generated/runtime paths
    _write(
        tmp_path / ".gitignore",
        ".vibecode/current/\n"
        ".vibecode/generated/\n"
        ".vibecode/runs/\n"
        ".vibecode/tmp/\n"
        ".vibecode/cache/\n"
        ".vibecode/logs/\n"
        ".vibecode/index/*.generated.*\n",
    )
    _commit_all(tmp_path)

    assert main(["index", str(tmp_path)]) == 0
    rc = main(["validate", str(tmp_path)])
    report_path = tmp_path / ".vibecode" / "current" / "validation.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert not any(
        "human-maintained .vibecode source-truth files are git-ignored" in item.get("message", "")
        for item in report["items"]
    )
