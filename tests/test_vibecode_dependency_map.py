"""Tests for the import dependency map builder (vibecode.indexer.dependency_map)."""

from __future__ import annotations

import json
from pathlib import Path

from vibecode.indexer.dependency_map import build_dependency_map, write_dependency_map
from vibecode.indexer.scanner import FileStatus, IndexedFile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _indexed(root: Path, rel: str) -> IndexedFile:
    abs_path = root / Path(rel)
    return IndexedFile(path=rel, status=FileStatus.UNKNOWN, size=abs_path.stat().st_size)


def _edges_from(result: dict, from_posix: str) -> list[dict]:
    return [e for e in result["edges"] if e["from"] == from_posix]


def _edge(result: dict, from_posix: str, import_target: str) -> dict:
    for e in result["edges"]:
        if e["from"] == from_posix and e["import_target"] == import_target:
            return e
    raise KeyError(f"No edge {from_posix!r} -> {import_target!r}")


# ---------------------------------------------------------------------------
# Schema and metadata
# ---------------------------------------------------------------------------


class TestSchemaAndMetadata:
    def test_schema_marker(self, tmp_path):
        result = build_dependency_map(tmp_path, [])
        assert result["$schema"] == "vibecode/dependency-map/v1"

    def test_generated_at_present(self, tmp_path):
        result = build_dependency_map(tmp_path, [])
        assert "generated_at" in result
        assert result["generated_at"]

    def test_edges_list_present(self, tmp_path):
        result = build_dependency_map(tmp_path, [])
        assert "edges" in result
        assert isinstance(result["edges"], list)

    def test_empty_files_yields_no_edges(self, tmp_path):
        result = build_dependency_map(tmp_path, [])
        assert result["edges"] == []


# ---------------------------------------------------------------------------
# Python import extraction
# ---------------------------------------------------------------------------


class TestPythonImports:
    def test_bare_import_detected(self, tmp_path):
        _write(tmp_path / "m.py", "import os\n")
        result = build_dependency_map(tmp_path, [_indexed(tmp_path, "m.py")])
        targets = {e["import_target"] for e in result["edges"]}
        assert "os" in targets

    def test_from_import_module_detected(self, tmp_path):
        _write(tmp_path / "m.py", "from pathlib import Path\n")
        result = build_dependency_map(tmp_path, [_indexed(tmp_path, "m.py")])
        targets = {e["import_target"] for e in result["edges"]}
        assert "pathlib" in targets

    def test_external_stdlib_marked_external(self, tmp_path):
        _write(tmp_path / "m.py", "import os\n")
        result = build_dependency_map(tmp_path, [_indexed(tmp_path, "m.py")])
        e = _edge(result, "m.py", "os")
        assert e["status"] == "external"
        assert "resolved_path" not in e

    def test_external_third_party_marked_external(self, tmp_path):
        _write(tmp_path / "m.py", "import requests\n")
        result = build_dependency_map(tmp_path, [_indexed(tmp_path, "m.py")])
        e = _edge(result, "m.py", "requests")
        assert e["status"] == "external"

    def test_relative_import_resolved_to_sibling(self, tmp_path):
        """Unit test: Python relative import resolves to sibling file."""
        _write(tmp_path / "src" / "main.py", "from . import utils\n")
        _write(tmp_path / "src" / "utils.py", "def foo(): pass\n")
        result = build_dependency_map(tmp_path, [_indexed(tmp_path, "src/main.py")])
        e = _edge(result, "src/main.py", ".utils")
        assert e["status"] == "resolved"
        assert e["resolved_path"] == "src/utils.py"

    def test_from_dot_module_import_resolved(self, tmp_path):
        _write(tmp_path / "src" / "views.py", "from .models import User\n")
        _write(tmp_path / "src" / "models.py", "class User: pass\n")
        result = build_dependency_map(tmp_path, [_indexed(tmp_path, "src/views.py")])
        e = _edge(result, "src/views.py", ".models")
        assert e["status"] == "resolved"
        assert e["resolved_path"] == "src/models.py"

    def test_relative_import_unresolved_when_file_missing(self, tmp_path):
        _write(tmp_path / "src" / "main.py", "from . import missing\n")
        result = build_dependency_map(tmp_path, [_indexed(tmp_path, "src/main.py")])
        e = _edge(result, "src/main.py", ".missing")
        assert e["status"] == "unresolved"
        assert "resolved_path" not in e

    def test_absolute_package_import_resolved(self, tmp_path):
        _write(tmp_path / "app" / "main.py", "from app import utils\n")
        _write(tmp_path / "app" / "__init__.py", "")
        _write(tmp_path / "app" / "utils.py", "")
        result = build_dependency_map(tmp_path, [_indexed(tmp_path, "app/main.py")])
        e = _edge(result, "app/main.py", "app")
        assert e["status"] == "resolved"
        assert e["resolved_path"] == "app/__init__.py"

    def test_does_not_crash_on_broken_python(self, tmp_path):
        _write(tmp_path / "broken.py", "def foo(:\n    pass\n")
        result = build_dependency_map(tmp_path, [_indexed(tmp_path, "broken.py")])
        assert isinstance(result["edges"], list)

    def test_does_not_crash_on_unknown_package(self, tmp_path):
        _write(tmp_path / "m.py", "import totally_nonexistent_package_xyz\n")
        result = build_dependency_map(tmp_path, [_indexed(tmp_path, "m.py")])
        e = _edge(result, "m.py", "totally_nonexistent_package_xyz")
        assert e["status"] == "external"

    def test_type_field_is_python(self, tmp_path):
        _write(tmp_path / "m.py", "import os\n")
        result = build_dependency_map(tmp_path, [_indexed(tmp_path, "m.py")])
        e = _edge(result, "m.py", "os")
        assert e["type"] == "python"

    def test_multiple_imports_all_detected(self, tmp_path):
        src = "import os\nimport sys\nfrom pathlib import Path\n"
        _write(tmp_path / "m.py", src)
        result = build_dependency_map(tmp_path, [_indexed(tmp_path, "m.py")])
        targets = {e["import_target"] for e in _edges_from(result, "m.py")}
        assert {"os", "sys", "pathlib"}.issubset(targets)


