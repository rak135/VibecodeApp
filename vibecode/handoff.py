"""Handoff file validation for .vibecode/handoff/{NOW,NEXT,BLOCKERS}.md."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from vibecode.git_state import inspect_git_state
from vibecode.paths import to_posix_str


@dataclass(frozen=True)
class HandoffIssue:
    file: str
    message: str


@dataclass
class HandoffResult:
    root: Path
    issues: list[HandoffIssue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return len(self.issues) == 0

    @property
    def status(self) -> str:
        return "ok" if self.passed else "error"

    def as_dict(self) -> dict:
        return {
            "$schema": "vibecode/handoff-validation/v1",
            "root": to_posix_str(self.root),
            "status": self.status,
            "issues": [{"file": i.file, "message": i.message} for i in self.issues],
        }


# Placeholder phrases that indicate the file was never filled in.
_PLACEHOLDER_PATTERNS: tuple[str, ...] = (
    "TODO",
    "TBD",
    "placeholder",
    "<!--",
)


def _read_handoff_file(root: Path, rel_path: str) -> str | None:
    """Read a handoff file, returning None if it does not exist."""
    path = root / rel_path
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def _lines_of(content: str) -> list[str]:
    return content.splitlines()


def _has_placeholder(content: str) -> bool:
    upper = content.upper()
    return any(pat.upper() in upper for pat in _PLACEHOLDER_PATTERNS)


def _has_empty_bullets(content: str) -> bool:
    for line in _lines_of(content):
        stripped = line.strip()
        # A bullet line with no content after the marker: "-", "*", etc.
        if stripped in ("-", "*"):
            return True
    return False


def _is_heading_only(content: str) -> bool:
    """Return True if the file contains only a heading line and nothing else."""
    non_empty = [line for line in _lines_of(content) if line.strip()]
    if len(non_empty) != 1:
        return False
    return non_empty[0].strip().startswith("#")


_ARCHITECTURE_PREFIX = ".vibecode/architecture/"
_HANDOFF_PATHS = (
    ".vibecode/handoff/NOW.md",
    ".vibecode/handoff/NEXT.md",
    ".vibecode/handoff/BLOCKERS.md",
)


def _is_architecture_doc(path: str) -> bool:
    return path.startswith(_ARCHITECTURE_PREFIX) and path.endswith(".md")


def _is_handoff_or_history(path: str) -> bool:
    if path in _HANDOFF_PATHS:
        return True
    return (
        path.startswith(".vibecode/history/")
        and path.endswith(".md")
        and "/" not in path.removeprefix(".vibecode/history/")
    )


def validate_handoff_files(
    root: Path,
    *,
    diff: Iterable[str] = (),
) -> HandoffResult:
    """Validate the three handoff files for empty/placeholder/useless content.

    Rules:
    - ``NOW.md`` must contain concrete current state, not only a heading.
    - ``NEXT.md`` must contain concrete next steps, not only a heading.
    - ``BLOCKERS.md`` must say either no hard blocker or list concrete blockers.
    - Placeholder phrases (TODO, TBD, placeholder, HTML comments) fail.
    - Empty bullets (``- `` with no text) fail.
    - Heading-only content (just ``# Title`` with no body) fails.
    - If any ``.vibecode/architecture/*.md`` file appears in *diff*, at least one
      handoff or history file must also appear in *diff* (architecture truth
      changes must be recorded alongside).
    """
    result = HandoffResult(root=root)

    _validate_single(result, root, "NOW.md", "now")
    _validate_single(result, root, "NEXT.md", "next")
    _validate_single(result, root, "BLOCKERS.md", "blockers")

    diff_paths = tuple(diff)
    _validate_architecture_change_recorded(result, diff_paths)

    return result


def _validate_architecture_change_recorded(
    result: HandoffResult,
    diff_paths: tuple[str, ...],
) -> None:
    architecture_changes = [p for p in diff_paths if _is_architecture_doc(p)]
    if not architecture_changes:
        return

    has_handoff_or_history = any(
        _is_handoff_or_history(p) for p in diff_paths
    )
    if has_handoff_or_history:
        return

    for path in architecture_changes:
        result.issues.append(
            HandoffIssue(
                file=path,
                message=(
                    f"Architecture file '{path}' changed; update "
                    f".vibecode/handoff/NOW.md or add a summary to "
                    f".vibecode/history/*.md to record the change."
                ),
            )
        )


def _validate_single(result: HandoffResult, root: Path, filename: str, label: str) -> None:
    rel = f".vibecode/handoff/{filename}"
    content = _read_handoff_file(root / ".vibecode" / "handoff", filename)

    if content is None:
        result.issues.append(HandoffIssue(file=rel, message=f"{filename} is missing"))
        return

    if _has_placeholder(content):
        result.issues.append(
            HandoffIssue(
                file=rel,
                message=f"{filename} contains placeholder text (TODO, TBD, placeholder, or HTML comment)",
            )
        )

    if _has_empty_bullets(content):
        result.issues.append(
            HandoffIssue(
                file=rel,
                message=f"{filename} contains empty bullet points",
            )
        )

    if _is_heading_only(content):
        result.issues.append(
            HandoffIssue(
                file=rel,
                message=f"{filename} contains only a heading with no body content",
            )
        )


def _strip_heading_and_comments(content: str) -> str:
    """Return content with top-level headings and HTML comment lines removed."""
    lines = []
    for line in _lines_of(content):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if stripped.startswith("<!--") and stripped.endswith("-->"):
            continue
        lines.append(line)
    return "\n".join(lines)


def cmd_handoff_check(args) -> int:
    """CLI entry point for ``vibecode handoff-check``."""
    repo_root: Path = Path(args.repo_root).resolve()
    write_json: bool = getattr(args, "json", False)

    if not repo_root.is_dir():
        print(f"Error: Repository root does not exist: {repo_root}", file=sys.stderr)
        return 1

    # Get git diff (changed file paths) including untracked new files
    git_state = inspect_git_state(repo_root)
    if not git_state.is_git_repo:
        print("Error: not a git repository.", file=sys.stderr)
        return 1
    diff_paths = git_state.diff_name_only + git_state.untracked_paths

    result = validate_handoff_files(repo_root, diff=diff_paths)

    if write_json:
        out_dir = repo_root / ".vibecode" / "current"
        out_dir.mkdir(parents=True, exist_ok=True)
        report_path = out_dir / "handoff_check.json"
        report_path.write_text(
            json.dumps(result.as_dict(), indent=2) + "\n", encoding="utf-8"
        )

    if result.passed:
        print("Handoff check passed.")
        return 0

    print(f"Handoff check failed ({len(result.issues)} issue(s)):", file=sys.stderr)
    for issue in result.issues:
        print(f"  • {issue.file}: {issue.message}", file=sys.stderr)
    return 1