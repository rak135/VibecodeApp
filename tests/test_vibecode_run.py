"""Tests for vibecode run command (vibecode.run).

All tests use a temporary directory as the repo root and a fake OpenCode
script so that no real OpenCode installation is required.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from vibecode.cli import main
from vibecode.run import cmd_run, _run_git_check, _write_run_metadata
from vibecode.run_plan import build_run_plan, RunPlan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, content: str) -> Path:
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


def _minimal_vibecode(repo: Path) -> None:
    """Write the minimal .vibecode/project.yaml and index for a valid repo."""
    _write(
        repo / ".vibecode" / "project.yaml",
        "project:\n"
        "  id: testproject\n"
        "  name: Test Project\n"
        "  root: .\n"
        "indexing:\n"
        "  include: ['*.py']\n"
        "  exclude: []\n"
        "  protected_paths: []\n"
        "  risk_rules: []\n",
    )
    now_iso = datetime.now(tz=timezone.utc).isoformat()
    _write(
        repo / ".vibecode" / "current" / "last_index.json",
        json.dumps(
            {
                "$schema": "vibecode/index-run/v1",
                "project_id": "testproject",
                "root": str(repo),
                "started_at": now_iso,
                "finished_at": now_iso,
                "counts": {"files": 3, "symbols": 10, "tests": 1, "warnings": 0, "errors": 0},
                "warnings": [],
                "errors": [],
                "generator": "vibecode 0.1.0",
            }
        ),
    )
    # Create handoff files so handoff-check passes.
    handoff_dir = repo / ".vibecode" / "handoff"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    _write(handoff_dir / "NOW.md", "# Now\n\nWorking.\n")
    _write(handoff_dir / "NEXT.md", "# Next\n\nDo stuff.\n")
    _write(handoff_dir / "BLOCKERS.md", "# Blockers\n\nNo blockers.\n")


def _fake_opencode_script(tmp_path: Path, exit_code: int = 0, stdout: str = "OK\n", stderr: str = "") -> Path:
    """Create a fake opencode command on PATH by creating both a Python
    script and a .cmd wrapper.  Returns the path to the .cmd file.
    """
    py_script = tmp_path / "opencode.py"
    py_script.write_text(
        f"""#!{sys.executable}
import sys

argv = sys.argv[1:] if len(sys.argv) > 1 else []
if "--version" in argv:
    sys.stdout.write("fake-opencode 1.0.0\\n")
    sys.exit(0)

