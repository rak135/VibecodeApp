"""Architecture orientation map renderer for vibecode."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterator

from vibecode.indexer.classifier import FileRecord


# ---------------------------------------------------------------------------
# Role notes and priorities (used by compact Tree section)
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Deterministic architecture labels (derived from well-known folder/file names)
# ---------------------------------------------------------------------------

# Maps well-known subfolder names → architectural role label.
_FOLDER_ARCH_LABELS: dict[str, str] = {
    "indexer": "[repository indexing core]",
    "context": "[agent context generation]",
    "api": "[API / routes]",
    "engine": "[core logic]",
    "scripts": "[scripts]",
}

# Maps well-known source filenames → purpose label.
# These are deterministic heuristics from the filename, not fabricated descriptions.
_FILE_ARCH_LABELS: dict[str, str] = {
    "cli.py": "[CLI entrypoint]",
    "config.py": "[project config]",
    "project.py": "[project initialization]",
    "paths.py": "[path utilities]",
    "validation.py": "[validation]",
    "write_rules.py": "[write rules]",
    "scoring.py": "[relevant-file scoring]",
    "renderer.py": "[context pack renderer]",
    "scanner.py": "[safe file discovery]",
    "classifier.py": "[file classification]",
    "inventory.py": "[file inventory output]",
    "repo_tree.py": "[architecture map rendering]",
    "symbols.py": "[Python AST symbol extraction]",
    "ts_symbols.py": "[TypeScript symbol extraction]",
    "dependency_map.py": "[import/dependency extraction]",
    "test_map.py": "[test discovery]",
    "entrypoints.py": "[entrypoint detection]",
    "risk_engine.py": "[risk/protected mapping]",
    "risky_files.py": "[risky files reporter]",
    "symbol_map.py": "[symbol map output]",
    "run_record.py": "[run record]",
    "code_intelligence.py": "[code intelligence]",
    "platform_export.py": "[platform prompt export]",
    "agents_export.py": "[AGENTS.md export]",
    "platform_registry.py": "[platform metadata/registry]",
}

# ---------------------------------------------------------------------------
# Exclusion rules
# ---------------------------------------------------------------------------

# These top-level directory names are generated artifacts and are always hidden
# from the compact Tree section.
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

# .vibecode subdirs that are human-maintained project truth (not ignored)
_VIBECODE_TRUTH_SUBDIRS: tuple[tuple[str, str], ...] = (
    ("architecture", "[human-maintained architecture truth]  `[risk/protected]`"),
    ("checks", "[human-maintained required checks]"),
    ("handoff", "[human-maintained handoff/status]  `[risk/protected]`"),
    ("history", "[human-maintained history]  `[risk/protected]`"),
)

# .vibecode subdirs that are generated or runtime state (ignored)
_VIBECODE_IGNORED_SUBDIRS: tuple[tuple[str, str], ...] = (
    ("index", "[generated / ignored]"),
    ("current", "[runtime / ignored]"),
    ("logs", "[runtime / ignored]"),
    ("runs", "[runtime / ignored]"),
    ("cache", "[runtime / ignored]"),
    ("tmp", "[runtime / ignored]"),
)


# ---------------------------------------------------------------------------
# In-memory tree
# ---------------------------------------------------------------------------


_TEST_DIR_NAMES: frozenset[str] = frozenset({"tests", "test", "spec", "specs"})


class _DirNode:
    """A directory node in the in-memory file tree."""

    __slots__ = ("name", "files", "dirs")

    def __init__(self, name: str) -> None:
        self.name = name
        self.files: list[FileRecord] = []
        self.dirs: dict[str, "_DirNode"] = {}

    def is_source_package(self) -> bool:
        """Return True if this directory directly contains an ``__init__.py`` file.

        Used to identify Python source packages that should be fully expanded in
        the compact Tree section regardless of their role or risk classification.
        """
        return any(PurePosixPath(f.path).name == "__init__.py" for f in self.files)

    def all_records(self) -> Iterator[FileRecord]:
        yield from self.files
        for child in self.dirs.values():
            yield from child.all_records()

    def dominant_role(self) -> str:
        """Return the highest-priority role among all non-test source files in this subtree.

        Files whose name starts with ``test_`` but live outside a ``tests/`` directory
        (e.g. ``vibecode/indexer/test_map.py``) are excluded from the role vote so they
        do not drag the whole package into the ``test`` bucket.
        """
        roles = [
            r.role_guess
            for r in self.all_records()
            if not _is_misclassified_source_as_test(r.path)
        ]
        if not roles:
            # Fall back to including all records if filtering produced nothing
            roles = [r.role_guess for r in self.all_records()]
        if not roles:
            return "unknown"
        return min(roles, key=lambda r: _ROLE_PRIORITY.get(r, 9))

    def has_interesting_content(self) -> bool:
        """Return True if this subtree is worth expanding in the tree."""
        if self.dominant_role() in _IMPORTANT_ROLES:
            return True
        return any(r.risk_level in ("high", "medium") for r in self.all_records())


def _is_misclassified_source_as_test(path: str) -> bool:
    """Return True for source files falsely classified as tests.

    ``vibecode/indexer/test_map.py`` starts with ``test_`` so the classifier
    tags it as ``test``, but it lives inside the source package, not in
    ``tests/``.  Excluding such files from the role-vote prevents the
    ``vibecode/`` package from being labelled as a test directory.
    """
    parts = PurePosixPath(path).parts
    if len(parts) < 2:
        return False
    # File must be in a tests/ directory to be a real test file
    if "tests" in parts[:-1]:
        return False
    # File is outside tests/ but has a test-like name → misclassified
    name = parts[-1]
    return name.startswith("test_") and name.endswith(".py")


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


# ---------------------------------------------------------------------------
# Summary section
# ---------------------------------------------------------------------------


def _render_summary(
    records: list[FileRecord],
    entrypoints_data: dict | None,
) -> list[str]:
    """Return lines for the ## Summary section."""
    non_excluded = [r for r in records if not _is_excluded_from_tree(r.path)]
    test_count = sum(
        1 for r in non_excluded
        if r.is_test and not _is_misclassified_source_as_test(r.path)
    )
    doc_count = sum(1 for r in non_excluded if r.is_doc)
    config_count = sum(1 for r in non_excluded if r.is_config)
    generated_count = sum(1 for r in non_excluded if r.role_guess == "generated")
    source_count = sum(
        1 for r in non_excluded
        if not r.is_test
        and not r.is_doc
        and not r.is_config
        and r.role_guess != "generated"
        and not _is_misclassified_source_as_test(r.path)
    )
    risky_count = sum(1 for r in non_excluded if r.risk_level in ("high", "medium"))

    entry_count = 0
    if entrypoints_data:
        entry_count = (
            len(entrypoints_data.get("backend") or [])
            + len(entrypoints_data.get("frontend") or [])
            + len(entrypoints_data.get("cli_scripts") or [])
            + len(entrypoints_data.get("runtime_config") or [])
        )

    return [
        "## Summary",
        "",
        f"- Source files: {source_count}",
        f"- Test files: {test_count}",
        f"- Documentation files: {doc_count}",
        f"- Config files: {config_count}",
        f"- Generated files: {generated_count}",
        f"- Entrypoints: {entry_count}",
        f"- Risky/protected files: {risky_count}",
        "",
    ]


