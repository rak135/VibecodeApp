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
from vibecode.permissions import PROFILES
from vibecode.run import cmd_run, _run_git_check, _write_run_metadata, _validate_permission_profile
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
        repo / ".gitignore",
        ".vibecode/current/\n"
        ".vibecode/generated/\n"
        ".vibecode/runs/\n"
        ".vibecode/tmp/\n"
        ".vibecode/cache/\n"
        ".vibecode/logs/\n"
        ".vibecode/index/*.generated.*\n",
    )
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
    # Write mock file_inventory.json so inventory health checks pass.
    _write(
        repo / ".vibecode" / "index" / "file_inventory.json",
        json.dumps({
            "$schema": "vibecode/file-inventory/v1",
            "files": [{"path": "test.py", "size": 100}],
        }),
    )
    # Create handoff files so handoff-check passes.
    handoff_dir = repo / ".vibecode" / "handoff"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    _write(handoff_dir / "NOW.md", "# Now\n\nWorking.\n")
    _write(handoff_dir / "NEXT.md", "# Next\n\nDo stuff.\n")
    _write(handoff_dir / "BLOCKERS.md", "# Blockers\n\nNo blockers.\n")
    for name, data in PROFILES.items():
        _write(
            repo / ".vibecode" / "agents" / f"{name}.json",
            json.dumps(data, indent=2) + "\n",
        )


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
            vibecode_dir / "runs" / "test-session", "test-session", plan,
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
            vibecode_dir / "runs" / "sess2", "sess2", plan,
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
        # Verify metadata was written to session directory.
        runs_dir = self.repo / ".vibecode" / "runs"
        meta_files = list(runs_dir.glob("*/metadata.json"))
        assert len(meta_files) == 1
        data = json.loads(meta_files[0].read_text(encoding="utf-8"))
        assert data["exit_code"] == 0
        assert data["task"] == "test task"
        assert data["platform"] == "opencode"

    def test_run_fails_with_fake_opencode_exit_nonzero(self):
        """OpenCode exits non-zero → run returns 1."""
        self._make_fake_opencode(exit_code=1, stdout="", stderr="Error: something broke\n")

        rc = main(["run", str(self.repo), "--task", "failing task", "--no-index"])

        assert rc == 1
        runs_dir = self.repo / ".vibecode" / "runs"
        meta_files = list(runs_dir.glob("*/metadata.json"))
        assert len(meta_files) == 1
        data = json.loads(meta_files[0].read_text(encoding="utf-8"))
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

        # Metadata should still record the failure under session directory.
        runs_dir = self.repo / ".vibecode" / "runs"
        meta_files = list(runs_dir.glob("*/metadata.json"))
        assert len(meta_files) >= 1
        data = json.loads(meta_files[0].read_text(encoding="utf-8"))
        assert data["exit_code"] != 0
        # When command is not found, command field should be None.
        assert data["command"] is None or data.get("error") is not None

    def test_run_snapshots_prompt_and_context_pack(self):
        """After a successful run, both current/ and run session snapshots exist."""
        self._make_fake_opencode(exit_code=0, stdout="All done.\n")

        main(["run", str(self.repo), "--task", "snapshot test", "--no-index"])

        # Current behavior preserved.
        current_dir = self.repo / ".vibecode" / "current"
        assert current_dir / "context_pack.md" in current_dir.glob("context_pack.md")
        assert current_dir / "opencode_prompt.md" in current_dir.glob("opencode_prompt.md")

        # Session snapshots exist.
        runs_dir = self.repo / ".vibecode" / "runs"
        sessions = list(runs_dir.glob("*/"))
        assert len(sessions) >= 1
        session_dir = sessions[0]
        context_snapshot = session_dir / "context_pack.md"
        prompt_snapshot = session_dir / "opencode_prompt.md"
        assert context_snapshot.exists(), f"Missing context_pack.md snapshot in {session_dir}"
        assert prompt_snapshot.exists(), f"Missing opencode_prompt.md snapshot in {session_dir}"

        # Snapshots match the current files.
        current_context = (current_dir / "context_pack.md").read_text(encoding="utf-8")
        assert context_snapshot.read_text(encoding="utf-8") == current_context
        current_prompt = (current_dir / "opencode_prompt.md").read_text(encoding="utf-8")
        assert prompt_snapshot.read_text(encoding="utf-8") == current_prompt