inp = sys.stdin.read()
sys.stderr.write({stderr!r})
sys.stdout.write({stdout!r})
sys.exit({exit_code})
""",
        encoding="utf-8",
    )

    wrapper = tmp_path / "opencode.cmd"
    wrapper.write_text(
        "@echo off\n" + '"' + sys.executable + '"' + ' "%~dp0opencode.py" %*\n',
        encoding="utf-8",
    )
    return wrapper


def _make_fake_opencode(self, exit_code: int = 0, stdout: str = "OK\n", stderr: str = "") -> Path:
    fake_dir = (self.repo / ".." / "fake_bin").resolve()
    fake_dir.mkdir(parents=True, exist_ok=True)
    wrapper = _fake_opencode_script(fake_dir, exit_code=exit_code, stdout=stdout, stderr=stderr)
    # Put fake bin dir on PATH so shutil.which("opencode") finds the .cmd wrapper.
    self.monkeypatch.setenv("PATH", str(fake_dir) + os.pathsep + os.environ.get("PATH", ""))
    return wrapper



# ---------------------------------------------------------------------------
# _run_git_check
# ---------------------------------------------------------------------------
class TestRunGitCheck:
    def test_clean_repo_returns_ok(self, tmp_path: Path):
        _init_repo(tmp_path)
        _write(tmp_path / "app.py", "x = 1\n")
        _commit_all(tmp_path)

        clean, errors = _run_git_check(tmp_path, allow_dirty=False)
        assert clean is True
        assert errors == []

    def test_dirty_repo_without_allow_dirty_fails(self, tmp_path: Path):
        _init_repo(tmp_path)
        _write(tmp_path / "app.py", "x = 1\n")
        _commit_all(tmp_path)
        _write(tmp_path / "app.py", "x = 2\n")

        clean, errors = _run_git_check(tmp_path, allow_dirty=False)
        assert clean is False
        assert any("dirty" in e.lower() for e in errors)

    def test_dirty_repo_with_allow_dirty_returns_ok(self, tmp_path: Path):
        _init_repo(tmp_path)
        _write(tmp_path / "app.py", "x = 1\n")
        _commit_all(tmp_path)
        _write(tmp_path / "app.py", "x = 2\n")

        clean, errors = _run_git_check(tmp_path, allow_dirty=True)
        assert clean is True
        # Warning-level messages are still returned.
        assert any("dirty" in e.lower() for e in errors)

    def test_non_git_dir_fails(self, tmp_path: Path):
        clean, errors = _run_git_check(tmp_path, allow_dirty=False)
        assert clean is False
        assert any("git" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# _write_run_metadata
# ---------------------------------------------------------------------------


class TestWriteRunMetadata:
    def test_writes_valid_json(self, tmp_path: Path):
        vibecode_dir = tmp_path / ".vibecode"
        plan = RunPlan(
            repo_root=str(tmp_path),
            task="test task",
            dirty=False,
            dirty_paths=(),
            index_fresh=True,
            index_age_seconds=0.0,
            context_pack_path=None,
            opencode_prompt_path=None,
            permission_profile=None,
            preflight_warnings=(),
            preflight_errors=(),
            commands=(),
        )
        path = _write_run_metadata(
            vibecode_dir, "test-session", plan,
            command="fake-opencode", exit_code=0, stdout="OK", stderr="",
        )
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["session_id"] == "test-session"
        assert data["exit_code"] == 0
        assert data["command"] == "fake-opencode"
        assert data["repo_root"] == str(tmp_path)

    def test_error_field_set_when_provided(self, tmp_path: Path):
        vibecode_dir = tmp_path / ".vibecode"
        plan = RunPlan(
            repo_root=str(tmp_path),
            task="test",
            dirty=False,
            dirty_paths=(),
            index_fresh=False,
            index_age_seconds=None,
            context_pack_path=None,
            opencode_prompt_path=None,
            permission_profile=None,
            preflight_warnings=(),
            preflight_errors=(),
            commands=(),
        )
        path = _write_run_metadata(
            vibecode_dir, "sess2", plan,
            command=None, exit_code=-1, stdout="", stderr="",
            error="OpenCode command not found.",
        )
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["error"] == "OpenCode command not found."


# ---------------------------------------------------------------------------
# cmd_run — end-to-end with fake OpenCode
# ---------------------------------------------------------------------------


class TestCmdRunEndToEnd:
    """Full integration tests using a fake OpenCode binary on PATH."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path: Path, monkeypatch):
        # Create a minimal git repo with vibecode config.
        _init_repo(tmp_path)
        _write(tmp_path / "app.py", "print('hello')\n")
        _commit_all(tmp_path)
        _minimal_vibecode(tmp_path)
        _write(
            tmp_path / ".vibecode" / "index" / "file_inventory.json",
            json.dumps({"files": []}),
        )
        _commit_all(tmp_path)

        self.repo = tmp_path
        self.monkeypatch = monkeypatch

    def _make_fake_opencode(self, exit_code: int = 0, stdout: str = "OK\n", stderr: str = "") -> Path:
        fake_dir = (self.repo / ".." / "fake_bin").resolve()
        fake_dir.mkdir(parents=True, exist_ok=True)
        wrapper = _fake_opencode_script(fake_dir, exit_code=exit_code, stdout=stdout, stderr=stderr)
        # Put fake bin dir on PATH so shutil.which("opencode") finds the .cmd wrapper.
        self.monkeypatch.setenv("PATH", str(fake_dir) + os.pathsep + os.environ.get("PATH", ""))
        return wrapper

    def test_run_succeeds_with_fake_opencode(self):
        """Happy path: clean repo, fake OpenCode exits 0."""
        self._make_fake_opencode(exit_code=0, stdout="All done.\n")

        rc = main(["run", str(self.repo), "--task", "test task", "--no-index"])

        assert rc == 0
        # Verify metadata was written.
        runs_dir = self.repo / ".vibecode" / "runs"
        sessions = list(runs_dir.glob("*.json"))
        assert len(sessions) == 1
        data = json.loads(sessions[0].read_text(encoding="utf-8"))
        assert data["exit_code"] == 0
        assert data["task"] == "test task"
        assert data["platform"] == "opencode"

    def test_run_fails_with_fake_opencode_exit_nonzero(self):
        """OpenCode exits non-zero → run returns 1."""
        self._make_fake_opencode(exit_code=1, stdout="", stderr="Error: something broke\n")

        rc = main(["run", str(self.repo), "--task", "failing task", "--no-index"])

        assert rc == 1
        runs_dir = self.repo / ".vibecode" / "runs"
        sessions = list(runs_dir.glob("*.json"))
        assert len(sessions) == 1
        data = json.loads(sessions[0].read_text(encoding="utf-8"))
        assert data["exit_code"] == 1
        assert "something broke" in data["stderr"]

    def test_run_writes_opencode_prompt(self):
        """Verify opencode_prompt.md is written during the run."""
        self._make_fake_opencode(exit_code=0)

        main(["run", str(self.repo), "--task", "prompt test", "--no-index"])

        prompt_path = self.repo / ".vibecode" / "current" / "opencode_prompt.md"
        assert prompt_path.exists()
        content = prompt_path.read_text(encoding="utf-8")
        assert "prompt test" in content
        assert "Vibecode-controlled repository" in content

    def test_run_with_allow_dirty(self, capsys):
        """Dirty repo with --allow-dirty should proceed (warning only)."""
        # Make a dirty change.
        _write(self.repo / "app.py", "print('changed')\n")
        self._make_fake_opencode(exit_code=0)

        rc = main(["run", str(self.repo), "--task", "dirty run", "--allow-dirty", "--no-index"])

        assert rc == 0
        out = capsys.readouterr().err
        assert "dirty" in out.lower() or "DIRTY" in out

    def test_run_without_allow_dirty_on_dirty_repo(self, capsys):
        """Dirty repo without --allow-dirty should error."""
        _write(self.repo / "app.py", "print('changed')\n")
        self._make_fake_opencode(exit_code=0)

        rc = main(["run", str(self.repo), "--task", "dirty run"])

        assert rc == 1
        err = capsys.readouterr().err
        assert "dirty" in err.lower()

    def test_run_missing_opencode_command(self, capsys):
        """When OpenCode binary is not on PATH, should fail clearly."""
        # Monkeypatch so the OpenCode command cannot be resolved,
        # but leave PATH intact so git still works.
        self.monkeypatch.setattr(
            "vibecode.run._get_opencode_command", lambda *a, **kw: None
        )

        rc = main(["run", str(self.repo), "--task", "no opencode"])

        assert rc == 1
        err = capsys.readouterr().err
        assert "OpenCode" in err
        assert "not found" in err.lower() or "INSTALL" in err

        # Metadata should still record the failure.
        runs_dir = self.repo / ".vibecode" / "runs"
        sessions = list(runs_dir.glob("*.json"))
        assert len(sessions) >= 1
        data = json.loads(sessions[0].read_text(encoding="utf-8"))
        assert data["exit_code"] != 0
        # When command is not found, command field should be None.
        assert data["command"] is None or data.get("error") is not None