# ---------------------------------------------------------------------------
# Architecture orientation section
# ---------------------------------------------------------------------------


def _build_source_test_index(test_map_data: dict | None) -> dict[str, list[str]]:
    """Return a mapping of source_path → [test_path, ...] from test_map rules."""
    index: dict[str, list[str]] = {}
    if not test_map_data:
        return index
    for rule in test_map_data.get("rules") or []:
        pattern = rule.get("path_pattern", "")
        if pattern == "**":
            continue
        checks = [
            c for c in (rule.get("required_checks") or [])
            if c.startswith("tests/")
        ]
        if checks:
            index[pattern] = checks
    return index


def _find_source_package_roots(records: list[FileRecord]) -> list[str]:
    """Return top-level Python source package directories (those with __init__.py).

    Directories named ``tests`` or living inside ``tests/`` are excluded so
    that the test package is never mis-reported as a source package.
    """
    pkg_dirs: list[str] = []
    seen: set[str] = set()
    for rec in records:
        path = PurePosixPath(rec.path)
        if path.name != "__init__.py":
            continue
        parent_parts = path.parts[:-1]
        if not parent_parts:
            continue
        top = parent_parts[0]
        # Exclude tests/ and anything nested under tests/
        if top == "tests" or "tests" in parent_parts:
            continue
        # Only track the top-level package directory
        pkg_dir = top
        if pkg_dir not in seen:
            seen.add(pkg_dir)
            pkg_dirs.append(pkg_dir)
    return sorted(pkg_dirs)


