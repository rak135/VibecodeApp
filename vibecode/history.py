"""History summary validation for .vibecode/history/*.md files."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


# Required sections that every committed history summary must contain.
# Order is intentional — it mirrors the natural flow of a change record.
REQUIRED_SECTIONS: tuple[str, ...] = (
    "Task",
    "Changed files",
    "Behavior changed",
    "Tests run",
    "Decisions",
    "Follow-up",
)

# Section heading prefix used in history summaries.
_SECTION_PREFIX = "### "


@dataclass(frozen=True)
class HistoryIssue:
    """A single validation issue found in a history summary file."""

    file: str
    message: str


@dataclass
class HistoryResult:
    """Validation result for one or more history summary files."""

    root: Path
    issues: list[HistoryIssue] = field(default_factory=list)
    files_checked: int = 0

    @property
    def passed(self) -> bool:
        return len(self.issues) == 0

    def as_dict(self) -> dict:
        return {
            "root": self.root.as_posix(),
            "passed": self.passed,
            "files_checked": self.files_checked,
            "issues": [
                {"file": i.file, "message": i.message} for i in self.issues
            ],
        }


def _extract_headings(content: str) -> list[str]:
    """Return the text of every ### heading in *content*."""
    headings: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith(_SECTION_PREFIX):
            heading_text = stripped.removeprefix(_SECTION_PREFIX).strip()
            if heading_text:
                headings.append(heading_text)
    return headings


def _has_placeholder(content: str) -> bool:
    """Return True if the file contains placeholder / unfilled markers."""
    upper = content.upper()
    return any(
        marker in upper
        for marker in ("TODO", "TBD", "PLACEHOLDER", "<!--")
    )


def validate_history_file(path: Path, repo_root: Path) -> list[HistoryIssue]:
    """Validate a single history summary markdown file.

    Rules
    -----
    1. Must contain every section listed in ``REQUIRED_SECTIONS``.
    2. Must not contain placeholder markers (TODO, TBD, PLACEHOLDER, HTML comments).
    3. Must not be heading-only (at least one section body is required).
    """
    rel = str(path.relative_to(repo_root)) if path.is_relative_to(repo_root) else path.name
    issues: list[HistoryIssue] = []

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        issues.append(HistoryIssue(file=rel, message=f"Cannot read file: {exc}"))
        return issues

    if _has_placeholder(content):
        issues.append(
            HistoryIssue(
                file=rel,
                message=(
                    "Contains placeholder text (TODO, TBD, PLACEHOLDER, or HTML comment). "
                    "History summaries record durable truth, not stubs."
                ),
            )
        )

    headings = _extract_headings(content)
    found = {h.lower(): h for h in headings}

    missing: list[str] = []
    for required in REQUIRED_SECTIONS:
        if required.lower() not in found:
            missing.append(required)

    if missing:
        issues.append(
            HistoryIssue(
                file=rel,
                message=(
                    f"Missing required section(s): {', '.join(missing)}. "
                    f"All of {', '.join(REQUIRED_SECTIONS)} are required."
                ),
            )
        )

    # Heading-only check: at least one section must have body content
    # (lines between headings that are not themselves headings or comments)
    lines = content.splitlines()
    has_body = False
    in_section = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("### "):
            if in_section and has_body:
                break  # found at least one section with content
            in_section = True
            has_body = False
            continue
        if in_section and stripped and not stripped.startswith("<!--"):
            has_body = True
    else:
        if in_section and not has_body:
            issues.append(
                HistoryIssue(
                    file=rel,
                    message=(
                        "Contains only headings with no body content. "
                        "Each section must describe the change."
                    ),
                )
            )

    return issues


def validate_history_dir(root: Path) -> HistoryResult:
    """Validate all ``*.md`` history summaries under ``.vibecode/history/``.

    Only top-level ``*.md`` files are checked (not subdirectories).
    The ``README.md`` policy file is always skipped since it is the
    policy definition itself, not a change summary.

    Returns a :class:`HistoryResult` with all issues found.
    """
    history_dir = root / ".vibecode" / "history"
    result = HistoryResult(root=root)

    if not history_dir.is_dir():
        return result

    for path in sorted(history_dir.glob("*.md")):
        if path.name == "README.md":
            continue
        result.files_checked += 1
        result.issues.extend(validate_history_file(path, root))

    return result


def cmd_history_check(args) -> int:
    """CLI entry point for ``vibecode history-check`` (planned)."""
    # Not yet wired into CLI — reserved for future use.
    raise NotImplementedError