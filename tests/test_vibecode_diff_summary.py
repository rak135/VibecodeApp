"""Tests for vibecode diff summary (vibecode.diff_summary).

Covers categorisation, change detection, protected path detection,
next-action suggestions, and JSON/serialization output.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from vibecode.diff_summary import (
    DiffSummary,
    FileChange,
    diff_summarise,
)
from vibecode.git_state import GitState, StatusPath
from vibecode.guard import _is_generated_runtime_path, _is_source_path, _is_test_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _status(
    path: str,
    index: str = "M",
    worktree: str = " ",
) -> StatusPath:
    """Shortcut to build a StatusPath for tests."""
    return StatusPath(path=path, index_status=index, worktree_status=worktree)


def _git_state(
    changed_paths: list[str] | None = None,
    untracked_paths: list[str] | None = None,
    status_paths: list[StatusPath] | None = None,
    is_git_repo: bool = True,
) -> GitState:
    """Build a GitState for testing.

    If status_paths is not given, it is synthesised from changed_paths.
    """
    if status_paths is None:
        sps: list[StatusPath] = []
        for p in changed_paths or []:
            sps.append(_status(p))
        for p in untracked_paths or []:
            sps.append(_status(p, index="?", worktree="?"))
        status_paths = sps

    return GitState(
        is_git_repo=is_git_repo,
        status_paths=tuple(status_paths),
        changed_paths=tuple(changed_paths or []),
        untracked_paths=tuple(untracked_paths or []),
        staged_paths=tuple(
            sp.path for sp in status_paths if sp.staged
        ),
        unstaged_paths=tuple(
            sp.path for sp in status_paths if sp.unstaged
        ),
        diff_name_only=tuple(changed_paths or []),
    )


# ---------------------------------------------------------------------------
# FileChange
# ---------------------------------------------------------------------------


class TestFileChange:
    def test_as_dict(self):
        fc = FileChange(path="src/app.py", status="modified", category="source")
        d = fc.as_dict()
        assert d == {"path": "src/app.py", "status": "modified", "category": "source"}


# ---------------------------------------------------------------------------
# DiffSummary — as_dict
# ---------------------------------------------------------------------------


class TestDiffSummaryAsDict:
    def test_empty_summary(self):
        ds = DiffSummary()
        d = ds.as_dict()
        assert d["changed_files"] == []
        assert d["added_files"] == []
        assert d["deleted_files"] == []
        assert d["categories"]["source"] == []
        assert d["protected_path_touches"] == []
        assert d["has_generated_runtime_changes"] is False

    def test_includes_schema_version(self):
        ds = DiffSummary()
        assert ds.as_dict()["$schema"] == "vibecode/diff-summary/v1"

    def test_populated_summary(self):
        ds = DiffSummary(
            changed_files=(
                FileChange(path="src/app.py", status="modified", category="source"),
                FileChange(path="tests/test_app.py", status="added", category="test"),
            ),
            modified_files=("src/app.py",),
            added_files=("tests/test_app.py",),
            source_files=("src/app.py",),
            test_files=("tests/test_app.py",),
        )
        d = ds.as_dict()
        assert len(d["changed_files"]) == 2
        assert d["modified_files"] == ["src/app.py"]
        assert d["added_files"] == ["tests/test_app.py"]
        assert d["categories"]["source"] == ["src/app.py"]
        assert d["categories"]["test"] == ["tests/test_app.py"]


# ---------------------------------------------------------------------------
# DiffSummary — as_text
# ---------------------------------------------------------------------------


class TestDiffSummaryAsText:
    def test_no_changes(self):
        ds = DiffSummary()
        text = ds.as_text()
        assert "No changes detected." in text

    def test_modified_and_added(self):
        ds = DiffSummary(
            changed_files=(
                FileChange(path="src/app.py", status="modified", category="source"),
                FileChange(path="README.md", status="added", category="docs"),
            ),
            modified_files=("src/app.py",),
            added_files=("README.md",),
            doc_files=("README.md",),
            source_files=("src/app.py",),
        )
        text = ds.as_text()
        assert "~ src/app.py" in text
        assert "+ README.md" in text
        assert "Modified (1):" in text
        assert "Added (1):" in text
        assert "Source:   src/app.py" in text
        assert "Docs:     README.md" in text

    def test_deleted_files(self):
        ds = DiffSummary(
            deleted_files=("old_module.py",),
            changed_files=(
                FileChange(path="old_module.py", status="deleted", category="source"),
            ),
        )
        text = ds.as_text()
        assert "- old_module.py" in text
        assert "Deleted (1):" in text

    def test_protected_path_touches_shown(self):
        ds = DiffSummary(
            changed_files=(
                FileChange(
                    path=".vibecode/architecture/OVERVIEW.md",
                    status="modified",
                    category="config",
                ),
            ),
            protected_path_touches=(".vibecode/architecture/OVERVIEW.md",),
        )
        text = ds.as_text()
        assert "Protected path touches:" in text
        assert "! .vibecode/architecture/OVERVIEW.md" in text

    def test_generated_runtime_warning(self):
        ds = DiffSummary(
            changed_files=(
                FileChange(
                    path=".vibecode/current/context_pack.md",
                    status="modified",
                    category="generated",
                ),
            ),
            generated_files=(".vibecode/current/context_pack.md",),
            has_generated_runtime_changes=True,
        )
        text = ds.as_text()
        assert "WARNING: Generated/runtime files were modified." in text

    def test_suggested_next_action(self):
        ds = DiffSummary(
            changed_files=(
                FileChange(path="src/app.py", status="modified", category="source"),
            ),
            modified_files=("src/app.py",),
            source_files=("src/app.py",),
            suggested_next_action="Review changes and commit.",
        )
        text = ds.as_text()
        assert "Next: Review changes and commit." in text


# ---------------------------------------------------------------------------
# diff_summarise — no changes
# ---------------------------------------------------------------------------


class TestDiffSummariseNoChanges:
    def test_both_none(self):
        result = diff_summarise(None, None)
        assert result.changed_files == ()
        assert result.suggested_next_action == "No action needed."

    def test_both_empty(self):
        pre = _git_state(changed_paths=[])
        post = _git_state(changed_paths=[])
        result = diff_summarise(pre, post)
        assert result.changed_files == ()

    def test_same_state(self):
        paths = ["src/app.py"]
        pre = _git_state(changed_paths=paths)
        post = _git_state(changed_paths=paths)
        # Since post-state paths overlap pre-state, no *new* changes
        result = diff_summarise(pre, post)
        # Paths exist in pre_changed, so they are not considered new changes
        assert result.changed_files == ()


# ---------------------------------------------------------------------------
# diff_summarise — new changes detected
# ---------------------------------------------------------------------------


class TestDiffSummariseNewChanges:
    def test_single_source_modified(self):
        """A source file appearing only in post-state is a new modification."""
        pre = _git_state(changed_paths=[])
        post = _git_state(changed_paths=["src/app.py"])
        result = diff_summarise(pre, post)

        assert len(result.changed_files) == 1
        fc = result.changed_files[0]
        assert fc.path == "src/app.py"
        assert fc.category == "source"
        assert fc.status == "modified"
        assert result.source_files == ("src/app.py",)

    def test_single_test_added(self):
        pre = _git_state(changed_paths=[])
        post = _git_state(changed_paths=["tests/test_new.py"])
        result = diff_summarise(pre, post)

        assert len(result.changed_files) == 1
        fc = result.changed_files[0]
        assert fc.category == "test"

    def test_doc_file(self):
        pre = _git_state(changed_paths=[])
        post = _git_state(changed_paths=["docs/guide.md"])
        result = diff_summarise(pre, post)

        fc = result.changed_files[0]
        assert fc.category == "docs"
        assert fc.path == "docs/guide.md"

    def test_generated_runtime_file(self):
        pre = _git_state(changed_paths=[])
        post = _git_state(changed_paths=[".vibecode/current/context_pack.md"])
        result = diff_summarise(pre, post)

        fc = result.changed_files[0]
        assert fc.category == "generated"
        assert result.has_generated_runtime_changes is True

    def test_deleted_file(self):
        """A file that only shows up in post-state as deleted."""
        sp = StatusPath(path="old/util.py", index_status="D", worktree_status=" ")
        pre = _git_state(changed_paths=[])
        post = _git_state(changed_paths=["old/util.py"], status_paths=[sp])
        result = diff_summarise(pre, post)

        assert len(result.changed_files) == 1
        fc = result.changed_files[0]
        assert fc.status == "deleted"
        assert fc.path == "old/util.py"
        assert "old/util.py" in result.deleted_files

    def test_untracked_file_as_added(self):
        """An untracked file (?? status) reported as 'added'."""
        sp = StatusPath(path="new_module.py", index_status="?", worktree_status="?")
        pre = _git_state(changed_paths=[])
        post = _git_state(status_paths=[sp], untracked_paths=["new_module.py"])
        result = diff_summarise(pre, post)

        assert len(result.changed_files) == 1
        fc = result.changed_files[0]
        # Untracked files use ?? index but diff_summarise only knows about
        # changed_paths, so we add untracked separately.
        # For this test, add to both changed + untracked so post-state picks it up

    def test_multiple_files_mixed_categories(self):
        pre = _git_state(changed_paths=[])
        post = _git_state(changed_paths=[
            "src/module.py",
            "tests/test_module.py",
            "docs/notes.md",
            ".vibecode/current/session.json",
            "config.yaml",
        ])
        result = diff_summarise(pre, post)

        assert len(result.changed_files) == 5
        assert set(result.source_files) == {"src/module.py"}
        assert set(result.test_files) == {"tests/test_module.py"}
        assert set(result.doc_files) == {"docs/notes.md"}
        assert set(result.generated_files) == {".vibecode/current/session.json"}
        assert set(result.other_files) == {"config.yaml"}


# ---------------------------------------------------------------------------
# Protected path detection
# ---------------------------------------------------------------------------


class TestDiffSummariseProtectedPaths:
    def test_default_protected_paths_detected(self):
        """Files under .vibecode/architecture/, .vibecode/handoff/, etc."""
        pre = _git_state(changed_paths=[])
        post = _git_state(changed_paths=[
            ".vibecode/architecture/OVERVIEW.md",
            ".vibecode/handoff/NOW.md",
            ".vibecode/index/file_inventory.json",
            "README.md",
        ])
        result = diff_summarise(pre, post)

        protected = set(result.protected_path_touches)
        assert ".vibecode/architecture/OVERVIEW.md" in protected
        assert ".vibecode/handoff/NOW.md" in protected
        assert ".vibecode/index/file_inventory.json" in protected
        # README.md is treated as a protected path by the default rules
        assert "README.md" in protected

    def test_custom_protected_paths(self):
        """Additional protected paths passed by the caller."""
        pre = _git_state(changed_paths=[])
        post = _git_state(changed_paths=["pipeline.yml", "src/run.py"])
        result = diff_summarise(
            pre, post,
            known_protected_paths=["pipeline.yml"],
        )

        assert "pipeline.yml" in result.protected_path_touches
        assert "src/run.py" not in result.protected_path_touches

    def test_no_protected_touches(self):
        pre = _git_state(changed_paths=[])
        post = _git_state(changed_paths=["src/app.py", "tests/test_app.py"])
        result = diff_summarise(pre, post)

        # .vibecode/ paths not touched
        assert result.protected_path_touches == ()


# ---------------------------------------------------------------------------
# Next-action suggestions
# ---------------------------------------------------------------------------


class TestDiffSummariseNextAction:
    def test_no_changes_says_no_action(self):
        result = diff_summarise(None, None)
        assert result.suggested_next_action == "No action needed."

    def test_generated_files_suggest_review(self):
        pre = _git_state(changed_paths=[])
        post = _git_state(changed_paths=[".vibecode/current/context_pack.md"])
        result = diff_summarise(pre, post)
        assert "generated" in result.suggested_next_action.lower()

    def test_source_without_test_suggests_tests(self):
        pre = _git_state(changed_paths=[])
        post = _git_state(changed_paths=["src/new_module.py"])
        result = diff_summarise(pre, post)
        assert "tests" in result.suggested_next_action.lower()

    def test_protected_touch_suggests_review(self):
        pre = _git_state(changed_paths=[])
        post = _git_state(changed_paths=[".vibecode/architecture/OVERVIEW.md"])
        result = diff_summarise(pre, post)
        assert "scope" in result.suggested_next_action.lower() or "review" in result.suggested_next_action.lower()

    def test_source_with_test_suggests_review(self):
        pre = _git_state(changed_paths=[])
        post = _git_state(changed_paths=[
            "src/module.py",
            "tests/test_module.py",
        ])
        result = diff_summarise(pre, post)
        assert result.suggested_next_action == "Review changes and commit."


# ---------------------------------------------------------------------------
# Deduplication — renamed files from git status
# ---------------------------------------------------------------------------


class TestDiffSummariseDeduplication:
    def test_renamed_file_not_duplicated(self):
        """A renamed file appears twice in git status (old → new).

        Only the new path should appear in the diff summary.
        """
        old_sp = StatusPath(
            path="old_name.py", index_status="R", worktree_status=" "
        )
        new_sp = StatusPath(
            path="new_name.py", index_status="R", worktree_status=" "
        )
        pre = _git_state(changed_paths=["old_name.py"])
        post = _git_state(
            changed_paths=["new_name.py"],
            status_paths=[old_sp, new_sp],
        )
        result = diff_summarise(pre, post)

        # Only new_name.py should appear (pre_state had old_name.py)
        assert len(result.changed_files) == 1
        assert result.changed_files[0].path == "new_name.py"


# ---------------------------------------------------------------------------
# DiffSummary — category helpers (indirect tests via _categorise_path)
# ---------------------------------------------------------------------------


class TestCategorisationViaDiffSummarise:
    """Test path categorisation indirectly through diff_summarise."""

    def _check_category(self, path: str, expected: str):
        pre = _git_state(changed_paths=[])
        post = _git_state(changed_paths=[path])
        result = diff_summarise(pre, post)
        fc = result.changed_files[0]
        assert fc.category == expected, (
            f"Expected '{expected}' for '{path}', got '{fc.category}'"
        )

    def test_source_extensions(self):
        for ext in [".py", ".pyi", ".js", ".jsx", ".ts", ".tsx"]:
            self._check_category(f"src/file{ext}", "source")

    def test_test_patterns(self):
        self._check_category("tests/test_foo.py", "test")
        self._check_category("src/foo_test.py", "test")
        self._check_category("src/foo.test.ts", "test")

    def test_documentation_extensions(self):
        for ext in [".md", ".mdx", ".rst", ".txt"]:
            self._check_category(f"docs/doc{ext}", "docs")

    def test_readme_is_docs(self):
        self._check_category("README.md", "docs")

    def test_config_is_config(self):
        self._check_category(".vibecode/project.yaml", "config")
        self._check_category(".vibecode/checks/protected_paths.yaml", "config")

    def test_generated_runtime_is_generated(self):
        for p in [
            ".vibecode/current/context_pack.md",
            ".vibecode/generated/file.generated.py",
            ".vibecode/index/repo_tree.generated.json",
        ]:
            self._check_category(p, "generated")


# ---------------------------------------------------------------------------
# RunSummary integration — diff field accepted
# ---------------------------------------------------------------------------


class TestRunSummaryWithDiff:
    """Verify RunSummary carries the diff field through as_dict."""

    def test_diff_in_as_dict(self):
        diff = DiffSummary(
            changed_files=(
                FileChange(
                    path="src/app.py", status="modified", category="source"
                ),
            ),
            modified_files=("src/app.py",),
            source_files=("src/app.py",),
        )
        summary = SimpleNamespace(
            session_id="s1",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:02+00:00",
            platform="opencode",
            profile="safe",
            repo_root="/tmp",
            task="test",
            dirty=False,
            index_fresh=True,
            command="opencode",
            exit_code=0,
            stdout="",
            stderr="",
            agent_status="success",
            guard=None,
            checks=None,
            handoff=None,
            diff=diff,
            error=None,
            overall_status="success",
            as_dict=lambda self=None: None,
        )

        # Manually build what as_dict would do (since RunSummary has as_dict method)
        from vibecode.run import RunSummary
        rs = RunSummary(
            session_id="s1",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:02+00:00",
            platform="opencode",
            profile="safe",
            repo_root="/tmp",
            task="test",
            dirty=False,
            index_fresh=True,
            command="opencode",
            exit_code=0,
            stdout="",
            stderr="",
            agent_status="success",
            diff=diff,
        )
        data = rs.as_dict()
        assert "diff" in data
        assert data["diff"]["$schema"] == "vibecode/diff-summary/v1"
        assert len(data["diff"]["changed_files"]) == 1
        assert data["diff"]["changed_files"][0]["path"] == "src/app.py"

    def test_diff_absent_when_none(self):
        from vibecode.run import RunSummary
        rs = RunSummary(
            session_id="s1",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:02+00:00",
            platform="opencode",
            profile="safe",
            repo_root="/tmp",
            task="test",
            dirty=False,
            index_fresh=True,
            command="opencode",
            exit_code=-1,
            stdout="",
            stderr="",
            agent_status="failure",
            diff=None,
            error="test error",
        )
        data = rs.as_dict()
        assert "diff" not in data
        assert data["error"] == "test error"