def _files_directly_in(records: list[FileRecord], dir_prefix: str) -> list[str]:
    """Return sorted filenames that are direct children of *dir_prefix*."""
    names: list[str] = []
    for rec in records:
        p = PurePosixPath(rec.path)
        if len(p.parts) == 2 and p.parts[0] == dir_prefix:  # noqa: PLR2004
            names.append(p.name)
    return sorted(names)


def _subfolders_of(records: list[FileRecord], dir_prefix: str) -> list[str]:
    """Return sorted immediate subfolder names under *dir_prefix*."""
    subs: set[str] = set()
    for rec in records:
        p = PurePosixPath(rec.path)
        if len(p.parts) >= 3 and p.parts[0] == dir_prefix:  # noqa: PLR2004
            subs.add(p.parts[1])
    return sorted(subs)


def _files_in_subdir(records: list[FileRecord], dir_prefix: str, subdir: str) -> list[str]:
    """Return sorted filenames in *dir_prefix*/*subdir* (direct children only)."""
    names: list[str] = []
    for rec in records:
        p = PurePosixPath(rec.path)
        if (
            len(p.parts) == 3  # noqa: PLR2004
            and p.parts[0] == dir_prefix
            and p.parts[1] == subdir
        ):
            names.append(p.name)
    return sorted(names)


def _render_file_line(filename: str, indent: str, test_links: list[str]) -> str:
    """Return a formatted architecture orientation line for one source file."""
    label = _FILE_ARCH_LABELS.get(filename, "")
    suffix = f"  {label}" if label else ""
    link_part = ""
    if test_links:
        # Show at most 2 test links to keep lines compact
        shown = test_links[:2]
        link_part = "  ← tests: " + ", ".join(shown)
        if len(test_links) > 2:  # noqa: PLR2004
            link_part += f" (+{len(test_links) - 2} more)"
    return f"{indent}{filename}{suffix}{link_part}"


def _render_source_package_section(
    pkg_dir: str,
    records: list[FileRecord],
    src_test_index: dict[str, list[str]],
) -> list[str]:
    """Return lines describing the source package *pkg_dir*."""
    lines: list[str] = []
    lines.append(f"`{pkg_dir}/`  [package root / source]")

    # Direct files (skip __init__.py for brevity, skip test_*.py misclassified)
    direct_files = [
        f for f in _files_directly_in(records, pkg_dir)
        if f != "__init__.py" and not (f.startswith("test_") and f.endswith(".py"))
    ]
    for fname in direct_files:
        source_path = f"{pkg_dir}/{fname}"
        test_links = src_test_index.get(source_path, [])
        lines.append(_render_file_line(fname, "  ", test_links))

    # Subfolders
    for subdir in _subfolders_of(records, pkg_dir):
        if subdir == "__pycache__":
            continue
        folder_label = _FOLDER_ARCH_LABELS.get(subdir, "")
        suffix = f"  {folder_label}" if folder_label else ""
        lines.append(f"  {subdir}/  {suffix}".rstrip())
        # Files inside the subfolder
        sub_files = [
            f for f in _files_in_subdir(records, pkg_dir, subdir)
            if f != "__init__.py" and not (f.startswith("test_") and f.endswith(".py"))
        ]
        for fname in sub_files:
            source_path = f"{pkg_dir}/{subdir}/{fname}"
            test_links = src_test_index.get(source_path, [])
            lines.append(_render_file_line(fname, "    ", test_links))

    return lines


