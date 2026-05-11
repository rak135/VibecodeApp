"""Tests for RunController — structured event emissions and orchestration.

All tests use a temporary directory as the repo root and a fake OpenCode
script so that no real OpenCode installation is required.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from vibecode.cli import main
from vibecode.events import (
    EVENT_AGENT_PROCESS,
    EVENT_CHECK,
    EVENT_CONTEXT,
    EVENT_GIT_PREFLIGHT,
    EVENT_GUARD,
    EVENT_HANDOFF,
    EVENT_INDEX_CHECK,
    EVENT_PROMPT,
    EVENT_RUN_LIFECYCLE,
    EVENT_SUMMARY,
    EventLevel,
    InMemoryEventSink,
)
from vibecode.permissions import PROFILES
from vibecode.run import RunController


# ---------------------------------------------------------------------------
# Helpers (shared with existing run tests)
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
    """Write minimal .vibecode structure for a valid run."""
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
    _write(
        repo / ".vibecode" / "index" / "file_inventory.json",
        json.dumps({
            "$schema": "vibecode/file-inventory/v1",
            "files": [{"path": "test.py", "size": 100}],
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
    tmp_path: Path, exit_code: int = 0, stdout: str = "OK\n", stderr: str = "",
    stdin_path: str | None = None,
) -> Path:
    """Create fake opencode command on PATH. Returns the .cmd wrapper path.

    When *stdin_path* is not None, the fake opencode writes its stdin to that
    file before exiting.  This allows tests to verify the exact prompt content
    passed to the agent process.
    """
    stdin_capture_block = ""
    if stdin_path is not None:
        stdin_capture_block = f"""
import pathlib
pathlib.Path({stdin_path!r}).write_text(inp, encoding='utf-8')
"""
    py_script = tmp_path / "opencode.py"
    py_script.write_text(
        f"""#!{sys.executable}
import sys

argv = sys.argv[1:] if len(sys.argv) > 1 else []
if "--version" in argv:
    sys.stdout.write("fake-opencode 1.0.0\\n")
    sys.exit(0)

inp = sys.stdin.read(){stdin_capture_block}
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A minimal clean git + vibecode repo for run tests."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    _init_repo(repo_dir)
    _minimal_vibecode(repo_dir)
    _write(repo_dir / "app.py", "x = 1\n")
    _commit_all(repo_dir)
    return repo_dir


