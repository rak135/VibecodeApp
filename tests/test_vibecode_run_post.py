"""Tests for vibecode run post-run flow (guard, check, handoff, summary).

All tests use a temporary directory as the repo root, a fake OpenCode
script, and optional fake check commands.  No real OpenCode installation
or real check commands are required.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from vibecode.cli import main
from vibecode.check import CheckResult, CheckRun
from vibecode.guard import GuardFinding, GuardResult
from vibecode.handoff import HandoffIssue, HandoffResult
from vibecode.permissions import PROFILES
from vibecode.run import (
    RunSummary,
    _run_post_checks,
    _write_run_summary,
    cmd_run,
)
from vibecode.run_plan import RunPlan


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
    _write(
        repo / ".vibecode" / "current" / "last_index.json",
        json.dumps(
            {
                "$schema": "vibecode/index-run/v1",
                "project_id": "testproject",
                "root": str(repo),
                "started_at": "2026-01-15T10:00:00+00:00",
                "finished_at": "2026-01-15T10:00:02+00:00",
                "counts": {"files": 3, "symbols": 10, "tests": 1, "warnings": 0, "errors": 0},
                "warnings": [],
                "errors": [],
                "generator": "vibecode 0.1.0",
            }
        ),
    )
    for name, data in PROFILES.items():
        _write(
            repo / ".vibecode" / "agents" / f"{name}.json",
            json.dumps(data, indent=2) + "\n",
        )


def _fake_opencode_script(
    tmp_path: Path,
    exit_code: int = 0,
    stdout: str = "OK\n",
    stderr: str = "",
    body: str = "",
) -> Path:
    """Create a fake opencode command by creating both a Python script and a
    .cmd wrapper on PATH (so shutil.which("opencode") finds it).
    Returns the path to the .cmd file.
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
{body}
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


def _make_fake_opencode(
    self,
    exit_code: int = 0,
    stdout: str = "OK\n",
    stderr: str = "",
    body: str = "",
) -> Path:
    fake_bin = (self.repo / ".." / "fake_bin").resolve()
    fake_bin.mkdir(parents=True, exist_ok=True)
    wrapper = _fake_opencode_script(
        fake_bin, exit_code=exit_code, stdout=stdout, stderr=stderr, body=body
    )
    # Put fake bin dir on PATH so shutil.which("opencode") finds the .cmd wrapper.
    self.monkeypatch.setenv("PATH", str(fake_bin) + os.pathsep + os.environ.get("PATH", ""))
    return wrapper


