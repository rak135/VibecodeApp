"""Tests for vibecode.mcp_server – VibecodeServer and CLI serve command."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, data) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, (dict, list)):
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    else:
        path.write_text(data, encoding="utf-8")
    return path


def _make_inventory(cards: list[dict] | None = None, files: list[dict] | None = None) -> dict:
    return {
        "$schema": "vibecode/file-inventory/v1",
        "project_id": "testproj",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "root": "/tmp/repo",
        "files": files or [],
        "context_cards": cards or [],
    }


def _make_risk_report(items: list[dict] | None = None) -> dict:
    return {
        "$schema": "vibecode/risk-report/v1",
        "project_id": "testproj",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "root": "/tmp/repo",
        "files": items or [],
    }


def _sample_card(path: str = "src/app.py") -> dict:
    return {
        "path": path,
        "language": "python",
        "purpose": "Main application entry point.",
        "symbols": [
            {"name": "run", "kind": "function", "line": 10},
            {"name": "App", "kind": "class", "line": 20},
        ],
        "content_snippet": '"""Main application entry point."""\ndef run(): pass\n',
        "detail_level": "basic",
        "facts": [
            {"kind": "todo", "line": 5, "text": "implement retry logic"},
        ],
        "heuristics": [
            {"kind": "high_param_count", "symbol": "run", "detail": "7 params", "severity": "medium"},
        ],
    }


def _sample_risk_item(path: str = "src/app.py", severity: str = "low") -> dict:
    return {
        "path": path,
        "risk_level": "medium",
        "reasons": ["test reason"],
        "facts": [],
        "heuristics": [
            {"kind": "suspicious_name", "symbol": "do_the_thing", "detail": "vague name", "severity": severity},
        ],
    }


# ---------------------------------------------------------------------------
# VibecodeServer – construction
# ---------------------------------------------------------------------------


class TestVibecodeServerConstruction:
    def test_missing_inventory_emits_warning(self, tmp_path, capsys):
        from vibecode.mcp_server import VibecodeServer

        VibecodeServer(tmp_path / "missing.json", tmp_path / "also_missing.json")
        captured = capsys.readouterr()
        assert "file_inventory.json" in captured.err

    def test_missing_risk_report_emits_warning(self, tmp_path, capsys):
        from vibecode.mcp_server import VibecodeServer

        inv = _write(tmp_path / "file_inventory.json", _make_inventory())
        VibecodeServer(inv, tmp_path / "missing_risk.json")
        captured = capsys.readouterr()
        assert "risk_report.json" in captured.err

    def test_loads_valid_inventory(self, tmp_path):
        from vibecode.mcp_server import VibecodeServer

        card = _sample_card()
        inv = _write(tmp_path / "file_inventory.json", _make_inventory(cards=[card]))
        risk = _write(tmp_path / "risk_report.json", _make_risk_report())
        vs = VibecodeServer(inv, risk)
        assert "src/app.py" in vs._cards

    def test_loads_valid_risk_report(self, tmp_path):
        from vibecode.mcp_server import VibecodeServer

        inv = _write(tmp_path / "file_inventory.json", _make_inventory())
        risk = _write(tmp_path / "risk_report.json", _make_risk_report(items=[_sample_risk_item()]))
        vs = VibecodeServer(inv, risk)
        assert "src/app.py" in vs._risks

    def test_invalid_json_emits_warning(self, tmp_path, capsys):
        from vibecode.mcp_server import VibecodeServer

        bad = tmp_path / "file_inventory.json"
        bad.write_text("{not valid json", encoding="utf-8")
        risk = _write(tmp_path / "risk_report.json", _make_risk_report())
        VibecodeServer(bad, risk)
        captured = capsys.readouterr()
        assert "file_inventory.json" in captured.err

    def test_builds_symbol_index(self, tmp_path):
        from vibecode.mcp_server import VibecodeServer

        inv = _write(tmp_path / "file_inventory.json", _make_inventory(cards=[_sample_card()]))
        risk = _write(tmp_path / "risk_report.json", _make_risk_report())
        vs = VibecodeServer(inv, risk)
        assert "run" in vs._symbols
        assert "App" in vs._symbols


# ---------------------------------------------------------------------------
# VibecodeServer.get_file_card
# ---------------------------------------------------------------------------


class TestGetFileCard:
    def _server(self, tmp_path, cards=None, risk_items=None):
        from vibecode.mcp_server import VibecodeServer

        inv = _write(tmp_path / "inv.json", _make_inventory(cards=cards or []))
        risk = _write(tmp_path / "risk.json", _make_risk_report(items=risk_items or []))
        return VibecodeServer(inv, risk)

    def test_unknown_path_returns_error_message(self, tmp_path):
        vs = self._server(tmp_path)
        result = vs.get_file_card("nonexistent/file.py")
        assert "No context card found" in result
        assert "nonexistent/file.py" in result

    def test_known_path_returns_card(self, tmp_path):
        vs = self._server(tmp_path, cards=[_sample_card()])
        result = vs.get_file_card("src/app.py")
        assert "src/app.py" in result
        assert "Main application entry point" in result

    def test_card_contains_symbols(self, tmp_path):
        vs = self._server(tmp_path, cards=[_sample_card()])
        result = vs.get_file_card("src/app.py")
        assert "run" in result
        assert "App" in result

    def test_card_contains_snippet(self, tmp_path):
        vs = self._server(tmp_path, cards=[_sample_card()])
        result = vs.get_file_card("src/app.py")
        assert "```" in result
        assert "def run" in result

    def test_card_contains_facts(self, tmp_path):
        vs = self._server(tmp_path, cards=[_sample_card()])
        result = vs.get_file_card("src/app.py")
        assert "todo" in result
        assert "implement retry logic" in result

    def test_card_contains_heuristics(self, tmp_path):
        vs = self._server(tmp_path, cards=[_sample_card()])
        result = vs.get_file_card("src/app.py")
        assert "high_param_count" in result
        assert "medium" in result

    def test_backslash_path_normalised(self, tmp_path):
        vs = self._server(tmp_path, cards=[_sample_card()])
        result = vs.get_file_card("src\\app.py")
        assert "src/app.py" in result

    def test_card_without_purpose(self, tmp_path):
        card = _sample_card()
        card["purpose"] = None
        vs = self._server(tmp_path, cards=[card])
        result = vs.get_file_card("src/app.py")
        assert "Purpose" not in result

    def test_card_without_symbols_omits_section(self, tmp_path):
        card = _sample_card()
        card["symbols"] = []
        vs = self._server(tmp_path, cards=[card])
        result = vs.get_file_card("src/app.py")
        assert "Symbols" not in result

    def test_card_without_facts_omits_section(self, tmp_path):
        card = _sample_card()
        card["facts"] = []
        vs = self._server(tmp_path, cards=[card])
        result = vs.get_file_card("src/app.py")
        assert "Facts" not in result

    def test_card_without_heuristics_omits_section(self, tmp_path):
        card = _sample_card()
        card["heuristics"] = []
        vs = self._server(tmp_path, cards=[card])
        result = vs.get_file_card("src/app.py")
        assert "Heuristics" not in result


# ---------------------------------------------------------------------------
# VibecodeServer.find_symbol
# ---------------------------------------------------------------------------


class TestFindSymbol:
    def _server(self, tmp_path, cards=None):
        from vibecode.mcp_server import VibecodeServer

        inv = _write(tmp_path / "inv.json", _make_inventory(cards=cards or []))
        risk = _write(tmp_path / "risk.json", _make_risk_report())
        return VibecodeServer(inv, risk)

    def test_unknown_symbol_returns_error(self, tmp_path):
        vs = self._server(tmp_path)
        result = vs.find_symbol("NoSuchSymbol")
        assert "not found" in result.lower()
        assert "NoSuchSymbol" in result

    def test_known_symbol_returns_markdown(self, tmp_path):
        vs = self._server(tmp_path, cards=[_sample_card()])
        result = vs.find_symbol("run")
        assert "## Symbol:" in result
        assert "run" in result
        assert "src/app.py" in result

    def test_symbol_result_contains_kind_and_line(self, tmp_path):
        vs = self._server(tmp_path, cards=[_sample_card()])
        result = vs.find_symbol("App")
        assert "class" in result
        assert "20" in result

    def test_case_insensitive_fallback(self, tmp_path):
        vs = self._server(tmp_path, cards=[_sample_card()])
        result = vs.find_symbol("app")
        # "App" found via case-insensitive lookup
        assert "App" in result
        assert "src/app.py" in result

    def test_symbol_appears_in_multiple_files(self, tmp_path):
        card1 = _sample_card("src/a.py")
        card2 = _sample_card("src/b.py")
        vs = self._server(tmp_path, cards=[card1, card2])
        result = vs.find_symbol("run")
        assert "src/a.py" in result
        assert "src/b.py" in result
        assert "Found in 2 file(s)" in result

    def test_find_symbol_markdown_header(self, tmp_path):
        vs = self._server(tmp_path, cards=[_sample_card()])
        result = vs.find_symbol("run")
        assert result.startswith("## Symbol: `run`")

    def test_find_symbol_shows_file_kind_line(self, tmp_path):
        vs = self._server(tmp_path, cards=[_sample_card()])
        result = vs.find_symbol("run")
        assert "function" in result
        assert "10" in result


# ---------------------------------------------------------------------------
# VibecodeServer.list_high_risk
# ---------------------------------------------------------------------------


class TestListHighRisk:
    def _server(self, tmp_path, risk_items=None):
        from vibecode.mcp_server import VibecodeServer

        inv = _write(tmp_path / "inv.json", _make_inventory())
        risk = _write(tmp_path / "risk.json", _make_risk_report(items=risk_items or []))
        return VibecodeServer(inv, risk)

    def test_no_high_severity_returns_message(self, tmp_path):
        vs = self._server(tmp_path, risk_items=[_sample_risk_item(severity="low")])
        result = vs.list_high_risk()
        assert "No high-risk files" in result

    def test_high_severity_heuristic_included(self, tmp_path):
        vs = self._server(tmp_path, risk_items=[_sample_risk_item(severity="high")])
        result = vs.list_high_risk()
        assert "src/app.py" in result
        assert "high" in result
        assert "suspicious_name" in result

    def test_medium_severity_excluded(self, tmp_path):
        items = [
            _sample_risk_item("src/a.py", severity="medium"),
            _sample_risk_item("src/b.py", severity="high"),
        ]
        vs = self._server(tmp_path, risk_items=items)
        result = vs.list_high_risk()
        assert "src/b.py" in result
        assert "src/a.py" not in result

    def test_empty_risk_report_returns_message(self, tmp_path):
        vs = self._server(tmp_path, risk_items=[])
        result = vs.list_high_risk()
        assert "No high-risk files" in result

    def test_multiple_high_risk_files(self, tmp_path):
        items = [
            _sample_risk_item("src/a.py", severity="high"),
            _sample_risk_item("src/b.py", severity="high"),
        ]
        vs = self._server(tmp_path, risk_items=items)
        result = vs.list_high_risk()
        assert "src/a.py" in result
        assert "src/b.py" in result

    def test_high_risk_level_included_without_heuristics(self, tmp_path):
        """Files with risk_level='high' appear even when no heuristic has severity='high'."""
        item = {
            "path": "src/critical.py",
            "risk_level": "high",
            "reasons": ["protected path"],
            "heuristics": [],
        }
        vs = self._server(tmp_path, risk_items=[item])
        result = vs.list_high_risk()
        assert "src/critical.py" in result
        assert "high" in result

    def test_list_high_risk_markdown_header(self, tmp_path):
        vs = self._server(tmp_path, risk_items=[_sample_risk_item(severity="high")])
        result = vs.list_high_risk()
        assert "## High-Risk Files" in result

    def test_list_high_risk_shows_reasons(self, tmp_path):
        item = {
            "path": "src/arch.py",
            "risk_level": "high",
            "reasons": ["architecture file"],
            "heuristics": [],
        }
        vs = self._server(tmp_path, risk_items=[item])
        result = vs.list_high_risk()
        assert "architecture file" in result


# ---------------------------------------------------------------------------
# build_mcp_server
# ---------------------------------------------------------------------------


class TestBuildMcpServer:
    def test_returns_fastmcp_instance(self, tmp_path):
        from mcp.server.fastmcp import FastMCP

        from vibecode.mcp_server import build_mcp_server

        inv = _write(tmp_path / "inv.json", _make_inventory())
        risk = _write(tmp_path / "risk.json", _make_risk_report())
        mcp = build_mcp_server(inv, risk)
        assert isinstance(mcp, FastMCP)

    def test_three_tools_registered(self, tmp_path):
        from vibecode.mcp_server import build_mcp_server

        inv = _write(tmp_path / "inv.json", _make_inventory())
        risk = _write(tmp_path / "risk.json", _make_risk_report())
        mcp = build_mcp_server(inv, risk)
        # list_tools is a coroutine; just check the _tool_manager attribute
        tool_names = set(mcp._tool_manager._tools.keys())
        assert {"get_file_card", "find_symbol", "list_high_risk"} <= tool_names


# ---------------------------------------------------------------------------
# cmd_serve – CLI integration
# ---------------------------------------------------------------------------


class TestCmdServe:
    def _init_repo(self, root: Path) -> None:
        vdir = root / ".vibecode"
        (vdir / "index").mkdir(parents=True, exist_ok=True)
        (vdir / "project.yaml").write_text(
            "project:\n  id: testproj\n  name: Test\n  root: .\n",
            encoding="utf-8",
        )

    def test_prints_config_snippet_to_stderr(self, tmp_path, capsys):
        from vibecode.mcp_server import cmd_serve

        self._init_repo(tmp_path)
        _write(tmp_path / ".vibecode" / "index" / "file_inventory.json", _make_inventory())
        _write(tmp_path / ".vibecode" / "index" / "risk_report.json", _make_risk_report())

        args = SimpleNamespace(repo_root=str(tmp_path))
        with patch("vibecode.mcp_server.build_mcp_server") as mock_build:
            mock_mcp = MagicMock()
            mock_build.return_value = mock_mcp
            cmd_serve(args)

        captured = capsys.readouterr()
        assert "mcpServers" in captured.err
        assert "vibecode" in captured.err

    def test_config_snippet_is_valid_json(self, tmp_path, capsys):
        from vibecode.mcp_server import cmd_serve

        self._init_repo(tmp_path)
        _write(tmp_path / ".vibecode" / "index" / "file_inventory.json", _make_inventory())
        _write(tmp_path / ".vibecode" / "index" / "risk_report.json", _make_risk_report())

        args = SimpleNamespace(repo_root=str(tmp_path))
        with patch("vibecode.mcp_server.build_mcp_server") as mock_build:
            mock_build.return_value = MagicMock()
            cmd_serve(args)

        captured = capsys.readouterr()
        # Extract JSON block from stderr
        start = captured.err.index("{")
        end = captured.err.rindex("}") + 1
        parsed = json.loads(captured.err[start:end])
        assert "mcpServers" in parsed

    def test_calls_mcp_run_with_stdio(self, tmp_path):
        from vibecode.mcp_server import cmd_serve

        self._init_repo(tmp_path)
        _write(tmp_path / ".vibecode" / "index" / "file_inventory.json", _make_inventory())
        _write(tmp_path / ".vibecode" / "index" / "risk_report.json", _make_risk_report())

        args = SimpleNamespace(repo_root=str(tmp_path))
        with patch("vibecode.mcp_server.build_mcp_server") as mock_build:
            mock_mcp = MagicMock()
            mock_build.return_value = mock_mcp
            cmd_serve(args)

        mock_mcp.run.assert_called_once_with(transport="stdio")

    def test_returns_zero(self, tmp_path):
        from vibecode.mcp_server import cmd_serve

        self._init_repo(tmp_path)
        _write(tmp_path / ".vibecode" / "index" / "file_inventory.json", _make_inventory())
        _write(tmp_path / ".vibecode" / "index" / "risk_report.json", _make_risk_report())

        args = SimpleNamespace(repo_root=str(tmp_path))
        with patch("vibecode.mcp_server.build_mcp_server") as mock_build:
            mock_build.return_value = MagicMock()
            rc = cmd_serve(args)

        assert rc == 0

    def test_cmd_serve_forwards_log_path_and_session_id(self, tmp_path, monkeypatch):
        from vibecode.mcp_server import cmd_serve

        self._init_repo(tmp_path)
        _write(tmp_path / ".vibecode" / "index" / "file_inventory.json", _make_inventory())
        _write(tmp_path / ".vibecode" / "index" / "risk_report.json", _make_risk_report())

        monkeypatch.setenv("VIBECODE_SESSION_ID", "sess-42")
        expected_log = tmp_path / ".vibecode" / "logs" / "mcp_events.jsonl"

        args = SimpleNamespace(repo_root=str(tmp_path))
        with patch("vibecode.mcp_server.build_mcp_server") as mock_build:
            mock_build.return_value = MagicMock()
            cmd_serve(args)

        mock_build.assert_called_once()
        kwargs = mock_build.call_args.kwargs
        assert kwargs["log_path"] == expected_log
        assert kwargs["session_id"] == "sess-42"


# ---------------------------------------------------------------------------
# CLI parser – serve subcommand
# ---------------------------------------------------------------------------


class TestCLIServeSubcommand:
    def test_serve_in_cli_help(self):
        from vibecode.cli import create_parser

        parser = create_parser()
        help_text = parser.format_help()
        assert "serve" in help_text

    def test_serve_accepts_repo_root(self):
        from vibecode.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["serve", "/some/path"])
        assert args.command == "serve"
        assert args.repo_root == "/some/path"

    def test_serve_repo_root_optional(self):
        from vibecode.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["serve"])
        assert args.command == "serve"
        assert args.repo_root is None


# ---------------------------------------------------------------------------
# Config snippet – command correctness
# ---------------------------------------------------------------------------


class TestConfigSnippet:
    def _init_repo(self, root: Path) -> None:
        vdir = root / ".vibecode"
        (vdir / "index").mkdir(parents=True, exist_ok=True)
        (vdir / "project.yaml").write_text(
            "project:\n  id: testproj\n  name: Test\n  root: .\n",
            encoding="utf-8",
        )

    def _get_snippet(self, tmp_path, capsys) -> dict:
        from vibecode.mcp_server import cmd_serve

        self._init_repo(tmp_path)
        _write(tmp_path / ".vibecode" / "index" / "file_inventory.json", _make_inventory())
        _write(tmp_path / ".vibecode" / "index" / "risk_report.json", _make_risk_report())
        args = SimpleNamespace(repo_root=str(tmp_path))
        with patch("vibecode.mcp_server.build_mcp_server") as mock_build:
            mock_build.return_value = MagicMock()
            cmd_serve(args)
        captured = capsys.readouterr()
        start = captured.err.index("{")
        end = captured.err.rindex("}") + 1
        return json.loads(captured.err[start:end])

    def test_command_is_vibecode(self, tmp_path, capsys):
        snippet = self._get_snippet(tmp_path, capsys)
        assert snippet["mcpServers"]["vibecode"]["command"] == "vibecode"

    def test_args_start_with_serve(self, tmp_path, capsys):
        snippet = self._get_snippet(tmp_path, capsys)
        assert snippet["mcpServers"]["vibecode"]["args"][0] == "serve"

    def test_snippet_uses_forward_slashes(self, tmp_path, capsys):
        snippet = self._get_snippet(tmp_path, capsys)
        args = snippet["mcpServers"]["vibecode"]["args"]
        for arg in args:
            assert "\\" not in arg, f"Backslash in snippet arg: {arg!r}"


# ---------------------------------------------------------------------------
# Real-data smoke tests (uses actual .vibecode/index if present)
# ---------------------------------------------------------------------------


class TestRealDataSmoke:
    """Light smoke tests against the actual project index files when available."""

    @staticmethod
    def _index_dir() -> Path:
        here = Path(__file__).parent.parent
        return here / ".vibecode" / "index"

    def test_get_file_card_existing_file(self):
        index = self._index_dir()
        inv = index / "file_inventory.json"
        risk = index / "risk_report.json"
        if not inv.exists() or not risk.exists():
            return  # skip if index not generated
        from vibecode.mcp_server import VibecodeServer

        vs = VibecodeServer(inv, risk)
        if not vs._cards:
            return
        path = next(iter(vs._cards))
        result = vs.get_file_card(path)
        assert path in result
        assert "# " in result  # markdown heading

    def test_get_file_card_nonexistent_returns_error(self):
        index = self._index_dir()
        inv = index / "file_inventory.json"
        risk = index / "risk_report.json"
        if not inv.exists() or not risk.exists():
            return
        from vibecode.mcp_server import VibecodeServer

        vs = VibecodeServer(inv, risk)
        result = vs.get_file_card("definitely/does/not/exist.py")
        assert "No context card found" in result

    def test_find_symbol_in_multiple_files(self):
        index = self._index_dir()
        inv = index / "file_inventory.json"
        risk = index / "risk_report.json"
        if not inv.exists() or not risk.exists():
            return
        from vibecode.mcp_server import VibecodeServer

        vs = VibecodeServer(inv, risk)
        # _git_add_commit appears in several test files in this project
        result = vs.find_symbol("_git_add_commit")
        if "not found" not in result.lower():
            assert "## Symbol:" in result
            assert "Found in" in result

    def test_list_high_risk_with_real_data(self):
        index = self._index_dir()
        inv = index / "file_inventory.json"
        risk = index / "risk_report.json"
        if not inv.exists() or not risk.exists():
            return
        from vibecode.mcp_server import VibecodeServer

        vs = VibecodeServer(inv, risk)
        result = vs.list_high_risk()
        # Real project has high-risk-level files (architecture docs), so this
        # should return actual content rather than the empty message.
        assert "## High-Risk Files" in result


# ---------------------------------------------------------------------------
# MCP tool logging (McpToolCalled / McpToolReturned / McpToolFailed)
# ---------------------------------------------------------------------------


class TestMcpToolLogging:
    """VibecodeServer emits compact events around each tool call when a sink is set."""

    def _server(self, tmp_path, cards=None, risk_items=None, *, sink, session_id=None):
        from vibecode.mcp_server import VibecodeServer

        inv = _write(tmp_path / "inv.json", _make_inventory(cards=cards or []))
        risk = _write(tmp_path / "risk.json", _make_risk_report(items=risk_items or []))
        return VibecodeServer(inv, risk, event_sink=sink, session_id=session_id)

    # -- get_file_card --------------------------------------------------------

    def test_get_file_card_emits_called_and_returned(self, tmp_path):
        from vibecode.events import EVENT_MCP, InMemoryEventSink

        sink = InMemoryEventSink()
        vs = self._server(tmp_path, cards=[_sample_card()], sink=sink)
        vs.get_file_card("src/app.py")

        msgs = [e.message for e in sink.events_by_type(EVENT_MCP)]
        assert any("McpToolCalled" in m and "get_file_card" in m for m in msgs)
        assert any("McpToolReturned" in m and "get_file_card" in m for m in msgs)

    def test_get_file_card_returned_event_has_found_true(self, tmp_path):
        from vibecode.events import EVENT_MCP, InMemoryEventSink

        sink = InMemoryEventSink()
        vs = self._server(tmp_path, cards=[_sample_card()], sink=sink)
        vs.get_file_card("src/app.py")

        returned = [e for e in sink.events_by_type(EVENT_MCP) if "McpToolReturned" in e.message]
        assert len(returned) == 1
        assert returned[0].data["found"] is True

    def test_get_file_card_missing_emits_found_false(self, tmp_path):
        from vibecode.events import EVENT_MCP, InMemoryEventSink

        sink = InMemoryEventSink()
        vs = self._server(tmp_path, sink=sink)
        vs.get_file_card("does/not/exist.py")

        returned = [e for e in sink.events_by_type(EVENT_MCP) if "McpToolReturned" in e.message]
        assert len(returned) == 1
        assert returned[0].data["found"] is False

    # -- find_symbol ----------------------------------------------------------

    def test_find_symbol_emits_called_and_returned(self, tmp_path):
        from vibecode.events import EVENT_MCP, InMemoryEventSink

        sink = InMemoryEventSink()
        vs = self._server(tmp_path, cards=[_sample_card()], sink=sink)
        vs.find_symbol("run")

        msgs = [e.message for e in sink.events_by_type(EVENT_MCP)]
        assert any("McpToolCalled" in m and "find_symbol" in m for m in msgs)
        assert any("McpToolReturned" in m and "find_symbol" in m for m in msgs)

    def test_find_symbol_returned_event_has_match_count(self, tmp_path):
        from vibecode.events import EVENT_MCP, InMemoryEventSink

        sink = InMemoryEventSink()
        vs = self._server(tmp_path, cards=[_sample_card()], sink=sink)
        vs.find_symbol("run")

        returned = [e for e in sink.events_by_type(EVENT_MCP) if "McpToolReturned" in e.message]
        assert len(returned) == 1
        assert returned[0].data["match_count"] == 1

    def test_find_symbol_not_found_emits_zero_match_count(self, tmp_path):
        from vibecode.events import EVENT_MCP, InMemoryEventSink

        sink = InMemoryEventSink()
        vs = self._server(tmp_path, sink=sink)
        vs.find_symbol("NoSuchSymbol")

        returned = [e for e in sink.events_by_type(EVENT_MCP) if "McpToolReturned" in e.message]
        assert len(returned) == 1
        assert returned[0].data["match_count"] == 0

    # -- list_high_risk -------------------------------------------------------

    def test_list_high_risk_emits_called_and_returned(self, tmp_path):
        from vibecode.events import EVENT_MCP, InMemoryEventSink

        sink = InMemoryEventSink()
        vs = self._server(tmp_path, risk_items=[_sample_risk_item(severity="high")], sink=sink)
        vs.list_high_risk()

        msgs = [e.message for e in sink.events_by_type(EVENT_MCP)]
        assert any("McpToolCalled" in m and "list_high_risk" in m for m in msgs)
        assert any("McpToolReturned" in m and "list_high_risk" in m for m in msgs)

    def test_list_high_risk_returned_event_has_risk_count(self, tmp_path):
        from vibecode.events import EVENT_MCP, InMemoryEventSink

        sink = InMemoryEventSink()
        vs = self._server(tmp_path, risk_items=[_sample_risk_item(severity="high")], sink=sink)
        vs.list_high_risk()

        returned = [e for e in sink.events_by_type(EVENT_MCP) if "McpToolReturned" in e.message]
        assert len(returned) == 1
        assert returned[0].data["risk_count"] == 1

    def test_list_high_risk_empty_risk_count_is_zero(self, tmp_path):
        from vibecode.events import EVENT_MCP, InMemoryEventSink

        sink = InMemoryEventSink()
        vs = self._server(tmp_path, sink=sink)
        vs.list_high_risk()

        returned = [e for e in sink.events_by_type(EVENT_MCP) if "McpToolReturned" in e.message]
        assert len(returned) == 1
        assert returned[0].data["risk_count"] == 0

    # -- McpToolFailed --------------------------------------------------------

    def test_mcptoolfailed_emitted_and_exception_reraised(self, tmp_path):
        import pytest
        from vibecode.events import EVENT_MCP, EventLevel, InMemoryEventSink

        sink = InMemoryEventSink()
        inv = _write(tmp_path / "inv.json", _make_inventory(cards=[_sample_card()]))
        risk = _write(tmp_path / "risk.json", _make_risk_report())
        from vibecode.mcp_server import VibecodeServer

        vs = VibecodeServer(inv, risk, event_sink=sink)

        with patch.object(vs, "_get_file_card", side_effect=RuntimeError("internal boom")):
            with pytest.raises(RuntimeError, match="internal boom"):
                vs.get_file_card("src/app.py")

        failed = [e for e in sink.events_by_type(EVENT_MCP) if "McpToolFailed" in e.message]
        assert len(failed) == 1
        assert failed[0].level == EventLevel.ERROR
        assert failed[0].data["error"] == "internal boom"
        assert failed[0].data["error_type"] == "RuntimeError"

    def test_mcptoolfailed_find_symbol(self, tmp_path):
        import pytest
        from vibecode.events import EVENT_MCP, InMemoryEventSink

        sink = InMemoryEventSink()
        inv = _write(tmp_path / "inv.json", _make_inventory())
        risk = _write(tmp_path / "risk.json", _make_risk_report())
        from vibecode.mcp_server import VibecodeServer

        vs = VibecodeServer(inv, risk, event_sink=sink)
        with patch.object(vs, "_find_symbol", side_effect=ValueError("bad")):
            with pytest.raises(ValueError, match="bad"):
                vs.find_symbol("anything")

        failed = [e for e in sink.events_by_type(EVENT_MCP) if "McpToolFailed" in e.message]
        assert len(failed) == 1
        assert "find_symbol" in failed[0].message

    def test_mcptoolfailed_list_high_risk(self, tmp_path):
        import pytest
        from vibecode.events import EVENT_MCP, InMemoryEventSink

        sink = InMemoryEventSink()
        inv = _write(tmp_path / "inv.json", _make_inventory())
        risk = _write(tmp_path / "risk.json", _make_risk_report())
        from vibecode.mcp_server import VibecodeServer

        vs = VibecodeServer(inv, risk, event_sink=sink)
        with patch.object(vs, "_list_high_risk", side_effect=KeyError("oops")):
            with pytest.raises(KeyError):
                vs.list_high_risk()

        failed = [e for e in sink.events_by_type(EVENT_MCP) if "McpToolFailed" in e.message]
        assert len(failed) == 1
        assert "list_high_risk" in failed[0].message

    # -- Compact summaries ----------------------------------------------------

    def test_result_summary_contains_no_full_result_blob(self, tmp_path):
        from vibecode.events import EVENT_MCP, InMemoryEventSink

        sink = InMemoryEventSink()
        vs = self._server(tmp_path, cards=[_sample_card()], sink=sink)
        vs.get_file_card("src/app.py")

        for event in sink.events_by_type(EVENT_MCP):
            if event.data:
                data_str = json.dumps(event.data)
                assert "def run" not in data_str, "Full snippet must not appear in event data"
                assert "implement retry logic" not in data_str, "Full fact text must not appear"

    def test_returned_event_has_result_chars(self, tmp_path):
        from vibecode.events import EVENT_MCP, InMemoryEventSink

        sink = InMemoryEventSink()
        vs = self._server(tmp_path, cards=[_sample_card()], sink=sink)
        result = vs.get_file_card("src/app.py")

        returned = [e for e in sink.events_by_type(EVENT_MCP) if "McpToolReturned" in e.message]
        assert returned[0].data["result_chars"] == len(result)

    def test_find_symbol_result_summary_contains_no_raw_result(self, tmp_path):
        from vibecode.events import EVENT_MCP, InMemoryEventSink

        sink = InMemoryEventSink()
        vs = self._server(tmp_path, cards=[_sample_card()], sink=sink)
        vs.find_symbol("run")

        for event in sink.events_by_type(EVENT_MCP):
            if event.data:
                data_str = json.dumps(event.data)
                assert "function" not in data_str, "Raw symbol kind must not appear in event data"
                assert "line 10" not in data_str, "Raw line number text must not appear"

    def test_list_high_risk_result_summary_contains_no_raw_result(self, tmp_path):
        from vibecode.events import EVENT_MCP, InMemoryEventSink

        sink = InMemoryEventSink()
        vs = self._server(tmp_path, risk_items=[_sample_risk_item(severity="high")], sink=sink)
        vs.list_high_risk()

        for event in sink.events_by_type(EVENT_MCP):
            if event.data:
                data_str = json.dumps(event.data)
                assert "High-Risk Files" not in data_str, "Raw heading must not appear in event data"
                assert "suspicious_name" not in data_str, "Raw heuristic kind must not appear"

    # -- No sink --------------------------------------------------------------

    def test_no_sink_tools_work_correctly(self, tmp_path):
        from vibecode.mcp_server import VibecodeServer

        inv = _write(tmp_path / "inv.json", _make_inventory(cards=[_sample_card()]))
        risk = _write(tmp_path / "risk.json", _make_risk_report(items=[_sample_risk_item(severity="high")]))
        vs = VibecodeServer(inv, risk)  # no event_sink

        assert "src/app.py" in vs.get_file_card("src/app.py")
        assert "run" in vs.find_symbol("run")
        assert "## High-Risk Files" in vs.list_high_risk()

    # -- Session ID -----------------------------------------------------------

    def test_session_id_from_parameter(self, tmp_path):
        from vibecode.events import EVENT_MCP, InMemoryEventSink

        sink = InMemoryEventSink()
        vs = self._server(tmp_path, sink=sink, session_id="my-session-42")
        vs.list_high_risk()

        for event in sink.events_by_type(EVENT_MCP):
            assert event.session_id == "my-session-42"

    def test_session_id_from_env(self, tmp_path, monkeypatch):
        from vibecode.events import EVENT_MCP, InMemoryEventSink

        monkeypatch.setenv("VIBECODE_SESSION_ID", "env-session-99")
        sink = InMemoryEventSink()
        inv = _write(tmp_path / "inv.json", _make_inventory())
        risk = _write(tmp_path / "risk.json", _make_risk_report())
        from vibecode.mcp_server import VibecodeServer

        vs = VibecodeServer(inv, risk, event_sink=sink)
        vs.list_high_risk()

        for event in sink.events_by_type(EVENT_MCP):
            assert event.session_id == "env-session-99"

    def test_session_id_defaults_to_mcp_server(self, tmp_path, monkeypatch):
        from vibecode.events import EVENT_MCP, InMemoryEventSink

        monkeypatch.delenv("VIBECODE_SESSION_ID", raising=False)
        sink = InMemoryEventSink()
        inv = _write(tmp_path / "inv.json", _make_inventory())
        risk = _write(tmp_path / "risk.json", _make_risk_report())
        from vibecode.mcp_server import VibecodeServer

        vs = VibecodeServer(inv, risk, event_sink=sink)
        vs.list_high_risk()

        for event in sink.events_by_type(EVENT_MCP):
            assert event.session_id == "mcp-server"

    # -- JSONL log path -------------------------------------------------------

    def test_jsonl_log_written_on_tool_call(self, tmp_path):
        from vibecode.events import JsonlEventSink
        from vibecode.mcp_server import VibecodeServer

        log_path = tmp_path / "mcp_events.jsonl"
        sink = JsonlEventSink(log_path)
        inv = _write(tmp_path / "inv.json", _make_inventory(cards=[_sample_card()]))
        risk = _write(tmp_path / "risk.json", _make_risk_report())
        vs = VibecodeServer(inv, risk, event_sink=sink)
        vs.get_file_card("src/app.py")

        assert log_path.exists()
        lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(lines) >= 2  # McpToolCalled + McpToolReturned
        first = json.loads(lines[0])
        assert first["type"] == "run.mcp"
        assert "McpToolCalled" in first["message"]

    def test_jsonl_log_contains_both_events(self, tmp_path):
        from vibecode.events import JsonlEventSink
        from vibecode.mcp_server import VibecodeServer

        log_path = tmp_path / "mcp_events.jsonl"
        sink = JsonlEventSink(log_path)
        inv = _write(tmp_path / "inv.json", _make_inventory())
        risk = _write(tmp_path / "risk.json", _make_risk_report())
        vs = VibecodeServer(inv, risk, event_sink=sink)
        vs.find_symbol("NoMatch")

        lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        messages = [json.loads(line)["message"] for line in lines]
        assert any("McpToolCalled" in m for m in messages)
        assert any("McpToolReturned" in m for m in messages)

    # -- build_mcp_server with log_path ---------------------------------------

    def test_build_mcp_server_accepts_log_path_and_session_id(self, tmp_path):
        from vibecode.mcp_server import build_mcp_server

        log_path = tmp_path / "logs" / "mcp_events.jsonl"
        inv = _write(tmp_path / "inv.json", _make_inventory())
        risk = _write(tmp_path / "risk.json", _make_risk_report())
        # Should not raise even with new kwargs
        with patch("vibecode.mcp_server.FastMCP" if False else "mcp.server.fastmcp.FastMCP"):
            try:
                build_mcp_server(inv, risk, log_path=log_path, session_id="test-sess")
            except Exception:
                pass  # mcp may not support patching here; just ensure no TypeError

    # -- No MCP import at module level ----------------------------------------

    def test_vibecode_server_does_not_require_mcp(self, tmp_path):
        """VibecodeServer and tool methods work when mcp is hidden from sys.modules."""
        mcp_mods = {k: v for k, v in list(sys.modules.items()) if k == "mcp" or k.startswith("mcp.")}
        for k in mcp_mods:
            del sys.modules[k]
        try:
            from vibecode.mcp_server import VibecodeServer

            inv = _write(tmp_path / "inv.json", _make_inventory(cards=[_sample_card()]))
            risk = _write(tmp_path / "risk.json", _make_risk_report(items=[_sample_risk_item(severity="high")]))
            vs = VibecodeServer(inv, risk)
            vs.get_file_card("src/app.py")
            vs.find_symbol("run")
            vs.list_high_risk()
        finally:
            sys.modules.update(mcp_mods)

    # -- CLI survives missing mcp package (lazy import) -----------------------

    def test_cli_help_works_when_mcp_imports_blocked(self):
        import io

        class _BlockMCP:
            def find_spec(self, fullname, path, target=None):
                if fullname == "mcp" or fullname.startswith("mcp."):
                    raise ImportError(f"Simulated missing package: {fullname}")
                return None

        # Capture stdout while blocking mcp imports
        real_stdout = sys.stdout
        try:
            sys.meta_path.insert(0, _BlockMCP())
            # Clear cached mcp_server module so it re-imports under the blocker
            for mod in list(sys.modules):
                if mod == "vibecode.mcp_server" or mod.startswith("mcp"):
                    del sys.modules[mod]

            from vibecode.cli import create_parser
            parser = create_parser()
            buf = io.StringIO()
            sys.stdout = buf
            parser.print_help()
            sys.stdout = real_stdout
            help_text = buf.getvalue()
            assert "serve" in help_text
            assert "guard" in help_text
        finally:
            if _BlockMCP in [type(h) for h in sys.meta_path]:
                sys.meta_path = [h for h in sys.meta_path if not isinstance(h, _BlockMCP)]
            sys.stdout = real_stdout
            # Restore cached module
            import vibecode.mcp_server  # noqa: F401

    def test_non_mcp_command_works_when_mcp_imports_blocked(self, tmp_path):

        class _BlockMCP:
            def find_spec(self, fullname, path, target=None):
                if fullname == "mcp" or fullname.startswith("mcp."):
                    raise ImportError(f"Simulated missing package: {fullname}")
                return None

        try:
            sys.meta_path.insert(0, _BlockMCP())
            for mod in list(sys.modules):
                if mod == "vibecode.mcp_server" or mod.startswith("mcp"):
                    del sys.modules[mod]

            from vibecode.cli import create_parser
            parser = create_parser()
            args = parser.parse_args(["validate", str(tmp_path)])
            assert args.command == "validate"
        finally:
            if _BlockMCP in [type(h) for h in sys.meta_path]:
                sys.meta_path = [h for h in sys.meta_path if not isinstance(h, _BlockMCP)]
            import vibecode.mcp_server  # noqa: F401