# ---------------------------------------------------------------------------
# cmd_run — preflight failures
# ---------------------------------------------------------------------------


class TestCmdRunPreflight:
    def test_no_project_yaml_exits_nonzero(self, tmp_path: Path, capsys):
        """Run without .vibecode/project.yaml should fail."""
        _init_repo(tmp_path)
        _write(tmp_path / "app.py", "x = 1\n")
        _commit_all(tmp_path)
        # No .vibecode/project.yaml

        # We need a fake opencode so the command won't fail at OpenCode check
        # — but preflight should fail earlier.
        fake_dir = tmp_path / ".vibecode" / "fake_bin"
        fake_dir.mkdir(parents=True, exist_ok=True)
        _fake_opencode_script(fake_dir)
        env = os.environ.copy()
        env["PATH"] = str(fake_dir) + os.pathsep + env.get("PATH", "")

        with monkeypatch.context() as m:
            m.setenv("PATH", env["PATH"])
            rc = main(["run", str(tmp_path), "--task", "test"])

        assert rc == 1
        err = capsys.readouterr().err
        # Should mention project.yaml or context pack failure.
        assert "project.yaml" in err or "Error" in err

    def test_no_index_without_no_index_flag(self, tmp_path: Path, capsys):
        """Run without an existing index and without --no-index should auto-index."""
        _init_repo(tmp_path)
        _minimal_vibecode(tmp_path)
        _commit_all(tmp_path)

        fake_dir = tmp_path / ".vibecode" / "fake_bin"
        fake_dir.mkdir(parents=True, exist_ok=True)
        _fake_opencode_script(fake_dir)

        with monkeypatch.context() as m:
            m.setenv("PATH", str(fake_dir) + os.pathsep + os.environ.get("PATH", ""))
            rc = main(["run", str(tmp_path), "--task", "auto-index test"])

        # May succeed or fail depending on index contents, but should NOT fail
        # with "no index found" — it should try to generate one.
        err = capsys.readouterr().err
        assert "no index found" not in err.lower() or rc == 0


# ---------------------------------------------------------------------------
# build_run_plan integration with run module
# ---------------------------------------------------------------------------


class TestBuildRunPlanForRun:
    """Ensure build_run_plan works correctly when called from run module context."""

    def test_run_plan_includes_metadata_for_session(self, tmp_path: Path):
        _init_repo(tmp_path)
        _minimal_vibecode(tmp_path)
        _commit_all(tmp_path)

        # Can't use monkeypatch in class-level fixture easily, so test plan directly.
        plan = build_run_plan(tmp_path, task="session test", platform="opencode")
        assert plan.metadata["platform"] == "opencode"
        assert "started_at" in plan.metadata