# ---------------------------------------------------------------------------
# TypeScript / JavaScript import extraction
# ---------------------------------------------------------------------------


class TestTypescriptImports:
    def test_relative_import_resolved(self, tmp_path):
        """Unit test: TS relative import resolves to sibling .ts file."""
        _write(tmp_path / "src" / "main.ts", "import { foo } from './utils';\n")
        _write(tmp_path / "src" / "utils.ts", "export const foo = 1;\n")
        result = build_dependency_map(tmp_path, [_indexed(tmp_path, "src/main.ts")])
        e = _edge(result, "src/main.ts", "./utils")
        assert e["status"] == "resolved"
        assert e["resolved_path"] == "src/utils.ts"

    def test_relative_tsx_import_resolved(self, tmp_path):
        _write(tmp_path / "src" / "App.tsx", "import Button from './Button';\n")
        _write(tmp_path / "src" / "Button.tsx", "export default function Button() {}\n")
        result = build_dependency_map(tmp_path, [_indexed(tmp_path, "src/App.tsx")])
        e = _edge(result, "src/App.tsx", "./Button")
        assert e["status"] == "resolved"
        assert e["resolved_path"] == "src/Button.tsx"

    def test_external_package_marked_external(self, tmp_path):
        """Unit test: TS external import marked external."""
        _write(tmp_path / "src" / "main.ts", "import React from 'react';\n")
        result = build_dependency_map(tmp_path, [_indexed(tmp_path, "src/main.ts")])
        e = _edge(result, "src/main.ts", "react")
        assert e["status"] == "external"
        assert "resolved_path" not in e

    def test_unresolved_relative_marked_unresolved(self, tmp_path):
        """Unit test: relative TS import with no matching file → unresolved."""
        _write(tmp_path / "src" / "main.ts", "import { foo } from './missing';\n")
        result = build_dependency_map(tmp_path, [_indexed(tmp_path, "src/main.ts")])
        e = _edge(result, "src/main.ts", "./missing")
        assert e["status"] == "unresolved"
        assert "resolved_path" not in e

    def test_side_effect_import_detected(self, tmp_path):
        _write(tmp_path / "src" / "main.ts", "import './styles.css';\n")
        result = build_dependency_map(tmp_path, [_indexed(tmp_path, "src/main.ts")])
        targets = {e["import_target"] for e in _edges_from(result, "src/main.ts")}
        assert "./styles.css" in targets

    def test_type_import_detected(self, tmp_path):
        _write(tmp_path / "src" / "main.ts", "import type { Foo } from './types';\n")
        result = build_dependency_map(tmp_path, [_indexed(tmp_path, "src/main.ts")])
        targets = {e["import_target"] for e in _edges_from(result, "src/main.ts")}
        assert "./types" in targets

    def test_require_detected(self, tmp_path):
        _write(tmp_path / "src" / "main.js", "const x = require('./helper');\n")
        _write(tmp_path / "src" / "helper.js", "module.exports = {};\n")
        result = build_dependency_map(tmp_path, [_indexed(tmp_path, "src/main.js")])
        e = _edge(result, "src/main.js", "./helper")
        assert e["status"] == "resolved"

    def test_parent_relative_import_resolved(self, tmp_path):
        _write(tmp_path / "src" / "views" / "list.ts", "import { db } from '../db';\n")
        _write(tmp_path / "src" / "db.ts", "export const db = {};\n")
        result = build_dependency_map(tmp_path, [_indexed(tmp_path, "src/views/list.ts")])
        e = _edge(result, "src/views/list.ts", "../db")
        assert e["status"] == "resolved"
        assert e["resolved_path"] == "src/db.ts"

    def test_type_field_reflects_language(self, tmp_path):
        _write(tmp_path / "m.ts", "import React from 'react';\n")
        result = build_dependency_map(tmp_path, [_indexed(tmp_path, "m.ts")])
        e = _edge(result, "m.ts", "react")
        assert e["type"] == "typescript"

    def test_no_duplicate_edges_for_same_import(self, tmp_path):
        src = "import React from 'react';\nimport React from 'react';\n"
        _write(tmp_path / "m.ts", src)
        result = build_dependency_map(tmp_path, [_indexed(tmp_path, "m.ts")])
        react_edges = [e for e in result["edges"] if e["import_target"] == "react"]
        assert len(react_edges) == 1


