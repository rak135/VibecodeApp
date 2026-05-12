"""Import dependency map builder.

Extracts import edges from Python and TypeScript/JavaScript files and
produces a ``dependency_map.json`` showing that file A depends on module B.

Edge status
~~~~~~~~~~~
* Edges with a ``resolved_path`` were traced to a file inside the repository.
* ``status: "external"`` — bare (non-relative) import that was not found locally.
* ``status: "unresolved"`` — relative import whose target could not be found.
"""

from __future__ import annotations

import ast
import json
import posixpath
import re
import warnings
from datetime import datetime, timezone
from pathlib import Path

from vibecode.indexer.classifier import detect_language
from vibecode.indexer.scanner import IndexedFile

_SCHEMA = "vibecode/dependency-map/v1"

_PY_LANG = "python"
_TS_LANGS: frozenset[str] = frozenset({
    "typescript",
    "typescriptreact",
    "javascript",
    "javascriptreact",
})

# Matches: import ... from '...' / import '...' / import type ... from '...'
_TS_IMPORT_RE: re.Pattern[str] = re.compile(
    r"""\bimport\s+(?:type\s+)?(?:[^'"]+?\s+from\s+)?['"]([^'"]+)['"]""",
    re.MULTILINE,
)
_TS_REQUIRE_RE: re.Pattern[str] = re.compile(r"""require\(['"]([^'"]+)['"]\)""")

_TS_EXTENSIONS: tuple[str, ...] = (".ts", ".tsx", ".js", ".jsx")


# ---------------------------------------------------------------------------
# Python import extraction
# ---------------------------------------------------------------------------


def _extract_python_imports(path: Path) -> list[str]:
    """Return raw import targets from *path* using the AST.

    * ``import os`` → ``["os"]``
    * ``from pathlib import Path`` → ``["pathlib"]``
    * ``from . import helpers`` → ``[".helpers"]``
    * ``from .utils import foo`` → ``[".utils"]``

    Returns an empty list on syntax or I/O error (no exception raised).
    """
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, OSError):
        return []

    targets: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                targets.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            level = node.level
            prefix = "." * level
            if module:
                targets.append(prefix + module)
            else:
                # e.g. "from . import helpers, utils" → ".helpers", ".utils"
                for alias in node.names:
                    targets.append(prefix + alias.name)
    return targets


# ---------------------------------------------------------------------------
# TS/JS import extraction
# ---------------------------------------------------------------------------


def _extract_ts_imports(path: Path) -> list[str]:
    """Return raw import targets from a TypeScript/JavaScript file at *path*."""
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    seen: set[str] = set()
    targets: list[str] = []
    for m in _TS_IMPORT_RE.finditer(source):
        t = m.group(1)
        if t not in seen:
            seen.add(t)
            targets.append(t)
    for m in _TS_REQUIRE_RE.finditer(source):
        t = m.group(1)
        if t not in seen:
            seen.add(t)
            targets.append(t)
    return targets


# ---------------------------------------------------------------------------
# Path resolution helpers
# ---------------------------------------------------------------------------


def _resolve_python_import(
    import_target: str,
    from_posix: str,
    root: Path,
) -> str | None:
    """Try to resolve *import_target* to a POSIX path relative to *root*.

    Returns the relative POSIX path if a matching ``.py`` file or package
    ``__init__.py`` is found, otherwise ``None``.
    """
    if import_target.startswith("."):
        level = len(import_target) - len(import_target.lstrip("."))
        module_part = import_target[level:]
        from_dir = from_posix.split("/")[:-1]
        levels_up = level - 1
        if levels_up > len(from_dir):
            return None
        base_parts = from_dir[:-levels_up] if levels_up > 0 else from_dir
        candidate_parts = base_parts + module_part.split(".") if module_part else base_parts
    else:
        candidate_parts = import_target.split(".")

    return _try_python_candidate(root, candidate_parts)


def _try_python_candidate(root: Path, parts: list[str]) -> str | None:
    if not parts:
        return None
    base = Path(*parts)
    # Try as a .py module file
    py_file = root / base.with_suffix(".py")
    if py_file.is_file():
        return py_file.relative_to(root).as_posix()
    # Try as a package (directory with __init__.py)
    init_file = root / base / "__init__.py"
    if init_file.is_file():
        return init_file.relative_to(root).as_posix()
    return None


def _resolve_ts_import(
    import_target: str,
    from_posix: str,
    root: Path,
) -> str | None:
    """Try to resolve a TS/JS relative import to a path inside *root*.

    Only relative specifiers (``./`` or ``../``) are attempted.
    Returns the relative POSIX path if found, otherwise ``None``.
    """
    if not (import_target.startswith("./") or import_target.startswith("../")):
        return None  # external or path-alias specifier

    from_dir = "/".join(from_posix.split("/")[:-1])
    if from_dir:
        raw = posixpath.normpath(posixpath.join(from_dir, import_target))
    else:
        raw = posixpath.normpath(import_target)

    candidate_base = root / Path(raw)

    # Try with known extensions (no extension added, exact first)
    if candidate_base.is_file():
        return candidate_base.relative_to(root).as_posix()
    for ext in _TS_EXTENSIONS:
        candidate = root / Path(raw + ext)
        if candidate.is_file():
            return candidate.relative_to(root).as_posix()
    # Try as a directory index
    for ext in _TS_EXTENSIONS:
        candidate = root / Path(raw) / f"index{ext}"
        if candidate.is_file():
            return candidate.relative_to(root).as_posix()
    return None


# ---------------------------------------------------------------------------
# Edge builder
# ---------------------------------------------------------------------------


def _make_edge(
    from_posix: str,
    import_target: str,
    language: str,
    root: Path,
) -> dict:
    edge: dict = {
        "from": from_posix,
        "import_target": import_target,
        "type": language,
    }
    if language == _PY_LANG:
        resolved = _resolve_python_import(import_target, from_posix, root)
    else:
        resolved = _resolve_ts_import(import_target, from_posix, root)

    if resolved is not None:
        edge["status"] = "resolved"
        edge["resolved_path"] = resolved
    elif import_target.startswith("."):
        edge["status"] = "unresolved"
    else:
        edge["status"] = "external"

    return edge


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_dependency_map(
    root: Path,
    indexed_files: list[IndexedFile],
    run_log: list[str] | None = None,
) -> dict:
    """Return the dependency map dict from *indexed_files*.

    Parsing errors are appended to *run_log* when provided.
    """
    edges: list[dict] = []

    for f in indexed_files:
        language = detect_language(f.path)
        abs_path = root / Path(f.path)

        if language == _PY_LANG:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                targets = _extract_python_imports(abs_path)
            for w in caught:
                if run_log is not None:
                    run_log.append(str(w.message))
        elif language in _TS_LANGS:
            targets = _extract_ts_imports(abs_path)
        else:
            continue

        for target in targets:
            if target:
                edges.append(_make_edge(f.path, target, language, root))

    return {
        "$schema": _SCHEMA,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "edges": edges,
    }


def write_dependency_map(
    root: Path,
    indexed_files: list[IndexedFile],
    output_path: Path,
    run_log: list[str] | None = None,
) -> None:
    """Write the dependency map JSON to *output_path*, creating parent dirs as needed."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = build_dependency_map(root, indexed_files, run_log=run_log)
    output_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
