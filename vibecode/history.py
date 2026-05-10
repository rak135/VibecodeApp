"""History summary creation and validation for .vibecode/history/*.md files."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
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

_PLACEHOLDER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bTODO\b", re.IGNORECASE),
    re.compile(r"\bTBD\b", re.IGNORECASE),
)

_PLACEHOLDER_PHRASES: tuple[str, ...] = (
    "_not yet filled._",
    "not yet filled",
    "fill in later",
    "to be filled",
)


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
    lower = content.lower()
    return (
        "<!--" in content
        or any(phrase in lower for phrase in _PLACEHOLDER_PHRASES)
        or any(_is_placeholder_marker(line.strip()) for line in content.splitlines())
        or any(pattern.search(content) for pattern in _PLACEHOLDER_PATTERNS)
    )


def _is_placeholder_marker(stripped: str) -> bool:
    """Return True for lines that are only placeholder marker text."""
    marker = stripped.strip("`*_[]<>(){}:.- ").lower()
    return marker in {"placeholder", "placeholder text"}


def _section_bodies(content: str) -> dict[str, list[str]]:
    """Return body lines keyed by lower-case section heading."""
    bodies: dict[str, list[str]] = {}
    current: str | None = None
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith(_SECTION_PREFIX):
            heading_text = stripped.removeprefix(_SECTION_PREFIX).strip()
            current = heading_text.lower() if heading_text else None
            if current:
                bodies.setdefault(current, [])
            continue
        if current:
            bodies[current].append(line)
    return bodies


def _is_empty_bullet(stripped: str) -> bool:
    """Return True for markdown bullet markers with no actual text."""
    return bool(re.fullmatch(r"[-*+]\s*(\[[ xX]\])?", stripped))


def _has_durable_section_content(lines: list[str]) -> bool:
    """Return True when a section body contains non-placeholder content."""
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("<!--") or _is_empty_bullet(stripped):
            continue
        if _has_placeholder(stripped):
            continue
        return True
    return False


def validate_history_file(path: Path, repo_root: Path) -> list[HistoryIssue]:
    """Validate a single history summary markdown file.

    Rules
    -----
    1. Must contain every section listed in ``REQUIRED_SECTIONS``.
    2. Must not contain placeholder markers (TODO, TBD, unfilled text, HTML comments).
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
                    "Contains placeholder text (TODO, TBD, unfilled marker, or HTML comment). "
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

    bodies = _section_bodies(content)
    for required in REQUIRED_SECTIONS:
        if required.lower() in found and not _has_durable_section_content(
            bodies.get(required.lower(), [])
        ):
            issues.append(
                HistoryIssue(
                    file=rel,
                    message=(
                        f"Section '{required}' has no durable content. "
                        "Each section must describe real project truth, "
                        "not empty bullets or placeholders."
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


def _sanitise_filename(task: str) -> str:
    """Convert a task description into a safe, lowercase filename slug."""
    slug = task.lower().strip().replace(" ", "-")
    slug = re.sub(r"[^a-z0-9\-_]", "", slug)
    slug = re.sub(r"-{2,}", "-", slug)
    return slug[:80]  # cap length to keep filenames reasonable


def _next_summary_path(history_dir: Path, slug: str) -> Path:
    """Return the next available history summary path using a timestamp prefix.

    Format: ``YYYYMMDD-HHMM-task-slug.md``
    If a file with the same name already exists, append ``-N`` before ``.md``.
    """
    now = datetime.now()
    stamp = now.strftime("%Y%m%d-%H%M")
    stem = f"{stamp}-{slug}"
    candidate = history_dir / f"{stem}.md"
    counter = 1
    while candidate.exists():
        candidate = history_dir / f"{stem}-{counter}.md"
        counter += 1
    return candidate


def create_summary(
    repo_root: Path,
    task: str,
    *,
    changed_files: str = "",
    behavior_changed: str = "",
    tests_run: str = "",
    decisions: str = "",
    follow_up: str = "",
    author: str = "",
) -> Path:
    """Create a durable history summary in ``.vibecode/history/``.

    Generates a timestamped markdown file with the required section headings,
    pre-filled with the provided content.  Does **not** overwrite an existing
    summary — if a file with the same timestamp slug already exists a suffix
    ``-N`` is appended.

    Parameters
    ----------
    repo_root:
        Repository root directory (will be resolved).
    task:
        Short description of the task or change.
    changed_files:
        Markdown list of files changed and why.
    behavior_changed:
        Description of behavioural impact.
    tests_run:
        Test results summary.
    decisions:
        Key architectural or design choices.
    follow_up:
        Open items or next steps.
    author:
        Optional author name / email.

    Returns
    -------
    Path
        The path of the created summary file.

    Raises
    ------
    FileExistsError
        If the target file somehow exists and cannot be uniquified (unlikely).
    """
    root = repo_root.resolve()
    history_dir = root / ".vibecode" / "history"
    history_dir.mkdir(parents=True, exist_ok=True)

    slug = _sanitise_filename(task)
    dest = _next_summary_path(history_dir, slug)

    # Build the structured content
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")

    header = f"# {task}\n\n"
    header += f"Date: {date_str}\n"
    if author:
        header += f"Author: {author}\n"
    header += "\n"

    sections = [
        ("Task", task),
        ("Changed files", changed_files),
        ("Behavior changed", behavior_changed),
        ("Tests run", tests_run),
        ("Decisions", decisions),
        ("Follow-up", follow_up),
    ]

    body_parts = [header]
    for name, content in sections:
        body_parts.append(f"### {name}\n")
        body_parts.append(content.strip() if content else "_Not yet filled._")
        body_parts.append("\n")

    dest.write_text("".join(body_parts), encoding="utf-8")
    return dest


def cmd_history(args) -> int:
    """CLI entry point for ``vibecode history new``."""
    sub = getattr(args, "history_subcommand", None)

    if sub == "new":
        repo_arg = getattr(args, "repo", None)
        repo = Path(repo_arg).resolve() if repo_arg else Path.cwd().resolve()
        task = getattr(args, "task", "")
        author = getattr(args, "author", "")

        changed_files = getattr(args, "changed_files", "") or ""
        behavior_changed = getattr(args, "behavior_changed", "") or ""
        tests_run = getattr(args, "tests_run", "") or ""
        decisions = getattr(args, "decisions", "") or ""
        follow_up = getattr(args, "follow_up", "") or ""

        dest = create_summary(
            repo,
            task,
            changed_files=changed_files,
            behavior_changed=behavior_changed,
            tests_run=tests_run,
            decisions=decisions,
            follow_up=follow_up,
            author=author,
        )
        print(f"History summary written: {dest}", file=sys.stderr)
        return 0

    # No recognised subcommand
    return 1


