"""Diff summary for post-run change reporting.

Compares pre-run and post-run git state to produce a structured,
human-readable summary of what the agent changed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

from vibecode.git_state import GitState, StatusPath
from vibecode.guard import (
    _is_documentation_path,
    _is_generated_runtime_path,
    _is_source_path,
    _is_test_path,
    _normalise_path,
)



@dataclass(frozen=True)
class FileChange:
    """A single file change between two git states."""

    path: str
    status: str  # "modified", "added", "deleted", "renamed"
    category: str  # "source", "test", "docs", "generated", "config", "other"

    def as_dict(self) -> dict:
        return {
            "path": self.path,
            "status": self.status,
            "category": self.category,
        }


@dataclass
class DiffSummary:
    """Structured summary of changes between two git states."""

    changed_files: tuple[FileChange, ...] = ()
    added_files: tuple[str, ...] = ()
    deleted_files: tuple[str, ...] = ()
    modified_files: tuple[str, ...] = ()
    source_files: tuple[str, ...] = ()
    test_files: tuple[str, ...] = ()
    doc_files: tuple[str, ...] = ()
    generated_files: tuple[str, ...] = ()
    config_files: tuple[str, ...] = ()
    other_files: tuple[str, ...] = ()
    protected_path_touches: tuple[str, ...] = ()
    has_generated_runtime_changes: bool = False
    suggested_next_action: str = ""

    def as_dict(self) -> dict:
        return {
            "$schema": "vibecode/diff-summary/v1",
            "changed_files": [c.as_dict() for c in self.changed_files],
            "added_files": list(self.added_files),
            "deleted_files": list(self.deleted_files),
            "modified_files": list(self.modified_files),
            "categories": {
                "source": list(self.source_files),
                "test": list(self.test_files),
                "docs": list(self.doc_files),
                "generated": list(self.generated_files),
                "config": list(self.config_files),
                "other": list(self.other_files),
            },
            "protected_path_touches": list(self.protected_path_touches),
            "has_generated_runtime_changes": self.has_generated_runtime_changes,
            "suggested_next_action": self.suggested_next_action,
        }

    def as_text(self) -> str:
        """Render a human-readable diff summary."""
        lines: list[str] = []

        if not self.changed_files:
            lines.append("No changes detected.")
            return "\n".join(lines)

        lines.append("=" * 50)
        lines.append("DIFF SUMMARY")
        lines.append("=" * 50)
        lines.append("")

        # Modified files
        if self.modified_files:
            lines.append(f"Modified ({len(self.modified_files)}):")
            for f in self.modified_files:
                lines.append(f"  ~ {f}")
            lines.append("")

        # Added files
        if self.added_files:
            lines.append(f"Added ({len(self.added_files)}):")
            for f in self.added_files:
                lines.append(f"  + {f}")
            lines.append("")

        # Deleted files
        if self.deleted_files:
            lines.append(f"Deleted ({len(self.deleted_files)}):")
            for f in self.deleted_files:
                lines.append(f"  - {f}")
            lines.append("")

        # Category summary
        lines.append("Categories:")
        if self.source_files:
            lines.append(f"  Source:   {', '.join(self.source_files)}")
        if self.test_files:
            lines.append(f"  Tests:    {', '.join(self.test_files)}")
        if self.doc_files:
            lines.append(f"  Docs:     {', '.join(self.doc_files)}")
        if self.generated_files:
            lines.append(f"  Generated:{', '.join(self.generated_files)}")
        if self.config_files:
            lines.append(f"  Config:   {', '.join(self.config_files)}")
        if self.other_files:
            lines.append(f"  Other:    {', '.join(self.other_files)}")
        if not any([self.source_files, self.test_files, self.doc_files,
                     self.generated_files, self.config_files, self.other_files]):
            lines.append("  (none categorised)")
        lines.append("")

        # Protected path touches
        if self.protected_path_touches:
            lines.append("Protected path touches:")
            for p in self.protected_path_touches:
                lines.append(f"  ! {p}")
            lines.append("")

        # Generated/runtime warning
        if self.has_generated_runtime_changes:
            lines.append("WARNING: Generated/runtime files were modified.")
            lines.append("")

        # Suggested next action
        if self.suggested_next_action:
            lines.append(f"Next: {self.suggested_next_action}")
            lines.append("")

        lines.append("=" * 50)
        return "\n".join(lines)


def _categorise_path(path: str) -> str:
    """Categorise a single path into source/test/docs/generated/config/other."""
    if _is_generated_runtime_path(path):
        return "generated"

    suffix = PurePosixPath(path).suffix.lower()

    # Config files
    if path.startswith(".vibecode/") and not path.startswith(".vibecode/index/"):
        return "config"
    if suffix in {".yaml", ".yml"} and path.startswith(".vibecode/"):
        return "config"

    # Source
    if _is_source_path(path):
        return "source"

    # Test
    if _is_test_path(path):
        return "test"

    # Documentation
    if _is_documentation_path(path):
        return "docs"

    return "other"


def _determine_next_action(
    changed_files: tuple[FileChange, ...],
    protected_touches: tuple[str, ...],
    has_generated: bool,
) -> str:
    """Suggest a next action based on the diff summary."""
    if not changed_files:
        return "No action needed."

    if has_generated:
        return "Review generated file changes and regenerate if needed."

    if protected_touches:
        return "Review protected path changes; ensure scope and tests."

    source_count = sum(1 for c in changed_files if c.category == "source")
    test_count = sum(1 for c in changed_files if c.category == "test")

    if source_count > 0 and test_count == 0:
        return "Source changed — consider adding or updating tests."

    return "Review changes and commit."


def diff_summarise(
    pre_state: GitState | None,
    post_state: GitState | None,
    *,
    repo_root: Path | None = None,
    known_protected_paths: Iterable[str] = (),
    known_source_paths: Iterable[str] = (),
) -> DiffSummary:
    """Compare pre-run and post-run git state and produce a diff summary.

    Parameters
    ----------
    pre_state:
        Git state captured before the agent ran (may be None).
    post_state:
        Git state captured after the agent ran (may be None).
    repo_root:
        Repository root for relative path display.
    known_protected_paths:
        Additional protected path patterns beyond defaults.
    known_source_paths:
        Paths known to be source files (for better categorisation).

    Returns
    -------
    DiffSummary
        Structured diff summary with categories and suggested action.
    """
    # Collect the pre-change baseline
    pre_changed: set[str] = set()
    if pre_state is not None:
        pre_changed = set(
            _normalise_path(p) for p in pre_state.changed_paths
        ) | set(_normalise_path(p) for p in pre_state.untracked_paths)

    # Collect the post-change state
    post_changed_paths: list[str] = []
    post_status_paths: dict[str, StatusPath] = {}
    if post_state is not None:
        for sp in post_state.status_paths:
            norm = _normalise_path(sp.path)
            post_changed_paths.append(norm)
            post_status_paths[norm] = sp

    # Deduplicate post paths (a renamed file appears twice in status)
    seen_origins: set[str] = set()
    deduped_paths: list[str] = []
    for p in post_changed_paths:
        if p in seen_origins:
            continue
        seen_origins.add(p)
        deduped_paths.append(p)

    changed: list[FileChange] = []
    added: list[str] = []
    deleted: list[str] = []
    modified: list[str] = []

    for path in deduped_paths:
        if path not in pre_changed:
            # New change relative to pre-run state
            sp = post_status_paths.get(path)
            if sp is not None and sp.deleted:
                status = "deleted"
                deleted.append(path)
            elif sp is not None and sp.untracked:
                status = "added"
                added.append(path)
            elif sp is not None and sp.staged and sp.unstaged:
                status = "modified"
                modified.append(path)
            elif sp is not None and sp.staged:
                status = "modified"
                modified.append(path)
            elif sp is not None and sp.unstaged:
                status = "modified"
                modified.append(path)
            else:
                status = "modified"
                modified.append(path)

            category = _categorise_path(path)
            changed.append(FileChange(path=path, status=status, category=category))

    # Categorise by domain
    source_files: list[str] = []
    test_files: list[str] = []
    doc_files: list[str] = []
    generated_files: list[str] = []
    config_files: list[str] = []
    other_files: list[str] = []

    for fc in changed:
        if fc.category == "source":
            source_files.append(fc.path)
        elif fc.category == "test":
            test_files.append(fc.path)
        elif fc.category == "docs":
            doc_files.append(fc.path)
        elif fc.category == "generated":
            generated_files.append(fc.path)
        elif fc.category == "config":
            config_files.append(fc.path)
        else:
            other_files.append(fc.path)

    # Check protected path touches
    protected_touches: list[str] = []
    all_default_prefixes = {
        ".vibecode/architecture/",
        ".vibecode/checks/",
        ".vibecode/handoff/",
        ".vibecode/index/",
        ".vibecode/current/",
        ".vibecode/generated/",
        ".vibecode/logs/",
        ".vibecode/runs/",
        ".vibecode/tmp/",
        ".vibecode/cache/",
        "README.md",
    }
    for fc in changed:
        if fc.path in known_protected_paths or fc.path.startswith(
            tuple(known_protected_paths)
        ):
            if fc.path not in protected_touches:
                protected_touches.append(fc.path)
        for prefix in all_default_prefixes:
            if fc.path == prefix or fc.path.startswith(prefix):
                if fc.path not in protected_touches:
                    protected_touches.append(fc.path)
                break

    # Check for generated/runtime changes
    has_generated = any(fc.category == "generated" for fc in changed)

    suggested = _determine_next_action(
        tuple(changed), tuple(protected_touches), has_generated
    )

    return DiffSummary(
        changed_files=tuple(changed),
        added_files=tuple(added),
        deleted_files=tuple(deleted),
        modified_files=tuple(modified),
        source_files=tuple(source_files),
        test_files=tuple(test_files),
        doc_files=tuple(doc_files),
        generated_files=tuple(generated_files),
        config_files=tuple(config_files),
        other_files=tuple(other_files),
        protected_path_touches=tuple(protected_touches),
        has_generated_runtime_changes=has_generated,
        suggested_next_action=suggested,
    )