# ---------------------------------------------------------------------------
# cmd_run — preflight failures
# ---------------------------------------------------------------------------


class TestCmdRunPreflight:
    def test_no_project_yaml_exits_nonzero(self, tmp_path: Path, capsys, monkeypatch):
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

    def test_no_index_without_no_index_flag(self, tmp_path: Path, capsys, monkeypatch):
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

    def test_unknown_profile_fails_before_launch(self, tmp_path: Path, monkeypatch, capsys):
        _init_repo(tmp_path)
        _minimal_vibecode(tmp_path)
        _write(tmp_path / "app.py", "x = 1\n")
        _commit_all(tmp_path)

        marker = tmp_path / "launched.txt"
        fake_dir = tmp_path / "fake_bin"
        fake_dir.mkdir(parents=True, exist_ok=True)
        script = fake_dir / "opencode.py"
        script.write_text(
            f"from pathlib import Path\nPath({str(marker)!r}).write_text('yes')\n",
            encoding="utf-8",
        )
        wrapper = fake_dir / "opencode.cmd"
        wrapper.write_text(
            "@echo off\n" + f'"{sys.executable}" "%~dp0opencode.py" %*\n',
            encoding="utf-8",
        )
        monkeypatch.setenv("OPENCODE_COMMAND", str(wrapper))

        rc = main(["run", str(tmp_path), "--task", "test", "--profile", "nonexistent"])

        assert rc == 1
        assert not marker.exists()
        assert "Unknown permission profile" in capsys.readouterr().err

    def test_missing_profile_fails_before_launch(self, tmp_path: Path, monkeypatch, capsys):
        _init_repo(tmp_path)
        _minimal_vibecode(tmp_path)
        (tmp_path / ".vibecode" / "agents" / "safe.json").unlink()
        _write(tmp_path / "app.py", "x = 1\n")
        _commit_all(tmp_path)

        marker = tmp_path / "launched.txt"
        fake_dir = tmp_path / "fake_bin"
        fake_dir.mkdir(parents=True, exist_ok=True)
        script = fake_dir / "opencode.py"
        script.write_text(
            f"from pathlib import Path\nPath({str(marker)!r}).write_text('yes')\n",
            encoding="utf-8",
        )
        wrapper = fake_dir / "opencode.cmd"
        wrapper.write_text(
            "@echo off\n" + f'"{sys.executable}" "%~dp0opencode.py" %*\n',
            encoding="utf-8",
        )
        monkeypatch.setenv("OPENCODE_COMMAND", str(wrapper))

        rc = main(["run", str(tmp_path), "--task", "test"])

        assert rc == 1
        assert not marker.exists()
        assert "Permission profile 'safe' is missing" in capsys.readouterr().err

    def test_missing_gitignore_blocks_agent_launch(self, tmp_path: Path, capsys, monkeypatch):
        _init_repo(tmp_path)
        _minimal_vibecode(tmp_path)
        (tmp_path / ".gitignore").unlink()
        _write(tmp_path / "app.py", "x = 1\n")
        _commit_all(tmp_path)

        marker = tmp_path / "launched.txt"
        fake_dir = (tmp_path / ".." / "fake_bin_ign").resolve()
        fake_dir.mkdir(parents=True, exist_ok=True)
        script = fake_dir / "opencode.py"
        script.write_text(
            "import sys\n"
            f"argv = sys.argv[1:] if len(sys.argv) > 1 else []\n"
            'if "--version" in argv:\n'
            '    sys.stdout.write("fake-opencode 1.0.0\\n")\n'
            "    sys.exit(0)\n"
            f"from pathlib import Path\nPath({str(marker)!r}).write_text('yes')\n",
            encoding="utf-8",
        )
        wrapper = fake_dir / "opencode.cmd"
        wrapper.write_text(
            "@echo off\n" + f'"{sys.executable}" "%~dp0opencode.py" %*\n',
            encoding="utf-8",
        )
        monkeypatch.setenv("OPENCODE_COMMAND", str(wrapper))

        rc = main(["run", str(tmp_path), "--task", "test", "--no-index"])

        assert rc == 1
        assert not marker.exists()
        assert "git-ignored" in capsys.readouterr().err

    def test_safe_gitignore_allows_agent_launch(self, tmp_path: Path, capsys, monkeypatch):
        _init_repo(tmp_path)
        _minimal_vibecode(tmp_path)
        _write(tmp_path / "app.py", "x = 1\n")
        _commit_all(tmp_path)

        marker = tmp_path / "launched.txt"
        fake_dir = (tmp_path / ".." / "fake_bin_safe").resolve()
        fake_dir.mkdir(parents=True, exist_ok=True)
        script = fake_dir / "opencode.py"
        script.write_text(
            "import sys\n"
            f"argv = sys.argv[1:] if len(sys.argv) > 1 else []\n"
            'if "--version" in argv:\n'
            '    sys.stdout.write("fake-opencode 1.0.0\\n")\n'
            "    sys.exit(0)\n"
            f"from pathlib import Path\nPath({str(marker)!r}).write_text('yes')\n"
            "sys.stdout.write('OK\\n')\n",
            encoding="utf-8",
        )
        wrapper = fake_dir / "opencode.cmd"
        wrapper.write_text(
            "@echo off\n" + f'"{sys.executable}" "%~dp0opencode.py" %*\n',
            encoding="utf-8",
        )
        monkeypatch.setenv("OPENCODE_COMMAND", str(wrapper))

        rc = main(["run", str(tmp_path), "--task", "test", "--no-index"])

        assert rc == 0
        assert marker.exists()

    def test_env_only_opencode_command_reaches_fake_runner(self, tmp_path: Path, monkeypatch):
        """run and run-plan should both accept OPENCODE_COMMAND without default opencode."""
        _init_repo(tmp_path)
        _minimal_vibecode(tmp_path)
        _write(tmp_path / "app.py", "x = 1\n")
        _commit_all(tmp_path)

        marker = tmp_path / ".vibecode" / "tmp" / "launched.txt"
        fake_dir = (tmp_path / ".." / "fake_bin_env").resolve()
        fake_dir.mkdir(parents=True, exist_ok=True)
        script = fake_dir / "fake_opencode_env.py"
        script.write_text(
            "import sys\n"
            "from pathlib import Path\n"
            "sys.stdin.read()\n"
            f"marker = Path({str(marker)!r})\n"
            "marker.parent.mkdir(parents=True, exist_ok=True)\n"
            "marker.write_text('yes', encoding='utf-8')\n"
            "sys.stdout.write('OK\\n')\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("OPENCODE_COMMAND", f"{sys.executable} {script}")

        rc = main(["run", str(tmp_path), "--task", "test", "--no-index"])

        assert rc == 0
        assert marker.exists()

    def test_invalid_env_opencode_command_fails_before_launch(
        self, tmp_path: Path, monkeypatch, capsys
    ):
        _init_repo(tmp_path)
        _minimal_vibecode(tmp_path)
        _write(tmp_path / "app.py", "x = 1\n")
        _commit_all(tmp_path)

        monkeypatch.setenv("OPENCODE_COMMAND", "definitely-not-opencode")

        rc = main(["run", str(tmp_path), "--task", "test", "--no-index"])

        assert rc == 1
        err = capsys.readouterr().err
        assert "OpenCode check failed" in err
        assert "definitely-not-opencode" in err

    def test_missing_gitignore_leaves_no_run_artifacts(self, tmp_path: Path, monkeypatch):
        """When .gitignore safety fails, no .vibecode/runs/** artifact must be written."""
        _init_repo(tmp_path)
        _minimal_vibecode(tmp_path)
        (tmp_path / ".gitignore").unlink()
        _write(tmp_path / "app.py", "x = 1\n")
        _commit_all(tmp_path)

        fake_dir = (tmp_path / ".." / "fake_bin_art").resolve()
        fake_dir.mkdir(parents=True, exist_ok=True)
        script = fake_dir / "opencode.py"
        script.write_text(
            "import sys\n"
            f"argv = sys.argv[1:] if len(sys.argv) > 1 else []\n"
            'if "--version" in argv:\n'
            '    sys.stdout.write("fake-opencode 1.0.0\\n")\n'
            "    sys.exit(0)\n"
            "sys.stdout.write('OK\\n')\n",
            encoding="utf-8",
        )
        wrapper = fake_dir / "opencode.cmd"
        wrapper.write_text(
            "@echo off\n" + f'"{sys.executable}" "%~dp0opencode.py" %*\n',
            encoding="utf-8",
        )
        monkeypatch.setenv("OPENCODE_COMMAND", str(wrapper))

        rc = main(["run", str(tmp_path), "--task", "test", "--no-index"])

        assert rc == 1
        runs_dir = tmp_path / ".vibecode" / "runs"
        # The runs directory must either not exist or be empty — gitignore safety
        # failure must not write any run artifacts into the target repo.
        assert not runs_dir.exists() or not any(runs_dir.iterdir()), (
            "No run artifacts should exist when gitignore safety check fails"
        )

    def test_post_safety_failure_writes_durable_events_and_summary(
        self, tmp_path: Path, monkeypatch
    ):
        """After gitignore safety passes, a post-safety failure must still write
        durable events.jsonl and summary.json so the run is replayable."""
        _init_repo(tmp_path)
        _minimal_vibecode(tmp_path)
        _write(tmp_path / "app.py", "x = 1\n")
        _commit_all(tmp_path)

        # Point to an invalid opencode so the run aborts after the safety check.
        monkeypatch.setenv("OPENCODE_COMMAND", "definitely-not-a-real-opencode")

        rc = main(["run", str(tmp_path), "--task", "test", "--no-index"])

        assert rc == 1
        runs_dir = tmp_path / ".vibecode" / "runs"
        assert runs_dir.exists(), "runs/ directory must exist after a post-safety failure"
        run_dirs = [d for d in runs_dir.iterdir() if d.is_dir()]
        assert len(run_dirs) == 1, "Exactly one run directory should be created"
        run_dir = run_dirs[0]
        assert (run_dir / "events.jsonl").exists(), (
            "events.jsonl must be written once gitignore safety has passed"
        )
        assert (run_dir / "summary.json").exists(), (
            "summary.json must be written for post-safety abort so 'runs show' can display it"
        )


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


# ---------------------------------------------------------------------------
# _validate_permission_profile
# ---------------------------------------------------------------------------


class TestValidatePermissionProfile:
    def test_known_profile_passes(self, tmp_path: Path):
        _init_repo(tmp_path)
        _minimal_vibecode(tmp_path)
        _commit_all(tmp_path)

        ok, err = _validate_permission_profile(tmp_path, "safe")
        assert ok is True
        assert err is None

    def test_unknown_profile_fails(self, tmp_path: Path):
        _init_repo(tmp_path)
        _minimal_vibecode(tmp_path)
        _commit_all(tmp_path)

        ok, err = _validate_permission_profile(tmp_path, "nonexistent")
        assert ok is False
        assert "Unknown permission profile" in err

    def test_missing_file_fails(self, tmp_path: Path):
        _init_repo(tmp_path)
        _minimal_vibecode(tmp_path)
        (tmp_path / ".vibecode" / "agents" / "safe.json").unlink()
        _commit_all(tmp_path)

        ok, err = _validate_permission_profile(tmp_path, "safe")
        assert ok is False
        assert "missing at" in err

    def test_corrupt_json_fails(self, tmp_path: Path):
        _init_repo(tmp_path)
        _minimal_vibecode(tmp_path)
        profile_path = tmp_path / ".vibecode" / "agents" / "safe.json"
        profile_path.write_text("not valid json{{{", encoding="utf-8")
        _commit_all(tmp_path)

        ok, err = _validate_permission_profile(tmp_path, "safe")
        assert ok is False
        assert "not valid JSON" in err

    def test_json_array_fails(self, tmp_path: Path):
        _init_repo(tmp_path)
        _minimal_vibecode(tmp_path)
        profile_path = tmp_path / ".vibecode" / "agents" / "safe.json"
        profile_path.write_text('["not", "a", "dict"]', encoding="utf-8")
        _commit_all(tmp_path)

        ok, err = _validate_permission_profile(tmp_path, "safe")
        assert ok is False
        assert "must be a JSON object" in err


# ---------------------------------------------------------------------------
# Profile recording in metadata
# ---------------------------------------------------------------------------


class TestProfileInMetadata:
    def test_run_plan_metadata_records_profile(self, tmp_path: Path):
        _init_repo(tmp_path)
        _minimal_vibecode(tmp_path)
        _commit_all(tmp_path)

        plan = build_run_plan(tmp_path, task="test", profile_name="audit")
        assert plan.metadata["profile"] == "audit"

        plan2 = build_run_plan(tmp_path, task="test", profile_name="fast")
        assert plan2.metadata["profile"] == "fast"

        # Default is "safe" when no profile specified
        plan3 = build_run_plan(tmp_path, task="test")
        assert plan3.metadata["profile"] == "safe"

    def test_run_summary_records_profile(self):
        from vibecode.run import RunSummary

        summary = RunSummary(
            session_id="test-session",
            started_at="2026-01-01T00:00:00Z",
            finished_at="2026-01-01T00:01:00Z",
            platform="opencode",
            profile="audit",
            repo_root="/test",
            task="test task",
            dirty=False,
            index_fresh=True,
            command="opencode",
            exit_code=0,
            stdout="OK",
            stderr="",
            agent_status="success",
        )
        assert summary.profile == "audit"
        data = summary.as_dict()
        assert data["profile"] == "audit"

    def test_run_metadata_json_includes_profile(self, tmp_path: Path):
        _init_repo(tmp_path)
        _minimal_vibecode(tmp_path)
        _commit_all(tmp_path)

        from vibecode.run import _write_run_metadata, RunSummary, _write_run_summary

        plan = build_run_plan(tmp_path, task="test", profile_name="fast")
        path = _write_run_metadata(
            tmp_path / ".vibecode", "session-prof",
            plan, command="opencode", exit_code=0, stdout="OK", stderr="",
        )
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["profile"] == "fast"

    def test_all_profiles_accepted_and_recorded(self, tmp_path: Path):
        _init_repo(tmp_path)
        _minimal_vibecode(tmp_path)
        _commit_all(tmp_path)

        for profile_name in ("safe", "fast", "audit"):
            plan = build_run_plan(tmp_path, task="test", profile_name=profile_name)
            assert plan.metadata["profile"] == profile_name
            # No preflight errors for valid profiles
            assert not any(
                e.level == "error" and "profile" in e.message.lower()
                for e in plan.preflight_errors
            )


# ---------------------------------------------------------------------------
# Run refuses dirty onboarding baseline without --allow-dirty
# ---------------------------------------------------------------------------


class TestRunRefusesDirtyOnboarding:
    def test_dirty_onboarding_baseline_refused(self, tmp_path: Path, capsys, monkeypatch):
        """Run must refuse a dirty onboarding baseline without --allow-dirty."""
        _init_repo(tmp_path)
        _write(tmp_path / "app.py", "x = 1\n")
        _commit_all(tmp_path)

        # Create .vibecode setup files (onboarding baseline, not committed).
        # A real 'vibecode init' would also write .gitignore with ignore rules, so
        # we include it here to let the pre-session gitignore safety check pass and
        # exercise the dirty-tree check this test is designed to cover.
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
        _write(
            tmp_path / ".vibecode" / "project.yaml",
            "project:\n  id: test\n  name: Test\n  root: .\n"
            "indexing:\n  include: ['*.py']\n  exclude: []\n  protected_paths: []\n"
            "  risk_rules: []\n",
        )
        _write(tmp_path / ".vibecode" / "handoff" / "NOW.md", "# Now\n\nWorking.\n")
        _write(tmp_path / ".vibecode" / "handoff" / "NEXT.md", "# Next\n\nDo stuff.\n")
        _write(tmp_path / ".vibecode" / "handoff" / "BLOCKERS.md", "# Blockers\n\nNo blockers.\n")
        # Create required profiles so preflight doesn't bail before git check
        from vibecode.permissions import PROFILES
        for name, data in PROFILES.items():
            _write(
                tmp_path / ".vibecode" / "agents" / f"{name}.json",
                json.dumps(data, indent=2) + "\n",
            )

        marker = tmp_path / "launched.txt"
        fake_dir = (tmp_path / ".." / "fake_bin_onb").resolve()
        fake_dir.mkdir(parents=True, exist_ok=True)
        script = fake_dir / "opencode.py"
        script.write_text(
            "import sys\n"
            f"argv = sys.argv[1:] if len(sys.argv) > 1 else []\n"
            'if "--version" in argv:\n'
            '    sys.stdout.write("fake-opencode 1.0.0\\n")\n'
            "    sys.exit(0)\n"
            f"from pathlib import Path\nPath({str(marker)!r}).write_text('yes')\n",
            encoding="utf-8",
        )
        wrapper = fake_dir / "opencode.cmd"
        wrapper.write_text(
            "@echo off\n" + f'"{sys.executable}" "%~dp0opencode.py" %*\n',
            encoding="utf-8",
        )
        monkeypatch.setenv("OPENCODE_COMMAND", str(wrapper))

        rc = main(["run", str(tmp_path), "--task", "test", "--no-index"])

        assert rc == 1
        assert not marker.exists()
        err = capsys.readouterr().err
        assert "dirty" in err.lower()

    def test_dirty_onboarding_with_allow_dirty_proceeds(self, tmp_path: Path, capsys, monkeypatch):
        """Run with --allow-dirty should proceed on a dirty onboarding baseline."""
        _init_repo(tmp_path)
        _write(tmp_path / "app.py", "x = 1\n")
        _commit_all(tmp_path)

        _minimal_vibecode(tmp_path)
        # Don't commit vibecode baseline — it's dirty

        marker = tmp_path / "launched.txt"
        fake_dir = (tmp_path / ".." / "fake_bin_onb2").resolve()
        fake_dir.mkdir(parents=True, exist_ok=True)
        script = fake_dir / "opencode.py"
        script.write_text(
            "import sys\n"
            f"argv = sys.argv[1:] if len(sys.argv) > 1 else []\n"
            'if "--version" in argv:\n'
            '    sys.stdout.write("fake-opencode 1.0.0\\n")\n'
            "    sys.exit(0)\n"
            f"from pathlib import Path\nPath({str(marker)!r}).write_text('yes')\n"
            "sys.stdout.write('OK\\n')\n",
            encoding="utf-8",
        )
        wrapper = fake_dir / "opencode.cmd"
        wrapper.write_text(
            "@echo off\n" + f'"{sys.executable}" "%~dp0opencode.py" %*\n',
            encoding="utf-8",
        )
        monkeypatch.setenv("OPENCODE_COMMAND", str(wrapper))

        rc = main(["run", str(tmp_path), "--task", "test", "--allow-dirty", "--no-index"])

        assert rc == 0
        assert marker.exists()
