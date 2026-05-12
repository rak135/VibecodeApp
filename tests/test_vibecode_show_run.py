"""Tests for vibecode show-run / runs list command (vibecode.show_run)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from vibecode.cli import main
from vibecode.events import (
    EventLevel,
    VibecodeEvent,
    create_event,
)
from vibecode.show_run import (
    format_run_list,
    format_run_show,
    list_runs,
    load_run_events,
    load_run_summary,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _make_run_dir(tmp_path: Path, session_id: str) -> Path:
    run_dir = tmp_path / ".vibecode" / "runs" / session_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _make_summary(session_id: str, **overrides) -> dict:
    base = {
        "$schema": "vibecode/run-summary/v1",
        "session_id": session_id,
        "started_at": "2026-01-01T10:00:00+00:00",
        "finished_at": "2026-01-01T10:05:00+00:00",
        "platform": "opencode",
        "profile": "safe",
        "task": "implement feature X",
        "dirty": False,
        "index_fresh": True,
        "command": "opencode",
        "exit_code": 0,
        "agent_status": "success",
        "guard_mode": "advisory",
        "overall_status": "success",
        "stdout": "",
        "stderr": "",
        "guard": {
            "passed": True,
            "findings": [],
            "counts_by_severity": {"error": 0, "warning": 0, "info": 0},
            "counts_by_category": {},
        },
        "checks": {"total": 2, "passed": 2, "failed": 0, "has_required_failures": False},
        "handoff": {"status": "ok", "issues": []},
    }
    base.update(overrides)
    return base


def _write_summary(run_dir: Path, summary: dict) -> Path:
    return _write(run_dir / "summary.json", json.dumps(summary, indent=2))


def _make_event(session_id: str, message: str, type_: str = "run.lifecycle") -> VibecodeEvent:
    return create_event(session_id, type_, EventLevel.INFO, message)


def _write_events_jsonl(run_dir: Path, events: list[VibecodeEvent]) -> Path:
    lines = "\n".join(e.as_json() for e in events)
    return _write(run_dir / "events.jsonl", lines + "\n")


# ---------------------------------------------------------------------------
# load_run_summary
# ---------------------------------------------------------------------------


class TestLoadRunSummary:
    def test_loads_summary_json(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, "sess1")
        summary = _make_summary("sess1")
        _write_summary(run_dir, summary)

        result, error = load_run_summary(run_dir)

        assert result is not None
        assert error is None
        assert result["session_id"] == "sess1"
        assert result["task"] == "implement feature X"

    def test_falls_back_to_metadata_json(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, "sess2")
        meta = {"session_id": "sess2", "task": "meta task"}
        _write(run_dir / "metadata.json", json.dumps(meta))

        result, error = load_run_summary(run_dir)

        assert result is not None
        assert error is None
        assert result["task"] == "meta task"

    def test_returns_none_when_no_file(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, "empty")

        result, error = load_run_summary(run_dir)

        assert result is None
        assert error == "missing"

    def test_returns_none_for_corrupt_json(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, "corrupt")
        _write(run_dir / "summary.json", "{not valid json")

        result, error = load_run_summary(run_dir)

        assert result is None
        assert error == "summary.json is corrupt"

    def test_prefers_summary_json_over_metadata(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, "both")
        _write_summary(run_dir, _make_summary("both", task="from summary"))
        _write(run_dir / "metadata.json", json.dumps({"task": "from metadata"}))

        result, _ = load_run_summary(run_dir)

        assert result["task"] == "from summary"


# ---------------------------------------------------------------------------
# load_run_events
# ---------------------------------------------------------------------------


class TestLoadRunEvents:
    def test_parses_valid_jsonl(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, "evts")
        ev1 = _make_event("evts", "Run started")
        ev2 = _make_event("evts", "Run finished")
        _write_events_jsonl(run_dir, [ev1, ev2])

        events, errors, exists = load_run_events(run_dir / "events.jsonl")

        assert len(events) == 2
        assert errors == []
        assert exists is True
        assert events[0].message == "Run started"
        assert events[1].message == "Run finished"

    def test_returns_empty_when_file_missing(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, "noevts")

        events, errors, exists = load_run_events(run_dir / "events.jsonl")

        assert events == []
        assert errors == []
        assert exists is False

    def test_skips_corrupt_lines_gracefully(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, "corrupt_lines")
        ev = _make_event("corrupt_lines", "Good event")
        content = ev.as_json() + "\n{bad json\n" + ev.as_json() + "\n"
        _write(run_dir / "events.jsonl", content)

        events, errors, exists = load_run_events(run_dir / "events.jsonl")

        assert len(events) == 2
        assert len(errors) == 1
        assert exists is True
        assert "2" in errors[0]  # line number

    def test_skips_blank_lines(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, "blanks")
        ev = _make_event("blanks", "Only event")
        _write(run_dir / "events.jsonl", "\n" + ev.as_json() + "\n\n")

        events, errors, exists = load_run_events(run_dir / "events.jsonl")

        assert len(events) == 1
        assert errors == []
        assert exists is True

    def test_event_fields_preserved(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, "fields")
        ts = datetime(2026, 5, 12, 10, 0, 0, tzinfo=timezone.utc)
        ev = create_event("fields", "run.mcp", EventLevel.WARNING, "Tool failed", timestamp=ts)
        _write_events_jsonl(run_dir, [ev])

        events, _, exists = load_run_events(run_dir / "events.jsonl")

        assert exists is True
        assert events[0].level == EventLevel.WARNING
        assert events[0].type == "run.mcp"
        assert events[0].timestamp == ts


# ---------------------------------------------------------------------------
# list_runs
# ---------------------------------------------------------------------------


class TestListRuns:
    def test_returns_empty_list_for_missing_dir(self, tmp_path: Path):
        runs_dir = tmp_path / ".vibecode" / "runs"

        result = list_runs(runs_dir)

        assert result == []

    def test_lists_runs_sorted_most_recent_first(self, tmp_path: Path):
        runs_dir = tmp_path / ".vibecode" / "runs"
        for sid in ("20260101T100000Z", "20260103T100000Z", "20260102T100000Z"):
            run_dir = runs_dir / sid
            run_dir.mkdir(parents=True, exist_ok=True)
            _write_summary(run_dir, _make_summary(sid))

        result = list_runs(runs_dir)
        ids = [r["session_id"] for r in result]

        assert ids == ["20260103T100000Z", "20260102T100000Z", "20260101T100000Z"]

    def test_includes_summary_fields(self, tmp_path: Path):
        runs_dir = tmp_path / ".vibecode" / "runs"
        run_dir = runs_dir / "sess_a"
        run_dir.mkdir(parents=True, exist_ok=True)
        _write_summary(run_dir, _make_summary("sess_a", task="fix bug"))

        result = list_runs(runs_dir)

        assert len(result) == 1
        assert result[0]["task"] == "fix bug"
        assert result[0]["overall_status"] == "success"

    def test_handles_run_dir_without_summary(self, tmp_path: Path):
        runs_dir = tmp_path / ".vibecode" / "runs"
        (runs_dir / "no_summary").mkdir(parents=True, exist_ok=True)

        result = list_runs(runs_dir)

        assert len(result) == 1
        assert result[0]["session_id"] == "no_summary"
        assert "task" not in result[0]

    def test_ignores_files_in_runs_dir(self, tmp_path: Path):
        runs_dir = tmp_path / ".vibecode" / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        _write(runs_dir / "stray.txt", "oops")
        (runs_dir / "real_run").mkdir()

        result = list_runs(runs_dir)

        assert len(result) == 1
        assert result[0]["session_id"] == "real_run"


# ---------------------------------------------------------------------------
# format_run_list / format_run_show
# ---------------------------------------------------------------------------


class TestFormatRunList:
    def test_no_runs(self):
        assert format_run_list([]) == "No runs found."

    def test_shows_session_ids(self):
        runs = [
            {"session_id": "sess1", "overall_status": "success", "platform": "opencode"},
            {"session_id": "sess2", "overall_status": "failure", "platform": "opencode"},
        ]
        output = format_run_list(runs)
        assert "sess1" in output
        assert "sess2" in output

    def test_shows_task_snippet(self):
        runs = [{"session_id": "s", "task": "implement something cool", "platform": "opencode"}]
        output = format_run_list(runs)
        assert "implement something cool" in output

    def test_truncates_long_task(self):
        long_task = "a" * 100
        runs = [{"session_id": "s", "task": long_task, "platform": "opencode"}]
        output = format_run_list(runs)
        assert "..." in output


class TestFormatRunShow:
    def test_shows_core_fields(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, "show_test")
        summary = _make_summary("show_test", task="do the thing")

        output = format_run_show(summary, run_dir)

        assert "show_test" in output
        assert "do the thing" in output
        assert "opencode" in output
        assert "safe" in output

    def test_shows_guard_counts(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, "guard_test")
        summary = _make_summary(
            "guard_test",
            guard={
                "passed": False,
                "findings": [],
                "counts_by_severity": {"error": 2, "warning": 1, "info": 0},
            },
        )

        output = format_run_show(summary, run_dir)

        assert "errors=2" in output
        assert "warnings=1" in output

    def test_shows_checks_status(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, "checks_test")
        summary = _make_summary(
            "checks_test",
            checks={"total": 3, "passed": 2, "failed": 1, "has_required_failures": True},
        )

        output = format_run_show(summary, run_dir)

        assert "2/3 passed" in output
        assert "1 failed" in output

    def test_lists_existing_artifacts(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, "artifacts_test")
        _write(run_dir / "summary.json", "{}")
        _write(run_dir / "events.jsonl", "")
        summary = _make_summary("artifacts_test")

        output = format_run_show(summary, run_dir)

        assert "summary" in output
        assert "events" in output

    def test_shows_no_artifacts_label_when_empty(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, "empty_artifacts")
        summary = _make_summary("empty_artifacts")

        output = format_run_show(summary, run_dir)

        assert "Artifacts:" not in output

    def test_replays_events_when_requested(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, "ev_replay")
        summary = _make_summary("ev_replay")
        ev = create_event("ev_replay", "run.lifecycle", EventLevel.INFO, "Run started")
        events = [ev]

        output = format_run_show(summary, run_dir, events=events, show_events=True)

        assert "Run started" in output
        assert "Events (1)" in output

    def test_no_events_section_when_not_requested(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, "no_events_section")
        summary = _make_summary("no_events_section")
        ev = create_event("no_events_section", "run.lifecycle", EventLevel.INFO, "msg")
        events = [ev]

        output = format_run_show(summary, run_dir, events=events, show_events=False)

        assert "Events" not in output

    def test_handles_missing_guard_gracefully(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, "noguard")
        summary = _make_summary("noguard")
        summary.pop("guard", None)

        output = format_run_show(summary, run_dir)

        assert "not recorded" in output

    def test_event_parse_errors_shown(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, "ev_err")
        summary = _make_summary("ev_err")
        ev = create_event("ev_err", "run.lifecycle", EventLevel.INFO, "ok event")
        events = [ev]
        errors = ["Line 2: invalid JSON"]

        output = format_run_show(
            summary, run_dir, events=events, event_errors=errors, show_events=True
        )

        assert "parse error" in output
        assert "Line 2" in output


# ---------------------------------------------------------------------------
# CLI integration — vibecode runs list
# ---------------------------------------------------------------------------


class TestRunsListCLI:
    def test_list_no_runs(self, tmp_path: Path, capsys):
        rc = main(["runs", "list", "--repo", str(tmp_path)])
        out = capsys.readouterr().out
        assert rc == 0
        assert "No runs found" in out

    def test_list_shows_sessions(self, tmp_path: Path, capsys):
        runs_dir = tmp_path / ".vibecode" / "runs"
        for sid in ("20260101T100000Z", "20260102T100000Z"):
            run_dir = runs_dir / sid
            run_dir.mkdir(parents=True, exist_ok=True)
            _write_summary(run_dir, _make_summary(sid))

        rc = main(["runs", "list", "--repo", str(tmp_path)])
        out = capsys.readouterr().out

        assert rc == 0
        assert "20260101T100000Z" in out
        assert "20260102T100000Z" in out

    def test_list_order_most_recent_first(self, tmp_path: Path, capsys):
        runs_dir = tmp_path / ".vibecode" / "runs"
        for sid in ("20260101T000000Z", "20260103T000000Z", "20260102T000000Z"):
            (runs_dir / sid).mkdir(parents=True, exist_ok=True)

        main(["runs", "list", "--repo", str(tmp_path)])
        out = capsys.readouterr().out

        pos1 = out.index("20260103T000000Z")
        pos2 = out.index("20260102T000000Z")
        pos3 = out.index("20260101T000000Z")
        assert pos1 < pos2 < pos3


# ---------------------------------------------------------------------------
# CLI integration — vibecode runs show
# ---------------------------------------------------------------------------


class TestRunsShowCLI:
    def test_show_existing_run(self, tmp_path: Path, capsys):
        sid = "20260101T120000Z"
        run_dir = tmp_path / ".vibecode" / "runs" / sid
        run_dir.mkdir(parents=True, exist_ok=True)
        _write_summary(run_dir, _make_summary(sid, task="fix the bug"))

        rc = main(["runs", "show", sid, "--repo", str(tmp_path)])
        out = capsys.readouterr().out

        assert rc == 0
        assert sid in out
        assert "fix the bug" in out

    def test_show_missing_run_returns_1(self, tmp_path: Path, capsys):
        rc = main(["runs", "show", "nonexistent-session", "--repo", str(tmp_path)])
        err = capsys.readouterr().err

        assert rc == 1
        assert "not found" in err

    def test_show_missing_run_suggests_available(self, tmp_path: Path, capsys):
        runs_dir = tmp_path / ".vibecode" / "runs"
        (runs_dir / "20260101T000000Z").mkdir(parents=True, exist_ok=True)

        main(["runs", "show", "bad_id", "--repo", str(tmp_path)])
        err = capsys.readouterr().err

        assert "20260101T000000Z" in err

    def test_show_with_events_flag(self, tmp_path: Path, capsys):
        sid = "20260101T130000Z"
        run_dir = tmp_path / ".vibecode" / "runs" / sid
        run_dir.mkdir(parents=True, exist_ok=True)
        _write_summary(run_dir, _make_summary(sid))
        ev = create_event(sid, "run.lifecycle", EventLevel.INFO, "Hello events")
        _write_events_jsonl(run_dir, [ev])

        rc = main(["runs", "show", sid, "--repo", str(tmp_path), "--events"])
        out = capsys.readouterr().out

        assert rc == 0
        assert "Hello events" in out
        assert "Events (1)" in out

    def test_show_corrupt_events_jsonl_graceful(self, tmp_path: Path, capsys):
        sid = "20260101T140000Z"
        run_dir = tmp_path / ".vibecode" / "runs" / sid
        run_dir.mkdir(parents=True, exist_ok=True)
        _write_summary(run_dir, _make_summary(sid))
        _write(run_dir / "events.jsonl", "{totally broken\n")

        rc = main(["runs", "show", sid, "--repo", str(tmp_path), "--events"])
        # Should not crash; exit code 0 because summary loaded fine
        assert rc == 0

    def test_show_missing_events_jsonl_graceful(self, tmp_path: Path, capsys):
        sid = "20260101T150000Z"
        run_dir = tmp_path / ".vibecode" / "runs" / sid
        run_dir.mkdir(parents=True, exist_ok=True)
        _write_summary(run_dir, _make_summary(sid))
        # no events.jsonl written

        rc = main(["runs", "show", sid, "--repo", str(tmp_path), "--events"])
        captured = capsys.readouterr()

        assert rc == 0
        assert "events.jsonl not found" in captured.err

    def test_show_run_no_summary_shows_artifacts(self, tmp_path: Path, capsys):
        sid = "20260101T160000Z"
        run_dir = tmp_path / ".vibecode" / "runs" / sid
        run_dir.mkdir(parents=True, exist_ok=True)
        _write(run_dir / "agent_stdout.log", "some output\n")

        rc = main(["runs", "show", sid, "--repo", str(tmp_path)])
        out = capsys.readouterr().out

        assert rc == 0
        assert "agent stdout" in out

    def test_show_run_empty_dir_returns_1(self, tmp_path: Path, capsys):
        sid = "20260101T170000Z"
        (tmp_path / ".vibecode" / "runs" / sid).mkdir(parents=True, exist_ok=True)

        rc = main(["runs", "show", sid, "--repo", str(tmp_path)])
        err = capsys.readouterr().err

        assert rc == 1
        assert "no recognised artifacts" in err

    def test_show_error_message_is_clear(self, tmp_path: Path, capsys):
        """Missing run id error must be clear (required by task spec)."""
        rc = main(["runs", "show", "my-bad-session-id", "--repo", str(tmp_path)])
        err = capsys.readouterr().err

        assert rc == 1
        assert "my-bad-session-id" in err
        assert "not found" in err

    def test_show_corrupt_summary_reports_corrupt(self, tmp_path: Path, capsys):
        """CLI reports corrupt summary.json as corrupt, not missing."""
        sid = "20260101T180000Z"
        run_dir = tmp_path / ".vibecode" / "runs" / sid
        run_dir.mkdir(parents=True, exist_ok=True)
        _write(run_dir / "summary.json", "{not valid json")
        _write(run_dir / "agent_stdout.log", "some output\n")

        rc = main(["runs", "show", sid, "--repo", str(tmp_path)])
        out = capsys.readouterr().out

        assert rc == 0
        assert "corrupt" in out
        assert "agent stdout" in out

    def test_show_corrupt_metadata_reports_corrupt(self, tmp_path: Path, capsys):
        """CLI reports corrupt metadata.json as corrupt."""
        sid = "20260101T190000Z"
        run_dir = tmp_path / ".vibecode" / "runs" / sid
        run_dir.mkdir(parents=True, exist_ok=True)
        _write(run_dir / "metadata.json", "{not valid")
        _write(run_dir / "agent_stdout.log", "out\n")

        rc = main(["runs", "show", sid, "--repo", str(tmp_path)])
        out = capsys.readouterr().out

        assert rc == 0
        assert "corrupt" in out


# ---------------------------------------------------------------------------
# Show output: findings sections
# ---------------------------------------------------------------------------


class TestFormatRunShowFindings:
    def test_guard_findings_shown_when_not_passed(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, "gf")
        summary = _make_summary(
            "gf",
            guard={
                "passed": False,
                "findings": [
                    {
                        "rule_id": "test-1",
                        "path": "src/foo.py",
                        "severity": "error",
                        "title": "Protected file edited",
                        "message": "src/foo.py is protected",
                    },
                    {
                        "rule_id": "test-2",
                        "path": "tests/bar.py",
                        "severity": "warning",
                        "title": "Test missing",
                        "message": "No test for src/bar.py",
                    },
                ],
                "counts_by_severity": {"error": 1, "warning": 1, "info": 0},
            },
        )

        output = format_run_show(summary, run_dir)

        assert "Guard findings:" in output
        assert "Protected file edited" in output
        assert "src/foo.py" in output
        assert "Test missing" in output
        assert "tests/bar.py" in output

    def test_no_guard_findings_when_passed(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, "gf_ok")
        summary = _make_summary("gf_ok")

        output = format_run_show(summary, run_dir)

        assert "Guard findings:" not in output

    def test_failed_checks_shown(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, "fc")
        summary = _make_summary(
            "fc",
            checks={
                "total": 3,
                "passed": 1,
                "failed": 2,
                "has_required_failures": True,
                "checks": [
                    {"name": "unit tests", "command": "pytest", "exit_code": 1, "status": "fail"},
                    {"name": "lint", "command": "ruff", "exit_code": 1, "status": "fail"},
                    {"name": "format", "command": "black", "exit_code": 0, "status": "pass"},
                ],
            },
        )

        output = format_run_show(summary, run_dir)

        assert "Failed checks:" in output
        assert "unit tests" in output
        assert "exit 1" in output
        assert "lint" in output

    def test_no_failed_checks_when_all_pass(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, "fc_ok")
        summary = _make_summary(
            "fc_ok",
            checks={
                "total": 2,
                "passed": 2,
                "failed": 0,
                "has_required_failures": False,
                "checks": [
                    {"name": "unit tests", "command": "pytest", "exit_code": 0, "status": "pass"},
                ],
            },
        )

        output = format_run_show(summary, run_dir)

        assert "Failed checks:" not in output

    def test_handoff_issues_shown(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, "hi")
        summary = _make_summary(
            "hi",
            handoff={
                "status": "error",
                "issues": [
                    {"file": "NOW.md", "message": "Missing required section"},
                    {"file": "NEXT.md", "message": "File is empty"},
                ],
            },
        )

        output = format_run_show(summary, run_dir)

        assert "Handoff issues:" in output
        assert "NOW.md" in output
        assert "Missing required section" in output
        assert "NEXT.md" in output
        assert "File is empty" in output

    def test_no_handoff_issues_when_ok(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, "hi_ok")
        summary = _make_summary("hi_ok")

        output = format_run_show(summary, run_dir)

        assert "Handoff issues:" not in output

    def test_top_level_error_shown(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, "err")
        summary = _make_summary("err", error="Something went wrong during execution")

        output = format_run_show(summary, run_dir)

        assert "Error:" in output
        assert "Something went wrong during execution" in output

    def test_no_error_when_not_present(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, "noerr")
        summary = _make_summary("noerr")

        output = format_run_show(summary, run_dir)

        assert "Error:" not in output

    def test_show_handoff_passed_based_on_status(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, "hs")
        summary = _make_summary("hs", handoff={"status": "ok", "issues": []})

        output = format_run_show(summary, run_dir)

        assert "Handoff      : passed" in output
