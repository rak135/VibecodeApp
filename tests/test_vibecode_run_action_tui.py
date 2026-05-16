"""Tests for [A] and [S] agent-run actions wired into VibecodeMainApp.

Covers:
  - AgentRunService (fake factory DI, result dict contract)
  - render_center_run_status() pure function
  - render_right_run_result() pure function
  - VibecodeMainApp.action_cmd_audit / action_cmd_safe wiring
  - Integration: AgentRunService with a fake OpenCode binary
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from vibecode.main_app import (
    AgentRunService,
    render_center_run_status,
    render_right_run_result,
)
from vibecode.permissions import PROFILES


# ---------------------------------------------------------------------------
# Shared test helpers (no-dep copies of run_controller helpers)
# ---------------------------------------------------------------------------


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _init_repo(repo: Path) -> None:
    result = subprocess.run(
        ["git", "init", "-b", "main"], cwd=repo, capture_output=True, text=True
    )
    if result.returncode != 0:
        _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")


def _commit_all(repo: Path) -> None:
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")


def _minimal_vibecode(repo: Path) -> None:
    _write(
        repo / ".gitignore",
        ".vibecode/current/\n.vibecode/generated/\n.vibecode/runs/\n"
        ".vibecode/tmp/\n.vibecode/cache/\n.vibecode/logs/\n"
        ".vibecode/index/*.generated.*\n",
    )
    _write(
        repo / ".vibecode" / "project.yaml",
        "project:\n  id: testproject\n  name: Test\n  root: .\n"
        "indexing:\n  include: ['*.py']\n  exclude: []\n"
        "  protected_paths: []\n  risk_rules: []\n",
    )
    now_iso = datetime.now(tz=timezone.utc).isoformat()
    _write(
        repo / ".vibecode" / "current" / "last_index.json",
        json.dumps({
            "$schema": "vibecode/index-run/v1",
            "project_id": "testproject",
            "root": str(repo),
            "started_at": now_iso,
            "finished_at": now_iso,
            "counts": {"files": 1, "symbols": 0, "tests": 0, "warnings": 0, "errors": 0},
            "warnings": [],
            "errors": [],
            "generator": "vibecode 0.1.0",
        }),
    )
    _write(
        repo / ".vibecode" / "index" / "file_inventory.json",
        json.dumps({
            "$schema": "vibecode/file-inventory/v1",
            "files": [{"path": "app.py", "size": 100}],
        }),
    )
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


def _fake_opencode_script(
    fake_dir: Path, exit_code: int = 0, stdout: str = "OK\n", stderr: str = ""
) -> None:
    """Write fake opencode .py + .cmd wrapper into *fake_dir*."""
    py_script = fake_dir / "opencode.py"
    py_script.write_text(
        f"""#!{sys.executable}
import sys
argv = sys.argv[1:] if len(sys.argv) > 1 else []
if "--version" in argv:
    sys.stdout.write("fake-opencode 1.0.0\\n")
    sys.exit(0)
