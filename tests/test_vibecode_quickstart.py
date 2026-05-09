"""Tests for the documented quickstart workflow.

These tests mirror the scenario described in docs/QUICKSTART.md step-by-step
so that a documentation regression is detectable automatically.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture()
def example_repo(tmp_path: Path) -> Path:
    """A minimal repository that mirrors the quickstart example."""
    (tmp_path / "app.py").write_text(
        "def hello(name: str) -> str:\n    return f'Hello, {name}!'\n",
        encoding="utf-8",
    )
    (tmp_path / "test_app.py").write_text(
        "from app import hello\n\ndef test_hello():\n    assert hello('world') == 'Hello, world!'\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# Example Project\nA minimal example.\n", encoding="utf-8")
    return tmp_path


class TestQuickstartInit:
    """Step 1 — vibecode init."""

    def test_creates_vibecode_directory(self, example_repo: Path) -> None:
        from vibecode.project import cmd_init

        class _Args:
            repo_root = str(example_repo)
            project_id = "example_repo"
            project_name = None
            force = False

        rc = cmd_init(_Args())
        assert rc == 0
        assert (example_repo / ".vibecode").is_dir()

    def test_creates_project_yaml(self, example_repo: Path) -> None:
        from vibecode.project import cmd_init

        class _Args:
            repo_root = str(example_repo)
            project_id = "example_repo"
            project_name = None
            force = False

        cmd_init(_Args())
        project_yaml = example_repo / ".vibecode" / "project.yaml"
        assert project_yaml.is_file()
        assert "example_repo" in project_yaml.read_text(encoding="utf-8")

    def test_creates_architecture_templates(self, example_repo: Path) -> None:
        from vibecode.project import cmd_init

        class _Args:
            repo_root = str(example_repo)
            project_id = "example_repo"
            project_name = None
            force = False

        cmd_init(_Args())
        arch_dir = example_repo / ".vibecode" / "architecture"
        assert arch_dir.is_dir()
        for name in ("OVERVIEW.md", "INVARIANTS.md", "STRUCTURE.md", "MODULE_BOUNDARIES.md"):
            assert (arch_dir / name).is_file(), f"Missing {name}"

    def test_creates_handoff_files(self, example_repo: Path) -> None:
        from vibecode.project import cmd_init

        class _Args:
            repo_root = str(example_repo)
            project_id = "example_repo"
            project_name = None
            force = False

        cmd_init(_Args())
        handoff_dir = example_repo / ".vibecode" / "handoff"
        for name in ("NOW.md", "NEXT.md", "BLOCKERS.md"):
            assert (handoff_dir / name).is_file(), f"Missing {name}"

    def test_skips_existing_files_without_force(self, example_repo: Path) -> None:
        from vibecode.project import cmd_init

        class _Args:
            repo_root = str(example_repo)
            project_id = "example_repo"
            project_name = None
            force = False

        cmd_init(_Args())
        project_yaml = example_repo / ".vibecode" / "project.yaml"
        original = project_yaml.read_text(encoding="utf-8")
        project_yaml.write_text("# manual edit\n", encoding="utf-8")

        cmd_init(_Args())
        assert project_yaml.read_text(encoding="utf-8") == "# manual edit\n", (
            "init must not overwrite human-maintained files without --force"
        )

        project_yaml.write_text(original, encoding="utf-8")


class TestQuickstartIndex:
    """Step 2 — vibecode index."""

    def _init(self, repo: Path) -> None:
        from vibecode.project import cmd_init

        class _Args:
            repo_root = str(repo)
            project_id = "example_repo"
            project_name = None
            force = False

        cmd_init(_Args())

    def test_index_writes_file_inventory(self, example_repo: Path) -> None:
        self._init(example_repo)
        from vibecode.indexer import cmd_index

        class _Args:
            repo_root = str(example_repo)

        rc = cmd_index(_Args())
        assert rc == 0
        inventory = example_repo / ".vibecode" / "index" / "file_inventory.json"
        assert inventory.is_file()
        data = json.loads(inventory.read_text(encoding="utf-8"))
        assert "files" in data
        assert len(data["files"]) > 0

    def test_index_writes_symbol_map(self, example_repo: Path) -> None:
        self._init(example_repo)
        from vibecode.indexer import cmd_index

        class _Args:
            repo_root = str(example_repo)

        cmd_index(_Args())
        symbol_map = example_repo / ".vibecode" / "index" / "symbol_map.json"
        assert symbol_map.is_file()
        data = json.loads(symbol_map.read_text(encoding="utf-8"))
        assert "files" in data

    def test_index_writes_repo_tree(self, example_repo: Path) -> None:
        self._init(example_repo)
        from vibecode.indexer import cmd_index

        class _Args:
            repo_root = str(example_repo)

        cmd_index(_Args())
        repo_tree = example_repo / ".vibecode" / "index" / "repo_tree.generated.md"
        assert repo_tree.is_file()

    def test_index_writes_last_index_json(self, example_repo: Path) -> None:
        self._init(example_repo)
        from vibecode.indexer import cmd_index

        class _Args:
            repo_root = str(example_repo)

        cmd_index(_Args())
        last_index = example_repo / ".vibecode" / "current" / "last_index.json"
        assert last_index.is_file()
        record = json.loads(last_index.read_text(encoding="utf-8"))
        assert record.get("project_id") == "example_repo"
        assert "counts" in record

    def test_index_writes_run_log(self, example_repo: Path) -> None:
        self._init(example_repo)
        from vibecode.indexer import cmd_index

        class _Args:
            repo_root = str(example_repo)

        cmd_index(_Args())
        run_logs = list((example_repo / ".vibecode" / "logs" / "index_runs").glob("*.json"))
        assert len(run_logs) >= 1, "Expected at least one run log"


class TestQuickstartMap:
    """Step 4 — vibecode map."""

    def _init_and_index(self, repo: Path) -> None:
        from vibecode.project import cmd_init
        from vibecode.indexer import cmd_index

        class _InitArgs:
            repo_root = str(repo)
            project_id = "example_repo"
            project_name = None
            force = False

        class _IndexArgs:
            repo_root = str(repo)

        cmd_init(_InitArgs())
        cmd_index(_IndexArgs())

    def test_map_returns_zero(self, example_repo: Path, capsys) -> None:
        self._init_and_index(example_repo)
        from vibecode.project import cmd_map

        class _Args:
            repo_root = str(example_repo)

        rc = cmd_map(_Args())
        assert rc == 0

    def test_map_output_contains_project_id(self, example_repo: Path, capsys) -> None:
        self._init_and_index(example_repo)
        from vibecode.project import cmd_map

        class _Args:
            repo_root = str(example_repo)

        cmd_map(_Args())
        out = capsys.readouterr().out
        assert "example_repo" in out

    def test_map_output_contains_file_count(self, example_repo: Path, capsys) -> None:
        self._init_and_index(example_repo)
        from vibecode.project import cmd_map

        class _Args:
            repo_root = str(example_repo)

        cmd_map(_Args())
        out = capsys.readouterr().out
        assert "Files:" in out


class TestQuickstartContext:
    """Step 5 — vibecode context."""

    def _init_and_index(self, repo: Path) -> None:
        from vibecode.project import cmd_init
        from vibecode.indexer import cmd_index

        class _InitArgs:
            repo_root = str(repo)
            project_id = "example_repo"
            project_name = None
            force = False

        class _IndexArgs:
            repo_root = str(repo)

        cmd_init(_InitArgs())
        cmd_index(_IndexArgs())

    def test_context_writes_context_pack(self, example_repo: Path) -> None:
        self._init_and_index(example_repo)

        class _Args:
            context_arg = "Add error handling to the login flow"
            task_option = None
            task = None
            repo = str(example_repo)
            platform = None

        from vibecode.context import cmd_context

        rc = cmd_context(_Args())
        assert rc == 0
        pack = example_repo / ".vibecode" / "current" / "context_pack.md"
        assert pack.is_file()
        content = pack.read_text(encoding="utf-8")
        assert "Add error handling to the login flow" in content

    def test_context_pack_contains_task_section(self, example_repo: Path) -> None:
        self._init_and_index(example_repo)

        class _Args:
            context_arg = "Add error handling to the login flow"
            task_option = None
            task = None
            repo = str(example_repo)
            platform = None

        from vibecode.context import cmd_context

        cmd_context(_Args())
        content = (example_repo / ".vibecode" / "current" / "context_pack.md").read_text(encoding="utf-8")
        assert "## Current task" in content

    def test_context_pack_contains_relevant_files_section(self, example_repo: Path) -> None:
        self._init_and_index(example_repo)

        class _Args:
            context_arg = "Add error handling to the login flow"
            task_option = None
            task = None
            repo = str(example_repo)
            platform = None

        from vibecode.context import cmd_context

        cmd_context(_Args())
        content = (example_repo / ".vibecode" / "current" / "context_pack.md").read_text(encoding="utf-8")
        assert "## Relevant files" in content


class TestQuickstartOpenCodeExport:
    """Step 6 — vibecode context --platform opencode."""

    def _init_and_index(self, repo: Path) -> None:
        from vibecode.project import cmd_init
        from vibecode.indexer import cmd_index

        class _InitArgs:
            repo_root = str(repo)
            project_id = "example_repo"
            project_name = None
            force = False

        class _IndexArgs:
            repo_root = str(repo)

        cmd_init(_InitArgs())
        cmd_index(_IndexArgs())

    def test_opencode_export_writes_prompt_file(self, example_repo: Path) -> None:
        self._init_and_index(example_repo)

        class _Args:
            context_arg = "Add rate limiting to the auth endpoint"
            task_option = None
            task = None
            repo = str(example_repo)
            platform = "opencode"

        from vibecode.context import cmd_context

        rc = cmd_context(_Args())
        assert rc == 0
        prompt = example_repo / ".vibecode" / "current" / "opencode_prompt.md"
        assert prompt.is_file(), "opencode_prompt.md should be written when --platform opencode is used"

    def test_opencode_prompt_contains_pre_edit_instructions(self, example_repo: Path) -> None:
        self._init_and_index(example_repo)

        class _Args:
            context_arg = "Add rate limiting to the auth endpoint"
            task_option = None
            task = None
            repo = str(example_repo)
            platform = "opencode"

        from vibecode.context import cmd_context

        cmd_context(_Args())
        content = (example_repo / ".vibecode" / "current" / "opencode_prompt.md").read_text(encoding="utf-8")
        assert "Pre-edit instructions" in content

    def test_opencode_prompt_embeds_context_pack(self, example_repo: Path) -> None:
        self._init_and_index(example_repo)

        class _Args:
            context_arg = "Add rate limiting to the auth endpoint"
            task_option = None
            task = None
            repo = str(example_repo)
            platform = "opencode"

        from vibecode.context import cmd_context

        cmd_context(_Args())
        content = (example_repo / ".vibecode" / "current" / "opencode_prompt.md").read_text(encoding="utf-8")
        assert "Add rate limiting to the auth endpoint" in content


class TestQuickstartDocumentationExists:
    """Smoke tests confirming the documentation files are present."""

    def test_quickstart_doc_exists(self) -> None:
        quickstart = Path(__file__).parent.parent / "docs" / "QUICKSTART.md"
        assert quickstart.is_file(), "docs/QUICKSTART.md must exist"

    def test_quickstart_covers_opencode_note(self) -> None:
        quickstart = Path(__file__).parent.parent / "docs" / "QUICKSTART.md"
        content = quickstart.read_text(encoding="utf-8")
        assert "OpenCode runtime" in content or "does not launch OpenCode" in content, (
            "QUICKSTART.md must state that OpenCode runtime is not yet launched"
        )

    def test_quickstart_covers_all_commands(self) -> None:
        quickstart = Path(__file__).parent.parent / "docs" / "QUICKSTART.md"
        content = quickstart.read_text(encoding="utf-8")
        for cmd in ("init", "index", "validate", "map", "context", "export-agents"):
            assert cmd in content, f"QUICKSTART.md must document the '{cmd}' command"

    def test_quickstart_covers_vibecode_structure(self) -> None:
        quickstart = Path(__file__).parent.parent / "docs" / "QUICKSTART.md"
        content = quickstart.read_text(encoding="utf-8")
        assert ".vibecode/" in content
        assert "human-maintained" in content.lower()
        assert "generated" in content.lower()

    def test_docs_explain_agent_file_lifecycles(self) -> None:
        root = Path(__file__).parent.parent
        content = "\n".join(
            [
                (root / "README.md").read_text(encoding="utf-8"),
                (root / "docs" / "QUICKSTART.md").read_text(encoding="utf-8"),
            ]
        )
        assert "Root `AGENTS.md` is stable agent instruction" in content
        assert ".vibecode/current/context_pack.md` is task-specific runtime output" in content
        assert ".vibecode/generated/AGENTS.generated.md` is generated export output" in content
        assert "manual root `AGENTS.md` is not overwritten without `--force`" in content
        assert "generate a task-specific" in content

    def test_quickstart_uses_example_repo_placeholder(self) -> None:
        quickstart = Path(__file__).parent.parent / "docs" / "QUICKSTART.md"
        content = quickstart.read_text(encoding="utf-8")
        assert r"C:\path\to\example-repo" in content, (
            "QUICKSTART.md must use C:\\path\\to\\example-repo as the path placeholder"
        )
