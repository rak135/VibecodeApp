"""Path normalization and classification utilities for cross-platform use.

Provides public helpers for normalising paths and classifying file types
(source, test, documentation, generated/runtime, architecture truth/reference).
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

_GENERATED_RUNTIME_PREFIXES: tuple[str, ...] = (
    ".vibecode/current/",
    ".vibecode/generated/",
    ".vibecode/logs/",
    ".vibecode/runs/",
    ".vibecode/tmp/",
    ".vibecode/cache/",
)
_SOURCE_EXTENSIONS: frozenset[str] = frozenset({
    ".py",
    ".pyi",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
})
_DOC_EXTENSIONS: frozenset[str] = frozenset({".md", ".mdx", ".rst", ".txt", ".adoc"})
_TS_TEST_SUFFIXES: tuple[str, ...] = (
    ".test.ts",
    ".test.tsx",
    ".spec.ts",
    ".spec.tsx",
    ".test.js",
    ".test.jsx",
    ".spec.js",
    ".spec.jsx",
)


def normalise_root(raw: str) -> Path:
    """Resolve a raw path string to an absolute :class:`~pathlib.Path`.

    Converts Windows-style backslash separators to forward slashes before
    passing to :class:`~pathlib.Path`, then calls :meth:`~pathlib.Path.resolve`.
    This means ``C:\\path\\to\\repo`` is accepted on Windows without treating
    the drive-letter colon as a special character.

    Parameters
    ----------
    raw:
        A path string, possibly using Windows backslash separators or starting
        with a drive letter (e.g. ``C:\\Users\\foo\\project``).

    Returns
    -------
    Path
        An absolute, resolved :class:`~pathlib.Path`.
    """
    return Path(strip_to_posix(raw)).resolve()


def strip_to_posix(raw: str) -> str:
    """Return *raw* with every backslash replaced by a forward slash.

    This is a pure string operation — no filesystem access, no path resolution.
    Drive-letter colons (``C:``) are left unchanged so that Windows absolute
    paths remain valid after the conversion.

    Use this when normalising path strings from YAML/JSON configuration or
    from user input that may originate on a Windows machine.
    """
    return raw.replace("\\", "/")


def to_posix_str(path: Path) -> str:
    """Return a forward-slash string representation of *path*.

    Wraps :meth:`~pathlib.Path.as_posix` and is safe to embed in JSON values
    and Markdown text on all platforms — no backslashes will appear in the
    output even on Windows.
    """
    return path.as_posix()


def normalise_path(path: str) -> str:
    """Normalise a path string: backslashes → forward slashes, strip whitespace."""
    return strip_to_posix(str(path).strip())


def is_generated_runtime_path(path: str) -> bool:
    """Return True if *path* is under a generated/runtime vibecode directory."""
    if path.startswith(_GENERATED_RUNTIME_PREFIXES):
        return True
    if not path.startswith(".vibecode/index/"):
        return False
    name = path.removeprefix(".vibecode/index/")
    return name not in {"README.md", "schema.json"}


def is_source_path(path: str) -> bool:
    """Return True if *path* looks like a source code file (not test/doc)."""
    if is_test_path(path) or is_documentation_path(path):
        return False
    return PurePosixPath(path).suffix in _SOURCE_EXTENSIONS


def is_test_path(path: str) -> bool:
    """Return True if *path* looks like a test file."""
    suffix = PurePosixPath(path).suffix
    name = PurePosixPath(path).name
    parts = path.split("/")
    if suffix == ".py":
        return (
            name.startswith("test_")
            or name.endswith("_test.py")
            or "tests" in parts[:-1]
        )
    if suffix in {".js", ".jsx", ".ts", ".tsx"}:
        return any(name.endswith(test_suffix) for test_suffix in _TS_TEST_SUFFIXES) or (
            "__tests__" in parts[:-1]
        )
    return False


def is_documentation_path(path: str) -> bool:
    """Return True if *path* looks like a documentation file."""
    if path == "README.md" or path.startswith("docs/"):
        return True
    return PurePosixPath(path).suffix in _DOC_EXTENSIONS


def is_architecture_truth_path(path: str) -> bool:
    """Return True for strict architecture truth docs under ``.vibecode/architecture/``.

    These are the canonical human-maintained architecture documents that
    guard rules protect and handoff requirements enforce.
    """
    if not path.startswith(".vibecode/architecture/") or not path.endswith(".md"):
        return False
    return "/" not in path.removeprefix(".vibecode/architecture/")


def is_architecture_reference_doc(path: str) -> bool:
    """Return True for architecture-related reference documents outside truth dir.

    Includes files like ``docs/ARCHITECTURE_MAP_PRD.md`` that describe architecture
    but are not guarded as canonical truth.  Scoring may use these for relevance
    boosting; guard rules do not treat them as protected architecture truth.
    """
    lower = path.lower()
    if is_architecture_truth_path(path):
        return True
    if "/architecture/" in lower:
        return lower.endswith(".md")
    return lower.startswith("docs/") and "architecture" in lower and lower.endswith(".md")