sys.stdin.read()
sys.stderr.write({stderr!r})
sys.stdout.write({stdout!r})
sys.exit({exit_code})
""",
        encoding="utf-8",
    )
    wrapper = fake_dir / "opencode.cmd"
    wrapper.write_text(
        '@echo off\n"' + sys.executable + '" "%~dp0opencode.py" %*\n',
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Fake factory helpers for AgentRunService unit tests
# ---------------------------------------------------------------------------


def _make_noop_factory(*, session_id: str = "fake-session-001"):
    """Return a RunController factory whose execute() returns (None, 1)."""

    class _FakeController:
        def __init__(self, **kwargs: object) -> None:
            self.session_id = session_id

        def execute(self):
            return None, 1

    return _FakeController


def _make_recording_factory(profile_capture: list, *, session_id: str = "fake-001"):
    """Return a factory that records which profile_name it was instantiated with."""

    class _FakeController:
        def __init__(self, **kwargs: object) -> None:
            self.session_id = session_id
            profile_capture.append(kwargs.get("profile_name"))

        def execute(self):
            return None, 1

    return _FakeController


def _make_raising_factory(error_msg: str):
    """Return a factory whose execute() raises RuntimeError."""

    class _FakeController:
        def __init__(self, **kwargs: object) -> None:
            self.session_id = "fake-001"

        def execute(self):
            raise RuntimeError(error_msg)

    return _FakeController


def _make_summary_factory(
    *,
    session_id: str = "fake-session-001",
    agent_exit_code: int = 0,
    agent_status: str = "success",
    overall_status: str = "success",
    guard_passed: bool = True,
    checks_passed: bool = True,
    handoff_passed: bool = True,
):
    """Return a RunController factory whose execute() returns a summary with
    the given raw agent exit code, plus a wrapper exit code that differs from it
    to prove the TUI uses the raw value.
    """
    from vibecode.run import RunSummary

    class _FakeController:
        def __init__(self, **kwargs: object) -> None:
            self.session_id = session_id

        def execute(self):
            summary = RunSummary(
                session_id=session_id,
                started_at="2026-01-01T00:00:00+00:00",
                finished_at="2026-01-01T00:01:00+00:00",
                platform="opencode",
                profile="safe",
                repo_root="/fake/repo",
                task="fake task",
                dirty=False,
                index_fresh=True,
                command="fake-opencode",
                exit_code=agent_exit_code,
                stdout="out",
                stderr="",
                agent_status=agent_status,
            )
            # Wrapper exit code is deliberately different from agent_exit_code
            # to verify the service uses the raw value.
            wrapper_code = 99
            return summary, wrapper_code

    return _FakeController


# ---------------------------------------------------------------------------
# TestAgentRunService — unit tests with fake factory
# ---------------------------------------------------------------------------


class TestAgentRunService:
    def test_returns_all_expected_keys(self, tmp_path):
        svc = AgentRunService(controller_factory=_make_noop_factory())
        result = svc.run(tmp_path, "task", "audit")
        expected = {
            "session_id", "task", "profile", "run_dir",
            "overall_status", "exit_code",
            "context_pack_path", "prompt_path",
            "guard_passed", "guard_errors", "guard_warnings",
            "checks_passed", "handoff_passed",
            "artifact_paths", "error",
        }
        assert expected.issubset(result.keys())

    def test_task_in_result(self, tmp_path):
        svc = AgentRunService(controller_factory=_make_noop_factory())
        result = svc.run(tmp_path, "my unique task", "safe")
        assert result["task"] == "my unique task"

    def test_profile_in_result(self, tmp_path):
        svc = AgentRunService(controller_factory=_make_noop_factory())
        result = svc.run(tmp_path, "task", "safe")
        assert result["profile"] == "safe"

    def test_session_id_comes_from_controller(self, tmp_path):
        svc = AgentRunService(controller_factory=_make_noop_factory(session_id="my-sid"))
        result = svc.run(tmp_path, "task", "audit")
        assert result["session_id"] == "my-sid"

    def test_correct_profile_passed_to_factory(self, tmp_path):
        captured: list[str] = []
        svc = AgentRunService(controller_factory=_make_recording_factory(captured))
        svc.run(tmp_path, "task", "audit")
        assert captured == ["audit"]

    def test_safe_profile_passed_to_factory(self, tmp_path):
        captured: list[str] = []
        svc = AgentRunService(controller_factory=_make_recording_factory(captured))
        svc.run(tmp_path, "task", "safe")
        assert captured == ["safe"]

    def test_aborted_run_gives_error_status(self, tmp_path):
        svc = AgentRunService(controller_factory=_make_noop_factory())
        result = svc.run(tmp_path, "task", "safe")
        assert result["overall_status"] == "error"

    def test_aborted_run_populates_error_field(self, tmp_path):
        svc = AgentRunService(controller_factory=_make_noop_factory())
        result = svc.run(tmp_path, "task", "safe")
        assert result["error"] is not None

    def test_exception_in_execute_is_captured(self, tmp_path):
        svc = AgentRunService(controller_factory=_make_raising_factory("disk full"))
        result = svc.run(tmp_path, "task", "audit")
        assert result["error"] == "disk full"

    def test_exception_does_not_propagate(self, tmp_path):
        svc = AgentRunService(controller_factory=_make_raising_factory("boom"))
        result = svc.run(tmp_path, "task", "audit")
        assert isinstance(result, dict)

    def test_artifact_paths_is_list(self, tmp_path):
        svc = AgentRunService(controller_factory=_make_noop_factory())
        result = svc.run(tmp_path, "task", "audit")
        assert isinstance(result["artifact_paths"], list)

    def test_run_dir_set_when_execute_returns(self, tmp_path):
        svc = AgentRunService(controller_factory=_make_noop_factory())
        result = svc.run(tmp_path, "task", "audit")
        # run_dir should be a non-None path string (even if dir doesn't exist yet)
        assert result["run_dir"] is not None
        assert "fake-session-001" in result["run_dir"]

    def test_default_factory_is_runcontroller(self, tmp_path):
        svc = AgentRunService()
        assert svc._controller_factory is None

    def test_raw_agent_exit_code_used_not_wrapper(self, tmp_path):
        svc = AgentRunService(
            controller_factory=_make_summary_factory(
                agent_exit_code=7, agent_status="failure", overall_status="failure"
            )
        )
        result = svc.run(tmp_path, "task", "audit")
        assert result["exit_code"] == 7

    def test_raw_agent_exit_code_zero(self, tmp_path):
        svc = AgentRunService(
            controller_factory=_make_summary_factory(agent_exit_code=0)
        )
        result = svc.run(tmp_path, "task", "safe")
        assert result["exit_code"] == 0

    def test_abort_surfaces_specific_error_from_disk(self, tmp_path):
        session_dir = tmp_path / ".vibecode" / "runs" / "fake-session-001"
        session_dir.mkdir(parents=True, exist_ok=True)
        summary_data = {
            "$schema": "vibecode/run-summary/v1",
            "session_id": "fake-session-001",
            "overall_status": "error",
            "error": "No .vibecode/project.yaml found.",
        }
        (session_dir / "summary.json").write_text(
            json.dumps(summary_data), encoding="utf-8"
        )
        svc = AgentRunService(controller_factory=_make_noop_factory())
        result = svc.run(tmp_path, "task", "safe")
        assert "No .vibecode/project.yaml found." in result["error"]

    def test_abort_fallback_when_no_summary_on_disk(self, tmp_path):
        svc = AgentRunService(controller_factory=_make_noop_factory(session_id="no-disk"))
        result = svc.run(tmp_path, "task", "safe")
        assert "see run directory" in result["error"]

    def test_artifact_paths_includes_handoff_report_json(self, tmp_path):
        session_dir = tmp_path / ".vibecode" / "runs" / "fake-session-001"
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "handoff_report.json").write_text("{}", encoding="utf-8")
        svc = AgentRunService(controller_factory=_make_noop_factory())
        result = svc.run(tmp_path, "task", "safe")
        assert any("handoff_report.json" in p for p in result["artifact_paths"])

    def test_artifact_paths_includes_agent_stderr_log(self, tmp_path):
        session_dir = tmp_path / ".vibecode" / "runs" / "fake-session-001"
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "agent_stderr.log").write_text("err", encoding="utf-8")
        svc = AgentRunService(controller_factory=_make_noop_factory())
        result = svc.run(tmp_path, "task", "safe")
        assert any("agent_stderr.log" in p for p in result["artifact_paths"])

    def test_artifact_paths_includes_metadata_json(self, tmp_path):
        session_dir = tmp_path / ".vibecode" / "runs" / "fake-session-001"
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "metadata.json").write_text("{}", encoding="utf-8")
        svc = AgentRunService(controller_factory=_make_noop_factory())
        result = svc.run(tmp_path, "task", "safe")
        assert any("metadata.json" in p for p in result["artifact_paths"])


# ---------------------------------------------------------------------------
# TestRenderCenterRunStatus
# ---------------------------------------------------------------------------


class TestRenderCenterRunStatus:
    def test_shows_opencode_provider(self):
        text = render_center_run_status("task", "audit", "running...")
        assert "OpenCode" in text

    def test_shows_profile(self):
        text = render_center_run_status("task", "audit", "running...")
        assert "audit" in text

    def test_shows_safe_profile(self):
        text = render_center_run_status("task", "safe", "running...")
        assert "safe" in text

    def test_shows_running_status(self):
        text = render_center_run_status("task", "audit", "running...")
        assert "running..." in text

    def test_shows_success_status(self):
        text = render_center_run_status("task", "safe", "success")
        assert "success" in text

    def test_shows_failure_status(self):
        text = render_center_run_status("task", "audit", "failure")
        assert "failure" in text

    def test_shows_task(self):
        text = render_center_run_status("my important task", "audit", "running...")
        assert "my important task" in text

    def test_long_task_is_truncated(self):
        long_task = "z" * 200
        text = render_center_run_status(long_task, "audit", "running...")
        assert "…" in text
        assert long_task not in text

    def test_session_id_shown_when_provided(self):
        text = render_center_run_status(
            "task", "audit", "success", session_id="abc-123"
        )
        assert "abc-123" in text

    def test_session_id_absent_when_not_provided(self):
        text = render_center_run_status("task", "audit", "success")
        assert "abc-123" not in text

    def test_run_dir_shown_when_provided(self):
        text = render_center_run_status(
            "task", "audit", "success", run_dir="/path/to/run"
        )
        assert "/path/to/run" in text

    def test_run_dir_absent_when_not_provided(self):
        text = render_center_run_status("task", "audit", "success")
        assert "Run dir:" not in text

    def test_no_llm_mentions(self):
        text = render_center_run_status("task", "audit", "running...").lower()
        assert "llm" not in text
        assert "gpt" not in text
        assert "claude" not in text


# ---------------------------------------------------------------------------
# TestRenderRightRunResult
# ---------------------------------------------------------------------------


class TestRenderRightRunResult:
    def _result(self, **overrides) -> dict:
        base: dict = {
            "session_id": "test-session-001",
            "task": "implement feature",
            "profile": "audit",
            "run_dir": "/repo/.vibecode/runs/test-session-001",
            "overall_status": "success",
            "exit_code": 0,
            "context_pack_path": None,
            "prompt_path": None,
            "guard_passed": True,
            "guard_errors": 0,
            "guard_warnings": 0,
            "checks_passed": True,
            "handoff_passed": True,
            "artifact_paths": [],
            "error": None,
        }
        base.update(overrides)
        return base

    def test_shows_session_id(self):
        text = render_right_run_result(self._result())
        assert "test-session-001" in text

    def test_shows_overall_status(self):
        text = render_right_run_result(self._result())
        assert "success" in text

    def test_shows_failure_status(self):
        text = render_right_run_result(self._result(overall_status="failure"))
        assert "failure" in text

    def test_shows_guard_passed(self):
        text = render_right_run_result(self._result(guard_passed=True))
        assert "PASSED" in text

    def test_shows_guard_failed_with_error_count(self):
        text = render_right_run_result(
            self._result(guard_passed=False, guard_errors=2, guard_warnings=1)
        )
        assert "FAILED" in text
        assert "2" in text

    def test_shows_guard_skipped_when_none(self):
        text = render_right_run_result(self._result(guard_passed=None))
        assert "skipped" in text

    def test_shows_checks_passed(self):
        text = render_right_run_result(self._result(checks_passed=True))
        assert "PASSED" in text

    def test_shows_checks_failed(self):
        text = render_right_run_result(self._result(checks_passed=False))
        assert "FAILED" in text

    def test_shows_checks_skipped(self):
        text = render_right_run_result(self._result(checks_passed=None))
        assert "skipped" in text

    def test_shows_handoff_passed(self):
        text = render_right_run_result(self._result(handoff_passed=True))
        assert "PASSED" in text

    def test_shows_handoff_skipped(self):
        text = render_right_run_result(self._result(handoff_passed=None))
        assert "skipped" in text

    def test_shows_context_pack_path(self):
        text = render_right_run_result(
            self._result(context_pack_path="/path/to/pack.md")
        )
        assert "/path/to/pack.md" in text

    def test_shows_prompt_path(self):
        text = render_right_run_result(self._result(prompt_path="/path/to/prompt.md"))
        assert "/path/to/prompt.md" in text

    def test_shows_artifact_paths(self):
        text = render_right_run_result(
            self._result(artifact_paths=["/run/summary.json"])
        )
        assert "/run/summary.json" in text

    def test_shows_error_field(self):
        text = render_right_run_result(self._result(error="disk full"))
        assert "ERROR" in text
        assert "disk full" in text

    def test_no_error_section_when_none(self):
        text = render_right_run_result(self._result(error=None))
        assert "ERROR" not in text

    def test_shows_run_dir(self):
        text = render_right_run_result(self._result())
        assert ".vibecode/runs/test-session-001" in text

    def test_shows_profile(self):
        text = render_right_run_result(self._result(profile="audit"))
        assert "audit" in text

    def test_shows_nonzero_exit_code(self):
        text = render_right_run_result(self._result(exit_code=7))
        assert "7" in text
        assert "Exit code" in text


# ---------------------------------------------------------------------------
# TestRunActionsInTUI — without running the full Textual event loop
# ---------------------------------------------------------------------------


class TestRunActionsInTUI:
    def _make_app(self, tmp_path: Path, run_service: object | None = None):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp
        from vibecode.repo_status import RepoStatus

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")

        status = RepoStatus(repo_path=tmp_path)
        app = VibecodeMainApp(
            repo_path=tmp_path,
            status=status,
            run_service=run_service,
        )
        app._log_event = lambda msg: None  # suppress
        return app

    # --- DI / service accessors ---

    def test_run_service_is_none_by_default(self, tmp_path):
        app = self._make_app(tmp_path)
        assert app._run_service is None

    def test_run_service_injected(self, tmp_path):
        class FakeSvc:
            pass

        svc = FakeSvc()
        app = self._make_app(tmp_path, run_service=svc)
        assert app._run_service is svc

    def test_get_run_service_returns_agent_run_service(self, tmp_path):
        app = self._make_app(tmp_path)
        svc = app._get_run_service()
        assert isinstance(svc, AgentRunService)

    def test_get_run_service_is_idempotent(self, tmp_path):
        app = self._make_app(tmp_path)
        assert app._get_run_service() is app._get_run_service()

    def test_pending_run_profile_none_on_init(self, tmp_path):
        app = self._make_app(tmp_path)
        assert app._pending_run_profile is None

    # --- action_cmd_audit / action_cmd_safe without current task ---

    def test_audit_pushes_screen_when_no_task(self, tmp_path):
        app = self._make_app(tmp_path)
        pushed: list = []
        app.push_screen = lambda *a, **kw: pushed.append(a)
        app.action_cmd_audit()
        assert len(pushed) == 1
        assert app._pending_run_profile == "audit"

    def test_safe_pushes_screen_when_no_task(self, tmp_path):
        app = self._make_app(tmp_path)
        pushed: list = []
        app.push_screen = lambda *a, **kw: pushed.append(a)
        app.action_cmd_safe()
        assert len(pushed) == 1
        assert app._pending_run_profile == "safe"

    def test_audit_does_not_push_screen_when_task_set(self, tmp_path):
        app = self._make_app(tmp_path)
        app._current_task = "existing task"
        pushed: list = []
        app.push_screen = lambda *a, **kw: pushed.append(a)
        with patch.object(threading.Thread, "start", lambda self: None):
            app.action_cmd_audit()
        assert pushed == []

    # --- action_cmd_audit / action_cmd_safe with current task set ---

    def test_audit_starts_thread_when_task_set(self, tmp_path):
        app = self._make_app(tmp_path)
        app._current_task = "existing task"
        log: list[str] = []
        app._log_event = lambda msg: log.append(msg)
        threads: list[str] = []

        with patch.object(threading.Thread, "start", lambda self: threads.append(self.name)):
            app.action_cmd_audit()

        assert any("tui-run-audit" in t for t in threads)

    def test_safe_starts_thread_when_task_set(self, tmp_path):
        app = self._make_app(tmp_path)
        app._current_task = "existing task"
        app._log_event = lambda msg: None
        threads: list[str] = []

        with patch.object(threading.Thread, "start", lambda self: threads.append(self.name)):
            app.action_cmd_safe()

        assert any("tui-run-safe" in t for t in threads)

    def test_audit_logs_starting_message(self, tmp_path):
        app = self._make_app(tmp_path)
        app._current_task = "existing task"
        log: list[str] = []
        app._log_event = lambda msg: log.append(msg)

        with patch.object(threading.Thread, "start", lambda self: None):
            app.action_cmd_audit()

        assert any("audit" in m.lower() or "Starting" in m for m in log)

    # --- _on_run_task_received_for_run ---

    def test_cancel_clears_pending_profile(self, tmp_path):
        app = self._make_app(tmp_path)
        log: list[str] = []
        app._log_event = lambda msg: log.append(msg)
        app._pending_run_profile = "audit"
        app._on_run_task_received_for_run(None)
        assert app._pending_run_profile is None
        assert any("cancel" in m.lower() for m in log)

    def test_cancel_does_not_set_current_task(self, tmp_path):
        app = self._make_app(tmp_path)
        app._log_event = lambda msg: None
        app._pending_run_profile = "audit"
        app._on_run_task_received_for_run(None)
        assert app._current_task is None

    def test_task_received_sets_current_task(self, tmp_path):
        app = self._make_app(tmp_path)
        app._log_event = lambda msg: None
        app._pending_run_profile = "safe"

        threads: list[str] = []
        with patch.object(threading.Thread, "start", lambda self: threads.append(self.name)):
            app._on_run_task_received_for_run("new task")

        assert app._current_task == "new task"
        assert any("tui-run-safe" in t for t in threads)

    def test_task_received_starts_run_with_correct_profile(self, tmp_path):
        app = self._make_app(tmp_path)
        app._log_event = lambda msg: None
        app._pending_run_profile = "audit"

        threads: list[str] = []
        with patch.object(threading.Thread, "start", lambda self: threads.append(self.name)):
            app._on_run_task_received_for_run("task desc")

        assert any("tui-run-audit" in t for t in threads)

    # --- _on_run_done ---

    def test_on_run_done_logs_completion(self, tmp_path):
        app = self._make_app(tmp_path)
        log: list[str] = []
        app._log_event = lambda msg: log.append(msg)

        class _FakeWidget:
            def update(self, text: str) -> None:
                pass

            def clear(self) -> None:
                pass

        app.query_one = lambda sel, *_: _FakeWidget()
        app._refresh_left_panel = lambda: None

        result = {
            "session_id": "s001",
            "task": "task",
            "profile": "audit",
            "run_dir": "/run/dir",
            "overall_status": "success",
            "exit_code": 0,
            "context_pack_path": None,
            "prompt_path": None,
            "guard_passed": True,
            "guard_errors": 0,
            "guard_warnings": 0,
            "checks_passed": True,
            "handoff_passed": True,
            "artifact_paths": [],
            "error": None,
        }
        app._on_run_done(result)
        assert any(
            "success" in m.lower() or "complete" in m.lower() or "Run" in m
            for m in log
        )

    def test_on_run_done_calls_refresh_left_panel(self, tmp_path):
        app = self._make_app(tmp_path)
        app._log_event = lambda msg: None

        class _FakeWidget:
            def update(self, text: str) -> None:
                pass

        refreshed: list[bool] = []
        app.query_one = lambda sel, *_: _FakeWidget()
        app._refresh_left_panel = lambda: refreshed.append(True)

        result = {
            "session_id": "s001",
            "task": "task",
            "profile": "audit",
            "run_dir": None,
            "overall_status": "success",
            "exit_code": 0,
            "context_pack_path": None,
            "prompt_path": None,
            "guard_passed": None,
            "guard_errors": 0,
            "guard_warnings": 0,
            "checks_passed": None,
            "handoff_passed": None,
            "artifact_paths": [],
            "error": None,
        }
        app._on_run_done(result)
        assert refreshed

    # --- _on_run_error ---

    def test_on_run_error_logs_error(self, tmp_path):
        app = self._make_app(tmp_path)
        log: list[str] = []
        app._log_event = lambda msg: log.append(msg)
        app._on_run_error("something went wrong")
        assert any("something went wrong" in m for m in log)

    def test_on_run_error_does_not_raise(self, tmp_path):
        app = self._make_app(tmp_path)
        app._log_event = lambda msg: None
        app._on_run_error("boom")  # must not raise


# ---------------------------------------------------------------------------
# TestAgentRunServiceIntegration — fake OpenCode binary
# ---------------------------------------------------------------------------


class TestAgentRunServiceIntegration:
    @pytest.fixture()
    def repo(self, tmp_path: Path) -> Path:
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        _init_repo(repo_dir)
        _minimal_vibecode(repo_dir)
        _write(repo_dir / "app.py", "x = 1\n")
        _commit_all(repo_dir)
        return repo_dir

    @pytest.fixture()
    def fake_bin(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        fake_dir = tmp_path / "fake_bin"
        fake_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv(
            "PATH", str(fake_dir) + os.pathsep + os.environ.get("PATH", "")
        )
        return fake_dir

    def test_successful_run_has_non_error_status(self, repo, fake_bin):
        _fake_opencode_script(fake_bin, exit_code=0, stdout="OK\n")
        svc = AgentRunService()
        result = svc.run(repo, "test task", "safe", session_id="int-success-001")
        assert result["overall_status"] in ("success", "needs_review", "incomplete")
        assert result["error"] is None

    def test_result_has_session_id(self, repo, fake_bin):
        _fake_opencode_script(fake_bin, exit_code=0, stdout="OK\n")
        svc = AgentRunService()
        result = svc.run(repo, "test task", "audit", session_id="int-sid-001")
        assert result["session_id"] == "int-sid-001"

    def test_result_has_run_dir(self, repo, fake_bin):
        _fake_opencode_script(fake_bin, exit_code=0, stdout="OK\n")
        svc = AgentRunService()
        result = svc.run(repo, "test task", "safe", session_id="int-dir-001")
        assert result["run_dir"] is not None
        assert "int-dir-001" in result["run_dir"]

    def test_run_creates_artifacts(self, repo, fake_bin):
        _fake_opencode_script(fake_bin, exit_code=0, stdout="OK\n")
        svc = AgentRunService()
        result = svc.run(repo, "test task", "safe", session_id="int-art-001")
        assert len(result["artifact_paths"]) > 0

    def test_failed_opencode_reflects_failure(self, repo, fake_bin):
        _fake_opencode_script(fake_bin, exit_code=1, stdout="", stderr="ERR\n")
        svc = AgentRunService()
        result = svc.run(repo, "test task", "audit", session_id="int-fail-001")
        assert result["overall_status"] in ("failure", "error", "needs_review")

    def test_profile_audit_in_result(self, repo, fake_bin):
        _fake_opencode_script(fake_bin, exit_code=0, stdout="OK\n")
        svc = AgentRunService()
        result = svc.run(repo, "test task", "audit", session_id="int-prof-001")
        assert result["profile"] == "audit"

    def test_profile_safe_in_result(self, repo, fake_bin):
        _fake_opencode_script(fake_bin, exit_code=0, stdout="OK\n")
        svc = AgentRunService()
        result = svc.run(repo, "test task", "safe", session_id="int-safe-001")
        assert result["profile"] == "safe"
