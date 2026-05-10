"""Tests for vibecode guard CLI command."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from vibecode.cli import create_parser, main
from vibecode.guard import (
    GuardFinding,
    GuardResult,
    _dedupe_findings,
    cmd_guard,
    evaluate_guard,
)
from vibecode.git_state import GitState
from types import SimpleNamespace


# ---------------------------------------------------------------------------
# cmd_guard unit tests (direct invocation with mocked state)
# ---------------------------------------------------------------------------


def _make_args(repo_root: str, strict: bool = False):
    """Build a minimal args namespace for cmd_guard."""
    return SimpleNamespace(repo_root=repo_root, strict=strict)


def test_cmd_guard_missing_project_yaml_exits_nonzero(tmp_path, capsys):
    """guard on a repo without project.yaml should fail with a clear message."""
    d = tmp_path / ".vibecode"
    d.mkdir()
    rc = cmd_guard(_make_args(str(tmp_path)))
    err = capsys.readouterr().err
    assert rc == 1
    assert "project.yaml" in err
    assert "vibecode init" in err


def test_cmd_guard_non_git_repo_exits_nonzero(tmp_path, capsys):
    """guard on a non-git directory should fail with a clear message."""
    vibecode_dir = tmp_path / ".vibecode"
    vibecode_dir.mkdir()
    (vibecode_dir / "project.yaml").write_text(
        "project:\n  id: test\n  name: test\n", encoding="utf-8"
    )
    rc = cmd_guard(_make_args(str(tmp_path)))
    err = capsys.readouterr().err
    assert rc == 1
    assert "not a git repository" in err


def test_cmd_guard_clean_repo_returns_zero(tmp_path):
    """guard on a clean git repo with no violations should return 0."""
    _init_git_repo(tmp_path)
    vibecode_dir = tmp_path / ".vibecode"
    vibecode_dir.mkdir()
    (vibecode_dir / "project.yaml").write_text(
        "project:\n  id: test\n  name: test\n  root: .\n", encoding="utf-8"
    )
    rc = cmd_guard(_make_args(str(tmp_path)))
    assert rc == 0


def test_cmd_guard_hard_violation_returns_nonzero(tmp_path):
    """guard should return 1 when there is a hard (error) finding."""
    _init_git_repo(tmp_path)
    vibecode_dir = tmp_path / ".vibecode"
    vibecode_dir.mkdir()
    (vibecode_dir / "project.yaml").write_text(
        "project:\n  id: test\n  name: test\n  root: .\n", encoding="utf-8"
    )
    # Create a generated runtime file and commit it, then modify it
    current_dir = vibecode_dir / "current"
    current_dir.mkdir()
    f = current_dir / "context_pack.md"
    f.write_text("# old\n", encoding="utf-8")
    _git_add_commit(tmp_path)
    f.write_text("# modified\n", encoding="utf-8")

    rc = cmd_guard(_make_args(str(tmp_path)))
    assert rc == 1


def test_cmd_guard_warning_only_returns_zero(tmp_path):
    """guard should return 0 when there are only warnings."""
    _init_git_repo(tmp_path)
    vibecode_dir = tmp_path / ".vibecode"
    vibecode_dir.mkdir()
    (vibecode_dir / "project.yaml").write_text(
        "project:\n  id: test\n  name: test\n  root: .\n", encoding="utf-8"
    )
    # Modify a source file without a corresponding test change (warning)
    src = tmp_path / "src" / "app.py"
    src.parent.mkdir()
    src.write_text("x = 1\n", encoding="utf-8")
    _git_add_commit(tmp_path)
    src.write_text("x = 2\n", encoding="utf-8")

    rc = cmd_guard(_make_args(str(tmp_path)))
    assert rc == 0


def test_cmd_guard_strict_flag_makes_warnings_fail(tmp_path):
    """With --strict, warnings should cause a non-zero exit."""
    _init_git_repo(tmp_path)
    vibecode_dir = tmp_path / ".vibecode"
    vibecode_dir.mkdir()
    (vibecode_dir / "project.yaml").write_text(
        "project:\n  id: test\n  name: test\n  root: .\n", encoding="utf-8"
    )
    # No violations at all — strict should still pass
    rc = cmd_guard(_make_args(str(tmp_path), strict=True))
    assert rc == 0


def test_cmd_guard_prints_clear_reasons_for_errors(tmp_path, capsys):
    """guard should print rule_id and message for hard violations."""
    _init_git_repo(tmp_path)
    vibecode_dir = tmp_path / ".vibecode"
    vibecode_dir.mkdir()
    (vibecode_dir / "project.yaml").write_text(
        "project:\n  id: test\n  name: test\n  root: .\n", encoding="utf-8"
    )
    current_dir = vibecode_dir / "current"
    current_dir.mkdir()
    f = current_dir / "context_pack.md"
    f.write_text("# old\n", encoding="utf-8")
    _git_add_commit(tmp_path)
    f.write_text("# modified\n", encoding="utf-8")

    rc = cmd_guard(_make_args(str(tmp_path)))
    err = capsys.readouterr().err

    assert rc == 1
    assert "HARD FAILURES" in err
    assert "protected-path-generated" in err


def test_cmd_guard_prints_warnings_separately(tmp_path, capsys):
    """guard should print warnings in a separate section."""
    _init_git_repo(tmp_path)
    vibecode_dir = tmp_path / ".vibecode"
    vibecode_dir.mkdir()
    (vibecode_dir / "project.yaml").write_text(
        "project:\n  id: test\n  name: test\n  root: .\n", encoding="utf-8"
    )
    src = tmp_path / "src" / "app.py"
    src.parent.mkdir()
    src.write_text("x = 1\n", encoding="utf-8")
    _git_add_commit(tmp_path)
    src.write_text("x = 2\n", encoding="utf-8")

    rc = cmd_guard(_make_args(str(tmp_path)))
    err = capsys.readouterr().err

    assert rc == 0
    assert "WARNINGS" in err


# ---------------------------------------------------------------------------
# CLI parser / dispatch tests
# ---------------------------------------------------------------------------


def test_guard_subparser_exists():
    """The CLI parser should include a 'guard' subcommand."""
    parser = create_parser()
    # Should not raise
    args = parser.parse_args(["guard", "."])
    assert args.command == "guard"


def test_guard_help_exits_zero():
    """guard --help should exit with code 0."""
    with pytest.raises(SystemExit) as exc_info:
        main(["guard", "--help"])
    assert exc_info.value.code == 0


def test_guard_missing_repo_root_exits_nonzero_with_message(tmp_path, capsys):
    """guard with a missing repo root should exit nonzero with a readable message."""
    missing = tmp_path / "nonexistent"
    rc = main(["guard", str(missing)])
    err = capsys.readouterr().err
    assert rc == 1
    assert "nonexistent" in err
    assert "Traceback" not in err


def test_guard_missing_project_yaml_exits_nonzero(tmp_path, capsys):
    """guard without project.yaml should exit with a clear error."""
    rc = main(["guard", str(tmp_path)])
    err = capsys.readouterr().err
    assert rc == 1
    assert "project.yaml" in err
    assert "vibecode init" in err


def test_guard_handles_config_load_error_gracefully(tmp_path, capsys):
    """guard should handle invalid project.yaml without a traceback."""
    vibecode_dir = tmp_path / ".vibecode"
    vibecode_dir.mkdir()
    (vibecode_dir / "project.yaml").write_text(
        "key: [unclosed\n", encoding="utf-8"
    )
    # Initialize git so it's detected as a repo
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=str(tmp_path),
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(tmp_path),
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(tmp_path),
        capture_output=True,
    )
    rc = main(["guard", str(tmp_path)])
    err = capsys.readouterr().err
    assert rc == 1
    assert "Error" in err
    assert "Traceback" not in err


# ---------------------------------------------------------------------------
# Internal guard logic integration
# ---------------------------------------------------------------------------


def test_evaluate_guard_with_clean_git_state():
    """evaluate_guard on a clean git state should return no findings."""
    state = GitState(is_git_repo=True, changed_paths=(), untracked_paths=())
    result = evaluate_guard(state, task="")
    assert result.passed is True
    assert result.findings == ()


def test_evaluate_guard_catches_generated_runtime_changes():
    """evaluate_guard should flag generated runtime file changes."""
    state = GitState(
        is_git_repo=True,
        changed_paths=(".vibecode/current/context_pack.md",),
        untracked_paths=(),
    )
    result = evaluate_guard(state, task="")
    assert result.passed is False
    rule_ids = {f.rule_id for f in result.findings}
    assert (
        "generated-runtime-files" in rule_ids
        or "protected-path-generated" in rule_ids
    )


def test_evaluate_guard_catches_readme_changes():
    """evaluate_guard should flag README.md changes."""
    state = GitState(
        is_git_repo=True,
        changed_paths=("README.md",),
        untracked_paths=(),
    )
    result = evaluate_guard(state, task="update app logic")
    assert result.passed is False
    assert any(f.rule_id == "readme-manual-only" for f in result.findings)


# ---------------------------------------------------------------------------
# _dedupe_findings
# ---------------------------------------------------------------------------


def test_dedupe_findings_removes_duplicates():
    f1 = GuardFinding(
        rule_id="test", path="foo.py", severity="error", message="msg"
    )
    f2 = GuardFinding(
        rule_id="test", path="foo.py", severity="error", message="msg"
    )
    result = _dedupe_findings((f1, f2))
    assert len(result) == 1


def test_dedupe_findings_keeps_distinct():
    f1 = GuardFinding(
        rule_id="test", path="foo.py", severity="error", message="msg1"
    )
    f2 = GuardFinding(
        rule_id="test", path="bar.py", severity="error", message="msg2"
    )
    result = _dedupe_findings((f1, f2))
    assert len(result) == 2


def test_dedupe_findings_keeps_distinct_rules_same_path():
    f1 = GuardFinding(
        rule_id="rule-a", path="foo.py", severity="error", message="msg1"
    )
    f2 = GuardFinding(
        rule_id="rule-b", path="foo.py", severity="error", message="msg2"
    )
    result = _dedupe_findings((f1, f2))
    assert len(result) == 2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init_git_repo(repo: Path) -> None:
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=str(repo),
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(repo),
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(repo),
        capture_output=True,
    )


def _git_add_commit(repo: Path) -> None:
    subprocess.run(
        ["git", "add", "."],
        cwd=str(repo),
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=str(repo),
        capture_output=True,
    )