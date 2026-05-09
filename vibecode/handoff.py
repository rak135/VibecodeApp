"""Handoff file validation for .vibecode/handoff/{NOW,NEXT,BLOCKERS}.md."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

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


def validate_handoff_files(root: Path) -> HandoffResult:
    """Validate the three handoff files for empty/placeholder/useless content.

    Rules:
    - ``NOW.md`` must contain concrete current state, not only a heading.
    - ``NEXT.md`` must contain concrete next steps, not only a heading.
    - ``BLOCKERS.md`` must say either no hard blocker or list concrete blockers.
    - Placeholder phrases (TODO, TBD, placeholder, HTML comments) fail.
    - Empty bullets (``- `` with no text) fail.
    - Heading-only content (just ``# Title`` with no body) fails.
    """
    result = HandoffResult(root=root)

    _validate_single(result, root, "NOW.md", "now")
    _validate_single(result, root, "NEXT.md", "next")
    _validate_single(result, root, "BLOCKERS.md", "blockers")

    return result


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