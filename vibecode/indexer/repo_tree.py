"""Compact repository tree renderer for vibecode."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterator

from vibecode.indexer.classifier import FileRecord


_ROLE_NOTES: dict[str, str] = {
    "backend_engine": "core logic",
    "backend_api": "API / routes",
    "frontend_screen": "UI screens",
    "frontend_component": "UI components",
    "script": "scripts",
    "test": "tests",
    "config": "configuration",
    "doc": "documentation",
    "generated": "generated",
}

# Lower value = higher priority when computing the dominant role of a directory.
_ROLE_PRIORITY: dict[str, int] = {
    "backend_engine": 0,
    "backend_api": 1,
    "frontend_screen": 2,
    "frontend_component": 3,
    "script": 4,
    "test": 5,
    "config": 6,
    "doc": 7,
    "generated": 8,
    "unknown": 9,
}

_IMPORTANT_ROLES: frozenset[str] = frozenset({
    "backend_engine",
    "backend_api",
    "frontend_screen",
    "frontend_component",
    "script",
})

# These top-level directory names are generated artifacts and are always hidden.
_EXCLUDED_TOP_DIRS: frozenset[str] = frozenset({
    "vibecode.egg-info",
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "coverage",
})

_EXCLUDED_PARTS: frozenset[str] = frozenset({
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    "coverage",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
})

_EXCLUDED_PREFIXES: tuple[str, ...] = (
    ".vibecode/current/",
    ".vibecode/runs/",
    ".vibecode/cache/",
    ".vibecode/tmp/",
    ".vibecode/logs/",
)


class _DirNode:
    """A directory node in the in-memory file tree."""

    __slots__ = ("name", "files", "dirs")

    def __init__(self, name: str) -> None:
        self.name = name
        self.files: list[FileRecord] = []
        self.dirs: dict[str, "_DirNode"] = {}

    def all_records(self) -> Iterator[FileRecord]:
        yield from self.files
        for child in self.dirs.values():
            yield from child.all_records()

    def dominant_role(self) -> str:
        """Return the highest-priority role among all files in this subtree."""
        roles = [r.role_guess for r in self.all_records()]
        if not roles:
            return "unknown"
        return min(roles, key=lambda r: _ROLE_PRIORITY.get(r, 9))

    def has_interesting_content(self) -> bool:
        """Return True if this subtree is worth expanding in the tree."""
        if self.dominant_role() in _IMPORTANT_ROLES:
            return True
        return any(r.risk_level in ("high", "medium") for r in self.all_records())


def _build_tree(records: list[FileRecord]) -> _DirNode:
    """Build an in-memory tree from a flat list of :class:`FileRecord` objects."""
    root = _DirNode("")
    for rec in records:
        if _is_excluded_from_tree(rec.path):
            continue
        parts = PurePosixPath(rec.path).parts
        node = root
        for part in parts[:-1]:
            if part not in node.dirs:
                node.dirs[part] = _DirNode(part)
            node = node.dirs[part]
        node.files.append(rec)
    return root


def _is_excluded_from_tree(path: str) -> bool:
    if any(path.startswith(prefix) for prefix in _EXCLUDED_PREFIXES):
        return True
    return any(part in _EXCLUDED_PARTS for part in PurePosixPath(path).parts[:-1])


def _render_children(
    node: _DirNode,
    current_depth: int,
    max_depth: int,
    prefix: str,
    lines: list[str],
) -> None:
    """Append Markdown tree lines for the children of *node*.

    *current_depth* is the depth of *node* itself (0 = root).
    Children of *node* are at depth *current_depth + 1*.
    """
    if current_depth >= max_depth:
        return

    at_top_level = current_depth == 0

    dirs_to_show = sorted(node.dirs.keys())
    if at_top_level:
        dirs_to_show = [d for d in dirs_to_show if d not in _EXCLUDED_TOP_DIRS]
    else:
        dirs_to_show = [d for d in dirs_to_show if node.dirs[d].has_interesting_content()]

    files_to_show = sorted(node.files, key=lambda f: PurePosixPath(f.path).name)
    if not at_top_level:
        files_to_show = [f for f in files_to_show if f.risk_level in ("high", "medium")]

    total = len(dirs_to_show) + len(files_to_show)
    if total == 0:
        return

    idx = 0

    for dirname in dirs_to_show:
        is_last = idx == total - 1
        connector = "└── " if is_last else "├── "
        child_prefix = prefix + ("    " if is_last else "│   ")

        child = node.dirs[dirname]
        role = child.dominant_role()
        role_note = _ROLE_NOTES.get(role, "")
        suffix = f"  _{role_note}_" if role_note else ""
        lines.append(f"{prefix}{connector}{dirname}/{suffix}")

        _render_children(child, current_depth + 1, max_depth, child_prefix, lines)
        idx += 1

    for rec in files_to_show:
        is_last = idx == total - 1
        connector = "└── " if is_last else "├── "
        if rec.risk_level == "high":
            risk_tag = "  `[HIGH RISK]`"
        elif rec.risk_level == "medium":
            risk_tag = "  `[MEDIUM RISK]`"
        else:
            risk_tag = ""
        filename = PurePosixPath(rec.path).name
        lines.append(f"{prefix}{connector}{filename}{risk_tag}")
        idx += 1


def render_repo_tree(
    root: Path,
    records: list[FileRecord],
    *,
    max_depth: int = 3,
    generated_at: datetime | None = None,
    git_commit: str | None = None,
) -> str:
    """Return a Markdown string representing a compact repository tree.

    Args:
        root: Repository root path (used for the heading).
        records: Classified file records from :func:`~vibecode.indexer.classifier.classify`.
        max_depth: Maximum directory nesting depth to expand (default 3).

    Returns:
        A Markdown string beginning with ``# Repo tree``.
    """
    tree = _build_tree(records)

    if generated_at is None:
        generated_at = datetime.now(tz=timezone.utc)

    lines: list[str] = [
        "# Repository Tree",
        "",
        f"Generated: `{generated_at.isoformat()}`",
        f"Repo root: `{root.as_posix()}`",
        f"Git commit: `{git_commit or 'unknown'}`",
        "",
        "## Tree",
        "",
        f"{root.name}/",
    ]

    _render_children(tree, 0, max_depth, "", lines)

    lines.append("")
    return "\n".join(lines)


def write_repo_tree(
    root: Path,
    records: list[FileRecord],
    output_path: Path,
    *,
    max_depth: int = 3,
    generated_at: datetime | None = None,
    git_commit: str | None = None,
) -> None:
    """Render and write ``repo_tree.md`` to *output_path*, creating parents as needed."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = render_repo_tree(
        root,
        records,
        max_depth=max_depth,
        generated_at=generated_at,
        git_commit=git_commit,
    )
    output_path.write_text(content, encoding="utf-8")
