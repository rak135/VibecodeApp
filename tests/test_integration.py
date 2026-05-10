"""Integration tests: inventory generation, data loader, MCP server, and TUI data."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, content: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _init_repo(repo: Path, project_id: str = "integration-test") -> None:
    vdir = repo / ".vibecode"
    (vdir / "checks").mkdir(parents=True, exist_ok=True)
    (vdir / "index").mkdir(parents=True, exist_ok=True)
    (vdir / "project.yaml").write_text(
        f"project:\n  id: {project_id}\n  name: IntegrationTest\n  root: .\n",
        encoding="utf-8",
    )


def _seed_repo(repo: Path) -> None:
    """Create a minimal Python project for inventory scanning."""
    _init_repo(repo)
    _write(
        repo / "src" / "app.py",
        '"""Main application module."""\n\ndef run(host: str, port: int) -> None:\n    """Start the server."""\n    pass\n',
    )
    _write(
        repo / "src" / "utils.py",
        '"""Utility helpers."""\n\ndef helper(x, y, z, a, b, c, d) -> None:\n    """Too many params."""\n    pass\n',
    )
    _write(repo / "README.md", "# Integration Test Repo\n")


# ---------------------------------------------------------------------------
# data_loader – missing-data path
# ---------------------------------------------------------------------------


class TestLoadProjectDataMissing:
    def test_missing_inventory_sets_flag(self, tmp_path):
        from vibecode.data_loader import load_project_data

        data = load_project_data(tmp_path)
        assert data.inventory_missing is True

    def test_missing_risk_report_sets_flag(self, tmp_path):
        from vibecode.data_loader import load_project_data

        index_dir = tmp_path / ".vibecode" / "index"
        index_dir.mkdir(parents=True)
        inv = {
            "$schema": "vibecode/file-inventory/v1",
            "files": [],
            "context_cards": [],
        }
        (index_dir / "file_inventory.json").write_text(
            json.dumps(inv), encoding="utf-8"
        )

        data = load_project_data(tmp_path)
        assert data.inventory_missing is False
        assert data.risk_report_missing is True

    def test_empty_repo_returns_zero_counts(self, tmp_path):
        from vibecode.data_loader import load_project_data

        data = load_project_data(tmp_path)
        assert data.cards == []
        assert data.total_files == 0
        assert data.high_risk_count == 0

    def test_corrupt_json_returns_empty_and_not_missing(self, tmp_path, capsys):
        from vibecode.data_loader import load_project_data

        index_dir = tmp_path / ".vibecode" / "index"
        index_dir.mkdir(parents=True)
        (index_dir / "file_inventory.json").write_text("{bad json", encoding="utf-8")

        data = load_project_data(tmp_path)
        assert data.inventory_missing is False
        assert data.cards == []
        err = capsys.readouterr().err
        assert "Warning" in err


# ---------------------------------------------------------------------------
# data_loader – happy path with real inventory output
# ---------------------------------------------------------------------------


class TestLoadProjectDataWithInventory:
    def test_cards_populated_after_inventory(self, tmp_path):
        _seed_repo(tmp_path)
        from vibecode.indexer import cmd_inventory

        cmd_inventory(SimpleNamespace(repo_root=str(tmp_path)))

        from vibecode.data_loader import load_project_data

        data = load_project_data(tmp_path)
        assert data.inventory_missing is False
        assert data.risk_report_missing is False
        assert data.total_files > 0
        assert len(data.cards) > 0

    def test_null_list_fields_normalized(self, tmp_path):
        """Cards with null list fields are normalized to [] by load_project_data."""
        index_dir = tmp_path / ".vibecode" / "index"
        index_dir.mkdir(parents=True)
        inv = {
            "$schema": "vibecode/file-inventory/v1",
            "files": [{"path": "a.py"}],
            "context_cards": [
                {"path": "a.py", "purpose": "x", "symbols": None, "facts": None, "heuristics": None}
            ],
        }
        (index_dir / "file_inventory.json").write_text(json.dumps(inv), encoding="utf-8")
        (index_dir / "risk_report.json").write_text(
            json.dumps({"files": []}), encoding="utf-8"
        )

        from vibecode.data_loader import load_project_data

        data = load_project_data(tmp_path)
        card = data.cards[0]
        assert card["symbols"] == []
        assert card["facts"] == []
        assert card["heuristics"] == []

    def test_high_risk_count_matches_risk_report(self, tmp_path):
        _seed_repo(tmp_path)
        from vibecode.indexer import cmd_inventory

        cmd_inventory(SimpleNamespace(repo_root=str(tmp_path)))

        from vibecode.data_loader import load_project_data

        data = load_project_data(tmp_path)
        # Verify high_risk_count is consistent with the raw risk_report
        manual_count = 0
        for entry in data.risk_report.get("files", []):
            if entry.get("risk_level") == "high":
                manual_count += 1
            elif any(h.get("severity") == "high" for h in entry.get("heuristics", [])):
                manual_count += 1
        assert data.high_risk_count == manual_count


# ---------------------------------------------------------------------------
# MCP server – integration with generated inventory
# ---------------------------------------------------------------------------


class TestMCPServerIntegration:
    def test_server_loads_generated_inventory(self, tmp_path):
        _seed_repo(tmp_path)
        from vibecode.indexer import cmd_inventory

        cmd_inventory(SimpleNamespace(repo_root=str(tmp_path)))

        index_dir = tmp_path / ".vibecode" / "index"
        from vibecode.mcp_server import VibecodeServer

        vs = VibecodeServer(
            index_dir / "file_inventory.json",
            index_dir / "risk_report.json",
        )
        assert len(vs._cards) > 0

    def test_get_file_card_returns_content(self, tmp_path):
        _seed_repo(tmp_path)
        from vibecode.indexer import cmd_inventory

        cmd_inventory(SimpleNamespace(repo_root=str(tmp_path)))

        index_dir = tmp_path / ".vibecode" / "index"
        from vibecode.mcp_server import VibecodeServer

        vs = VibecodeServer(
            index_dir / "file_inventory.json",
            index_dir / "risk_report.json",
        )
        # Find a card path and request it
        path = next(iter(vs._cards))
        result = vs.get_file_card(path)
        assert path in result

    def test_find_symbol_run_found(self, tmp_path):
        _seed_repo(tmp_path)
        from vibecode.indexer import cmd_inventory

        cmd_inventory(SimpleNamespace(repo_root=str(tmp_path)))

        index_dir = tmp_path / ".vibecode" / "index"
        from vibecode.mcp_server import VibecodeServer

        vs = VibecodeServer(
            index_dir / "file_inventory.json",
            index_dir / "risk_report.json",
        )
        result = vs.find_symbol("run")
        assert "run" in result


# ---------------------------------------------------------------------------
# TUI data loader – integration with generated inventory
# ---------------------------------------------------------------------------


class TestDashboardDataIntegration:
    def test_dashboard_data_matches_project_data(self, tmp_path):
        _seed_repo(tmp_path)
        from vibecode.indexer import cmd_inventory

        cmd_inventory(SimpleNamespace(repo_root=str(tmp_path)))

        from vibecode.data_loader import load_project_data
        from vibecode.tui_app import load_dashboard_data

        project = load_project_data(tmp_path)
        dashboard = load_dashboard_data(tmp_path)

        assert dashboard.total_files == project.total_files
        assert dashboard.high_risk_count == project.high_risk_count
        assert len(dashboard.cards) == len(project.cards)


# ---------------------------------------------------------------------------
# CLI – missing-data prompt via subprocess
# ---------------------------------------------------------------------------


class TestCLIMissingDataPrompt:
    def test_serve_emits_hint_when_no_inventory(self, tmp_path):
        """cmd_serve prints an inventory hint to stderr when index is absent."""
        _init_repo(tmp_path)
        result = subprocess.run(
            [sys.executable, "-m", "vibecode.cli", "serve", str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert "vibecode inventory" in result.stderr