# ---------------------------------------------------------------------------
# External imports (combined acceptance criterion)
# ---------------------------------------------------------------------------


class TestExternalImports:
    def test_python_external_no_resolved_path(self, tmp_path):
        _write(tmp_path / "m.py", "import numpy\n")
        result = build_dependency_map(tmp_path, [_indexed(tmp_path, "m.py")])
        e = _edge(result, "m.py", "numpy")
        assert e["status"] == "external"
        assert "resolved_path" not in e

    def test_ts_external_no_resolved_path(self, tmp_path):
        _write(tmp_path / "m.ts", "import axios from 'axios';\n")
        result = build_dependency_map(tmp_path, [_indexed(tmp_path, "m.ts")])
        e = _edge(result, "m.ts", "axios")
        assert e["status"] == "external"
        assert "resolved_path" not in e


# ---------------------------------------------------------------------------
# Valid JSON output
# ---------------------------------------------------------------------------


class TestValidJson:
    def test_output_is_valid_json(self, tmp_path):
        _write(tmp_path / "m.py", "import os\nfrom pathlib import Path\n")
        result = build_dependency_map(tmp_path, [_indexed(tmp_path, "m.py")])
        serialised = json.dumps(result)
        parsed = json.loads(serialised)
        assert isinstance(parsed, dict)
        assert "edges" in parsed

    def test_write_creates_valid_json_file(self, tmp_path):
        _write(tmp_path / "m.py", "import os\n")
        out = tmp_path / "out" / "dependency_map.json"
        write_dependency_map(tmp_path, [_indexed(tmp_path, "m.py")], out)
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "$schema" in data
        assert "edges" in data

    def test_write_creates_parent_dirs(self, tmp_path):
        _write(tmp_path / "m.py", "import os\n")
        out = tmp_path / "a" / "b" / "dependency_map.json"
        write_dependency_map(tmp_path, [_indexed(tmp_path, "m.py")], out)
        assert out.exists()

    def test_mixed_python_and_ts_output_valid(self, tmp_path):
        _write(tmp_path / "main.py", "import os\nfrom . import helper\n")
        _write(tmp_path / "helper.py", "")
        _write(tmp_path / "app.ts", "import React from 'react';\nimport { x } from './lib';\n")
        _write(tmp_path / "lib.ts", "export const x = 1;\n")
        files = [
            _indexed(tmp_path, "main.py"),
            _indexed(tmp_path, "app.ts"),
        ]
        result = build_dependency_map(tmp_path, files)
        serialised = json.dumps(result)
        parsed = json.loads(serialised)
        assert isinstance(parsed["edges"], list)
        assert len(parsed["edges"]) > 0

    def test_unsupported_file_skipped(self, tmp_path):
        _write(tmp_path / "styles.css", ".btn { color: red; }")
        result = build_dependency_map(tmp_path, [_indexed(tmp_path, "styles.css")])
        assert result["edges"] == []