@pytest.fixture()
def fake_bin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A directory containing a fake opencode command, added to PATH."""
    fake_dir = tmp_path / "fake_bin"
    fake_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PATH", str(fake_dir) + os.pathsep + os.environ.get("PATH", ""))
    return fake_dir


def _make_fake_opencode(
    fake_dir: Path, exit_code: int = 0, stdout: str = "OK\n", stderr: str = "",
    stdin_path: str | None = None,
) -> None:
    _fake_opencode_script(fake_dir, exit_code=exit_code, stdout=stdout, stderr=stderr, stdin_path=stdin_path)


# ---------------------------------------------------------------------------
# Tests: event sequence for a successful run
# ---------------------------------------------------------------------------


class TestRunControllerEventSequence:
    def test_run_emits_started_and_finished(self, repo: Path, fake_bin: Path):
        _make_fake_opencode(fake_bin)
        sink = InMemoryEventSink()
        controller = RunController(
            root=repo,
            task="test task",
            platform="opencode",
            profile_name="safe",
            allow_dirty=False,
            no_index=True,
            sink=sink,
            session_id="test-seq-001",
        )
        summary, exit_code = controller.execute()

        assert exit_code == 0
        assert summary is not None

        types = [e.type for e in sink.events]
        assert types[0] == EVENT_RUN_LIFECYCLE
        assert sink.events[0].data["phase"] == "started"
        assert types[-1] == EVENT_RUN_LIFECYCLE
        assert sink.events[-1].data["phase"] == "finished"

    def test_run_emits_all_lifecycle_phases_in_order(self, repo: Path, fake_bin: Path):
        _make_fake_opencode(fake_bin)
        sink = InMemoryEventSink()
        controller = RunController(
            root=repo,
            task="test task",
            platform="opencode",
            profile_name="safe",
            allow_dirty=False,
            no_index=True,
            sink=sink,
            session_id="test-seq-002",
        )
        controller.execute()

        types = [e.type for e in sink.events]

        # All required event types must appear.
        assert EVENT_RUN_LIFECYCLE in types
        assert EVENT_GIT_PREFLIGHT in types
        assert EVENT_INDEX_CHECK in types
        assert EVENT_CONTEXT in types
        assert EVENT_PROMPT in types
        assert EVENT_AGENT_PROCESS in types
        assert EVENT_GUARD in types
        assert EVENT_CHECK in types
        assert EVENT_HANDOFF in types
        assert EVENT_SUMMARY in types

    def test_git_preflight_completed_before_index_check(self, repo: Path, fake_bin: Path):
        _make_fake_opencode(fake_bin)
        sink = InMemoryEventSink()
        controller = RunController(
            root=repo,
            task="t",
            platform="opencode",
            profile_name="safe",
            allow_dirty=False,
            no_index=True,
            sink=sink,
            session_id="test-order-001",
        )
        controller.execute()

        git_idx = next(
            i for i, e in enumerate(sink.events)
            if e.type == EVENT_GIT_PREFLIGHT and e.data and e.data.get("phase") == "completed"
        )
        idx_start = next(
            i for i, e in enumerate(sink.events)
            if e.type == EVENT_INDEX_CHECK and e.data and e.data.get("phase") == "started"
        )
        assert git_idx < idx_start

    def test_agent_started_before_agent_finished(self, repo: Path, fake_bin: Path):
        _make_fake_opencode(fake_bin)
        sink = InMemoryEventSink()
        controller = RunController(
            root=repo,
            task="t",
            platform="opencode",
            profile_name="safe",
            allow_dirty=False,
            no_index=True,
            sink=sink,
            session_id="test-order-002",
        )
        controller.execute()

        agent_events = [e for e in sink.events if e.type == EVENT_AGENT_PROCESS]
        phases = [e.data["phase"] for e in agent_events if e.data]
        assert phases.index("started") < phases.index("finished")

    def test_guard_started_before_guard_completed(self, repo: Path, fake_bin: Path):
        _make_fake_opencode(fake_bin)
        sink = InMemoryEventSink()
        controller = RunController(
            root=repo,
            task="t",
            platform="opencode",
            profile_name="safe",
            allow_dirty=False,
            no_index=True,
            sink=sink,
        )
        controller.execute()

        guard_events = [e for e in sink.events if e.type == EVENT_GUARD]
        phases = [e.data["phase"] for e in guard_events if e.data]
        assert phases.index("started") < phases.index("completed")

    def test_summary_written_before_run_finished(self, repo: Path, fake_bin: Path):
        _make_fake_opencode(fake_bin)
        sink = InMemoryEventSink()
        controller = RunController(
            root=repo,
            task="t",
            platform="opencode",
            profile_name="safe",
            allow_dirty=False,
            no_index=True,
            sink=sink,
        )
        controller.execute()

        types = [e.type for e in sink.events]
        summary_idx = next(i for i, t in enumerate(types) if t == EVENT_SUMMARY)
        finished_idx = next(
            i for i, e in enumerate(sink.events)
            if e.type == EVENT_RUN_LIFECYCLE and e.data and e.data.get("phase") == "finished"
        )
        assert summary_idx < finished_idx


# ---------------------------------------------------------------------------
# Tests: summary file is written
# ---------------------------------------------------------------------------


class TestRunControllerSummaryWritten:
    def test_summary_json_exists_after_successful_run(self, repo: Path, fake_bin: Path):
        _make_fake_opencode(fake_bin)
        controller = RunController(
            root=repo,
            task="my task",
            platform="opencode",
            profile_name="safe",
            allow_dirty=False,
            no_index=True,
            session_id="test-summary-001",
        )
        summary, exit_code = controller.execute()

        assert exit_code == 0
        session_dir = repo / ".vibecode" / "runs" / "test-summary-001"
        summary_path = session_dir / "summary.json"
        assert summary_path.exists()
        data = json.loads(summary_path.read_text())
        assert data["session_id"] == "test-summary-001"
        assert data["overall_status"] == "success"

        events_path = session_dir / "events.jsonl"
        assert events_path.exists()
        events_lines = events_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(events_lines) > 0

    def test_summary_event_has_correct_path(self, repo: Path, fake_bin: Path):
        _make_fake_opencode(fake_bin)
        sink = InMemoryEventSink()
        controller = RunController(
            root=repo,
            task="t",
            platform="opencode",
            profile_name="safe",
            allow_dirty=False,
            no_index=True,
            sink=sink,
            session_id="test-summary-002",
        )
        controller.execute()

        summary_events = [e for e in sink.events if e.type == EVENT_SUMMARY]
        assert len(summary_events) == 1
        assert "summary.json" in summary_events[0].data["path"]
        assert summary_events[0].data["phase"] == "written"

    def test_returned_summary_matches_written_file(self, repo: Path, fake_bin: Path):
        _make_fake_opencode(fake_bin, stdout="agent output\n")
        controller = RunController(
            root=repo,
            task="my task",
            platform="opencode",
            profile_name="safe",
            allow_dirty=False,
            no_index=True,
            session_id="test-summary-003",
        )
        summary, _ = controller.execute()

        assert summary is not None
        assert summary.session_id == "test-summary-003"
        assert summary.task == "my task"
        assert summary.stdout == "agent output\n"


# ---------------------------------------------------------------------------
# Tests: failure events
# ---------------------------------------------------------------------------


class TestRunControllerFailureEvents:
    def test_no_project_yaml_emits_error_run_finished(self, tmp_path: Path):
        """Missing project.yaml → error RunFinished with no_project_yaml."""
        sink = InMemoryEventSink()
        controller = RunController(
            root=tmp_path,
            task="t",
            platform="opencode",
            profile_name="safe",
            allow_dirty=False,
            no_index=True,
            sink=sink,
        )
        summary, exit_code = controller.execute()

        assert exit_code == 1
        assert summary is None
        lifecycle_events = [e for e in sink.events if e.type == EVENT_RUN_LIFECYCLE]
        # RunStarted + RunFinished(error)
        assert lifecycle_events[0].data["phase"] == "started"
        finished = lifecycle_events[-1]
        assert finished.data["phase"] == "finished"
        assert finished.data["status"] == "error"
        assert finished.level == EventLevel.ERROR

    def test_dirty_repo_without_allow_dirty_emits_git_preflight_failed(
        self, repo: Path, fake_bin: Path
    ):
        """Dirty git tree without allow_dirty → GitPreflightCompleted(passed=False)."""
        _make_fake_opencode(fake_bin)
        _write(repo / "app.py", "x = 99\n")  # make dirty

        sink = InMemoryEventSink()
        controller = RunController(
            root=repo,
            task="t",
            platform="opencode",
            profile_name="safe",
            allow_dirty=False,
            no_index=True,
            sink=sink,
        )
        _, exit_code = controller.execute()

        assert exit_code == 1
        git_completed = next(
            (e for e in sink.events
             if e.type == EVENT_GIT_PREFLIGHT and e.data and e.data.get("phase") == "completed"),
            None,
        )
        assert git_completed is not None
        assert git_completed.data["passed"] is False
        assert git_completed.level == EventLevel.ERROR

    def test_agent_failure_emits_error_level_agent_finished(self, repo: Path, fake_bin: Path):
        """Agent exits non-zero → AgentFinished at ERROR level."""
        _make_fake_opencode(fake_bin, exit_code=1, stderr="agent error\n")
        sink = InMemoryEventSink()
        controller = RunController(
            root=repo,
            task="t",
            platform="opencode",
            profile_name="safe",
            allow_dirty=False,
            no_index=True,
            sink=sink,
        )
        summary, exit_code = controller.execute()

        # Exit code may be 1 (failure) but the run completes through post-checks.
        agent_finished = next(
            e for e in sink.events
            if e.type == EVENT_AGENT_PROCESS and e.data and e.data.get("phase") == "finished"
        )
        assert agent_finished.level == EventLevel.ERROR
        assert agent_finished.data["exit_code"] == 1
        assert agent_finished.data["status"] == "failure"

    def test_no_opencode_command_emits_error_events(self, repo: Path, monkeypatch: pytest.MonkeyPatch):
        """No opencode on PATH → error events emitted, no summary written."""
        # Remove opencode from PATH by wiping OPENCODE_COMMAND and PATH
        monkeypatch.setenv("OPENCODE_COMMAND", "nonexistent_opencode_cmd_xyz")

        sink = InMemoryEventSink()
        controller = RunController(
            root=repo,
            task="t",
            platform="opencode",
            profile_name="safe",
            allow_dirty=False,
            no_index=True,
            sink=sink,
        )
        summary, exit_code = controller.execute()

        assert exit_code == 1
        assert summary is None

        # AgentProcess error event should be emitted
        agent_err = next(
            (e for e in sink.events
             if e.type == EVENT_AGENT_PROCESS and e.level == EventLevel.ERROR),
            None,
        )
        assert agent_err is not None

        # RunFinished should have status "error"
        run_finished = next(
            e for e in sink.events
            if e.type == EVENT_RUN_LIFECYCLE and e.data and e.data.get("phase") == "finished"
        )
        assert run_finished.data["status"] == "error"

    def test_agent_failure_run_finished_has_failure_status(self, repo: Path, fake_bin: Path):
        """Agent exits non-zero → RunFinished status is 'failure'."""
        _make_fake_opencode(fake_bin, exit_code=1)
        sink = InMemoryEventSink()
        controller = RunController(
            root=repo,
            task="t",
            platform="opencode",
            profile_name="safe",
            allow_dirty=False,
            no_index=True,
            sink=sink,
        )
        controller.execute()

        run_finished = next(
            e for e in sink.events
            if e.type == EVENT_RUN_LIFECYCLE and e.data and e.data.get("phase") == "finished"
        )
        assert run_finished.data["status"] == "failure"


# ---------------------------------------------------------------------------
# Tests: legacy CLI path (cmd_run via main())
# ---------------------------------------------------------------------------


class TestLegacyCLIPath:
    def test_cli_run_exits_0_on_success(self, repo: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch):
        """vibecode run via CLI returns 0 on a successful agent run."""
        _make_fake_opencode(fake_bin)
        rc = main(["run", str(repo), "--task", "cli test", "--no-index"])
        assert rc == 0

    def test_cli_run_exits_1_on_missing_init(self, tmp_path: Path):
        """vibecode run without project.yaml returns 1."""
        rc = main(["run", str(tmp_path), "--task", "x"])
        assert rc == 1

    def test_cli_run_exits_1_on_agent_failure(self, repo: Path, fake_bin: Path):
        """vibecode run returns 1 when agent exits non-zero."""
        _make_fake_opencode(fake_bin, exit_code=1)
        rc = main(["run", str(repo), "--task", "x", "--no-index"])
        assert rc == 1

    def test_cli_run_writes_summary_json(self, repo: Path, fake_bin: Path):
        """CLI run still writes a summary.json under .vibecode/runs/."""
        _make_fake_opencode(fake_bin)
        rc = main(["run", str(repo), "--task", "cli-summary-test", "--no-index"])
        assert rc == 0
        runs_dir = repo / ".vibecode" / "runs"
        run_dirs = list(runs_dir.iterdir())
        assert len(run_dirs) >= 1
        session_dir = run_dirs[-1]
        summary_file = session_dir / "summary.json"
        assert summary_file.exists()
        data = json.loads(summary_file.read_text())
        assert data["task"] == "cli-summary-test"

        events_file = session_dir / "events.jsonl"
        assert events_file.exists()
        events_lines = events_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(events_lines) > 0


# ---------------------------------------------------------------------------
# Tests: NullEventSink default (no sink provided → no crash)
# ---------------------------------------------------------------------------


class TestNullEventSinkDefault:
    def test_controller_without_sink_does_not_crash(self, repo: Path, fake_bin: Path):
        """RunController with no sink (uses NullEventSink) completes normally."""
        _make_fake_opencode(fake_bin)
        controller = RunController(
            root=repo,
            task="null sink test",
            platform="opencode",
            profile_name="safe",
            allow_dirty=False,
            no_index=True,
        )
        summary, exit_code = controller.execute()
        assert exit_code == 0
        assert summary is not None


# ---------------------------------------------------------------------------
# Tests: event session_id is consistent
# ---------------------------------------------------------------------------


class TestEventSessionId:
    def test_all_events_share_session_id(self, repo: Path, fake_bin: Path):
        """Every emitted event carries the controller's session_id."""
        _make_fake_opencode(fake_bin)
        sink = InMemoryEventSink()
        sid = "test-session-consistency"
        controller = RunController(
            root=repo,
            task="t",
            platform="opencode",
            profile_name="safe",
            allow_dirty=False,
            no_index=True,
            sink=sink,
            session_id=sid,
        )
        controller.execute()

        assert len(sink.events) > 0
        for event in sink.events:
            assert event.session_id == sid, (
                f"Event {event.type} has session_id={event.session_id!r}, expected {sid!r}"
            )


