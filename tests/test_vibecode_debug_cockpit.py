from __future__ import annotations

import json
from pathlib import Path

from vibecode.main_app import SessionArtifactWatcher, TuiEventLog, render_right_debug_cockpit


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_tui_event_log_is_bounded_and_truncates_messages() -> None:
    event_log = TuiEventLog(max_entries=3, max_message_chars=10)
    event_log.add("0123456789abcdef", category="refresh", level="info")
    event_log.add("second", category="context", level="info")
    event_log.add("third", category="run", level="warning")
    event_log.add("fourth", category="validation", level="error")

    latest = event_log.latest(10)
    assert len(latest) == 3
    assert latest[0].message == "second"
    assert latest[-1].message == "fourth"
    assert latest[0].category == "context"
    assert "…" in latest[0].message or latest[0].message == "second"


def test_session_artifact_watcher_handles_missing_files(tmp_path: Path) -> None:
    watcher = SessionArtifactWatcher(tmp_path)
    snapshot = watcher.snapshot()

    labels = {item["label"] for item in snapshot["artifacts"]}
    assert "events.jsonl" in labels
    assert "summary.json" in labels
    assert "guard report" in labels
    assert any("No run session selected yet." in w for w in snapshot["warnings"])
    assert any(not item["exists"] for item in snapshot["artifacts"])


def test_session_artifact_watcher_reads_existing_artifacts(tmp_path: Path) -> None:
    run_dir = tmp_path / ".vibecode" / "runs" / "sess-001"
    _write(run_dir / "context_pack.md", "# Context\n\nhello\n")
    _write(run_dir / "opencode_prompt.md", "prompt")
    _write(run_dir / "events.jsonl", '{"type":"run.lifecycle"}\n')
    _write(run_dir / "summary.json", json.dumps({"overall_status": "success"}))
    _write(run_dir / "agent_stdout.log", "ok\n")
    _write(run_dir / "agent_stderr.log", "warn\n")
    _write(run_dir / "guard_report.json", "{}")
    _write(run_dir / "checks_report.json", "{}")
    _write(run_dir / "handoff_report.json", "{}")

    watcher = SessionArtifactWatcher(tmp_path)
    snapshot = watcher.snapshot("sess-001")
    by_label = {item["label"]: item for item in snapshot["artifacts"]}

    assert snapshot["session_id"] == "sess-001"
    assert by_label["events.jsonl"]["exists"] is True
    assert by_label["summary.json"]["exists"] is True
    assert by_label["agent stderr.log"]["path"].endswith("agent_stderr.log")
    assert by_label["guard report"]["path"].endswith("guard_report.json")
    assert "hello" in snapshot["context_summary"]


def test_session_artifact_watcher_truncates_large_logs(tmp_path: Path) -> None:
    run_dir = tmp_path / ".vibecode" / "runs" / "sess-002"
    _write(run_dir / "context_pack.md", "context")
    _write(run_dir / "opencode_prompt.md", "prompt")
    _write(run_dir / "events.jsonl", "x\n" * 2000)
    _write(run_dir / "summary.json", "{}")
    _write(run_dir / "agent_stderr.log", "ERR\n" * 3000)

    watcher = SessionArtifactWatcher(tmp_path)
    snapshot = watcher.snapshot("sess-002")

    assert snapshot["events_truncated"] is True
    assert snapshot["stderr_truncated"] is True
    assert "ERR" in snapshot["stderr_summary"]


def test_session_artifact_watcher_uses_latest_existing_run(tmp_path: Path) -> None:
    run_old = tmp_path / ".vibecode" / "runs" / "20260101T000000000000Z"
    run_new = tmp_path / ".vibecode" / "runs" / "20260102T000000000000Z"
    _write(run_old / "summary.json", "{}")
    _write(run_new / "summary.json", "{}")
    _write(run_new / "context_pack.md", "ctx")
    _write(run_new / "opencode_prompt.md", "prompt")

    watcher = SessionArtifactWatcher(tmp_path)
    snapshot = watcher.snapshot()

    assert snapshot["session_id"] == "20260102T000000000000Z"


def test_render_right_debug_cockpit_includes_expected_debug_sections() -> None:
    event_log = TuiEventLog()
    event_log.add("Refresh complete", category="refresh", level="info")
    event_log.add("Context ready", category="context", level="info")
    event_log.add("Run completed", category="run", level="info")
    event_log.add("Checks failed", category="validation", level="warning")

    snapshot = {
        "session_id": "sess-xyz",
        "run_dir": "C:\\repo\\.vibecode\\runs\\sess-xyz",
        "artifacts": [
            {"label": "context pack", "path": "C:\\repo\\.vibecode\\runs\\sess-xyz\\context_pack.md", "exists": True},
            {"label": "events.jsonl", "path": "C:\\repo\\.vibecode\\runs\\sess-xyz\\events.jsonl", "exists": True},
            {"label": "summary.json", "path": "C:\\repo\\.vibecode\\runs\\sess-xyz\\summary.json", "exists": True},
            {"label": "guard report", "path": "C:\\repo\\.vibecode\\runs\\sess-xyz\\guard_report.json", "exists": False},
            {"label": "checks report", "path": "C:\\repo\\.vibecode\\runs\\sess-xyz\\checks_report.json", "exists": False},
            {"label": "handoff report", "path": "C:\\repo\\.vibecode\\runs\\sess-xyz\\handoff_report.json", "exists": False},
        ],
        "context_summary": "## Current task\nFix bug",
        "events_summary": "event line",
        "stderr_summary": "stderr line",
        "context_truncated": True,
        "events_truncated": True,
        "stderr_truncated": True,
        "warnings": ["Missing artifacts: guard report"],
        "errors": [],
    }
    text = render_right_debug_cockpit(
        snapshot=snapshot,
        event_log=event_log,
        refresh_report={"validation_status": "ok", "generated_artifacts": ["a", "b"]},
        context_preview={"task": "Fix bug"},
        run_result={"overall_status": "success", "exit_code": 0, "session_id": "sess-xyz"},
        guard_result={"passed": False, "errors": 1, "warnings": 0},
        check_result={"status": "fail", "failed": 2},
        handoff_result={"passed": True, "issues": []},
        next_action="Run [G] and [T].",
    )

    assert "Session: sess-xyz" in text
    assert "context pack" in text
    assert "events.jsonl" in text
    assert "guard report" in text
    assert "Latest Vibecode events" in text
    assert "[truncated]" in text
    assert "Next recommended action" in text
