"""Repository file scanner."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

_BUILTIN_EXCLUDE_DIRS: frozenset[str] = frozenset({
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
})

DEFAULT_SIZE_LIMIT = 10 * 1024 * 1024  # 10 MiB

_pattern_cache: dict[str, re.Pattern[str]] = {}


class FileStatus(str, Enum):
    """Relationship between a file and the git index."""

    TRACKED = "tracked"
    UNTRACKED = "untracked"
    UNKNOWN = "unknown"  # git not available


@dataclass
class IndexedFile:
    """A single file entry produced by :func:`scan`."""

    path: str  # relative POSIX path from the repository root
    status: FileStatus
    size: int  # bytes


def scan(
    root: Path,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    size_limit: int = DEFAULT_SIZE_LIMIT,
) -> list[IndexedFile]:
    """Return the files under *root* as :class:`IndexedFile` objects.

    * Prefers ``git ls-files`` when *root* is inside a git repository.
    * Falls back to filesystem walking otherwise.
    * Never descends into builtin-excluded directories (.git, node_modules,
      .venv, venv, __pycache__, dist, build, .pytest_cache, .mypy_cache).
    * Applies *include* / *exclude* glob patterns from the caller.
    * Files larger than *size_limit* bytes are silently skipped.
    * All returned paths use POSIX (forward-slash) separators relative to *root*.
    """
    inc = list(include or [])
    exc = list(exclude or [])

    if _is_git_repo(root):
        return _scan_git(root, inc, exc, size_limit)
    return _scan_filesystem(root, inc, exc, size_limit)


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _is_git_repo(root: Path) -> bool:
    """Return True if *root* is inside a git repository and git is available."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=root,
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def _git_ls_files(root: Path, *extra_args: str) -> list[str]:
    """Run ``git ls-files`` from *root* and return non-empty path strings."""
    try:
        result = subprocess.run(
            ["git", "ls-files", *extra_args],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            return []
        return [line for line in result.stdout.splitlines() if line]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return []


def _scan_git(
    root: Path,
    include: list[str],
    exclude: list[str],
    size_limit: int,
) -> list[IndexedFile]:
    tracked = set(_git_ls_files(root, "--cached"))
    untracked = set(_git_ls_files(root, "--others", "--exclude-standard"))
    all_posix = sorted(tracked | untracked)

    results: list[IndexedFile] = []
    for posix in all_posix:
        if _in_builtin_excluded_dir(posix):
            continue
        abs_path = root / Path(posix)
        if not abs_path.is_file():
            continue
        size = abs_path.stat().st_size
        if not _should_include(posix, size, include, exclude, size_limit):
            continue
        status = FileStatus.TRACKED if posix in tracked else FileStatus.UNTRACKED
        results.append(IndexedFile(path=posix, status=status, size=size))
    return results


# ---------------------------------------------------------------------------
# Filesystem walker
# ---------------------------------------------------------------------------


def _scan_filesystem(
    root: Path,
    include: list[str],
    exclude: list[str],
    size_limit: int,
) -> list[IndexedFile]:
    results: list[IndexedFile] = []
    for abs_path in _walk(root):
        posix = abs_path.relative_to(root).as_posix()
        size = abs_path.stat().st_size
        if not _should_include(posix, size, include, exclude, size_limit):
            continue
        results.append(IndexedFile(path=posix, status=FileStatus.UNKNOWN, size=size))
    results.sort(key=lambda f: f.path)
    return results


def _walk(directory: Path):
    """Yield files under *directory*, never entering builtin-excluded dirs."""
    try:
        entries = sorted(directory.iterdir(), key=lambda e: e.name)
    except PermissionError:
        return
    for entry in entries:
        if entry.name in _BUILTIN_EXCLUDE_DIRS:
            continue
        if entry.is_symlink():
            continue
        if entry.is_dir():
            yield from _walk(entry)
        elif entry.is_file():
            yield entry


# ---------------------------------------------------------------------------
# Filter helpers
# ---------------------------------------------------------------------------


def _in_builtin_excluded_dir(posix: str) -> bool:
    """Return True if any *directory* component of *posix* is a builtin-excluded name."""
    parts = posix.split("/")
    return any(part in _BUILTIN_EXCLUDE_DIRS for part in parts[:-1])


def _should_include(
    posix: str,
    size: int,
    include: list[str],
    exclude: list[str],
    size_limit: int,
) -> bool:
    if size > size_limit:
        return False
    if exclude and _matches_any(posix, exclude):
        return False
    if include and not _matches_any(posix, include):
        return False
    return True


def _matches_any(posix: str, patterns: list[str]) -> bool:
    return any(_match_pattern(posix, p) for p in patterns)


def _match_pattern(posix: str, pattern: str) -> bool:
    """Match *posix* against a glob *pattern* with ``**`` support.

    For patterns without a path separator, also tests the bare filename so
    that ``*.pyc`` matches ``src/foo.pyc`` as well as ``foo.pyc``.
    """
    rx = _compile_pattern(pattern)
    if rx.match(posix):
        return True
    # For path-separator-free patterns, also check just the filename.
    if "/" not in pattern:
        basename = posix.rsplit("/", 1)[-1]
        if rx.match(basename):
            return True
    return False


def _compile_pattern(pattern: str) -> re.Pattern[str]:
    """Translate a glob pattern (with ``**`` support) to a compiled regex.

    Supported syntax:
    * ``**`` – match any sequence of characters including path separators.
    * ``*``  – match any sequence of characters within one path component.
    * ``?``  – match a single character within one path component.
    * All other characters are matched literally.
    """
    if pattern in _pattern_cache:
        return _pattern_cache[pattern]

    parts: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern[i : i + 3] == "**/":
            # Zero or more path components (including none)
            parts.append("(.*/)?")
            i += 3
        elif pattern[i : i + 2] == "**":
            # Trailing ** – match everything
            parts.append(".*")
            i += 2
        elif pattern[i] == "*":
            parts.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            parts.append("[^/]")
            i += 1
        else:
            parts.append(re.escape(pattern[i]))
            i += 1

    rx = re.compile("^" + "".join(parts) + "$")
    _pattern_cache[pattern] = rx
    return rx
