"""Tests for the combined symbol map builder (vibecode.indexer.symbol_map)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecode.indexer.scanner import FileStatus, IndexedFile
from vibecode.indexer.symbol_map import build_symbol_map, write_symbol_map


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _indexed(root: Path, rel: str) -> IndexedFile:
    """Build an IndexedFile for a file already written under *root*."""
    abs_path = root / Path(rel)
    return IndexedFile(path=rel, status=FileStatus.UNKNOWN, size=abs_path.stat().st_size)


# ---------------------------------------------------------------------------
# Fixture test: Python + TSX both appear in the output
# ---------------------------------------------------------------------------


class TestFixturePythonAndTsx:
    """A single fixture containing a Python file and a TSX file; both must appear."""

    def _build(self, tmp_path: Path) -> tuple[dict, list[str]]:
        _write(
            tmp_path / "src" / "service.py",
            "class UserService:\n    def get(self, uid): pass\n",
        )
        _write(
            tmp_path / "src" / "Button.tsx",
            "export function Button(): JSX.Element {\n  return <button />;\n}\n",
        )

        files = [
            _indexed(tmp_path, "src/service.py"),
            _indexed(tmp_path, "src/Button.tsx"),
        ]
        run_log: list[str] = []
        result = build_symbol_map(tmp_path, files, run_log=run_log)
        return result, run_log

    def test_python_file_in_output(self, tmp_path):
        result, _ = self._build(tmp_path)
        paths = {f["path"] for f in result["files"]}
        assert "src/service.py" in paths

    def test_tsx_file_in_output(self, tmp_path):
        result, _ = self._build(tmp_path)
        paths = {f["path"] for f in result["files"]}
        assert "src/Button.tsx" in paths

    def test_python_symbols_correct(self, tmp_path):
        result, _ = self._build(tmp_path)
        by_path = {f["path"]: f for f in result["files"]}
        py_entry = by_path["src/service.py"]
        names = {s["name"] for s in py_entry["symbols"]}
        assert "UserService" in names
        assert "get" in names

    def test_tsx_symbols_correct(self, tmp_path):
        result, _ = self._build(tmp_path)
        by_path = {f["path"]: f for f in result["files"]}
        tsx_entry = by_path["src/Button.tsx"]
        names = {s["name"] for s in tsx_entry["symbols"]}
        assert "Button" in names

    def test_tsx_component_kind(self, tmp_path):
        result, _ = self._build(tmp_path)
        by_path = {f["path"]: f for f in result["files"]}
        tsx_entry = by_path["src/Button.tsx"]
        kinds = {s["name"]: s["kind"] for s in tsx_entry["symbols"]}
        assert kinds["Button"] == "component"

    def test_no_run_log_errors(self, tmp_path):
        _, run_log = self._build(tmp_path)
        assert run_log == []

    def test_output_is_valid_json(self, tmp_path):
        result, _ = self._build(tmp_path)
        serialised = json.dumps(result)
        parsed = json.loads(serialised)
        assert isinstance(parsed, dict)


# ---------------------------------------------------------------------------
# Schema and metadata
# ---------------------------------------------------------------------------


class TestSchemaAndMetadata:
    def test_schema_marker_present(self, tmp_path):
        result = build_symbol_map(tmp_path, [])
        assert result["$schema"] == "vibecode/symbol-map/v1"

    def test_generated_at_present(self, tmp_path):
        result = build_symbol_map(tmp_path, [])
        assert "generated_at" in result
        assert result["generated_at"]

    def test_files_key_present(self, tmp_path):
        result = build_symbol_map(tmp_path, [])
        assert "files" in result
        assert isinstance(result["files"], list)

    def test_language_field_python(self, tmp_path):
        _write(tmp_path / "m.py", "def f(): pass\n")
        files = [_indexed(tmp_path, "m.py")]
        result = build_symbol_map(tmp_path, files)
        by_path = {f["path"]: f for f in result["files"]}
        assert by_path["m.py"]["language"] == "python"

    def test_language_field_tsx(self, tmp_path):
        _write(tmp_path / "C.tsx", "export function C() { return null; }\n")
        files = [_indexed(tmp_path, "C.tsx")]
        result = build_symbol_map(tmp_path, files)
        by_path = {f["path"]: f for f in result["files"]}
        assert by_path["C.tsx"]["language"] == "typescriptreact"


# ---------------------------------------------------------------------------
# Omission strategy: files without symbols are excluded
# ---------------------------------------------------------------------------


class TestOmissionStrategy:
    def test_empty_python_file_omitted(self, tmp_path):
        _write(tmp_path / "empty.py", "")
        files = [_indexed(tmp_path, "empty.py")]
        result = build_symbol_map(tmp_path, files)
        assert result["files"] == []

    def test_empty_ts_file_omitted(self, tmp_path):
        _write(tmp_path / "empty.ts", "")
        files = [_indexed(tmp_path, "empty.ts")]
        result = build_symbol_map(tmp_path, files)
        assert result["files"] == []

    def test_unsupported_language_omitted(self, tmp_path):
        _write(tmp_path / "styles.css", ".btn { color: red; }")
        files = [_indexed(tmp_path, "styles.css")]
        result = build_symbol_map(tmp_path, files)
        assert result["files"] == []

    def test_file_with_symbols_not_omitted(self, tmp_path):
        _write(tmp_path / "m.py", "def hello(): pass\n")
        files = [_indexed(tmp_path, "m.py")]
        result = build_symbol_map(tmp_path, files)
        assert len(result["files"]) == 1


# ---------------------------------------------------------------------------
# Parse error logging
# ---------------------------------------------------------------------------


class TestParseErrorLogging:
    def test_broken_python_logged_to_run_log(self, tmp_path):
        _write(tmp_path / "broken.py", "def foo(:\n    pass\n")
        files = [_indexed(tmp_path, "broken.py")]
        run_log: list[str] = []
        build_symbol_map(tmp_path, files, run_log=run_log)
        assert len(run_log) == 1
        assert "broken.py" in run_log[0]

    def test_broken_python_omitted_from_files(self, tmp_path):
        _write(tmp_path / "broken.py", "def foo(:\n    pass\n")
        files = [_indexed(tmp_path, "broken.py")]
        result = build_symbol_map(tmp_path, files, run_log=[])
        assert result["files"] == []

    def test_run_log_none_does_not_raise(self, tmp_path):
        _write(tmp_path / "broken.py", "def foo(:\n    pass\n")
        files = [_indexed(tmp_path, "broken.py")]
        # Must not raise even without a run_log receiver
        build_symbol_map(tmp_path, files, run_log=None)

    def test_good_file_alongside_broken_still_included(self, tmp_path):
        _write(tmp_path / "broken.py", "def foo(:\n    pass\n")
        _write(tmp_path / "good.py", "def ok(): pass\n")
        files = [
            _indexed(tmp_path, "broken.py"),
            _indexed(tmp_path, "good.py"),
        ]
        run_log: list[str] = []
        result = build_symbol_map(tmp_path, files, run_log=run_log)
        paths = {f["path"] for f in result["files"]}
        assert "good.py" in paths
        assert "broken.py" not in paths
        assert len(run_log) == 1


# ---------------------------------------------------------------------------
# Symbol shape
# ---------------------------------------------------------------------------


class TestSymbolShape:
    def test_symbol_has_name_kind_line_start(self, tmp_path):
        _write(tmp_path / "m.py", "def greet(): pass\n")
        files = [_indexed(tmp_path, "m.py")]
        result = build_symbol_map(tmp_path, files)
        sym = result["files"][0]["symbols"][0]
        assert "name" in sym
        assert "kind" in sym
        assert "line_start" in sym

    def test_python_symbol_has_line_end(self, tmp_path):
        _write(tmp_path / "m.py", "def greet():\n    return 1\n")
        files = [_indexed(tmp_path, "m.py")]
        result = build_symbol_map(tmp_path, files)
        sym = result["files"][0]["symbols"][0]
        assert "line_end" in sym
        assert sym["line_end"] is not None

    def test_ts_symbol_no_line_end(self, tmp_path):
        _write(tmp_path / "m.ts", "export function hello() {}\n")
        files = [_indexed(tmp_path, "m.ts")]
        result = build_symbol_map(tmp_path, files)
        sym = result["files"][0]["symbols"][0]
        assert "line_end" not in sym


# ---------------------------------------------------------------------------
# write_symbol_map
# ---------------------------------------------------------------------------


class TestWriteSymbolMap:
    def test_writes_valid_json_file(self, tmp_path):
        _write(tmp_path / "m.py", "def f(): pass\n")
        files = [_indexed(tmp_path, "m.py")]
        out = tmp_path / "out" / "symbol_map.json"
        write_symbol_map(tmp_path, files, out)
        assert out.exists()
        parsed = json.loads(out.read_text(encoding="utf-8"))
        assert "$schema" in parsed

    def test_creates_parent_dirs(self, tmp_path):
        _write(tmp_path / "m.py", "def f(): pass\n")
        files = [_indexed(tmp_path, "m.py")]
        out = tmp_path / "a" / "b" / "c" / "symbol_map.json"
        write_symbol_map(tmp_path, files, out)
        assert out.exists()

    def test_json_tool_compatible(self, tmp_path):
        """Output must be parseable by Python's json module (mirrors `python -m json.tool`)."""
        _write(tmp_path / "m.py", "class Foo:\n    def bar(self): pass\n")
        _write(tmp_path / "C.tsx", "export function Card() { return null; }\n")
        files = [
            _indexed(tmp_path, "m.py"),
            _indexed(tmp_path, "C.tsx"),
        ]
        out = tmp_path / "symbol_map.json"
        write_symbol_map(tmp_path, files, out)
        # json.loads succeeds without raising
        data = json.loads(out.read_text(encoding="utf-8"))
        paths = {f["path"] for f in data["files"]}
        assert "m.py" in paths
        assert "C.tsx" in paths