def _render_test_suite_section(
    records: list[FileRecord],
    test_map_data: dict | None,
) -> list[str]:
    """Return lines for the test suite section."""
    lines: list[str] = []

    # Build reverse index: test_path → [source_path, ...]
    reverse_index: dict[str, list[str]] = {}
    if test_map_data:
        for rule in test_map_data.get("rules") or []:
            pattern = rule.get("path_pattern", "")
            if pattern == "**":
                continue
            for check in rule.get("required_checks") or []:
                if check.startswith("tests/"):
                    reverse_index.setdefault(check, []).append(pattern)

    # Collect test files directly in tests/ (not in subdirs like tests/fixtures/)
    test_files = sorted(
        rec.path
        for rec in records
        if (
            rec.path.startswith("tests/")
            and not _is_excluded_from_tree(rec.path)
            and len(PurePosixPath(rec.path).parts) == 2  # noqa: PLR2004
            and PurePosixPath(rec.path).name != "__init__.py"
        )
    )

    if not test_files:
        return lines

    lines.append("`tests/`  [test suite]")
    for tf in test_files:
        fname = PurePosixPath(tf).name
        sources = reverse_index.get(tf, [])
        if sources:
            src_part = " → " + ", ".join(sources[:2])
            if len(sources) > 2:  # noqa: PLR2004
                src_part += f" (+{len(sources) - 2} more)"
        else:
            src_part = ""
        lines.append(f"  {fname}{src_part}")
    return lines


def _render_vibecode_truth_section(records: list[FileRecord]) -> list[str]:
    """Return lines for the human-maintained .vibecode project truth."""
    lines: list[str] = []
    present_dirs = {
        PurePosixPath(rec.path).parts[1]
        for rec in records
        if rec.path.startswith(".vibecode/") and len(PurePosixPath(rec.path).parts) >= 3  # noqa: PLR2004
    }

    for subdir, label in _VIBECODE_TRUTH_SUBDIRS:
        if subdir in present_dirs:
            lines.append(f"`.vibecode/{subdir}/`  {label}")

    return lines


def _render_architecture_orientation(
    records: list[FileRecord],
    entrypoints_data: dict | None,
    test_map_data: dict | None,
) -> list[str]:
    """Return lines for the ## Architecture Orientation section."""
    lines: list[str] = ["## Architecture Orientation", ""]

    src_test_index = _build_source_test_index(test_map_data)

    # --- Core source packages ---
    pkg_roots = _find_source_package_roots(records)
    if pkg_roots:
        lines.append("### Core package")
        lines.append("")
        for pkg_dir in pkg_roots:
            lines.extend(_render_source_package_section(pkg_dir, records, src_test_index))
        lines.append("")

    # --- CLI/entrypoints note ---
    if entrypoints_data:
        cli_scripts = entrypoints_data.get("cli_scripts") or []
        if cli_scripts:
            lines.append("### Entrypoints")
            lines.append("")
            for s in cli_scripts:
                lines.append(f"- `{s['name']}` → `{s['target']}` _(source: {s['source']})_")
            lines.append("")

    # --- Test suite ---
    test_lines = _render_test_suite_section(records, test_map_data)
    if test_lines:
        lines.append("### Test suite")
        lines.append("")
        lines.extend(test_lines)
        lines.append("")

    # --- Documentation ---
    doc_dirs = [
        d for d in (
            "docs",
        )
        if any(rec.path.startswith(f"{d}/") for rec in records)
    ]
    truth_lines = _render_vibecode_truth_section(records)
    if doc_dirs or truth_lines:
        lines.append("### Documentation and project truth")
        lines.append("")
        for d in doc_dirs:
            lines.append(f"`{d}/`  [documentation]")
        lines.extend(truth_lines)
        lines.append("")

    # --- Generated / runtime state ---
    if any(rec.path.startswith(".vibecode/") for rec in records):
        lines.append("### Generated and runtime state")
        lines.append("")
        for subdir, label in _VIBECODE_IGNORED_SUBDIRS[:3]:  # index, current, logs
            lines.append(f"`.vibecode/{subdir}/`  {label}")
        lines.append("")

    return lines


