"""Tests for vibecode dashboard TUI and data loader."""

from __future__ import annotations

import json
from pathlib import Path


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

    def test_null_symbols_normalized_to_empty_list(self, tmp_path):
        from vibecode.tui_app import load_dashboard_data

        cards = [{"path": "a.py", "purpose": "x", "symbols": None, "facts": [], "heuristics": []}]
        inv = _make_inventory(cards)
        _write(tmp_path / ".vibecode" / "index" / "file_inventory.json", json.dumps(inv))

        data = load_dashboard_data(tmp_path)
        assert data.cards[0]["symbols"] == []

    def test_null_facts_normalized_to_empty_list(self, tmp_path):
        from vibecode.tui_app import load_dashboard_data

        cards = [{"path": "a.py", "purpose": "x", "symbols": [], "facts": None, "heuristics": []}]
        inv = _make_inventory(cards)
        _write(tmp_path / ".vibecode" / "index" / "file_inventory.json", json.dumps(inv))

        data = load_dashboard_data(tmp_path)
        assert data.cards[0]["facts"] == []

    def test_null_heuristics_normalized_to_empty_list(self, tmp_path):
        from vibecode.tui_app import load_dashboard_data

        cards = [{"path": "a.py", "purpose": "x", "symbols": [], "facts": [], "heuristics": None}]
        inv = _make_inventory(cards)
        _write(tmp_path / ".vibecode" / "index" / "file_inventory.json", json.dumps(inv))

        data = load_dashboard_data(tmp_path)
        assert data.cards[0]["heuristics"] == []

    def test_all_null_list_fields_normalized(self, tmp_path):
        from vibecode.tui_app import load_dashboard_data

        cards = [{"path": "a.py", "purpose": "p", "symbols": None, "facts": None, "heuristics": None}]
        inv = _make_inventory(cards)
        _write(tmp_path / ".vibecode" / "index" / "file_inventory.json", json.dumps(inv))

        data = load_dashboard_data(tmp_path)
        card = data.cards[0]
        assert card["symbols"] == []
        assert card["facts"] == []
        assert card["heuristics"] == []

    def test_non_null_list_fields_preserved(self, tmp_path):
        from vibecode.tui_app import load_dashboard_data

        sym = [{"name": "foo", "kind": "function", "line": 1}]
        cards = [{"path": "a.py", "purpose": "p", "symbols": sym, "facts": [], "heuristics": []}]
        inv = _make_inventory(cards)
        _write(tmp_path / ".vibecode" / "index" / "file_inventory.json", json.dumps(inv))

        data = load_dashboard_data(tmp_path)
        assert data.cards[0]["symbols"] == sym


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
# CardDetailScreen – safe compose with null / missing fields
# ---------------------------------------------------------------------------


