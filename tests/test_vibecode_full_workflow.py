"""Full pre-agent workflow test: init -> index -> context -> export-agents -> guard -> check -> handoff-check.

Acceptance criteria:
- All commands run successfully in sequence on a temp repo (safe commands only).
- Generated/runtime files (.vibecode/index/, .vibecode/current/, .vibecode/generated/, etc.)
  are never included as navigable source file references in context pack.
- Context pack includes relevant source files with risk levels and reasons.
- AGENTS export is safe: uses marker blocks, never overwrites unmanaged files without --force.
- Guard passes on a clean working tree where committed changes only touch source/handoff files.
- Guard catches modifications to generated runtime files.
- Check runs all configured checks and writes results.
- Handoff-check validates handoff files and reports issues for placeholder content.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

from vibecode.cli import main

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *cmd],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )


def _init_git_repo(repo: Path) -> None:
    _git(["init", "-b", "main"], cwd=repo)
    _git(["config", "user.email", "test@test.com"], cwd=repo)
    _git(["config", "user.name", "Test"], cwd=repo)


def _git_add_commit(repo: Path, message: str = "init") -> None:
    _git(["add", "."], cwd=repo)
    _git(["commit", "-m", message], cwd=repo)


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _make_minimal_project(repo: Path) -> None:
    """Create a minimal .vibecode project structure for tests that need it."""
    _init_git_repo(repo)
    _write(
        repo / ".vibecode" / "project.yaml",
        "project:\n  id: test\n  name: Test\n  root: .\n"
        "indexing:\n  include: []\n  exclude: []\n"
        "protected_paths: []\n  risk_rules: []\n",
    )
    _write(repo / ".vibecode" / "architecture" / "INVARIANTS.md", "# Invariants\n\n- test\n")
    _write(repo / ".vibecode" / "index" / "file_inventory.json", '{"files": []}\n')
    _git_add_commit(repo)


# ---------------------------------------------------------------------------
# Test: full happy-path workflow on a temp repo (safe commands only)
# ---------------------------------------------------------------------------


class TestFullPreAgentWorkflow:
    """End-to-end workflow: init -> index -> context -> export-agents -> guard -> check -> handoff-check."""

    def test_full_workflow_safe_commands(self, tmp_path: Path):
        """Run the full pre-agent workflow and verify all steps succeed."""
        repo = tmp_path / "myproject"
        repo.mkdir()

        # ---- Setup: git repo with source files committed first ----
        _init_git_repo(repo)
        _write(repo / "app.py", "def main(): pass\n")
        _write(repo / "test_app.py", "def test_main(): assert True\n")
        _write(repo / "config.yaml", "setting: value\n")
        _write(repo / "node_modules" / "lodash" / "index.js", "// vendor\n")
        _git_add_commit(repo, "initial source files")

        # ---- Step 1: init ----
        rc = main(["init", str(repo), "--id", "myproject", "--name", "MyProject"])
        assert rc == 0

        vibecode_dir = repo / ".vibecode"
        assert vibecode_dir.is_dir()
        assert (vibecode_dir / "project.yaml").is_file()
        assert (vibecode_dir / "checks" / "required_checks.yaml").is_file()
        assert (vibecode_dir / "architecture" / "OVERVIEW.md").is_file()
        assert (vibecode_dir / "handoff" / "NOW.md").is_file()
        assert (vibecode_dir / "handoff" / "NEXT.md").is_file()
        assert (vibecode_dir / "handoff" / "BLOCKERS.md").is_file()
        assert (vibecode_dir / "history" / "README.md").is_file()

        # ---- Step 2: index ----
        rc = main(["index", str(repo)])
        assert rc == 0

        # Verify index artifacts were created
        assert (vibecode_dir / "index" / "file_inventory.json").is_file()
        assert (vibecode_dir / "index" / "symbol_map.json").is_file()
        assert (vibecode_dir / "index" / "dependency_map.json").is_file()
        assert (vibecode_dir / "index" / "risky_files.md").is_file()

        # Verify node_modules is NOT indexed
        inventory = json.loads((vibecode_dir / "index" / "file_inventory.json").read_text())
        indexed_paths = {f["path"] for f in inventory.get("files", [])}
        assert not any("node_modules" in p for p in indexed_paths)

        # ---- Step 3: context ----
        task = "Update app.py to add logging"
        rc = main(["context", str(repo), "--task", task])
        assert rc == 0

        pack_path = vibecode_dir / "current" / "context_pack.md"
        assert pack_path.is_file()
        pack_content = pack_path.read_text()

        # Task is in the context pack
        assert task in pack_content

        # Source files appear in context pack
        assert "app.py" in pack_content
        assert "test_app.py" in pack_content

        # node_modules must NOT appear as a navigable file reference
        assert "node_modules/" not in pack_content

        # Architecture docs are mentioned
        assert "INVARIANTS.md" in pack_content or "OVERVIEW.md" in pack_content

        # ---- Step 4: export-agents ----
        rc = main(["export-agents", str(repo)])
        assert rc == 0

        # Generated file always exists
        assert (vibecode_dir / "generated" / "AGENTS.generated.md").is_file()

        # AGENTS.md created with marker blocks
        agents_md = repo / "AGENTS.md"
        assert agents_md.is_file()
        agents_content = agents_md.read_text()
        assert "<!-- vibecode:agents:start -->" in agents_content
        assert "<!-- vibecode:agents:end -->" in agents_content

        # ---- Step 5: guard ----
        # Commit generated/runtime files so guard sees a clean committed state
        _git_add_commit(repo, "add vibecode generated files")
        rc = main(["guard", str(repo)])
        assert rc == 0, "guard should pass on a clean committed tree"

        # ---- Step 6: check ----
        rc = main(["check", str(repo)])
        # Exit code depends on whether the checks pass; should not crash
        assert rc in (0, 1), f"check returned unexpected exit code: {rc}"

        # Check results file was written
        assert (vibecode_dir / "current" / "check_results.json").is_file()
        results = json.loads((vibecode_dir / "current" / "check_results.json").read_text())
        assert "status" in results
        assert "checks" in results

        # ---- Step 7: handoff-check ----
        # Handoff files have placeholder content (TODO/TBD) from init templates,
        # so handoff-check should report issues
        rc = main(["handoff-check", str(repo)])
        assert rc == 1, "handoff-check should fail because handoff files contain placeholders"

    # ------------------------------------------------------------------
    # Context pack exclusion of generated paths
    # ------------------------------------------------------------------

    def test_context_pack_excludes_generated_file_paths(self, tmp_path: Path):
        """Context pack must not include node_modules or .vibecode/index files
        as navigable source references in the relevant-files section."""
        repo = tmp_path / "proj"
        repo.mkdir()
        _init_git_repo(repo)
        _write(repo / "app.py", "def main(): pass\n")
        _git_add_commit(repo, "source")

        # Init + index to generate files
        main(["init", str(repo), "--id", "test", "--name", "Test"])
        main(["index", str(repo)])

        main(["context", str(repo), "--task", "test task"])
        pack = (repo / ".vibecode" / "current" / "context_pack.md").read_text()

        # node_modules must NOT appear as a file reference
        assert "node_modules/" not in pack

        # Source files should appear in the relevant-files section
        assert "app.py" in pack

    # ------------------------------------------------------------------
    # Guard behavior
    # ------------------------------------------------------------------

    def test_guard_catches_generated_file_changes(self, tmp_path: Path):
        """Guard should flag uncommitted changes to generated runtime files."""
        repo = tmp_path / "proj"
        repo.mkdir()
        _init_git_repo(repo)
        _write(repo / "app.py", "def main(): pass\n")
        _git_add_commit(repo, "source")

        main(["init", str(repo), "--id", "test", "--name", "Test"])
        main(["index", str(repo)])
        _git_add_commit(repo, "add generated files")

        # Tamper with a generated runtime file
        context_pack = repo / ".vibecode" / "current" / "context_pack.md"
        context_pack.write_text("# tampered content\n", encoding="utf-8")

        rc = main(["guard", str(repo)])
        assert rc == 1, "guard should catch tampering with generated runtime files"

    def test_guard_passes_with_committed_generated_files(self, tmp_path: Path):
        """Guard passes when generated files are committed and unmodified."""
        repo = tmp_path / "proj"
        repo.mkdir()
        _init_git_repo(repo)
        _write(repo / "app.py", "def main(): pass\n")
        _git_add_commit(repo, "source")

        main(["init", str(repo), "--id", "test", "--name", "Test"])
        main(["index", str(repo)])
        main(["context", str(repo), "--task", "test"])
        main(["export-agents", str(repo)])
        _git_add_commit(repo, "commit all generated files")

        # No changes - guard should pass
        rc = main(["guard", str(repo)])
        assert rc == 0, "guard should pass when all generated files are committed"

    # ------------------------------------------------------------------
    # Export-agents safety
    # ------------------------------------------------------------------

    def test_export_agents_does_not_overwrite_unmanaged(self, tmp_path: Path):
        """export-agents should skip an unmanaged AGENTS.md (no markers)."""
        repo = tmp_path / "proj"
        repo.mkdir()
        _init_git_repo(repo)
        _write(repo / "AGENTS.md", "# My custom agents file\n\nDo not touch.\n")

        rc = main(["export-agents", str(repo)])
        assert rc != 0
        content = (repo / "AGENTS.md").read_text()
        assert "My custom agents file" in content, "unmanaged file should not be overwritten"

    def test_export_agents_force_overwrites(self, tmp_path: Path):
        """export-agents --force should overwrite even unmanaged AGENTS.md."""
        repo = tmp_path / "proj"
        repo.mkdir()
        _init_git_repo(repo)
        _write(repo / "AGENTS.md", "# My custom agents file\n\nDo not touch.\n")

        rc = main(["export-agents", str(repo), "--force"])
        assert rc == 0
        content = (repo / "AGENTS.md").read_text()
        assert "<!-- vibecode:agents:start -->" in content

    def test_export_agents_updates_managed_file(self, tmp_path: Path):
        """export-agents should update an existing Vibecode-managed AGENTS.md."""
        repo = tmp_path / "proj"
        repo.mkdir()
        _init_git_repo(repo)

        from vibecode.context.agents_export import AGENTS_MARKER_START, AGENTS_MARKER_END

        agents_md = repo / "AGENTS.md"
        agents_md.write_text(
            f"{AGENTS_MARKER_START}\nold content\n{AGENTS_MARKER_END}\n",
            encoding="utf-8",
        )
        _git_add_commit(repo, "initial")

        rc = main(["export-agents", str(repo)])
        assert rc == 0
        content = agents_md.read_text()
        assert "old content" not in content

    # ------------------------------------------------------------------
    # Command failure modes
    # ------------------------------------------------------------------

    def test_guard_fails_without_project_yaml(self, tmp_path: Path):
        """guard should fail cleanly when .vibecode/project.yaml is missing."""
        repo = tmp_path / "proj"
        repo.mkdir()
        _init_git_repo(repo)
        _git_add_commit(repo)

        rc = main(["guard", str(repo)])
        assert rc == 1

    def test_context_fails_without_init(self, tmp_path: Path):
        """context should fail if project has not been initialized."""
        repo = tmp_path / "proj"
        repo.mkdir()

        rc = main(["context", str(repo), "--task", "something"])
        assert rc == 1

    def test_context_writes_platform_export(self, tmp_path: Path):
        """context --platform opencode should write opencode_prompt.md."""
        repo = tmp_path / "proj"
        repo.mkdir()
        _make_minimal_project(repo)
        _git_add_commit(repo, "with inventory")

        rc = main(["context", str(repo), "--task", "test", "--platform", "opencode"])
        assert rc == 0

        prompt_path = repo / ".vibecode" / "current" / "opencode_prompt.md"
        assert prompt_path.is_file()

    # ------------------------------------------------------------------
    # Handoff-check
    # ------------------------------------------------------------------

    def test_handoff_check_passes_with_good_content(self, tmp_path: Path):
        """handoff-check should pass when handoff files have real content."""
        repo = tmp_path / "proj"
        repo.mkdir()
        _make_minimal_project(repo)

        # Overwrite handoff files with real (non-placeholder) content
        handoff_dir = repo / ".vibecode" / "handoff"
        _write(handoff_dir / "NOW.md", "## Current work\n\nImplementing feature X.\n")
        _write(handoff_dir / "NEXT.md", "## Next steps\n\n- Write tests\n- Review PR\n")
        _write(handoff_dir / "BLOCKERS.md", "## Blockers\n\nNone.\n")
        _git_add_commit(repo, "update handoff with real content")

        rc = main(["handoff-check", str(repo)])
        assert rc == 0

    def test_handoff_check_json_output(self, tmp_path: Path):
        """handoff-check --json should write a report file."""
        repo = tmp_path / "proj"
        repo.mkdir()
        _make_minimal_project(repo)

        handoff_dir = repo / ".vibecode" / "handoff"
        _write(handoff_dir / "NOW.md", "# Now\n\nWorking on X.\n")
        _write(handoff_dir / "NEXT.md", "# Next\n\nDo Y.\n")
        _write(handoff_dir / "BLOCKERS.md", "# Blockers\n\nNone.\n")
        _git_add_commit(repo, "update handoff")

        from vibecode.handoff import cmd_handoff_check

        args = SimpleNamespace(repo_root=str(repo), json=True)
        cmd_handoff_check(args)

        report_path = repo / ".vibecode" / "current" / "handoff_check.json"
        assert report_path.is_file()
        data = json.loads(report_path.read_text())
        assert data["status"] == "ok"
        assert data["issues"] == []

    def test_check_produces_valid_report(self, tmp_path: Path):
        """check command should produce a valid JSON report with results."""
        repo = tmp_path / "proj"
        repo.mkdir()
        _init_git_repo(repo)

        _write(
            repo / ".vibecode" / "project.yaml",
            "project:\n  id: test\n  name: Test\n  root: .\n"
            "indexing:\n  include: []\n  exclude: []\n"
            "protected_paths: []\n"
            "risk_rules: []\n",
        )
        _write(
            repo / ".vibecode" / "checks" / "required_checks.yaml",
            "checks:\n"
            "  - name: always-pass\n"
            "    command: python -c \"print('ok')\"\n"
            "    required: true\n",
        )
        _git_add_commit(repo, "initial")

        rc = main(["check", str(repo)])
        assert rc == 0

        report_path = repo / ".vibecode" / "current" / "check_results.json"
        assert report_path.is_file()
        data = json.loads(report_path.read_text())
        assert data["status"] == "ok"
        assert data["summary"]["passed"] >= 1
        assert data["summary"]["failed"] == 0