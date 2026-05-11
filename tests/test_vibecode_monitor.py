"""Tests for the vibecode monitor command and TUI event formatting.

Covers:
- Pure formatting helpers (route_event, format_agent_line, format_vibecode_line)
- TUIEventSink event bridge
- MonitorApp import and required symbols
- CLI parser registration
- cmd_monitor smoke path (MonitorApp.run() mocked)
- CLI dispatch smoke path
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from vibecode.events import (
    EVENT_AGENT_PROCESS,
    EVENT_CHECK,
    EVENT_GUARD,
    EVENT_HANDOFF,
    EVENT_RUN_LIFECYCLE,
    EVENT_SUMMARY,
    EventLevel,
    create_event,
)
from vibecode.monitor_app import (
    TUIEventSink,
    format_agent_line,
    format_vibecode_line,
    route_event,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _evt(
    type_: str,
    level: EventLevel = EventLevel.INFO,
    message: str = "test message",
    data: dict | None = None,
):
    return create_event(
        session_id="test-session",
        type_=type_,
        level=level,
        message=message,
        data=data,
        timestamp=datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
    )


# ---------------------------------------------------------------------------
# route_event
# ---------------------------------------------------------------------------


class TestRouteEvent:
    def test_agent_process_routes_to_agent(self):
        assert route_event(_evt(EVENT_AGENT_PROCESS)) == "agent"

    def test_guard_routes_to_event(self):
        assert route_event(_evt(EVENT_GUARD)) == "event"

    def test_check_routes_to_event(self):
        assert route_event(_evt(EVENT_CHECK)) == "event"

    def test_lifecycle_routes_to_event(self):
        assert route_event(_evt(EVENT_RUN_LIFECYCLE)) == "event"

    def test_summary_routes_to_event(self):
        assert route_event(_evt(EVENT_SUMMARY)) == "event"

    def test_handoff_routes_to_event(self):
        assert route_event(_evt(EVENT_HANDOFF)) == "event"


# ---------------------------------------------------------------------------
# format_agent_line
# ---------------------------------------------------------------------------


class TestFormatAgentLine:
    def test_stdout_phase_returns_plain_text(self):
        event = _evt(
            EVENT_AGENT_PROCESS,
            message="hello from agent",
            data={"phase": "stdout", "text": "hello from agent\n"},
        )
        line = format_agent_line(event)
        assert line == "hello from agent"

    def test_stderr_phase_has_stderr_prefix(self):
        event = _evt(
            EVENT_AGENT_PROCESS,
            message="error text",
            data={"phase": "stderr", "text": "error text\n"},
        )
        line = format_agent_line(event)
        assert line.startswith("[stderr]")
        assert "error text" in line

    def test_started_phase_has_started_label(self):
        event = _evt(
            EVENT_AGENT_PROCESS,
            message="Agent started: opencode",
            data={"phase": "started", "command": "opencode"},
        )
        line = format_agent_line(event)
        assert "[STARTED]" in line
        assert "Agent started" in line

    def test_finished_phase_has_finished_label(self):
        event = _evt(
            EVENT_AGENT_PROCESS,
            message="Agent finished (exit_code=0)",
            data={"phase": "finished", "exit_code": 0},
        )
        line = format_agent_line(event)
        assert "[FINISHED]" in line

    def test_preflight_failed_phase_has_label(self):
        event = _evt(
            EVENT_AGENT_PROCESS,
            message="Agent command not found",
            data={"phase": "preflight_failed"},
        )
        line = format_agent_line(event)
        assert "[PREFLIGHT_FAILED]" in line

    def test_no_data_uses_message(self):
        event = _evt(EVENT_AGENT_PROCESS, message="bare message", data=None)
        line = format_agent_line(event)
        assert "bare message" in line

    def test_strips_trailing_newline_from_message(self):
        event = _evt(
            EVENT_AGENT_PROCESS,
            message="line with newline\n",
            data={"phase": "stdout", "text": "line with newline\n"},
        )
        line = format_agent_line(event)
        assert not line.endswith("\n")
        assert not line.endswith("\r")

    def test_strips_trailing_carriage_return(self):
        event = _evt(
            EVENT_AGENT_PROCESS,
            message="line\r\n",
            data={"phase": "stdout", "text": "line\r\n"},
        )
        line = format_agent_line(event)
        assert not line.endswith("\r")

    def test_unknown_phase_returns_plain_text(self):
        event = _evt(
            EVENT_AGENT_PROCESS,
            message="some output",
            data={"phase": "unknown_phase", "text": "some output\n"},
        )
        line = format_agent_line(event)
        assert "some output" in line


# ---------------------------------------------------------------------------
# format_vibecode_line
# ---------------------------------------------------------------------------


class TestFormatVibecodeeLine:
    def test_includes_timestamp(self):
        event = _evt(EVENT_GUARD, message="Guard completed")
        line = format_vibecode_line(event)
        assert "12:00:00" in line

    def test_includes_level_name_info(self):
        event = _evt(EVENT_GUARD, level=EventLevel.INFO, message="Guard completed")
        line = format_vibecode_line(event)
        assert "INFO" in line

    def test_includes_level_name_warning(self):
        event = _evt(EVENT_GUARD, level=EventLevel.WARNING, message="Guard findings")
        line = format_vibecode_line(event)
        assert "WARNING" in line

    def test_includes_level_name_error(self):
        event = _evt(EVENT_CHECK, level=EventLevel.ERROR, message="Check failed")
        line = format_vibecode_line(event)
        assert "ERROR" in line

    def test_includes_event_type(self):
        event = _evt(EVENT_GUARD, message="Guard completed")
        line = format_vibecode_line(event)
        assert EVENT_GUARD in line

    def test_includes_message(self):
        event = _evt(EVENT_CHECK, message="All checks passed")
        line = format_vibecode_line(event)
        assert "All checks passed" in line

    def test_lifecycle_event_format(self):
        event = _evt(EVENT_RUN_LIFECYCLE, message="Run started", data={"phase": "started"})
        line = format_vibecode_line(event)
        assert EVENT_RUN_LIFECYCLE in line
        assert "Run started" in line


# ---------------------------------------------------------------------------
# TUIEventSink
# ---------------------------------------------------------------------------


class TestTUIEventSink:
    def test_emit_calls_call_from_thread(self):
        mock_app = MagicMock()
        sink = TUIEventSink(mock_app)
        event = _evt(EVENT_AGENT_PROCESS, message="hello")
        sink.emit(event)
        mock_app.call_from_thread.assert_called_once_with(
            mock_app.handle_vibecode_event, event
        )

    def test_emit_passes_correct_event(self):
        captured = []
        mock_app = MagicMock()
        mock_app.call_from_thread.side_effect = lambda fn, ev: captured.append(ev)
        sink = TUIEventSink(mock_app)
        event = _evt(EVENT_GUARD, message="guard event")
        sink.emit(event)
        assert len(captured) == 1
        assert captured[0] is event

    def test_emit_multiple_events_in_order(self):
        captured = []
        mock_app = MagicMock()
        mock_app.call_from_thread.side_effect = lambda fn, ev: captured.append(ev)
        sink = TUIEventSink(mock_app)
        events = [_evt(EVENT_AGENT_PROCESS, message=f"line {i}") for i in range(3)]
        for e in events:
            sink.emit(e)
        assert [c.message for c in captured] == ["line 0", "line 1", "line 2"]


# ---------------------------------------------------------------------------
# Module import / symbol checks
# ---------------------------------------------------------------------------


class TestMonitorModuleImport:
    def test_module_importable(self):
        import vibecode.monitor_app as mod  # noqa: F401

    def test_has_monitor_app_class(self):
        from vibecode.monitor_app import MonitorApp

        assert MonitorApp is not None

    def test_has_tui_event_sink(self):
        from vibecode.monitor_app import TUIEventSink

        assert TUIEventSink is not None

    def test_has_cmd_monitor(self):
        from vibecode.monitor_app import cmd_monitor

        assert callable(cmd_monitor)

    def test_has_format_agent_line(self):
        from vibecode.monitor_app import format_agent_line

        assert callable(format_agent_line)

    def test_has_format_vibecode_line(self):
        from vibecode.monitor_app import format_vibecode_line

        assert callable(format_vibecode_line)

    def test_has_route_event(self):
        from vibecode.monitor_app import route_event

        assert callable(route_event)


# ---------------------------------------------------------------------------
# CLI parser registration
# ---------------------------------------------------------------------------


class TestMonitorCLIParser:
    def test_monitor_subcommand_registered(self):
        from vibecode.cli import create_parser

        parser = create_parser()
        ns, _ = parser.parse_known_args(["monitor", "--task", "hello"])
        assert ns.command == "monitor"

    def test_monitor_task_arg(self):
        from vibecode.cli import create_parser

        parser = create_parser()
        ns, _ = parser.parse_known_args(["monitor", "--task", "fix the bug"])
        assert ns.task == "fix the bug"

    def test_monitor_platform_arg(self):
        from vibecode.cli import create_parser

        parser = create_parser()
        ns, _ = parser.parse_known_args(["monitor", "--platform", "opencode"])
        assert ns.platform == "opencode"

    def test_monitor_guard_mode_arg(self):
        from vibecode.cli import create_parser

        parser = create_parser()
        ns, _ = parser.parse_known_args(["monitor", "--guard-mode", "strict"])
        assert ns.guard_mode == "strict"

    def test_monitor_no_index_flag(self):
        from vibecode.cli import create_parser

        parser = create_parser()
        ns, _ = parser.parse_known_args(["monitor", "--no-index"])
        assert ns.no_index is True

    def test_monitor_allow_dirty_flag(self):
        from vibecode.cli import create_parser

        parser = create_parser()
        ns, _ = parser.parse_known_args(["monitor", "--allow-dirty"])
        assert ns.allow_dirty is True

    def test_monitor_help_exits_zero(self):
        from vibecode.cli import create_parser

        parser = create_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["monitor", "--help"])
        assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# cmd_monitor smoke path
# ---------------------------------------------------------------------------


class TestCmdMonitor:
    def test_cmd_monitor_calls_run_and_returns_zero(self, tmp_path):
        from vibecode.monitor_app import cmd_monitor

        args = SimpleNamespace(
            repo_root=str(tmp_path),
            task="test task",
            platform="opencode",
            profile="safe",
            allow_dirty=False,
            no_index=True,
            guard_mode="advisory",
        )
        with patch("vibecode.monitor_app.MonitorApp") as MockApp:
            mock_instance = MagicMock()
            MockApp.return_value = mock_instance
            result = cmd_monitor(args)

        assert result == 0
        mock_instance.run.assert_called_once()

    def test_cmd_monitor_defaults_profile_to_safe(self, tmp_path):
        from vibecode.monitor_app import cmd_monitor

        args = SimpleNamespace(
            repo_root=str(tmp_path),
            task="",
            platform="opencode",
            profile=None,
            allow_dirty=False,
            no_index=True,
            guard_mode="advisory",
        )
        with patch("vibecode.monitor_app.MonitorApp") as MockApp:
            MockApp.return_value = MagicMock()
            cmd_monitor(args)

        call_kwargs = MockApp.call_args[1]
        assert call_kwargs["profile"] == "safe"

    def test_cmd_monitor_passes_repo_root(self, tmp_path):
        from vibecode.monitor_app import cmd_monitor

        args = SimpleNamespace(
            repo_root=str(tmp_path),
            task="some task",
            platform="opencode",
            profile="fast",
            allow_dirty=True,
            no_index=False,
            guard_mode="strict",
        )
        with patch("vibecode.monitor_app.MonitorApp") as MockApp:
            MockApp.return_value = MagicMock()
            cmd_monitor(args)

        call_kwargs = MockApp.call_args[1]
        assert call_kwargs["repo_root"] == tmp_path
        assert call_kwargs["task"] == "some task"
        assert call_kwargs["platform"] == "opencode"
        assert call_kwargs["profile"] == "fast"
        assert call_kwargs["allow_dirty"] is True
        assert call_kwargs["no_index"] is False
        assert call_kwargs["guard_mode"] == "strict"

    def test_cmd_monitor_guard_mode_defaults_to_advisory(self, tmp_path):
        from vibecode.monitor_app import cmd_monitor

        args = SimpleNamespace(
            repo_root=str(tmp_path),
            task="",
            platform="opencode",
            profile="safe",
            allow_dirty=False,
            no_index=True,
            guard_mode=None,
        )
        with patch("vibecode.monitor_app.MonitorApp") as MockApp:
            MockApp.return_value = MagicMock()
            cmd_monitor(args)

        call_kwargs = MockApp.call_args[1]
        assert call_kwargs["guard_mode"] == "advisory"


# ---------------------------------------------------------------------------
# CLI dispatch smoke path
# ---------------------------------------------------------------------------


class TestMonitorCLIDispatch:
    def test_main_monitor_dispatches_to_cmd_monitor(self, tmp_path):
        """main() with 'monitor' command reaches cmd_monitor and returns 0."""
        from vibecode.cli import main

        with patch("vibecode.monitor_app.MonitorApp") as MockApp:
            MockApp.return_value = MagicMock()
            rc = main(["monitor", str(tmp_path), "--task", "smoke test", "--no-index"])

        assert rc == 0
        MockApp.assert_called_once()
        MockApp.return_value.run.assert_called_once()

    def test_main_monitor_nonexistent_root_returns_error(self, tmp_path):
        from vibecode.cli import main

        fake = str(tmp_path / "does_not_exist")
        rc = main(["monitor", fake, "--task", "test"])
        assert rc == 1
