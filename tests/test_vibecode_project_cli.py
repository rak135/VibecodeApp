"""Tests for ``vibecode project`` CLI commands."""

from __future__ import annotations

import os

import pytest

from vibecode.cli import create_parser, main
from vibecode.registry import ProjectRegistry


@pytest.fixture
def tmp_registry(tmp_path):
    """Return a ProjectRegistry that stores its file under *tmp_path*."""
    home = tmp_path / "home"
    os.environ["VIBECODE_HOME"] = str(home)
    try:
        yield ProjectRegistry()
    finally:
        os.environ.pop("VIBECODE_HOME", None)


# ---------------------------------------------------------------------------
# Parser creation
# ---------------------------------------------------------------------------


def test_project_subparser_exists():
    parser = create_parser()
    # "project" should be a valid top-level command
    with pytest.raises(SystemExit):
        parser.parse_args(["project", "--help"])


def test_project_add_help_exits_zero():
    with pytest.raises(SystemExit) as exc_info:
        main(["project", "add", "--help"])
    assert exc_info.value.code == 0


def test_project_use_help_exits_zero():
    with pytest.raises(SystemExit) as exc_info:
        main(["project", "use", "--help"])
    assert exc_info.value.code == 0


def test_project_list_help_exits_zero():
    with pytest.raises(SystemExit) as exc_info:
        main(["project", "list", "--help"])
    assert exc_info.value.code == 0


def test_project_remove_help_exits_zero():
    with pytest.raises(SystemExit) as exc_info:
        main(["project", "remove", "--help"])
    assert exc_info.value.code == 0


def test_project_current_help_exits_zero():
    with pytest.raises(SystemExit) as exc_info:
        main(["project", "current", "--help"])
    assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------


def test_project_add(tmp_path, tmp_registry, capsys):
    repo = tmp_path / "myrepo"
    repo.mkdir()

    rc = main(["project", "add", "myproj", str(repo)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Added project" in out
    assert "myproj" in out

    entry = tmp_registry.get("myproj")
    assert entry is not None
    assert entry.name == "myproj"
    assert entry.path == str(repo.resolve())


def test_project_add_duplicate_fails(tmp_path, tmp_registry, capsys):
    repo1 = tmp_path / "repo1"
    repo1.mkdir()
    repo2 = tmp_path / "repo2"
    repo2.mkdir()

    main(["project", "add", "proj", str(repo1)])
    rc = main(["project", "add", "proj", str(repo2)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "already exists" in err

    # Original entry is unchanged.
    entry = tmp_registry.get("proj")
    assert entry is not None
    assert entry.path == str(repo1.resolve())


def test_project_add_missing_directory(tmp_registry, capsys):
    rc = main(["project", "add", "ghost", "/nonexistent/path"])
    # The CLI resolves the path but doesn't require it to exist for add.
    # Registry stores the path as-is after resolve.
    assert rc == 0


# ---------------------------------------------------------------------------
# use
# ---------------------------------------------------------------------------


def test_project_use(tmp_path, tmp_registry, capsys):
    repo = tmp_path / "myrepo"
    repo.mkdir()
    main(["project", "add", "myproj", str(repo)])

    rc = main(["project", "use", "myproj"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Active project set to" in out
    assert "myproj" in out

    assert tmp_registry._active_name() == "myproj"


def test_project_use_unknown_fails(tmp_registry, capsys):
    rc = main(["project", "use", "nope"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "Error" in err


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def test_project_list_empty(tmp_registry, capsys):
    rc = main(["project", "list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "No projects registered" in out


def test_project_list_shows_entries(tmp_path, tmp_registry, capsys):
    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    repo_a.mkdir()
    repo_b.mkdir()

    main(["project", "add", "alpha", str(repo_a)])
    main(["project", "add", "beta", str(repo_b)])

    rc = main(["project", "list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "alpha" in out
    assert "beta" in out


def test_project_list_marks_active(tmp_path, tmp_registry, capsys):
    repo = tmp_path / "myrepo"
    repo.mkdir()
    main(["project", "add", "myproj", str(repo)])
    main(["project", "use", "myproj"])

    rc = main(["project", "list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "(*)" in out


# ---------------------------------------------------------------------------
# remove
# ---------------------------------------------------------------------------


def test_project_remove(tmp_path, tmp_registry, capsys):
    repo = tmp_path / "myrepo"
    repo.mkdir()
    main(["project", "add", "myproj", str(repo)])

    rc = main(["project", "remove", "myproj"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Removed project" in out
    assert tmp_registry.get("myproj") is None


def test_project_remove_unknown_fails(tmp_registry, capsys):
    rc = main(["project", "remove", "nope"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "not found" in err


def test_project_remove_active_clears_active(tmp_path, tmp_registry, capsys):
    repo = tmp_path / "myrepo"
    repo.mkdir()
    main(["project", "add", "myproj", str(repo)])
    main(["project", "use", "myproj"])
    assert tmp_registry._active_name() == "myproj"

    main(["project", "remove", "myproj"])
    assert tmp_registry._active_name() is None


# ---------------------------------------------------------------------------
# current
# ---------------------------------------------------------------------------


def test_project_current_none(tmp_registry, capsys):
    rc = main(["project", "current"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "No active project" in out


def test_project_current_shows_active(tmp_path, tmp_registry, capsys):
    repo = tmp_path / "myrepo"
    repo.mkdir()
    main(["project", "add", "myproj", str(repo)])
    main(["project", "use", "myproj"])

    rc = main(["project", "current"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "myproj" in out
    assert str(repo.resolve()) in out