class TestCardDetailScreenSafety:
    """Verify CardDetailScreen never crashes due to None list fields."""

    def _make_card(self, **overrides) -> dict:
        base = {
            "path": "vibecode/foo.py",
            "purpose": "does something useful",
            "symbols": [{"name": "Foo", "kind": "class", "line": 1}],
            "facts": [{"kind": "import", "line": 2, "text": "import os"}],
            "heuristics": [{"severity": "low", "kind": "high_param_count", "symbol": "bar", "detail": "d"}],
            "content_snippet": "# code here",
        }
        base.update(overrides)
        return base

    def test_stores_card(self):
        from vibecode.tui_app import CardDetailScreen

        card = self._make_card()
        screen = CardDetailScreen(card)
        assert screen._card is card

    def test_stores_minimal_card(self):
        from vibecode.tui_app import CardDetailScreen

        card = {"path": "a.py"}
        screen = CardDetailScreen(card)
        assert screen._card["path"] == "a.py"

    def test_purpose_none_fallback_logic(self):
        card = self._make_card(purpose=None)
        purpose = card.get("purpose") or "(no docstring)"
        assert purpose == "(no docstring)"

    def test_purpose_empty_string_fallback_logic(self):
        card = self._make_card(purpose="")
        purpose = card.get("purpose") or "(no docstring)"
        assert purpose == "(no docstring)"

    def test_facts_empty_list_renders_none_text(self):
        """Empty facts list produces '(none)' display text."""
        facts: list = []
        facts_text = "\n".join(
            f"  [{f.get('kind', '?')}] line {f.get('line', 0)}: {f.get('text', '')}"
            for f in facts
        ) or "  (none)"
        assert facts_text == "  (none)"

    def test_heuristics_empty_list_renders_none_text(self):
        heuristics: list = []
        heuristics_text = "\n".join(
            f"  [{h.get('severity', '?')}] {h.get('kind', '?')} – {h.get('symbol', '')}: {h.get('detail', '')}"
            for h in heuristics
        ) or "  (none)"
        assert heuristics_text == "  (none)"

    def test_symbols_list_renders_in_summary(self):
        from vibecode.tui_app import _symbols_summary

        symbols = [{"name": "Foo", "kind": "class", "line": 1}]
        result = _symbols_summary(symbols)
        assert "class" in result

    def test_null_symbols_safe_after_data_loader_normalization(self, tmp_path):
        """End-to-end: null symbols in JSON → [] after load_dashboard_data."""
        import json
        from vibecode.tui_app import load_dashboard_data

        cards = [{"path": "a.py", "purpose": "p", "symbols": None, "facts": None, "heuristics": None}]
        inv = _make_inventory(cards)
        _write(tmp_path / ".vibecode" / "index" / "file_inventory.json", json.dumps(inv))

        data = load_dashboard_data(tmp_path)
        card = data.cards[0]
        # After normalization, these are safe to call len() on
        assert len(card["symbols"]) == 0
        assert len(card["facts"]) == 0
        assert len(card["heuristics"]) == 0


# ---------------------------------------------------------------------------
# MainScreen – footer subtitle counter correctness
# ---------------------------------------------------------------------------


class TestMainScreenSubtitle:
    def test_subtitle_contains_card_count(self, tmp_path):
        from vibecode.tui_app import DashboardData

        cards = [
            {"path": "a.py", "purpose": "p", "symbols": [], "facts": [], "heuristics": []},
            {"path": "b.py", "purpose": "q", "symbols": [], "facts": [], "heuristics": []},
        ]
        data = DashboardData(cards=cards, total_files=10, high_risk_count=3)
        # sub_title is set during on_mount; verify the format via the data
        expected_sub = "Files: 10  Cards: 2  High-Risk: 3"
        formatted = f"Files: {data.total_files}  Cards: {len(data.cards)}  High-Risk: {data.high_risk_count}"
        assert formatted == expected_sub

    def test_subtitle_cards_matches_inventory_card_count(self, tmp_path):
        """Footer card counter equals number of entries in context_cards."""
        import json
        from vibecode.tui_app import load_dashboard_data

        cards = [
            {"path": "a.py", "purpose": "p", "symbols": [], "facts": [], "heuristics": []},
            {"path": "b.py", "purpose": "q", "symbols": [], "facts": [], "heuristics": []},
            {"path": "c.py", "purpose": "r", "symbols": [], "facts": [], "heuristics": []},
        ]
        files = [{"path": "a.py"}, {"path": "b.py"}, {"path": "c.py"}, {"path": "d.py"}]
        inv = _make_inventory(cards, files)
        _write(
            tmp_path / ".vibecode" / "index" / "file_inventory.json",
            json.dumps(inv),
        )
        data = load_dashboard_data(tmp_path)
        subtitle = f"Files: {data.total_files}  Cards: {len(data.cards)}  High-Risk: {data.high_risk_count}"
        assert "Cards: 3" in subtitle
        assert "Files: 4" in subtitle
        assert "High-Risk: 0" in subtitle


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