def _fake_check_script(tmp_path: Path, exit_code: int = 0, stdout: str = "", stderr: str = "") -> Path:
    """Create a fake check script.

    Returns the path to the script.
    """
    script = tmp_path / "fake_check.py"
    script.write_text(
        f"""#!{sys.executable}
import sys
sys.stderr.write({stderr!r})
sys.stdout.write({stdout!r})
sys.exit({exit_code})
""",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


# ---------------------------------------------------------------------------
# RunSummary — overall_status
# ---------------------------------------------------------------------------


class TestRunSummaryOverallStatus:
    """Test the overall_status logic of RunSummary."""

    def _make_plan(self) -> RunPlan:
        return RunPlan(
            repo_root="/tmp",
            task="test",
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

    def test_agent_success_no_issues_is_success(self):
        plan = self._make_plan()
        summary = RunSummary(
            session_id="s1",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:01+00:00",
            platform="opencode",
            profile="safe",
            repo_root="/tmp",
            task="test",
            dirty=False,
            index_fresh=True,
            command="opencode",
            exit_code=0,
            stdout="",
            stderr="",
            agent_status="success",
        )
        # No guard, checks, or handoff set — treated as passing
        assert summary.overall_status == "success"

    def test_agent_failure_causes_failure(self):
        plan = self._make_plan()
        summary = RunSummary(
            session_id="s1",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:01+00:00",
            platform="opencode",
            profile="safe",
            repo_root="/tmp",
            task="test",
            dirty=False,
            index_fresh=True,
            command="opencode",
            exit_code=1,
            stdout="",
            stderr="",
            agent_status="failure",
        )
        assert summary.overall_status == "failure"

    def test_guard_with_error_causes_failure(self):
        guard = GuardResult(
            findings=(
                GuardFinding(
                    rule_id="test-rule",
                    path="foo.py",
                    severity="error",
                    message="Hard violation",
                ),
            )
        )
        plan = self._make_plan()
        summary = RunSummary(
            session_id="s1",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:01+00:00",
            platform="opencode",
            profile="safe",
            repo_root="/tmp",
            task="test",
            dirty=False,
            index_fresh=True,
            command="opencode",
            exit_code=0,
            stdout="",
            stderr="",
            agent_status="success",
            guard=guard,
        )
        assert summary.overall_status == "failure"

    def test_guard_warning_only_not_failure(self):
        guard = GuardResult(
            findings=(
                GuardFinding(
                    rule_id="test-rule",
                    path="foo.py",
                    severity="warning",
                    message="Soft warning",
                ),
            )
        )
        plan = self._make_plan()
        summary = RunSummary(
            session_id="s1",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:01+00:00",
            platform="opencode",
            profile="safe",
            repo_root="/tmp",
            task="test",
            dirty=False,
            index_fresh=True,
            command="opencode",
            exit_code=0,
            stdout="",
            stderr="",
            agent_status="success",
            guard=guard,
        )
        # Guard warnings alone don't cause failure
        assert summary.overall_status == "success"

    def test_required_check_failure_causes_failure(self):
        check_run = CheckRun(root=Path("/tmp"))
        check_run.results = [
            CheckResult("fail1", "cmd1", True, 1, 0.5, "", ""),
        ]
        plan = self._make_plan()
        summary = RunSummary(
            session_id="s1",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:01+00:00",
            platform="opencode",
            profile="safe",
            repo_root="/tmp",
            task="test",
            dirty=False,
            index_fresh=True,
            command="opencode",
            exit_code=0,
            stdout="",
            stderr="",
            agent_status="success",
            checks=check_run,
        )
        assert summary.overall_status == "failure"

    def test_optional_check_failure_not_failure(self):
        check_run = CheckRun(root=Path("/tmp"))
        check_run.results = [
            CheckResult("warn1", "cmd1", False, 1, 0.5, "", ""),
        ]
        plan = self._make_plan()
        summary = RunSummary(
            session_id="s1",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:01+00:00",
            platform="opencode",
            profile="safe",
            repo_root="/tmp",
            task="test",
            dirty=False,
            index_fresh=True,
            command="opencode",
            exit_code=0,
            stdout="",
            stderr="",
            agent_status="success",
            checks=check_run,
        )
        assert summary.overall_status == "success"

    def test_missing_handoff_causes_incomplete(self):
        handoff = HandoffResult(root=Path("/tmp"))
        handoff.issues.append(
            HandoffIssue(file=".vibecode/handoff/NOW.md", message="NOW.md is missing")
        )
        plan = self._make_plan()
        summary = RunSummary(
            session_id="s1",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:01+00:00",
            platform="opencode",
            profile="safe",
            repo_root="/tmp",
            task="test",
            dirty=False,
            index_fresh=True,
            command="opencode",
            exit_code=0,
            stdout="",
            stderr="",
            agent_status="success",
            handoff=handoff,
        )
        assert summary.overall_status == "incomplete"

    def test_handoff_passes_with_no_issues(self):
        handoff = HandoffResult(root=Path("/tmp"))
        plan = self._make_plan()
        summary = RunSummary(
            session_id="s1",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:01+00:00",
            platform="opencode",
            profile="safe",
            repo_root="/tmp",
            task="test",
            dirty=False,
            index_fresh=True,
            command="opencode",
            exit_code=0,
            stdout="",
            stderr="",
            agent_status="success",
            handoff=handoff,
        )
        assert summary.overall_status == "success"

    def test_error_field_causes_error_status(self):
        plan = self._make_plan()
        summary = RunSummary(
            session_id="s1",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:01+00:00",
            platform="opencode",
            profile="safe",
            repo_root="/tmp",
            task="test",
            dirty=False,
            index_fresh=True,
            command="opencode",
            exit_code=-1,
            stdout="",
            stderr="",
            agent_status="failure",
            error="Something went wrong",
        )
        assert summary.overall_status == "error"

    def test_guard_failure_overrides_agent_success(self):
        """Guard failure should cause failure even if agent succeeded."""
        guard = GuardResult(
            findings=(
                GuardFinding(
                    rule_id="protected-path-generated",
                    path=".vibecode/current/context_pack.md",
                    severity="error",
                    message="Generated file changed.",
                ),
            )
        )
        check_run = CheckRun(root=Path("/tmp"))
        check_run.results = [
            CheckResult("ok", "pytest", True, 0, 1.0, "1 passed", ""),
        ]
        handoff = HandoffResult(root=Path("/tmp"))
        # handoff passes

        plan = self._make_plan()
        summary = RunSummary(
            session_id="s1",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:01+00:00",
            platform="opencode",
            profile="safe",
            repo_root="/tmp",
            task="test",
            dirty=False,
            index_fresh=True,
            command="opencode",
            exit_code=0,
            stdout="",
            stderr="",
            agent_status="success",
            guard=guard,
            checks=check_run,
            handoff=handoff,
        )
        assert summary.overall_status == "failure"

    def test_all_pass_is_success(self):
        guard = GuardResult()
        check_run = CheckRun(root=Path("/tmp"))
        check_run.results = [
            CheckResult("ok1", "cmd1", True, 0, 0.5, "", ""),
            CheckResult("ok2", "cmd2", False, 0, 0.3, "", ""),
        ]
        handoff = HandoffResult(root=Path("/tmp"))

        plan = self._make_plan()
        summary = RunSummary(
            session_id="s1",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:01+00:00",
            platform="opencode",
            profile="safe",
            repo_root="/tmp",
            task="test",
            dirty=False,
            index_fresh=True,
            command="opencode",
            exit_code=0,
            stdout="ok output",
            stderr="",
            agent_status="success",
            guard=guard,
            checks=check_run,
            handoff=handoff,
        )
        assert summary.overall_status == "success"


# ---------------------------------------------------------------------------
# RunSummary — as_dict
# ---------------------------------------------------------------------------


class TestRunSummaryAsDict:
    def test_includes_all_fields(self):
        guard = GuardResult()
        check_run = CheckRun(root=Path("/tmp"))
        check_run.results = [CheckResult("c1", "cmd1", True, 0, 0.1, "", "")]
        handoff = HandoffResult(root=Path("/tmp"))

        plan = RunPlan(
            repo_root="/tmp",
            task="test",
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
        summary = RunSummary(
            session_id="s1",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:01+00:00",
            platform="opencode",
            profile="safe",
            repo_root="/tmp",
            task="test",
            dirty=False,
            index_fresh=True,
            command="opencode",
            exit_code=0,
            stdout="hello",
            stderr="",
            agent_status="success",
            guard=guard,
            checks=check_run,
            handoff=handoff,
        )

        data = summary.as_dict()
        assert data["session_id"] == "s1"
        assert data["overall_status"] == "success"
        assert data["agent_status"] == "success"
        assert data["exit_code"] == 0
        assert data["stdout"] == "hello"
        assert "guard" in data
        assert "checks" in data
        assert "handoff" in data
        assert "$schema" in data

    def test_optional_sections_absent_when_none(self):
        summary = RunSummary(
            session_id="s1",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:01+00:00",
            platform="opencode",
            profile="safe",
            repo_root="/tmp",
            task="test",
            dirty=False,
            index_fresh=True,
            command=None,
            exit_code=-1,
            stdout="",
            stderr="",
            agent_status="failure",
            error="Command not found",
        )
        data = summary.as_dict()
        assert "guard" not in data
        assert "checks" not in data
        assert "handoff" not in data
        assert data["error"] == "Command not found"

    def test_handoff_incomplete_reflected_in_status(self):
        handoff = HandoffResult(root=Path("/tmp"))
        handoff.issues.append(
            HandoffIssue(file=".vibecode/handoff/NOW.md", message="Missing")
        )
        summary = RunSummary(
            session_id="s1",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:01+00:00",
            platform="opencode",
            profile="safe",
            repo_root="/tmp",
            task="test",
            dirty=False,
            index_fresh=True,
            command="opencode",
            exit_code=0,
            stdout="",
            stderr="",
            agent_status="success",
            handoff=handoff,
        )
        data = summary.as_dict()
        assert data["overall_status"] == "incomplete"
        assert len(data["handoff"]["issues"]) == 1


# ---------------------------------------------------------------------------
# _write_run_summary
# ---------------------------------------------------------------------------


class TestWriteRunSummary:
    def test_writes_valid_json(self, tmp_path: Path):
        vibecode_dir = tmp_path / ".vibecode"
        guard = GuardResult()
        summary = RunSummary(
            session_id="test-session",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:01+00:00",
            platform="opencode",
            profile="safe",
            repo_root=str(tmp_path),
            task="test task",
            dirty=False,
            index_fresh=True,
            command="opencode",
            exit_code=0,
            stdout="All good.",
            stderr="",
            agent_status="success",
            guard=guard,
        )
        path = _write_run_summary(vibecode_dir, summary)
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["session_id"] == "test-session"
        assert data["overall_status"] == "success"
        assert data["command"] == "opencode"
        assert "guard" in data
        assert data["stdout"] == "All good."

    def test_incomplete_status_written(self, tmp_path: Path):
        vibecode_dir = tmp_path / ".vibecode"
        handoff = HandoffResult(root=tmp_path)
        handoff.issues.append(
            HandoffIssue(file=".vibecode/handoff/NOW.md", message="NOW.md missing")
        )
        summary = RunSummary(
            session_id="s2",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:01+00:00",
            platform="opencode",
            profile="safe",
            repo_root=str(tmp_path),
            task="test",
            dirty=False,
            index_fresh=True,
            command="opencode",
            exit_code=0,
            stdout="",
            stderr="",
            agent_status="success",
            handoff=handoff,
        )
        path = _write_run_summary(vibecode_dir, summary)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["overall_status"] == "incomplete"
        assert len(data["handoff"]["issues"]) == 1

    def test_summary_dir_is_nested(self, tmp_path: Path):
        """Summary is written inside .vibecode/runs/<session_id>/summary.json."""
        vibecode_dir = tmp_path / ".vibecode"
        summary = RunSummary(
            session_id="session-abc-123",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:01+00:00",
            platform="opencode",
            profile="safe",
            repo_root=str(tmp_path),
            task="test",
            dirty=False,
            index_fresh=True,
            command=None,
            exit_code=-1,
            stdout="",
            stderr="",
            agent_status="failure",
            error="test error",
        )
        path = _write_run_summary(vibecode_dir, summary)
        assert path == vibecode_dir / "runs" / "session-abc-123" / "summary.json"
        assert path.exists()


# ---------------------------------------------------------------------------
# _run_post_checks (unit tests with mocks)
# ---------------------------------------------------------------------------


class TestRunPostChecks:
    """Test _run_post_checks with mocked subsystem calls."""

    def test_all_checks_pass(self, tmp_path: Path):
        root = tmp_path
        vibecode_dir = root / ".vibecode"
        vibecode_dir.mkdir()
        _write(vibecode_dir / "project.yaml", "project:\n  id: test\n  name: test\n  root: .\n")

        git_state = SimpleNamespace(is_git_repo=True, changed_paths=(), untracked_paths=(), diff_name_only=())
        session_id = "test-session"

        guard_r, check_r, handoff_r = _run_post_checks(root, vibecode_dir, git_state, session_id)

        assert guard_r is not None
        assert guard_r.passed
        assert check_r is not None
        # May have no checks configured, so check_run may be empty
        assert handoff_r is not None

    def test_guard_failure_detected(self, tmp_path: Path):
        """When changed_paths includes a generated runtime file, guard should fail."""
        root = tmp_path
        vibecode_dir = root / ".vibecode"
        vibecode_dir.mkdir()
        _write(vibecode_dir / "project.yaml", "project:\n  id: test\n  name: test\n  root: .\n")

        # Simulate a change to a generated runtime path (which is a guard error)
        git_state = SimpleNamespace(
            is_git_repo=True,
            changed_paths=(".vibecode/current/context_pack.md",),
            untracked_paths=(),
            diff_name_only=(".vibecode/current/context_pack.md",),
        )
        _write(vibecode_dir / "current" / "context_pack.md", "# old\n")
        _git(root, "init")
        _git(root, "config", "user.email", "test@test.com")
        _git(root, "config", "user.name", "Test")
        _commit_all(root)
        _write(vibecode_dir / "current" / "context_pack.md", "# new\n")

        session_id = "test-session"
        guard_r, check_r, handoff_r = _run_post_checks(root, vibecode_dir, git_state, session_id)

        assert guard_r is not None
        assert not guard_r.passed
        assert any(f.severity == "error" for f in guard_r.findings)

    def test_missing_handoff_detected(self, tmp_path: Path):
        """When handoff files are missing, handoff result should have issues."""
        root = tmp_path
        vibecode_dir = root / ".vibecode"
        vibecode_dir.mkdir()
        _write(vibecode_dir / "project.yaml", "project:\n  id: test\n  name: test\n  root: .\n")

        git_state = SimpleNamespace(is_git_repo=True, changed_paths=(), untracked_paths=(), diff_name_only=())
        session_id = "test-session"

        guard_r, check_r, handoff_r = _run_post_checks(root, vibecode_dir, git_state, session_id)

        assert handoff_r is not None
        assert not handoff_r.passed
        assert any("NOW.md" in i.message or "missing" in i.message.lower() for i in handoff_r.issues)

    def test_with_git_state_none(self, tmp_path: Path):
        """Should not crash when git_state is None; skip guard and handoff."""
        root = tmp_path
        vibecode_dir = root / ".vibecode"
        vibecode_dir.mkdir()
        _write(vibecode_dir / "project.yaml", "project:\n  id: test\n  name: test\n  root: .\n")

        session_id = "test-session"
        guard_r, check_r, handoff_r = _run_post_checks(root, vibecode_dir, None, session_id)

        assert guard_r is None
        assert check_r is not None
        assert handoff_r is None


# ---------------------------------------------------------------------------
# cmd_run — integration with post-run flow using fake OpenCode
# ---------------------------------------------------------------------------


class TestCmdRunWithPostChecks:
    """Integration tests for full run including post-run checks."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path: Path, monkeypatch):
        _init_repo(tmp_path)
        _write(tmp_path / "app.py", "print('hello')\n")
        _commit_all(tmp_path)
        _minimal_vibecode(tmp_path)

        # Create architecture files so validation passes during index.
        arch_dir = tmp_path / ".vibecode" / "architecture"
        arch_dir.mkdir(parents=True, exist_ok=True)
        _write(arch_dir / "OVERVIEW.md", "# Overview\n\nTest project.\n")
        _write(arch_dir / "INVARIANTS.md", "# Invariants\n\nNo invariants.\n")
        _write(arch_dir / "STRUCTURE.md", "# Structure\n\nSimple structure.\n")
        _write(arch_dir / "DATA_FLOW.md", "# Data Flow\n\nTBD.\n")
        _write(arch_dir / "MODULE_BOUNDARIES.md", "# Module Boundaries\n\nTBD.\n")
        _write(arch_dir / "PROTECTED_AREAS.md", "# Protected Areas\n\nNone.\n")

        # Update index timestamp to now so it isn't considered stale.
        now_iso = datetime.now(tz=timezone.utc).isoformat()
        _write(
            tmp_path / ".vibecode" / "current" / "last_index.json",
            json.dumps(
                {
                    "$schema": "vibecode/index-run/v1",
                    "project_id": "testproject",
                    "root": str(tmp_path),
                    "started_at": now_iso,
                    "finished_at": now_iso,
                    "counts": {"files": 1, "symbols": 1, "tests": 0, "warnings": 0, "errors": 0},
                    "warnings": [],
                    "errors": [],
                    "generator": "vibecode 0.1.0",
                }
            ),
        )

        # Create required checks config with a fake check that passes
        checks_dir = tmp_path / ".vibecode" / "checks"
        checks_dir.mkdir(parents=True, exist_ok=True)
        # Use a script outside the repo so it doesn't dirty the git tree
        fake_bin = tmp_path / ".." / "fake_bin"
        fake_bin.mkdir(parents=True, exist_ok=True)
        check_script = _fake_check_script(fake_bin, exit_code=0)
        _write(
            checks_dir / "required_checks.yaml",
            "checks:\n"
            "  - name: fake check\n"
            f"    command: {sys.executable} {check_script}\n"
            "    required: true\n",
        )
        # Create handoff files
        handoff_dir = tmp_path / ".vibecode" / "handoff"
        handoff_dir.mkdir(parents=True, exist_ok=True)
        _write(handoff_dir / "NOW.md", "# Now\n\nWorking on test task.\n")
        _write(handoff_dir / "NEXT.md", "# Next\n\nDo more tests.\n")
        _write(handoff_dir / "BLOCKERS.md", "# Blockers\n\nNo blockers.\n")
        _commit_all(tmp_path)

        self.repo = tmp_path
        self.monkeypatch = monkeypatch

    def _make_fake_opencode(
        self,
        exit_code: int = 0,
        stdout: str = "OK\n",
        stderr: str = "",
        body: str = "",
    ) -> Path:
        fake_bin = (self.repo / ".." / "fake_bin").resolve()
        fake_bin.mkdir(parents=True, exist_ok=True)
        script = _fake_opencode_script(
            fake_bin, exit_code=exit_code, stdout=stdout, stderr=stderr, body=body
        )
        # Set OPENCODE_COMMAND to the .cmd wrapper path directly so it is
        # executed by the shell (not parsed as a Python file argument).
        self.monkeypatch.setenv("OPENCODE_COMMAND", str(script))
        return script

    def _make_fake_check(self, exit_code: int = 0) -> Path:
        fake_bin = self.repo / ".." / "fake_bin"
        fake_bin.mkdir(parents=True, exist_ok=True)
        script = _fake_check_script(fake_bin, exit_code=exit_code)
        # Use sys.executable to invoke the script so it works cross-platform.
        self.monkeypatch.setenv(
            "PATH", str(fake_bin) + os.pathsep + os.environ.get("PATH", "")
        )
        # Rewrite required_checks.yaml to invoke the script with the real Python
        # interpreter, ensuring it works on all platforms (not just Linux).
        checks_dir = self.repo / ".vibecode" / "checks"
        _write(
            checks_dir / "required_checks.yaml",
            "checks:\n"
            "  - name: fake check\n"
            f"    command: {sys.executable} {script}\n"
            "    required: true\n",
        )
        return script

    def test_successful_run_all_checks_pass(self):
        """Happy path: agent exits 0, guard passes, required checks pass, handoff is valid."""
        self._make_fake_opencode(exit_code=0, stdout="All done.\n")

        rc = main(["run", str(self.repo), "--task", "test task"])

        assert rc == 0
        # Verify run metadata exists
        runs_dir = self.repo / ".vibecode" / "runs"
        sessions = list(runs_dir.glob("*.json"))
        assert len(sessions) >= 1

        # Verify summary exists
        summaries = list(runs_dir.glob("*/summary.json"))
        assert len(summaries) >= 1
        data = json.loads(summaries[0].read_text(encoding="utf-8"))
        assert data["overall_status"] == "success"
        assert data["agent_status"] == "success"
        assert data["guard"]["passed"] is True
        assert data["handoff"]["status"] == "ok"
        assert data["diff"]["changed_files"] == []

    def test_run_guard_catches_readme_modified_by_agent(self):
        """Post-run guard must evaluate the actual post-agent working tree."""
        _write(self.repo / "README.md", "# Test\n")
        _commit_all(self.repo)
        body = "from pathlib import Path\nPath('README.md').write_text('# Modified by agent\\n', encoding='utf-8')"
        self._make_fake_opencode(exit_code=0, stdout="Changed README.\n", body=body)

        rc = main(["run", str(self.repo), "--task", "change app behavior"])

        assert rc == 1
        summaries = list((self.repo / ".vibecode" / "runs").glob("*/summary.json"))
        assert len(summaries) >= 1
        data = json.loads(summaries[0].read_text(encoding="utf-8"))
        assert data["overall_status"] == "failure"
        assert data["guard"]["passed"] is False
        assert any(
            finding["rule_id"] == "readme-manual-only"
            for finding in data["guard"]["findings"]
        )
        assert any(path["path"] == "README.md" for path in data["diff"]["changed_files"])

    def test_run_reports_source_without_test_warning_for_agent_change(self):
        """Source-only agent edits should surface as guard warnings."""
        body = "from pathlib import Path\nPath('app.py').write_text(\"print('changed')\\n\", encoding='utf-8')"
        self._make_fake_opencode(exit_code=0, stdout="Changed source.\n", body=body)

        rc = main(["run", str(self.repo), "--task", "change app behavior"])

        assert rc == 0
        summaries = list((self.repo / ".vibecode" / "runs").glob("*/summary.json"))
        assert len(summaries) >= 1
        data = json.loads(summaries[0].read_text(encoding="utf-8"))
        assert data["overall_status"] == "success"
        assert any(
            finding["rule_id"] == "source-test-change-balance"
            and finding["severity"] == "warning"
            for finding in data["guard"]["findings"]
        )
        assert any(path["path"] == "app.py" for path in data["diff"]["changed_files"])

    def test_run_summary_reports_guard_failure(self):
        """When guard detects an error, overall status should be 'failure'."""
        # Create a generated runtime file and commit it, then have the fake
        # agent modify it after the pre-agent git baseline is captured.
        current_dir = self.repo / ".vibecode" / "current"
        _write(current_dir / "test_generated.md", "# generated\n")
        _commit_all(self.repo)
        body = (
            "from pathlib import Path\n"
            "Path('.vibecode/current/test_generated.md').write_text('# modified\\n', encoding='utf-8')"
        )

        self._make_fake_opencode(exit_code=0, stdout="OK\n", body=body)

        rc = main(["run", str(self.repo), "--task", "test task"])

        assert rc == 1
        runs_dir = self.repo / ".vibecode" / "runs"
        summaries = list(runs_dir.glob("*/summary.json"))
        assert len(summaries) >= 1
        data = json.loads(summaries[0].read_text(encoding="utf-8"))
        assert data["overall_status"] == "failure"
        assert data["guard"]["passed"] is False

    def test_run_summary_reports_check_failure(self):
        """When a required check fails, overall status should be 'failure'."""
        # Update required_checks.yaml to use a failing check
        checks_dir = self.repo / ".vibecode" / "checks"
        _write(
            checks_dir / "required_checks.yaml",
            "checks:\n"
            "  - name: failing check\n"
            "    command: python -c \"import sys; sys.exit(1)\"\n"
            "    required: true\n",
        )
        _commit_all(self.repo)

        self._make_fake_opencode(exit_code=0, stdout="OK\n")

        rc = main(["run", str(self.repo), "--task", "test task"])

        assert rc == 1
        runs_dir = self.repo / ".vibecode" / "runs"
        summaries = list(runs_dir.glob("*/summary.json"))
        assert len(summaries) >= 1
        data = json.loads(summaries[0].read_text(encoding="utf-8"))
        assert data["overall_status"] == "failure"
        assert data["checks"]["summary"]["failed"] >= 1

    def test_run_summary_reports_missing_handoff(self):
        """When handoff files are missing, overall status should be 'incomplete'."""
        # Remove handoff files
        handoff_dir = self.repo / ".vibecode" / "handoff"
        for f in handoff_dir.iterdir():
            f.unlink()
        _commit_all(self.repo)

        self._make_fake_opencode(exit_code=0, stdout="OK\n")

        rc = main(["run", str(self.repo), "--task", "test task"])

        # exit code 2 for incomplete
        assert rc == 2
        runs_dir = self.repo / ".vibecode" / "runs"
        summaries = list(runs_dir.glob("*/summary.json"))
        assert len(summaries) >= 1
        data = json.loads(summaries[0].read_text(encoding="utf-8"))
        assert data["overall_status"] == "incomplete"
        assert len(data["handoff"]["issues"]) > 0

    def test_run_agent_failure_causes_failure_status(self):
        """When agent exits non-zero, overall status should be 'failure'."""
        self._make_fake_opencode(exit_code=1, stdout="", stderr="Error!\n")

        rc = main(["run", str(self.repo), "--task", "failing task"])

        assert rc == 1
        runs_dir = self.repo / ".vibecode" / "runs"
        summaries = list(runs_dir.glob("*/summary.json"))
        assert len(summaries) >= 1
        data = json.loads(summaries[0].read_text(encoding="utf-8"))
        assert data["overall_status"] == "failure"
        assert data["agent_status"] == "failure"

    def test_run_summary_prints_concise_result(self, capsys):
        """The summary should print a concise RUN SUCCESS/FAILURE result."""
        self._make_fake_opencode(exit_code=0, stdout="OK\n")

        rc = main(["run", str(self.repo), "--task", "test task"])

        assert rc == 0
        err = capsys.readouterr().err
        assert "RUN SUCCESS" in err or "RUN SUCCESS" in err.upper()

    def test_run_summary_dir_nested(self):
        """Summary should be in .vibecode/runs/<session_id>/summary.json."""
        self._make_fake_opencode(exit_code=0, stdout="OK\n")

        main(["run", str(self.repo), "--task", "test task"])

        runs_dir = self.repo / ".vibecode" / "runs"
        # There should be a directory with summary.json inside it
        summary_found = False
        for session_dir in runs_dir.iterdir():
            if session_dir.is_dir():
                summary_file = session_dir / "summary.json"
                if summary_file.exists():
                    summary_found = True
                    data = json.loads(summary_file.read_text(encoding="utf-8"))
                    assert data["$schema"] == "vibecode/run-summary/v1"
                    assert "guard" in data
                    assert "checks" in data
                    assert "handoff" in data
                    break
        assert summary_found, "No summary.json found in any run session directory"

    def test_run_with_missing_opencode_does_not_crash(self, monkeypatch, capsys):
        """Run with no OpenCode command should fail gracefully, no crash from post-checks."""
        # Monkeypatch so the OpenCode command cannot be resolved,
        # but leave PATH intact so git still works.
        monkeypatch.setattr(
            "vibecode.run._get_opencode_command", lambda *a, **kw: None
        )

        rc = main(["run", str(self.repo), "--task", "no opencode"])

        assert rc == 1
        err = capsys.readouterr().err
        assert "OpenCode" in err


# ---------------------------------------------------------------------------
# RunSummary — priority ordering of statuses
# ---------------------------------------------------------------------------


class TestRunSummaryStatusPriority:
    """Verify the priority ordering: error > failure > incomplete > success."""

    def _base_summary(self, **kwargs):
        defaults = dict(
            session_id="s1",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:01+00:00",
            platform="opencode",
            profile="safe",
            repo_root="/tmp",
            task="test",
            dirty=False,
            index_fresh=True,
            command="opencode",
            exit_code=0,
            stdout="",
            stderr="",
            agent_status="success",
        )
        defaults.update(kwargs)
        return RunSummary(**defaults)

    def test_error_overrides_all(self):
        s = self._base_summary(error="critical")
        assert s.overall_status == "error"

    def test_guard_failure_overrides_agent_success(self):
        guard = GuardResult(
            findings=(
                GuardFinding(
                    rule_id="test",
                    path="x.py",
                    severity="error",
                    message="fail",
                ),
            )
        )
        s = self._base_summary(guard=guard)
        assert s.overall_status == "failure"

    def test_check_failure_overrides_agent_success(self):
        check_run = CheckRun(root=Path("/tmp"))
        check_run.results = [
            CheckResult("c1", "cmd", True, 1, 0.1, "", ""),
        ]
        s = self._base_summary(checks=check_run)
        assert s.overall_status == "failure"

    def test_handoff_issue_downgrades_to_incomplete(self):
        handoff = HandoffResult(root=Path("/tmp"))
        handoff.issues.append(
            HandoffIssue(file=".vibecode/handoff/NOW.md", message="missing")
        )
        s = self._base_summary(handoff=handoff)
        assert s.overall_status == "incomplete"

    def test_all_passing_is_success(self):
        guard = GuardResult()
        check_run = CheckRun(root=Path("/tmp"))
        check_run.results = [CheckResult("c1", "cmd", True, 0, 0.1, "", "")]
        handoff = HandoffResult(root=Path("/tmp"))
        s = self._base_summary(guard=guard, checks=check_run, handoff=handoff)
        assert s.overall_status == "success"