# ---------------------------------------------------------------------------
# Compact Tree section (existing rendering)
# ---------------------------------------------------------------------------


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

    # Source packages (Python dirs with __init__.py that are not the test suite) are
    # always fully expanded so the agent can see the actual source structure.
    expand_as_source = (
        not at_top_level
        and node.name not in _TEST_DIR_NAMES
        and node.is_source_package()
    )

    dirs_to_show = sorted(node.dirs.keys())
    if at_top_level:
        dirs_to_show = [d for d in dirs_to_show if d not in _EXCLUDED_TOP_DIRS]
    elif expand_as_source:
        # Show subpackages only; skip __pycache__ and other excluded parts.
        dirs_to_show = [
            d for d in dirs_to_show
            if d not in _EXCLUDED_PARTS
            and d != "__pycache__"
            and node.dirs[d].is_source_package()
        ]
    else:
        dirs_to_show = [d for d in dirs_to_show if node.dirs[d].has_interesting_content()]

    files_to_show = sorted(node.files, key=lambda f: PurePosixPath(f.path).name)
    if at_top_level:
        pass  # show all top-level files
    elif expand_as_source:
        # Show all source files; omit __init__.py and genuine test files.
        files_to_show = [
            f for f in files_to_show
            if PurePosixPath(f.path).name != "__init__.py"
            and "tests" not in PurePosixPath(f.path).parts[:-1]
        ]
    else:
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_repo_tree(
    root: Path,
    records: list[FileRecord],
    *,
    max_depth: int = 3,
    generated_at: datetime | None = None,
    git_commit: str | None = None,
    entrypoints_data: dict | None = None,
    test_map_data: dict | None = None,
) -> str:
    """Return a Markdown string representing the repository architecture map.

    Args:
        root: Repository root path (used for the heading).
        records: Classified file records from :func:`~vibecode.indexer.classifier.classify`.
        max_depth: Maximum directory nesting depth to expand in the compact Tree section.
        generated_at: Timestamp to embed in the header (defaults to now).
        git_commit: Git commit SHA to embed in the header.
        entrypoints_data: Output of :func:`~vibecode.indexer.entrypoints.detect_entrypoints`
            used to enrich the Architecture Orientation section.
        test_map_data: Output of :func:`~vibecode.indexer.test_map.build_test_map`
            used to show source↔test relationships.

    Returns:
        A Markdown string beginning with ``# Repository Tree``.
    """
    tree = _build_tree(records)

    if generated_at is None:
        generated_at = datetime.now(tz=timezone.utc)

    lines: list[str] = [
        "# Repository Tree",
        "",
        "Generated from deterministic repository index.",
        "This file is generated and is not source of truth.",
        "",
        f"Generated: `{generated_at.isoformat()}`",
        f"Repo root: `{root.as_posix()}`",
        f"Git commit: `{git_commit or 'unknown'}`",
        "",
    ]

    lines.extend(_render_summary(records, entrypoints_data))
    lines.extend(_render_architecture_orientation(records, entrypoints_data, test_map_data))

    lines.extend([
        "## Tree",
        "",
        f"{root.name}/",
    ])
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
    entrypoints_data: dict | None = None,
    test_map_data: dict | None = None,
) -> None:
    """Render and write ``repo_tree.generated.md`` to *output_path*, creating parents as needed."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = render_repo_tree(
        root,
        records,
        max_depth=max_depth,
        generated_at=generated_at,
        git_commit=git_commit,
        entrypoints_data=entrypoints_data,
        test_map_data=test_map_data,
    )
    output_path.write_text(content, encoding="utf-8")
