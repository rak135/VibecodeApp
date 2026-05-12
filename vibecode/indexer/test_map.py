"""Test discovery and source-to-test mapping."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from vibecode.indexer.classifier import detect_language
from vibecode.indexer.dependency_map import (
    _extract_python_imports,
    _extract_ts_imports,
    _resolve_ts_import,
)
from vibecode.indexer.scanner import IndexedFile

_SCHEMA = "vibecode/test-map/v1"

_PY_LANG = "python"
_TS_LANGS: frozenset[str] = frozenset({
    "typescript",
    "typescriptreact",
    "javascript",
    "javascriptreact",
})

_TS_TEST_EXTS: tuple[str, ...] = (
    ".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx",
    ".test.js", ".spec.js", ".test.jsx", ".spec.jsx",
)


@dataclass
class TestEntry:
    """A discovered test file with its framework kind."""

    path: str  # relative POSIX path
    kind: str  # "pytest", "unittest", "jest", "playwright", "cypress"


@dataclass
class TestRule:
    """Mapping from a source-file pattern to the checks that must pass."""

    path_pattern: str
    required_checks: list[str] = field(default_factory=list)
    reason: str = ""


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------


def _is_python_test(posix: str) -> bool:
    """Return True if *posix* looks like a Python test file."""
    if detect_language(posix) != _PY_LANG:
        return False
    name = PurePosixPath(posix).name
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    parts = posix.split("/")
    return "tests" in parts[:-1]


def _is_ts_test(posix: str) -> bool:
    """Return True if *posix* looks like a TypeScript/React test file."""
    if detect_language(posix) not in _TS_LANGS:
        return False
    name = PurePosixPath(posix).name
    if any(name.endswith(ext) for ext in _TS_TEST_EXTS):
        return True
    parts = posix.split("/")
    return "__tests__" in parts[:-1]


def _classify_python_test_kind(path: Path) -> str:
    """Return "pytest" or "unittest" based on the file's imports."""
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "pytest"
    if "import unittest" in src or "from unittest" in src:
        return "unittest"
    return "pytest"


def _classify_ts_test_kind(path: Path) -> str:
    """Return "playwright", "cypress", or "jest" based on the file's content."""
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "jest"
    if "@playwright/test" in src:
        return "playwright"
    if "cypress" in src.lower():
        return "cypress"
    return "jest"


# ---------------------------------------------------------------------------
# Test discovery
# ---------------------------------------------------------------------------


def discover_tests(root: Path, indexed_files: list[IndexedFile]) -> list[TestEntry]:
    """Return a :class:`TestEntry` for every test file in *indexed_files*."""
    entries: list[TestEntry] = []
    for f in indexed_files:
        if _is_python_test(f.path):
            kind = _classify_python_test_kind(root / Path(f.path))
            entries.append(TestEntry(path=f.path, kind=kind))
        elif _is_ts_test(f.path):
            kind = _classify_ts_test_kind(root / Path(f.path))
            entries.append(TestEntry(path=f.path, kind=kind))
    return entries


# ---------------------------------------------------------------------------
# Import-based matching
# ---------------------------------------------------------------------------


def _python_test_imports_source(test_path: Path, source_posix: str) -> bool:
    """Return True if *test_path* imports the module corresponding to *source_posix*."""
    stem = PurePosixPath(source_posix).stem
    module_path = PurePosixPath(source_posix).with_suffix("").as_posix().replace("/", ".")
    for raw in _extract_python_imports(test_path):
        clean = raw.lstrip(".")
        if clean in (stem, module_path) or clean.endswith(f".{stem}"):
            return True
    return False


def _ts_test_imports_source(
    test_path: Path,
    test_posix: str,
    source_posix: str,
    root: Path,
) -> bool:
    """Return True if the TS test file has a relative import that resolves to *source_posix*."""
    for imp in _extract_ts_imports(test_path):
        if not (imp.startswith("./") or imp.startswith("../")):
            continue
        if _resolve_ts_import(imp, test_posix, root) == source_posix:
            return True
    return False


# ---------------------------------------------------------------------------
# Rule builders
# ---------------------------------------------------------------------------


