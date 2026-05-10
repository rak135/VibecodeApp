"""Tests for vibecode dashboard TUI and data loader."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _make_inventory(cards: list[dict], files: list[dict] | None = None) -> dict:
    return {
        "$schema": "vibecode/file-inventory/v1",
        "project_id": "test",
        "generated_at": "2024-01-01T00:00:00+00:00",
        "root": "/tmp/repo",
        "files": files or [],
        "context_cards": cards,
    }


def _make_risk_report(entries: list[dict]) -> dict:
    return {
        "$schema": "vibecode/risk-report/v1",
        "project_id": "test",
        "generated_at": "2024-01-01T00:00:00+00:00",
        "root": "/tmp/repo",
        "files": entries,
    }


# ---------------------------------------------------------------------------
# load_dashboard_data – basic behaviour
# ---------------------------------------------------------------------------


class TestLoadDashboardData:
    def test_empty_repo_returns_empty_data(self, tmp_path):
        from vibecode.tui_app import load_dashboard_data

        data = load_dashboard_data(tmp_path)
        assert data.cards == []
        assert data.total_files == 0
        assert data.high_risk_count == 0

    def test_loads_cards_from_inventory(self, tmp_path):
        from vibecode.tui_app import load_dashboard_data

        cards = [
            {"path": "foo.py", "purpose": "does foo", "symbols": [], "content_snippet": ""},
            {"path": "bar.py", "purpose": "does bar", "symbols": [], "content_snippet": ""},
        ]
        files = [{"path": "foo.py"}, {"path": "bar.py"}, {"path": "baz.py"}]
        inv = _make_inventory(cards, files)
        _write(
            tmp_path / ".vibecode" / "index" / "file_inventory.json",
            json.dumps(inv),
        )

        data = load_dashboard_data(tmp_path)
        assert len(data.cards) == 2
        assert data.total_files == 3
        assert data.high_risk_count == 0

    def test_counts_high_risk_by_risk_level(self, tmp_path):
        from vibecode.tui_app import load_dashboard_data

        risk = _make_risk_report([
            {"path": "a.py", "risk_level": "high", "facts": [], "heuristics": []},
            {"path": "b.py", "risk_level": "low", "facts": [], "heuristics": []},
            {"path": "c.py", "risk_level": "high", "facts": [], "heuristics": []},
        ])
        _write(
            tmp_path / ".vibecode" / "index" / "risk_report.json",
            json.dumps(risk),
        )

        data = load_dashboard_data(tmp_path)
        assert data.high_risk_count == 2

    def test_counts_high_risk_by_heuristic_severity(self, tmp_path):
        from vibecode.tui_app import load_dashboard_data

        risk = _make_risk_report([
            {
                "path": "a.py",
                "risk_level": "low",
                "facts": [],
                "heuristics": [{"kind": "suspicious_name", "symbol": "x", "detail": "d", "severity": "high"}],
            },
            {
                "path": "b.py",
                "risk_level": "low",
                "facts": [],
                "heuristics": [{"kind": "high_param_count", "symbol": "y", "detail": "d", "severity": "medium"}],
            },
        ])
        _write(
            tmp_path / ".vibecode" / "index" / "risk_report.json",
            json.dumps(risk),
        )

        data = load_dashboard_data(tmp_path)
        assert data.high_risk_count == 1

    def test_handles_corrupt_inventory_json(self, tmp_path):
        from vibecode.tui_app import load_dashboard_data

        _write(
            tmp_path / ".vibecode" / "index" / "file_inventory.json",
            "not valid json {{{",
        )
        data = load_dashboard_data(tmp_path)
        assert data.cards == []
        assert data.total_files == 0

    def test_handles_corrupt_risk_json(self, tmp_path):
        from vibecode.tui_app import load_dashboard_data

        _write(
            tmp_path / ".vibecode" / "index" / "risk_report.json",
            "not valid json {{{",
        )
        data = load_dashboard_data(tmp_path)
        assert data.high_risk_count == 0

    def test_missing_context_cards_key_gives_empty_list(self, tmp_path):
        from vibecode.tui_app import load_dashboard_data

        inv = {"$schema": "vibecode/file-inventory/v1", "files": [{"path": "a.py"}]}
        _write(
            tmp_path / ".vibecode" / "index" / "file_inventory.json",
            json.dumps(inv),
        )
        data = load_dashboard_data(tmp_path)
        assert data.cards == []
        assert data.total_files == 1


# ---------------------------------------------------------------------------
# _symbols_summary helper
# ---------------------------------------------------------------------------


class TestSymbolsSummary:
    def test_empty_returns_dash(self):
        from vibecode.tui_app import _symbols_summary

        assert _symbols_summary([]) == "—"

    def test_single_function(self):
        from vibecode.tui_app import _symbols_summary

        result = _symbols_summary([{"name": "foo", "kind": "function", "line": 1}])
        assert "function" in result
        assert "1" in result

    def test_mixed_kinds(self):
        from vibecode.tui_app import _symbols_summary

        symbols = [
            {"name": "Foo", "kind": "class", "line": 1},
            {"name": "bar", "kind": "function", "line": 5},
            {"name": "baz", "kind": "function", "line": 9},
        ]
        result = _symbols_summary(symbols)
        assert "2 function" in result
        assert "1 class" in result


# ---------------------------------------------------------------------------
# DashboardData NamedTuple
# ---------------------------------------------------------------------------


class TestDashboardData:
    def test_namedtuple_fields(self):
        from vibecode.tui_app import DashboardData

        d = DashboardData(cards=[{"path": "x.py"}], total_files=5, high_risk_count=2)
        assert len(d.cards) == 1
        assert d.total_files == 5
        assert d.high_risk_count == 2


# ---------------------------------------------------------------------------
# CLI integration – dashboard command registered
# ---------------------------------------------------------------------------


class TestDashboardCLI:
    def test_dashboard_help(self):
        """The dashboard subcommand must be registered and show help without error."""
        from vibecode.cli import create_parser

        parser = create_parser()
        # Parsing --help would exit; just verify the subcommand is registered
        subparsers_action = None
        for action in parser._actions:
            if hasattr(action, "_name_parser_map"):
                subparsers_action = action
                break
        assert subparsers_action is not None
        assert "dashboard" in subparsers_action._name_parser_map

    def test_dashboard_parser_accepts_repo_root(self):
        from vibecode.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["dashboard", "/some/path"])
        assert args.command == "dashboard"
        assert args.repo_root == "/some/path"

    def test_dashboard_parser_repo_root_optional(self):
        from vibecode.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["dashboard"])
        assert args.command == "dashboard"
        assert args.repo_root is None


# ---------------------------------------------------------------------------
# VibecodeTUI – basic instantiation (no display required)
# ---------------------------------------------------------------------------


class TestVibecodeTUIInstantiation:
    def test_instantiates_with_repo_root(self, tmp_path):
        from vibecode.tui_app import VibecodeTUI

        app = VibecodeTUI(repo_root=tmp_path)
        assert app._repo_root == tmp_path

    def test_instantiates_with_default_cwd(self):
        from vibecode.tui_app import VibecodeTUI
        from pathlib import Path

        app = VibecodeTUI()
        assert app._repo_root == Path.cwd()

    def test_css_path_exists(self):
        from vibecode.tui_app import VibecodeTUI
        from pathlib import Path

        css_path = Path(VibecodeTUI.CSS_PATH)
        assert css_path.exists(), f"CSS file not found: {css_path}"

    def test_title_is_set(self):
        from vibecode.tui_app import VibecodeTUI

        assert VibecodeTUI.TITLE == "Vibecode Dashboard"