# ---------------------------------------------------------------------------
# Tests: dirty tree with allow_dirty emits warning not error
# ---------------------------------------------------------------------------


class TestAllowDirty:
    def test_dirty_with_allow_dirty_emits_warning_not_error(self, repo: Path, fake_bin: Path):
        """With allow_dirty=True, dirty tree emits WARNING preflight events, not ERROR."""
        _make_fake_opencode(fake_bin)
        _write(repo / "app.py", "x = 42\n")  # make dirty

        sink = InMemoryEventSink()
        controller = RunController(
            root=repo,
            task="t",
            platform="opencode",
            profile_name="safe",
            allow_dirty=True,
            no_index=True,
            sink=sink,
        )
        _, exit_code = controller.execute()

        # Run should still complete (0 or non-zero depending on summary)
        git_warnings = [
            e for e in sink.events
            if e.type == EVENT_GIT_PREFLIGHT and e.level == EventLevel.WARNING
        ]
        assert len(git_warnings) >= 1

        # No blocking git preflight error
        git_completed = next(
            (e for e in sink.events
             if e.type == EVENT_GIT_PREFLIGHT and e.data and e.data.get("phase") == "completed"),
            None,
        )
        assert git_completed is not None
        assert git_completed.data["passed"] is True


# ---------------------------------------------------------------------------
# Tests: context pack and prompt snapshot events
# ---------------------------------------------------------------------------


