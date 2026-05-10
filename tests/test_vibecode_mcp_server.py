"""Tests for vibecode.mcp_server – VibecodeServer and CLI serve command."""

from __future__ import annotations

import json
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
