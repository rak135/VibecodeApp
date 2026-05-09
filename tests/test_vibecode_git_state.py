"""Tests for git working tree inspection helpers."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from vibecode.git_state import inspect_git_state


git_available = pytest.mark.skipif(
    shutil.which("git") is None, reason="git not available"
)


def _write(path: Path, content: str = "# placeholder\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(repo: Path) -> None:
    result = subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")


def _commit_all(repo: Path) -> None:
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")


def _repo(tmp_path: Path) -> Path:
    _init_repo(tmp_path)
    _write(tmp_path / "src" / "app.py", "print('hello')\n")
    _write(tmp_path / "tests" / "test_app.py", "def test_app():\n    assert True\n")
    _commit_all(tmp_path)
    return tmp_path


@git_available
def test_clean_repo_has_empty_change_state(tmp_path):
    repo = _repo(tmp_path)

    state = inspect_git_state(repo)

    assert state.is_git_repo is True
    assert state.error is None
    assert state.changed_paths == ()
    assert state.staged_paths == ()
    assert state.unstaged_paths == ()
    assert state.diff_name_only == ()
    assert state.staged_diff_name_only == ()
    assert state.diff_stat == ""


@git_available
def test_modified_source_file_is_reported_as_unstaged(tmp_path):
    repo = _repo(tmp_path)
    _write(repo / "src" / "app.py", "print('changed')\n")

    state = inspect_git_state(repo)

    assert state.changed_paths == ("src/app.py",)
    assert state.staged_paths == ()
    assert state.unstaged_paths == ("src/app.py",)
    assert state.diff_name_only == ("src/app.py",)
    assert "src/app.py" in state.diff_stat


@git_available
def test_modified_test_file_is_reported_separately_from_staged_source(tmp_path):
    repo = _repo(tmp_path)
    _write(repo / "src" / "app.py", "print('staged')\n")
    _git(repo, "add", "src/app.py")
    _write(repo / "tests" / "test_app.py", "def test_app():\n    assert False\n")

    state = inspect_git_state(repo)

    assert state.changed_paths == ("src/app.py", "tests/test_app.py")
    assert state.staged_paths == ("src/app.py",)
    assert state.unstaged_paths == ("tests/test_app.py",)
    assert state.staged_diff_name_only == ("src/app.py",)
    assert state.diff_name_only == ("tests/test_app.py",)
    assert "src/app.py" in state.staged_diff_stat


@git_available
def test_deleted_file_is_reported(tmp_path):
    repo = _repo(tmp_path)
    (repo / "src" / "app.py").unlink()

    state = inspect_git_state(repo)

    assert state.changed_paths == ("src/app.py",)
    assert state.deleted_paths == ("src/app.py",)
    assert state.unstaged_paths == ("src/app.py",)
    assert state.diff_name_only == ("src/app.py",)


@git_available
def test_untracked_file_is_reported_without_diff_name_only(tmp_path):
    repo = _repo(tmp_path)
    _write(repo / "notes" / "todo.md", "todo\n")

    state = inspect_git_state(repo)

    assert state.changed_paths == ("notes/todo.md",)
    assert state.untracked_paths == ("notes/todo.md",)
    assert state.unstaged_paths == ("notes/todo.md",)
    assert state.diff_name_only == ()


def test_non_git_directory_returns_empty_state(tmp_path):
    state = inspect_git_state(tmp_path)

    assert state.is_git_repo is False
    assert state.error is None
    assert state.changed_paths == ()
    assert state.status_paths == ()