def _get_ctx_written(sink: InMemoryEventSink):
    """Return the EVENT_CONTEXT 'written' event from *sink*."""
    return next(
        e for e in sink.events
        if e.type == EVENT_CONTEXT and e.data and e.data.get("phase") == "written"
    )


def _get_prompt_written(sink: InMemoryEventSink):
    """Return the EVENT_PROMPT 'written' event from *sink*."""
    return next(
        e for e in sink.events
        if e.type == EVENT_PROMPT and e.data and e.data.get("phase") == "written"
    )


class TestContextAndPromptSnapshotEvents:
    """Verify that context pack and prompt events carry snapshot paths and metadata."""

    def test_context_event_has_snapshot_path(self, repo: Path, fake_bin: Path):
        """EVENT_CONTEXT written event includes a non-None snapshot_path."""
        _make_fake_opencode(fake_bin)
        sink = InMemoryEventSink()
        RunController(
            root=repo, task="fix the login bug", platform="opencode",
            profile_name="safe", allow_dirty=False, no_index=True,
            sink=sink, session_id="snap-ctx-001",
        ).execute()

        evt = _get_ctx_written(sink)
        assert "snapshot_path" in evt.data
        assert evt.data["snapshot_path"] is not None

    def test_context_event_snapshot_path_contains_session_id(self, repo: Path, fake_bin: Path):
        """The snapshot_path in EVENT_CONTEXT is inside the session run directory."""
        _make_fake_opencode(fake_bin)
        sink = InMemoryEventSink()
        RunController(
            root=repo, task="t", platform="opencode",
            profile_name="safe", allow_dirty=False, no_index=True,
            sink=sink, session_id="snap-ctx-002",
        ).execute()

        evt = _get_ctx_written(sink)
        assert "snap-ctx-002" in evt.data["snapshot_path"]

    def test_context_snapshot_file_exists_on_disk(self, repo: Path, fake_bin: Path):
        """The file at snapshot_path actually exists and is non-empty."""
        _make_fake_opencode(fake_bin)
        sink = InMemoryEventSink()
        RunController(
            root=repo, task="t", platform="opencode",
            profile_name="safe", allow_dirty=False, no_index=True,
            sink=sink, session_id="snap-ctx-003",
        ).execute()

        snapshot_path = Path(_get_ctx_written(sink).data["snapshot_path"])
        assert snapshot_path.exists(), f"snapshot not found: {snapshot_path}"
        assert snapshot_path.stat().st_size > 0

    def test_context_snapshot_path_is_under_run_dir(self, repo: Path, fake_bin: Path):
        """snapshot_path in EVENT_CONTEXT is inside .vibecode/runs/<session_id>/."""
        _make_fake_opencode(fake_bin)
        sink = InMemoryEventSink()
        RunController(
            root=repo, task="t", platform="opencode",
            profile_name="safe", allow_dirty=False, no_index=True,
            sink=sink, session_id="snap-rundir-001",
        ).execute()

        run_dir = repo / ".vibecode" / "runs" / "snap-rundir-001"
        snapshot_path = Path(_get_ctx_written(sink).data["snapshot_path"])
        assert str(snapshot_path).startswith(str(run_dir))

    def test_context_event_has_positive_size_bytes(self, repo: Path, fake_bin: Path):
        """EVENT_CONTEXT written event has size_bytes > 0."""
        _make_fake_opencode(fake_bin)
        sink = InMemoryEventSink()
        RunController(
            root=repo, task="t", platform="opencode",
            profile_name="safe", allow_dirty=False, no_index=True,
            sink=sink,
        ).execute()

        evt = _get_ctx_written(sink)
        assert "size_bytes" in evt.data
        assert isinstance(evt.data["size_bytes"], int)
        assert evt.data["size_bytes"] > 0

    def test_context_event_has_task_summary(self, repo: Path, fake_bin: Path):
        """task_summary in EVENT_CONTEXT matches the controller's task."""
        _make_fake_opencode(fake_bin)
        sink = InMemoryEventSink()
        RunController(
            root=repo, task="fix the auth module", platform="opencode",
            profile_name="safe", allow_dirty=False, no_index=True,
            sink=sink,
        ).execute()

        evt = _get_ctx_written(sink)
        assert evt.data.get("task_summary") == "fix the auth module"

    def test_context_event_task_summary_is_truncated_for_long_tasks(self, repo: Path, fake_bin: Path):
        """task_summary is at most 200 characters even for very long task strings."""
        _make_fake_opencode(fake_bin)
        long_task = "x" * 300
        sink = InMemoryEventSink()
        RunController(
            root=repo, task=long_task, platform="opencode",
            profile_name="safe", allow_dirty=False, no_index=True,
            sink=sink,
        ).execute()

        evt = _get_ctx_written(sink)
        assert len(evt.data.get("task_summary", "")) <= 200

    def test_context_event_has_sections_list(self, repo: Path, fake_bin: Path):
        """sections in EVENT_CONTEXT is a non-empty list of heading strings."""
        _make_fake_opencode(fake_bin)
        sink = InMemoryEventSink()
        RunController(
            root=repo, task="t", platform="opencode",
            profile_name="safe", allow_dirty=False, no_index=True,
            sink=sink,
        ).execute()

        evt = _get_ctx_written(sink)
        assert "sections" in evt.data
        assert isinstance(evt.data["sections"], list)
        assert len(evt.data["sections"]) > 0
        assert all(isinstance(s, str) for s in evt.data["sections"])

    def test_context_sections_match_context_pack_headings(self, repo: Path, fake_bin: Path):
        """sections in EVENT_CONTEXT matches ## headings in the written context pack file."""
        _make_fake_opencode(fake_bin)
        sink = InMemoryEventSink()
        RunController(
            root=repo, task="t", platform="opencode",
            profile_name="safe", allow_dirty=False, no_index=True,
            sink=sink,
        ).execute()

        evt = _get_ctx_written(sink)
        context_pack_path = Path(evt.data["path"])
        expected_sections = [
            line[3:].strip()
            for line in context_pack_path.read_text(encoding="utf-8").splitlines()
            if line.startswith("## ")
        ]
        assert evt.data["sections"] == expected_sections

    def test_prompt_event_has_snapshot_path(self, repo: Path, fake_bin: Path):
        """EVENT_PROMPT written event includes a non-None snapshot_path."""
        _make_fake_opencode(fake_bin)
        sink = InMemoryEventSink()
        RunController(
            root=repo, task="t", platform="opencode",
            profile_name="safe", allow_dirty=False, no_index=True,
            sink=sink, session_id="snap-prompt-001",
        ).execute()

        evt = _get_prompt_written(sink)
        assert "snapshot_path" in evt.data
        assert evt.data["snapshot_path"] is not None

    def test_prompt_event_snapshot_path_contains_session_id(self, repo: Path, fake_bin: Path):
        """snapshot_path in EVENT_PROMPT is inside the session run directory."""
        _make_fake_opencode(fake_bin)
        sink = InMemoryEventSink()
        RunController(
            root=repo, task="t", platform="opencode",
            profile_name="safe", allow_dirty=False, no_index=True,
            sink=sink, session_id="snap-prompt-002",
        ).execute()

        evt = _get_prompt_written(sink)
        assert "snap-prompt-002" in evt.data["snapshot_path"]

    def test_prompt_event_has_platform_and_profile(self, repo: Path, fake_bin: Path):
        """EVENT_PROMPT written event includes platform and profile fields."""
        _make_fake_opencode(fake_bin)
        sink = InMemoryEventSink()
        RunController(
            root=repo, task="t", platform="opencode",
            profile_name="safe", allow_dirty=False, no_index=True,
            sink=sink,
        ).execute()

        evt = _get_prompt_written(sink)
        assert evt.data.get("platform") == "opencode"
        assert evt.data.get("profile") == "safe"

    def test_prompt_event_has_size_bytes(self, repo: Path, fake_bin: Path):
        """EVENT_PROMPT written event has size_bytes as an integer."""
        _make_fake_opencode(fake_bin)
        sink = InMemoryEventSink()
        RunController(
            root=repo, task="t", platform="opencode",
            profile_name="safe", allow_dirty=False, no_index=True,
            sink=sink,
        ).execute()

        evt = _get_prompt_written(sink)
        assert "size_bytes" in evt.data
        assert isinstance(evt.data["size_bytes"], int)

    def test_context_snapshots_are_session_specific(self, repo: Path, fake_bin: Path):
        """Two runs produce independent context pack snapshot paths."""
        _make_fake_opencode(fake_bin)

        sink_a = InMemoryEventSink()
        sink_b = InMemoryEventSink()

        RunController(
            root=repo, task="t", platform="opencode",
            profile_name="safe", allow_dirty=False, no_index=True,
            sink=sink_a, session_id="snap-sess-A",
        ).execute()
        RunController(
            root=repo, task="t", platform="opencode",
            profile_name="safe", allow_dirty=False, no_index=True,
            sink=sink_b, session_id="snap-sess-B",
        ).execute()

        path_a = _get_ctx_written(sink_a).data["snapshot_path"]
        path_b = _get_ctx_written(sink_b).data["snapshot_path"]
        assert path_a != path_b
        assert "snap-sess-A" in path_a
        assert "snap-sess-B" in path_b

    def test_prompt_snapshots_are_session_specific(self, repo: Path, fake_bin: Path):
        """Two runs produce independent prompt snapshot paths."""
        _make_fake_opencode(fake_bin)

        sink_a = InMemoryEventSink()
        sink_b = InMemoryEventSink()

        RunController(
            root=repo, task="t", platform="opencode",
            profile_name="safe", allow_dirty=False, no_index=True,
            sink=sink_a, session_id="snap-prompt-sess-A",
        ).execute()
        RunController(
            root=repo, task="t", platform="opencode",
            profile_name="safe", allow_dirty=False, no_index=True,
            sink=sink_b, session_id="snap-prompt-sess-B",
        ).execute()

        path_a = _get_prompt_written(sink_a).data["snapshot_path"]
        path_b = _get_prompt_written(sink_b).data["snapshot_path"]
        assert path_a != path_b
        assert "snap-prompt-sess-A" in path_a
        assert "snap-prompt-sess-B" in path_b

    def test_context_event_data_has_no_raw_body_text(self, repo: Path, fake_bin: Path):
        """EVENT_CONTEXT data must not embed raw context pack body text."""
        _make_fake_opencode(fake_bin)
        sink = InMemoryEventSink()
        RunController(
            root=repo, task="snapshot body check", platform="opencode",
            profile_name="safe", allow_dirty=False, no_index=True,
            sink=sink, session_id="body-ctx-001",
        ).execute()

        evt = _get_ctx_written(sink)
        data_json = json.dumps(evt.data, sort_keys=True)

        context_pack_path = Path(evt.data["path"])
        body = context_pack_path.read_text(encoding="utf-8") if context_pack_path.exists() else ""

        assert "body" not in evt.data
        for key in evt.data:
            assert isinstance(evt.data[key], (str, int, list, type(None))), \
                f"data key '{key}' has non-trivial type {type(evt.data[key])}"

        if len(body) > 100:
            assert body[:100] not in data_json, "raw context pack start found in event data"
            assert body[-100:] not in data_json, "raw context pack end found in event data"

    def test_prompt_event_data_has_no_raw_body_text(self, repo: Path, fake_bin: Path):
        """EVENT_PROMPT data must not embed raw prompt body text."""
        _make_fake_opencode(fake_bin)
        sink = InMemoryEventSink()
        RunController(
            root=repo, task="prompt body check", platform="opencode",
            profile_name="safe", allow_dirty=False, no_index=True,
            sink=sink, session_id="body-prompt-001",
        ).execute()

        evt = _get_prompt_written(sink)
        data_json = json.dumps(evt.data, sort_keys=True)

        assert "body" not in evt.data
        assert "content" not in evt.data
        assert "prompt_text" not in evt.data
        assert "prompt_raw" not in evt.data
        for key in evt.data:
            assert isinstance(evt.data[key], (str, int, list, type(None))), \
                f"data key '{key}' has non-trivial type {type(evt.data[key])}"

        prompt_path = Path(evt.data["path"]) if evt.data.get("path") else None
        if prompt_path and prompt_path.exists():
            body = prompt_path.read_text(encoding="utf-8")
            if len(body) > 100:
                assert body[:100] not in data_json, "raw prompt start found in event data"
                assert body[-100:] not in data_json, "raw prompt end found in event data"

    def test_fake_opencode_stdin_matches_prompt_snapshot(self, repo: Path, fake_bin: Path):
        """Fake OpenCode stdin exactly matches the prompt snapshot on disk."""
        stdin_capture = fake_bin / "stdin_captured.txt"
        _make_fake_opencode(fake_bin, stdin_path=str(stdin_capture))
        sink = InMemoryEventSink()
        RunController(
            root=repo, task="stdin match test", platform="opencode",
            profile_name="safe", allow_dirty=False, no_index=True,
            sink=sink, session_id="stdin-match-001",
        ).execute()

        prompt_evt = _get_prompt_written(sink)
        snapshot_path = Path(prompt_evt.data["snapshot_path"])
        assert snapshot_path.exists(), f"prompt snapshot missing: {snapshot_path}"

        snapshot_text = snapshot_path.read_text(encoding="utf-8")
        assert stdin_capture.exists(), "fake opencode did not write stdin"
        stdin_text = stdin_capture.read_text(encoding="utf-8")

        assert stdin_text == snapshot_text, \
            f"stdin ({len(stdin_text)} chars) != snapshot ({len(snapshot_text)} chars)"
