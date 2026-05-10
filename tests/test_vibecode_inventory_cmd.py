"""Tests for the `vibecode inventory` CLI command."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, content: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _init_repo(repo: Path, project_id: str = "testproj") -> None:
    """Create a minimal .vibecode project structure."""
    vdir = repo / ".vibecode"
    (vdir / "checks").mkdir(parents=True, exist_ok=True)
    (vdir / "index").mkdir(parents=True, exist_ok=True)
    (vdir / "project.yaml").write_text(
        f"project:\n  id: {project_id}\n  name: Test\n  root: .\n",
        encoding="utf-8",
    )


def _args(repo: Path) -> SimpleNamespace:
    return SimpleNamespace(repo_root=str(repo))


# ---------------------------------------------------------------------------
# cmd_inventory – basic behaviour
# ---------------------------------------------------------------------------


class TestCmdInventoryBasic:
    def test_returns_zero_on_success(self, tmp_path):
        _init_repo(tmp_path)
        _write(tmp_path / "src" / "app.py", '"""App module."""\ndef run(): pass\n')
        from vibecode.indexer import cmd_inventory

        rc = cmd_inventory(_args(tmp_path))
        assert rc == 0

    def test_writes_file_inventory(self, tmp_path):
        _init_repo(tmp_path)
        _write(tmp_path / "main.py", "x = 1\n")
        from vibecode.indexer import cmd_inventory

        cmd_inventory(_args(tmp_path))
        inv_path = tmp_path / ".vibecode" / "index" / "file_inventory.json"
        assert inv_path.exists()

    def test_writes_risk_report(self, tmp_path):
        _init_repo(tmp_path)
        _write(tmp_path / "main.py", "x = 1\n")
        from vibecode.indexer import cmd_inventory

        cmd_inventory(_args(tmp_path))
        rr_path = tmp_path / ".vibecode" / "index" / "risk_report.json"
        assert rr_path.exists()

    def test_no_project_yaml_returns_one(self, tmp_path):
        from vibecode.indexer import cmd_inventory

        rc = cmd_inventory(_args(tmp_path))
        assert rc == 1


# ---------------------------------------------------------------------------
# cmd_inventory – file_inventory.json content
# ---------------------------------------------------------------------------


class TestCmdInventoryFileInventory:
    def _run(self, repo: Path) -> dict:
        from vibecode.indexer import cmd_inventory

        cmd_inventory(_args(repo))
        return json.loads(
            (repo / ".vibecode" / "index" / "file_inventory.json").read_text(encoding="utf-8")
        )

    def test_has_context_cards_key(self, tmp_path):
        _init_repo(tmp_path)
        _write(tmp_path / "mod.py", '"""Mod."""\n')
        data = self._run(tmp_path)
        assert "context_cards" in data

    def test_context_cards_covers_python_files(self, tmp_path):
        _init_repo(tmp_path)
        _write(tmp_path / "alpha.py", '"""Alpha."""\n')
        _write(tmp_path / "beta.py", '"""Beta."""\n')
        _write(tmp_path / "README.md", "# readme")
        data = self._run(tmp_path)
        card_paths = {c["path"] for c in data["context_cards"]}
        assert "alpha.py" in card_paths
        assert "beta.py" in card_paths
        # non-Python file must not appear in context_cards
        assert "README.md" not in card_paths

    def test_card_has_purpose_field(self, tmp_path):
        _init_repo(tmp_path)
        _write(tmp_path / "mod.py", '"""My module docstring."""\ndef f(): pass\n')
        data = self._run(tmp_path)
        card = next(c for c in data["context_cards"] if c["path"] == "mod.py")
        assert "purpose" in card
        assert card["purpose"] == "My module docstring."

    def test_card_purpose_none_for_no_docstring(self, tmp_path):
        _init_repo(tmp_path)
        _write(tmp_path / "util.py", "x = 42\n")
        data = self._run(tmp_path)
        card = next(c for c in data["context_cards"] if c["path"] == "util.py")
        assert card["purpose"] is None

    def test_card_symbols_are_dicts(self, tmp_path):
        _init_repo(tmp_path)
        _write(tmp_path / "mod.py", "class MyClass:\n    pass\ndef my_func():\n    pass\n")
        data = self._run(tmp_path)
        card = next(c for c in data["context_cards"] if c["path"] == "mod.py")
        symbols = card["symbols"]
        assert isinstance(symbols, list)
        for s in symbols:
            assert "name" in s
            assert "kind" in s
            assert "line" in s

    def test_card_symbols_kinds(self, tmp_path):
        _init_repo(tmp_path)
        _write(tmp_path / "mod.py", "class Foo:\n    pass\ndef bar():\n    pass\n")
        data = self._run(tmp_path)
        card = next(c for c in data["context_cards"] if c["path"] == "mod.py")
        kinds = {s["kind"] for s in card["symbols"]}
        assert "class" in kinds
        assert "function" in kinds

    def test_card_has_content_snippet(self, tmp_path):
        _init_repo(tmp_path)
        content = '"""Docstring."""\n' + "x = 1\n" * 50
        _write(tmp_path / "mod.py", content)
        data = self._run(tmp_path)
        card = next(c for c in data["context_cards"] if c["path"] == "mod.py")
        assert "content_snippet" in card
        assert card["content_snippet"] == content[:200]
        assert len(card["content_snippet"]) == 200

    def test_card_has_facts_and_heuristics(self, tmp_path):
        _init_repo(tmp_path)
        _write(tmp_path / "mod.py", "# TODO: fix me\ndef f(): pass\n")
        data = self._run(tmp_path)
        card = next(c for c in data["context_cards"] if c["path"] == "mod.py")
        assert isinstance(card["facts"], list)
        assert isinstance(card["heuristics"], list)
        assert any(f["kind"] == "todo" for f in card["facts"])

    def test_heuristic_has_severity(self, tmp_path):
        _init_repo(tmp_path)
        _write(tmp_path / "mod.py", "def big(a, b, c, d, e, f, g): pass\n")
        data = self._run(tmp_path)
        card = next(c for c in data["context_cards"] if c["path"] == "mod.py")
        item = next(h for h in card["heuristics"] if h["kind"] == "high_param_count")
        assert "severity" in item
        assert item["severity"] == "medium"


# ---------------------------------------------------------------------------
# cmd_inventory – risk_report.json content
# ---------------------------------------------------------------------------


class TestCmdInventoryRiskReport:
    def _run(self, repo: Path) -> dict:
        from vibecode.indexer import cmd_inventory

        cmd_inventory(_args(repo))
        return json.loads(
            (repo / ".vibecode" / "index" / "risk_report.json").read_text(encoding="utf-8")
        )

    def test_risk_report_schema(self, tmp_path):
        _init_repo(tmp_path)
        data = self._run(tmp_path)
        assert data["$schema"] == "vibecode/risk-report/v1"

    def test_risk_report_has_files(self, tmp_path):
        _init_repo(tmp_path)
        _write(tmp_path / "mod.py", "x = 1\n")
        data = self._run(tmp_path)
        assert isinstance(data["files"], list)

    def test_risk_report_entry_has_facts_and_heuristics(self, tmp_path):
        _init_repo(tmp_path)
        _write(tmp_path / "mod.py", "# TODO: do stuff\nx = 1\n")
        data = self._run(tmp_path)
        entry = next((f for f in data["files"] if f["path"] == "mod.py"), None)
        assert entry is not None
        assert "facts" in entry
        assert "heuristics" in entry
        assert any(f["kind"] == "todo" for f in entry["facts"])

    def test_risk_report_heuristic_has_severity(self, tmp_path):
        _init_repo(tmp_path)
        _write(tmp_path / "mod.py", "def big(a, b, c, d, e, f, g): pass\n")
        data = self._run(tmp_path)
        entry = next((f for f in data["files"] if f["path"] == "mod.py"), None)
        assert entry is not None
        h = next((x for x in entry["heuristics"] if x["kind"] == "high_param_count"), None)
        assert h is not None
        assert h["severity"] == "medium"


# ---------------------------------------------------------------------------
# cmd_inventory – via CLI main()
# ---------------------------------------------------------------------------


class TestCmdInventoryViaCLI:
    def test_cli_inventory_command_registered(self, tmp_path):
        _init_repo(tmp_path)
        _write(tmp_path / "mod.py", '"""Module."""\ndef f(): pass\n')
        from vibecode.cli import main

        rc = main(["inventory", str(tmp_path)])
        assert rc == 0

    def test_cli_inventory_writes_artifacts(self, tmp_path):
        _init_repo(tmp_path)
        _write(tmp_path / "mod.py", "x = 1\n")
        from vibecode.cli import main

        main(["inventory", str(tmp_path)])
        assert (tmp_path / ".vibecode" / "index" / "file_inventory.json").exists()
        assert (tmp_path / ".vibecode" / "index" / "risk_report.json").exists()

    def test_cli_inventory_help_exits_zero(self, tmp_path):
        from vibecode.cli import main

        with pytest.raises(SystemExit) as exc_info:
            main(["inventory", "--help"])
        assert exc_info.value.code == 0