def _build_rule_for_python_source(
    source_posix: str,
    tests: list[TestEntry],
    root: Path,
) -> TestRule | None:
    """Return a :class:`TestRule` mapping *source_posix* to any matching Python tests."""
    stem = PurePosixPath(source_posix).stem
    matched: list[str] = []
    reasons: list[str] = []

    for t in tests:
        test_name = PurePosixPath(t.path).name
        if test_name == f"test_{stem}.py":
            if t.path not in matched:
                matched.append(t.path)
                reasons.append(f"name match: {test_name}")
        elif test_name == f"{stem}_test.py":
            if t.path not in matched:
                matched.append(t.path)
                reasons.append(f"name match: {test_name}")
        elif _python_test_imports_source(root / Path(t.path), source_posix):
            if t.path not in matched:
                matched.append(t.path)
                reasons.append(f"import match: {t.path}")

    if not matched:
        return None
    return TestRule(
        path_pattern=source_posix,
        required_checks=matched,
        reason="; ".join(reasons),
    )


def _test_stem_from_name(test_name: str) -> str:
    """Strip test/spec extension from *test_name* to get the base stem."""
    for ext in _TS_TEST_EXTS:
        if test_name.endswith(ext):
            return test_name[: -len(ext)]
    return PurePosixPath(test_name).stem


def _build_rule_for_ts_source(
    source_posix: str,
    tests: list[TestEntry],
    root: Path,
) -> TestRule | None:
    """Return a :class:`TestRule` mapping *source_posix* to any matching TS tests."""
    stem = PurePosixPath(source_posix).stem
    matched: list[str] = []
    reasons: list[str] = []

    for t in tests:
        test_name = PurePosixPath(t.path).name

        # Direct name match: Component.test.tsx / Component.spec.tsx
        if any(test_name == f"{stem}{ext}" for ext in _TS_TEST_EXTS):
            if t.path not in matched:
                matched.append(t.path)
                reasons.append(f"name match: {test_name}")
            continue

        # Related screen tests: test stem starts with source stem
        # e.g. ButtonScreen.test.tsx -> Button.tsx
        test_stem = _test_stem_from_name(test_name)
        if (
            stem
            and test_stem.lower().startswith(stem.lower())
            and test_stem.lower() != stem.lower()
        ):
            if t.path not in matched:
                matched.append(t.path)
                reasons.append(f"name contains: {stem}")
            continue

        # Import-based: relative import in the test resolves to the source file
        if _ts_test_imports_source(root / Path(t.path), t.path, source_posix, root):
            if t.path not in matched:
                matched.append(t.path)
                reasons.append(f"import match: {t.path}")

    if not matched:
        return None
    return TestRule(
        path_pattern=source_posix,
        required_checks=matched,
        reason="; ".join(reasons),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_test_map(
    root: Path,
    indexed_files: list[IndexedFile],
    required_checks: list[str] | None = None,
) -> dict:
    """Return the test map as a JSON-serialisable dict.

    *required_checks* from project.yaml are prepended as a global ``"**"`` rule
    so they take precedence over per-file auto-discovered rules.
    """
    tests = discover_tests(root, indexed_files)

    rules: list[dict] = []

    if required_checks:
        rules.append({
            "path_pattern": "**",
            "required_checks": list(required_checks),
            "reason": "project.yaml global required_checks",
        })

    py_tests = [t for t in tests if detect_language(t.path) == _PY_LANG]
    ts_tests = [t for t in tests if detect_language(t.path) in _TS_LANGS]

    for f in indexed_files:
        if _is_python_test(f.path) or _is_ts_test(f.path):
            continue
        lang = detect_language(f.path)
        if lang == _PY_LANG:
            rule = _build_rule_for_python_source(f.path, py_tests, root)
        elif lang in _TS_LANGS:
            rule = _build_rule_for_ts_source(f.path, ts_tests, root)
        else:
            continue
        if rule is not None:
            rules.append({
                "path_pattern": rule.path_pattern,
                "required_checks": rule.required_checks,
                "reason": rule.reason,
            })

    result: dict = {
        "$schema": _SCHEMA,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "tests": [{"path": t.path, "kind": t.kind} for t in tests],
        "rules": rules,
    }

    if not tests:
        result["warning"] = "No test files discovered in indexed files."

    return result


def write_test_map(
    root: Path,
    indexed_files: list[IndexedFile],
    output_path: Path,
    required_checks: list[str] | None = None,
) -> None:
    """Write the test map JSON to *output_path*, creating parent directories as needed."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = build_test_map(root, indexed_files, required_checks=required_checks)
    output_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
