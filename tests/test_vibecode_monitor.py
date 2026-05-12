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
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from vibecode.events import (
    EVENT_AGENT_PROCESS,
    EVENT_CHECK,
    EVENT_CONTEXT,
    EVENT_GUARD,
    EVENT_GUARD_FINDING,
    EVENT_HANDOFF,
    EVENT_MCP,
    EVENT_PROMPT,
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

    def test_mcp_routes_to_event(self):
        assert route_event(_evt(EVENT_MCP)) == "event"


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

    def test_context_event_shows_snapshot_path(self):
        event = _evt(
            EVENT_CONTEXT,
            message="Context pack written",
            data={
                "phase": "written",
                "path": "/tmp/vibecode/current/context_pack.md",
                "snapshot_path": "/tmp/.vibecode/runs/sess-123/context_pack.md",
                "size_bytes": 5000,
            },
        )
        line = format_vibecode_line(event)
        assert "Context pack written" in line
        assert ".vibecode/runs/sess-123/context_pack.md" in line
        assert EVENT_CONTEXT in line

    def test_context_event_falls_back_to_path_when_no_snapshot(self):
        event = _evt(
            EVENT_CONTEXT,
            message="Context pack written",
            data={
                "phase": "written",
                "path": "/tmp/vibecode/current/context_pack.md",
                "snapshot_path": None,
                "size_bytes": 5000,
            },
        )
        line = format_vibecode_line(event)
        assert "Context pack written" in line
        assert "/tmp/vibecode/current/context_pack.md" in line

    def test_context_event_no_path_no_crash(self):
        event = _evt(
            EVENT_CONTEXT,
            message="Context pack written",
            data={"phase": "written"},
        )
        line = format_vibecode_line(event)
        assert "Context pack written" in line

    def test_prompt_event_shows_snapshot_path_platform_profile(self):
        event = _evt(
            EVENT_PROMPT,
            message="Prompt written",
            data={
                "phase": "written",
                "snapshot_path": "/tmp/.vibecode/runs/sess-123/opencode_prompt.md",
                "platform": "opencode",
                "profile": "safe",
                "size_bytes": 1200,
            },
        )
        line = format_vibecode_line(event)
        assert "Prompt written" in line
        assert "opencode_prompt.md" in line
        assert "opencode" in line
        assert "safe" in line
        assert EVENT_PROMPT in line

    def test_prompt_event_falls_back_to_path_when_no_snapshot(self):
        event = _evt(
            EVENT_PROMPT,
            message="Prompt written",
            data={
                "phase": "written",
                "path": "/tmp/vibecode/current/opencode_prompt.md",
                "snapshot_path": None,
                "platform": "opencode",
                "profile": "fast",
                "size_bytes": 800,
            },
        )
        line = format_vibecode_line(event)
        assert "opencode_prompt.md" in line
        assert "opencode" in line
        assert "fast" in line

    def test_guard_finding_warning_shows_details(self):
        event = _evt(
            EVENT_GUARD_FINDING,
            level=EventLevel.WARNING,
            message="source-test-change-balance",
            data={
                "rule_id": "source-test-change-balance",
                "severity": "warning",
                "category": "test-balance",
                "path": "src/foo.py",
                "title": "Source changed but tests unchanged",
                "message": "Source file src/foo.py was modified without corresponding test changes.",
                "recommended_fix": "Add or update tests in tests/test_foo.py.",
                "required_tests": ["test_foo_feature"],
            },
        )
        line = format_vibecode_line(event)
        assert "WARNING" in line
        assert EVENT_GUARD_FINDING in line
        assert "warning" in line.upper().lower() or "WARNING" in line
        assert "test-balance" in line
        assert "src/foo.py" in line
        assert "Source changed but tests unchanged" in line
        assert "Add or update tests" in line
        assert "test_foo_feature" in line

    def test_guard_finding_error_shows_severity(self):
        event = _evt(
            EVENT_GUARD_FINDING,
            level=EventLevel.ERROR,
            message="protected-file-modified",
            data={
                "rule_id": "protected-file-modified",
                "severity": "error",
                "category": "protection",
                "path": ".vibecode/architecture/INVARIANTS.md",
                "title": "Protected file was modified",
                "message": "The file is a protected invariant.",
                "recommended_fix": "Revert the change.",
                "required_tests": [],
            },
        )
        line = format_vibecode_line(event)
        assert "ERROR" in line
        assert EVENT_GUARD_FINDING in line
        assert "INVARIANTS.md" in line
        assert "Protected file was modified" in line
        assert "Revert the change" in line

    def test_guard_finding_no_tests_no_fix_no_crash(self):
        event = _evt(
            EVENT_GUARD_FINDING,
            level=EventLevel.WARNING,
            message="some finding",
            data={
                "rule_id": "r1",
                "severity": "warning",
                "category": "general",
                "path": "f.txt",
                "title": "Some finding",
                "recommended_fix": "",
                "required_tests": [],
            },
        )
        line = format_vibecode_line(event)
        assert "some finding" in line or "Some finding" in line
        assert EVENT_GUARD_FINDING in line


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


# ---------------------------------------------------------------------------
# format_vibecode_line – MCP event formatting
# ---------------------------------------------------------------------------


class TestMcpEventFormatting:
    """Tests for EVENT_MCP rendering in format_vibecode_line."""

    def _mcp_evt(self, message: str, data: dict | None = None, level: EventLevel = EventLevel.INFO):
        return _evt(EVENT_MCP, level=level, message=message, data=data)

    def test_mcp_called_routes_to_event_pane(self):
        """MCP events are routed to the event pane, not agent pane."""
        evt = self._mcp_evt("McpToolCalled: get_file_card", data={"tool": "get_file_card"})
        assert route_event(evt) == "event"

    def test_mcp_called_formats_with_arrow(self):
        """McpToolCalled renders as '→ toolname'."""
        evt = self._mcp_evt(
            "McpToolCalled: get_file_card",
            data={"tool": "get_file_card"},
        )
        line = format_vibecode_line(evt)
        assert "→ get_file_card" in line
        assert EVENT_MCP in line

    def test_mcp_called_includes_path_arg(self):
        """McpToolCalled includes path argument when present."""
        evt = self._mcp_evt(
            "McpToolCalled: get_file_card",
            data={"tool": "get_file_card", "path": "src/app.py"},
        )
        line = format_vibecode_line(evt)
        assert "src/app.py" in line

    def test_mcp_called_includes_symbol_arg(self):
        """McpToolCalled includes symbol argument when present."""
        evt = self._mcp_evt(
            "McpToolCalled: find_symbol",
            data={"tool": "find_symbol", "symbol": "run_controller"},
        )
        line = format_vibecode_line(evt)
        assert "run_controller" in line

    def test_mcp_called_no_arg_no_crash(self):
        """McpToolCalled renders cleanly with no path or symbol."""
        evt = self._mcp_evt(
            "McpToolCalled: list_high_risk",
            data={"tool": "list_high_risk"},
        )
        line = format_vibecode_line(evt)
        assert "list_high_risk" in line

    def test_mcp_returned_formats_with_left_arrow(self):
        """McpToolReturned renders as '← toolname'."""
        evt = self._mcp_evt(
            "McpToolReturned: get_file_card",
            data={"tool": "get_file_card", "result_chars": 1234, "found": True},
        )
        line = format_vibecode_line(evt)
        assert "← get_file_card" in line
        assert EVENT_MCP in line

    def test_mcp_returned_shows_result_chars(self):
        """McpToolReturned includes result character count."""
        evt = self._mcp_evt(
            "McpToolReturned: get_file_card",
            data={"tool": "get_file_card", "result_chars": 5678},
        )
        line = format_vibecode_line(evt)
        assert "5678" in line

    def test_mcp_returned_shows_found_field(self):
        """McpToolReturned includes 'found' field when present."""
        evt = self._mcp_evt(
            "McpToolReturned: get_file_card",
            data={"tool": "get_file_card", "found": True, "result_chars": 100},
        )
        line = format_vibecode_line(evt)
        assert "found=True" in line

    def test_mcp_returned_shows_match_count(self):
        """McpToolReturned includes 'match_count' field when present."""
        evt = self._mcp_evt(
            "McpToolReturned: find_symbol",
            data={"tool": "find_symbol", "match_count": 3, "result_chars": 200},
        )
        line = format_vibecode_line(evt)
        assert "matches=3" in line

    def test_mcp_returned_shows_risk_count(self):
        """McpToolReturned includes 'risk_count' field when present."""
        evt = self._mcp_evt(
            "McpToolReturned: list_high_risk",
            data={"tool": "list_high_risk", "risk_count": 7, "result_chars": 500},
        )
        line = format_vibecode_line(evt)
        assert "risks=7" in line

    def test_mcp_failed_formats_with_cross(self):
        """McpToolFailed renders as '✗ toolname [error_type]'."""
        evt = self._mcp_evt(
            "McpToolFailed: get_file_card",
            data={"tool": "get_file_card", "error_type": "KeyError", "error": "key missing"},
            level=EventLevel.ERROR,
        )
        line = format_vibecode_line(evt)
        assert "✗ get_file_card" in line
        assert "KeyError" in line
        assert EVENT_MCP in line

    def test_mcp_failed_includes_error_message(self):
        """McpToolFailed includes the error message."""
        evt = self._mcp_evt(
            "McpToolFailed: find_symbol",
            data={"tool": "find_symbol", "error_type": "ValueError", "error": "bad input"},
        )
        line = format_vibecode_line(evt)
        assert "bad input" in line

    def test_mcp_failed_no_error_field_no_crash(self):
        """McpToolFailed renders cleanly even without 'error' field."""
        evt = self._mcp_evt(
            "McpToolFailed: list_high_risk",
            data={"tool": "list_high_risk", "error_type": "RuntimeError"},
        )
        line = format_vibecode_line(evt)
        assert "✗ list_high_risk" in line
        assert "RuntimeError" in line

    def test_mcp_unknown_variant_falls_back_to_default(self):
        """Unknown MCP message variant falls back to default format without crash."""
        evt = self._mcp_evt(
            "McpToolSomethingElse: get_file_card",
            data={"tool": "get_file_card"},
        )
        line = format_vibecode_line(evt)
        # Should include event type and message without crashing
        assert EVENT_MCP in line
        assert "McpToolSomethingElse" in line

    def test_mcp_event_includes_timestamp(self):
        """MCP event line includes formatted timestamp."""
        evt = self._mcp_evt("McpToolCalled: get_file_card", data={"tool": "get_file_card"})
        line = format_vibecode_line(evt)
        assert "12:00:00" in line

    def test_mcp_no_data_no_crash(self):
        """MCP event with no data dict does not crash."""
        evt = _evt(EVENT_MCP, message="McpToolCalled: mystery", data=None)
        line = format_vibecode_line(evt)
        assert EVENT_MCP in line
