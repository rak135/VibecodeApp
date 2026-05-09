"""Tests for vibecode handoff-check CLI command."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from vibecode.cli import create_parser, main
from vibecode.handoff import cmd_handoff_check


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


def _make_handoff(repo: Path, now: str, next_: str, blockers: str) -> None:
    handoff_dir = repo / ".vibecode" / "handoff"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    (handoff_dir / "NOW.md").write_text(f"# Now\n\n{now}\n", encoding="utf-8")
    (handoff_dir / "NEXT.md").write_text(f"# Next\n\n{next_}\n", encoding="utf-8")
    (handoff_dir / "BLOCKERS.md").write_text(f"# Blockers\n\n{blockers}\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# cmd_handoff_check unit tests (direct invocation)
# ---------------------------------------------------------------------------


def test_cmd_handoff_check_missing_repo_returns_nonzero():
    """handoff-check on a missing directory should return 1."""
    args = SimpleNamespace(repo_root="/nonexistent/path", json=False)
    rc = cmd_handoff_check(args)
    assert rc == 1


def test_cmd_handoff_check_non_git_repo_returns_nonzero(tmp_path):
    """handoff-check on a non-git directory should return 1."""
    _make_handoff(tmp_path, "Working on X.", "Do Y.", "No blocker.")
    args = SimpleNamespace(repo_root=str(tmp_path), json=False)
    rc = cmd_handoff_check(args)
    assert rc == 1


def test_cmd_handoff_check_valid_passes(tmp_path):
    """Valid handoff files with no architecture changes → return 0."""
    _init_git_repo(tmp_path)
    _make_handoff(tmp_path, "Working on X.", "Do Y.", "No blocker.")
    _git_add_commit(tmp_path)

    args = SimpleNamespace(repo_root=str(tmp_path), json=False)
    rc = cmd_handoff_check(args)
    assert rc == 0


def test_cmd_handoff_check_placeholder_fails(tmp_path):
    """Placeholder text in handoff files → return 1."""
    _init_git_repo(tmp_path)
    _make_handoff(tmp_path, "TODO: figure this out", "Do Y.", "No blocker.")
    _git_add_commit(tmp_path)

    args = SimpleNamespace(repo_root=str(tmp_path), json=False)
    rc = cmd_handoff_check(args)
    assert rc == 1


def test_cmd_handoff_check_missing_files_fails(tmp_path):
    """Missing handoff files → return 1."""
    _init_git_repo(tmp_path)
    _git_add_commit(tmp_path)

    args = SimpleNamespace(repo_root=str(tmp_path), json=False)
    rc = cmd_handoff_check(args)
    assert rc == 1


def test_cmd_handoff_check_arch_change_without_handoff_fails(tmp_path):
    """Architecture doc changed without updating handoff/history → return 1."""
    _init_git_repo(tmp_path)
    _make_handoff(tmp_path, "Working on X.", "Do Y.", "No blocker.")
    arch_dir = tmp_path / ".vibecode" / "architecture"
    arch_dir.mkdir(parents=True, exist_ok=True)
    (arch_dir / "INVARIANTS.md").write_text("# Invariants\n\nSome rules.\n")
    _git_add_commit(tmp_path)

    # Simulate changing the architecture doc
    (arch_dir / "INVARIANTS.md").write_text("# Invariants\n\nUpdated rules.\n")

    args = SimpleNamespace(repo_root=str(tmp_path), json=False)
    rc = cmd_handoff_check(args)
    assert rc == 1


def test_cmd_handoff_check_arch_change_with_handoff_passes(tmp_path):
    """Architecture doc changed alongside handoff update → return 0."""
    _init_git_repo(tmp_path)
    _make_handoff(tmp_path, "Working on X.", "Do Y.", "No blocker.")
    arch_dir = tmp_path / ".vibecode" / "architecture"
    arch_dir.mkdir(parents=True, exist_ok=True)
    (arch_dir / "INVARIANTS.md").write_text("# Invariants\n\nSome rules.\n")
    _git_add_commit(tmp_path)

    # Change architecture doc AND update a handoff file
    (arch_dir / "INVARIANTS.md").write_text("# Invariants\n\nUpdated rules.\n")
    _make_handoff(tmp_path, "Updated current state.", "Do Y.", "No blocker.")

    args = SimpleNamespace(repo_root=str(tmp_path), json=False)
    rc = cmd_handoff_check(args)
    assert rc == 0


def test_cmd_handoff_check_arch_change_with_history_passes(tmp_path):
    """Architecture doc changed alongside history file → return 0."""
    _init_git_repo(tmp_path)
    _make_handoff(tmp_path, "Working on X.", "Do Y.", "No blocker.")
    arch_dir = tmp_path / ".vibecode" / "architecture"
    arch_dir.mkdir(parents=True, exist_ok=True)
    (arch_dir / "STRUCTURE.md").write_text("# Structure\n\nOverview.\n")
    _git_add_commit(tmp_path)

    # Change architecture doc AND add a history file
    (arch_dir / "STRUCTURE.md").write_text("# Structure\n\nUpdated overview.\n")
    history_dir = tmp_path / ".vibecode" / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    (history_dir / "structure-change.md").write_text(
        "# Structure Change\n\nDescribed the update.\n"
    )

    args = SimpleNamespace(repo_root=str(tmp_path), json=False)
    rc = cmd_handoff_check(args)
    assert rc == 0


# ---------------------------------------------------------------------------
# CLI parser / dispatch tests
# ---------------------------------------------------------------------------


def test_handoff_check_subparser_exists():
    """The CLI parser should include a 'handoff-check' subcommand."""
    parser = create_parser()
    args = parser.parse_args(["handoff-check", "."])
    assert args.command == "handoff-check"


def test_handoff_check_help_exits_zero():
    """handoff-check --help should exit with code 0."""
    with pytest.raises(SystemExit) as exc_info:
        main(["handoff-check", "--help"])
    assert exc_info.value.code == 0


def test_handoff_check_missing_repo_root_exits_nonzero(tmp_path, capsys):
    """handoff-check with a missing repo root should exit nonzero."""
    missing = tmp_path / "nonexistent"
    rc = main(["handoff-check", str(missing)])
    err = capsys.readouterr().err
    assert rc == 1
    assert "nonexistent" in err
    assert "Traceback" not in err


def test_handoff_check_non_git_exits_nonzero(tmp_path, capsys):
    """handoff-check on a non-git dir should exit nonzero."""
    _make_handoff(tmp_path, "Now.", "Next.", "No blocker.")
    rc = main(["handoff-check", str(tmp_path)])
    err = capsys.readouterr().err
    assert rc == 1
    assert "not a git repository" in err


def test_handoff_check_valid_exits_zero(tmp_path):
    """handoff-check with valid handoff files returns 0 via CLI."""
    _init_git_repo(tmp_path)
    _make_handoff(tmp_path, "Working on X.", "Do Y.", "No blocker.")
    _git_add_commit(tmp_path)

    rc = main(["handoff-check", str(tmp_path)])
    assert rc == 0


def test_handoff_check_placeholder_exits_nonzero(tmp_path):
    """handoff-check with placeholder text returns 1 via CLI."""
    _init_git_repo(tmp_path)
    _make_handoff(tmp_path, "TBD", "Do stuff.", "No blocker.")
    _git_add_commit(tmp_path)

    rc = main(["handoff-check", str(tmp_path)])
    assert rc == 1


def test_handoff_check_arch_change_without_handoff_exits_nonzero(tmp_path):
    """Architecture change without handoff update → non-zero exit."""
    _init_git_repo(tmp_path)
    _make_handoff(tmp_path, "Working on X.", "Do Y.", "No blocker.")
    arch_dir = tmp_path / ".vibecode" / "architecture"
    arch_dir.mkdir(parents=True, exist_ok=True)
    (arch_dir / "INVARIANTS.md").write_text("# Invariants\n\nSome rules.\n")
    _git_add_commit(tmp_path)

    (arch_dir / "INVARIANTS.md").write_text("# Invariants\n\nUpdated rules.\n")

    rc = main(["handoff-check", str(tmp_path)])
    assert rc == 1


# ---------------------------------------------------------------------------
# --json flag
# ---------------------------------------------------------------------------


def test_handoff_check_json_writes_report(tmp_path):
    """--json flag should write handoff_check.json."""
    _init_git_repo(tmp_path)
    _make_handoff(tmp_path, "Working on X.", "Do Y.", "No blocker.")
    _git_add_commit(tmp_path)

    args = SimpleNamespace(repo_root=str(tmp_path), json=True)
    rc = cmd_handoff_check(args)

    report_path = tmp_path / ".vibecode" / "current" / "handoff_check.json"
    assert report_path.is_file()

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "ok"
    assert report["issues"] == []
    assert rc == 0


def test_handoff_check_json_writes_report_on_failure(tmp_path):
    """--json flag writes report even when validation fails."""
    _init_git_repo(tmp_path)
    _make_handoff(tmp_path, "TODO: fix this", "Do Y.", "No blocker.")
    _git_add_commit(tmp_path)

    args = SimpleNamespace(repo_root=str(tmp_path), json=True)
    rc = cmd_handoff_check(args)

    report_path = tmp_path / ".vibecode" / "current" / "handoff_check.json"
    assert report_path.is_file()

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "error"
    assert len(report["issues"]) > 0
    assert rc == 1