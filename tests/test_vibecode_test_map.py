"""Tests for test discovery and source-to-test mapping."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecode.indexer.scanner import FileStatus, IndexedFile
from vibecode.indexer.test_map import (
    _classify_python_test_kind,
    _classify_ts_test_kind,
    _is_python_test,
    _is_ts_test,
    build_test_map,
    discover_tests,
    write_test_map,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _file(path: str, size: int = 100) -> IndexedFile:
    return IndexedFile(path=path, status=FileStatus.UNKNOWN, size=size)


def _write(path: Path, content: str = "# placeholder\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# _is_python_test
# ---------------------------------------------------------------------------


class TestIsPythonTest:
    def test_test_prefix_at_root(self):
        assert _is_python_test("test_foo.py")

    def test_test_prefix_in_subdir(self):
        assert _is_python_test("tests/test_bar.py")

    def test_test_suffix(self):
        assert _is_python_test("foo_test.py")
        assert _is_python_test("src/foo_test.py")

    def test_inside_tests_dir(self):
        assert _is_python_test("tests/helpers.py")

    def test_non_test_source(self):
        assert not _is_python_test("src/foo.py")
        assert not _is_python_test("vibecode/indexer/scanner.py")

    def test_non_python_file_rejected(self):
        assert not _is_python_test("tests/Button.test.tsx")
        assert not _is_python_test("Button.test.tsx")


# ---------------------------------------------------------------------------
# _is_ts_test
# ---------------------------------------------------------------------------


class TestIsTsTest:
    def test_test_tsx(self):
        assert _is_ts_test("src/Button.test.tsx")
        assert _is_ts_test("Button.test.tsx")

    def test_spec_tsx(self):
        assert _is_ts_test("src/Button.spec.tsx")

    def test_test_ts(self):
        assert _is_ts_test("src/util.test.ts")

    def test_spec_ts(self):
        assert _is_ts_test("src/util.spec.ts")

    def test_tests_subdir(self):
        assert _is_ts_test("__tests__/Button.tsx")

    def test_non_test_tsx(self):
        assert not _is_ts_test("src/Button.tsx")
        assert not _is_ts_test("src/index.ts")

    def test_non_ts_file_rejected(self):
        assert not _is_ts_test("test_foo.py")
        assert not _is_ts_test("tests/test_bar.py")


# ---------------------------------------------------------------------------
# _classify_python_test_kind
# ---------------------------------------------------------------------------


class TestClassifyPythonTestKind:
    def test_pure_pytest(self, tmp_path):
        p = _write(tmp_path / "test_foo.py", "def test_it(): assert True\n")
        assert _classify_python_test_kind(p) == "pytest"

    def test_unittest_import(self, tmp_path):
        p = _write(tmp_path / "test_bar.py", "import unittest\nclass T(unittest.TestCase): pass\n")
        assert _classify_python_test_kind(p) == "unittest"

    def test_from_unittest_import(self, tmp_path):
        p = _write(tmp_path / "test_baz.py", "from unittest import TestCase\n")
        assert _classify_python_test_kind(p) == "unittest"

    def test_missing_file_defaults_to_pytest(self, tmp_path):
        assert _classify_python_test_kind(tmp_path / "nonexistent.py") == "pytest"


# ---------------------------------------------------------------------------
# _classify_ts_test_kind
# ---------------------------------------------------------------------------


class TestClassifyTsTestKind:
    def test_jest_default(self, tmp_path):
        p = _write(tmp_path / "Button.test.tsx", "describe('Button', () => {})\n")
        assert _classify_ts_test_kind(p) == "jest"

    def test_playwright(self, tmp_path):
        p = _write(tmp_path / "e2e.spec.ts", "import { test } from '@playwright/test';\n")
        assert _classify_ts_test_kind(p) == "playwright"

    def test_cypress(self, tmp_path):
        p = _write(
            tmp_path / "login.spec.ts",
            "/// <reference types=\"cypress\" />\ndescribe('login', () => { cy.visit('/') })\n",
        )
        assert _classify_ts_test_kind(p) == "cypress"

    def test_missing_file_defaults_to_jest(self, tmp_path):
        assert _classify_ts_test_kind(tmp_path / "nonexistent.ts") == "jest"


# ---------------------------------------------------------------------------
# discover_tests
# ---------------------------------------------------------------------------


class TestDiscoverTests:
    def test_discovers_pytest_file(self, tmp_path):
        _write(tmp_path / "tests" / "test_foo.py", "def test_bar(): pass\n")
        tests = discover_tests(tmp_path, [_file("tests/test_foo.py")])
        assert len(tests) == 1
        assert tests[0].path == "tests/test_foo.py"
        assert tests[0].kind == "pytest"

    def test_discovers_unittest_file(self, tmp_path):
        _write(tmp_path / "test_bar.py", "import unittest\nclass T(unittest.TestCase): pass\n")
        tests = discover_tests(tmp_path, [_file("test_bar.py")])
        assert len(tests) == 1
        assert tests[0].kind == "unittest"

    def test_discovers_ts_jest(self, tmp_path):
        _write(tmp_path / "src" / "Button.test.tsx", "describe('Button', () => {})\n")
        tests = discover_tests(tmp_path, [_file("src/Button.test.tsx")])
        assert len(tests) == 1
        assert tests[0].path == "src/Button.test.tsx"
        assert tests[0].kind == "jest"

    def test_discovers_playwright(self, tmp_path):
        _write(tmp_path / "e2e" / "login.spec.ts", "import { test } from '@playwright/test';\n")
        tests = discover_tests(tmp_path, [_file("e2e/login.spec.ts")])
        assert len(tests) == 1
        assert tests[0].kind == "playwright"

    def test_non_test_files_excluded(self, tmp_path):
        _write(tmp_path / "src" / "foo.py")
        _write(tmp_path / "src" / "Button.tsx")
        tests = discover_tests(tmp_path, [_file("src/foo.py"), _file("src/Button.tsx")])
        assert tests == []

    def test_suffix_test_name(self, tmp_path):
        _write(tmp_path / "foo_test.py", "def test_x(): pass\n")
        tests = discover_tests(tmp_path, [_file("foo_test.py")])
        assert len(tests) == 1
        assert tests[0].path == "foo_test.py"


# ---------------------------------------------------------------------------
# build_test_map — Python source/test pair
# ---------------------------------------------------------------------------


class TestBuildTestMapPython:
    def test_name_match_test_prefix(self, tmp_path):
        _write(tmp_path / "src" / "foo.py", "def do_thing(): pass\n")
        _write(tmp_path / "tests" / "test_foo.py", "def test_it(): pass\n")
        result = build_test_map(tmp_path, [_file("src/foo.py"), _file("tests/test_foo.py")])
        rule = next((r for r in result["rules"] if r["path_pattern"] == "src/foo.py"), None)
        assert rule is not None
        assert "tests/test_foo.py" in rule["required_checks"]

    def test_name_match_test_suffix(self, tmp_path):
        _write(tmp_path / "src" / "bar.py", "x = 1\n")
        _write(tmp_path / "src" / "bar_test.py", "def test_x(): pass\n")
        result = build_test_map(tmp_path, [_file("src/bar.py"), _file("src/bar_test.py")])
        rule = next((r for r in result["rules"] if r["path_pattern"] == "src/bar.py"), None)
        assert rule is not None
        assert "src/bar_test.py" in rule["required_checks"]

    def test_import_based_match(self, tmp_path):
        """Test that a test file importing the source module is discovered."""
        _write(tmp_path / "src" / "utils.py", "def helper(): pass\n")
        _write(
            tmp_path / "tests" / "test_misc.py",
            "from src.utils import helper\ndef test_helper(): pass\n",
        )
        result = build_test_map(
            tmp_path, [_file("src/utils.py"), _file("tests/test_misc.py")]
        )
        rule = next((r for r in result["rules"] if r["path_pattern"] == "src/utils.py"), None)
        assert rule is not None
        assert "tests/test_misc.py" in rule["required_checks"]

    def test_source_without_test_produces_no_rule(self, tmp_path):
        _write(tmp_path / "src" / "orphan.py", "x = 1\n")
        result = build_test_map(tmp_path, [_file("src/orphan.py")])
        assert not any(r["path_pattern"] == "src/orphan.py" for r in result["rules"])

    def test_test_file_itself_has_no_rule(self, tmp_path):
        _write(tmp_path / "tests" / "test_foo.py", "def test_it(): pass\n")
        result = build_test_map(tmp_path, [_file("tests/test_foo.py")])
        assert not any(r["path_pattern"] == "tests/test_foo.py" for r in result["rules"])


# ---------------------------------------------------------------------------
# build_test_map — TSX source/test pair
# ---------------------------------------------------------------------------


class TestBuildTestMapTsx:
    def test_name_match_test_tsx(self, tmp_path):
        _write(tmp_path / "src" / "Button.tsx", "export const Button = () => null\n")
        _write(tmp_path / "src" / "Button.test.tsx", "describe('Button', () => {})\n")
        result = build_test_map(
            tmp_path, [_file("src/Button.tsx"), _file("src/Button.test.tsx")]
        )
        rule = next((r for r in result["rules"] if r["path_pattern"] == "src/Button.tsx"), None)
        assert rule is not None
        assert "src/Button.test.tsx" in rule["required_checks"]

    def test_name_match_spec_tsx(self, tmp_path):
        _write(tmp_path / "src" / "Modal.tsx", "export const Modal = () => null\n")
        _write(tmp_path / "src" / "Modal.spec.tsx", "describe('Modal', () => {})\n")
        result = build_test_map(
            tmp_path, [_file("src/Modal.tsx"), _file("src/Modal.spec.tsx")]
        )
        rule = next((r for r in result["rules"] if r["path_pattern"] == "src/Modal.tsx"), None)
        assert rule is not None
        assert "src/Modal.spec.tsx" in rule["required_checks"]

    def test_related_screen_test(self, tmp_path):
        """ButtonScreen.test.tsx should map to Button.tsx."""
        _write(tmp_path / "src" / "Button.tsx", "export const Button = () => null\n")
        _write(tmp_path / "src" / "ButtonScreen.test.tsx", "describe('ButtonScreen', () => {})\n")
        result = build_test_map(
            tmp_path, [_file("src/Button.tsx"), _file("src/ButtonScreen.test.tsx")]
        )
        rule = next((r for r in result["rules"] if r["path_pattern"] == "src/Button.tsx"), None)
        assert rule is not None
        assert "src/ButtonScreen.test.tsx" in rule["required_checks"]

    def test_import_based_match(self, tmp_path):
        """Test import resolution for TS source/test pairs."""
        _write(tmp_path / "src" / "utils.ts", "export function greet() {}\n")
        _write(
            tmp_path / "src" / "other.test.ts",
            "import { greet } from './utils';\ndescribe('g', () => {})\n",
        )
        result = build_test_map(
            tmp_path, [_file("src/utils.ts"), _file("src/other.test.ts")]
        )
        rule = next((r for r in result["rules"] if r["path_pattern"] == "src/utils.ts"), None)
        assert rule is not None
        assert "src/other.test.ts" in rule["required_checks"]

    def test_tsx_without_test_produces_no_rule(self, tmp_path):
        _write(tmp_path / "src" / "Orphan.tsx", "export const Orphan = () => null\n")
        result = build_test_map(tmp_path, [_file("src/Orphan.tsx")])
        assert not any(r["path_pattern"] == "src/Orphan.tsx" for r in result["rules"])


# ---------------------------------------------------------------------------
# build_test_map — config-level required_checks
# ---------------------------------------------------------------------------


class TestBuildTestMapRequiredChecks:
    def test_required_checks_produces_global_rule(self, tmp_path):
        result = build_test_map(tmp_path, [], required_checks=["lint", "tests"])
        global_rule = next((r for r in result["rules"] if r["path_pattern"] == "**"), None)
        assert global_rule is not None
        assert "lint" in global_rule["required_checks"]
        assert "tests" in global_rule["required_checks"]
        assert global_rule["reason"] == "project.yaml global required_checks"

    def test_global_rule_is_first(self, tmp_path):
        _write(tmp_path / "src" / "foo.py", "x = 1\n")
        _write(tmp_path / "tests" / "test_foo.py", "def test_x(): pass\n")
        result = build_test_map(
            tmp_path,
            [_file("src/foo.py"), _file("tests/test_foo.py")],
            required_checks=["lint"],
        )
        assert result["rules"][0]["path_pattern"] == "**"

    def test_no_required_checks_no_global_rule(self, tmp_path):
        result = build_test_map(tmp_path, [])
        assert not any(r["path_pattern"] == "**" for r in result["rules"])


# ---------------------------------------------------------------------------
# build_test_map — no tests found
# ---------------------------------------------------------------------------


class TestBuildTestMapNoTests:
    def test_empty_tests_list(self, tmp_path):
        result = build_test_map(tmp_path, [_file("src/foo.py")])
        assert result["tests"] == []

    def test_warning_present(self, tmp_path):
        result = build_test_map(tmp_path, [_file("src/foo.py")])
        assert "warning" in result
        assert result["warning"]

    def test_no_crash_on_empty_indexed_files(self, tmp_path):
        result = build_test_map(tmp_path, [])
        assert result["tests"] == []
        assert isinstance(result["rules"], list)


# ---------------------------------------------------------------------------
# build_test_map — JSON schema and structure
# ---------------------------------------------------------------------------


class TestBuildTestMapSchema:
    def test_schema_marker(self, tmp_path):
        result = build_test_map(tmp_path, [])
        assert result["$schema"] == "vibecode/test-map/v1"

    def test_generated_at_present(self, tmp_path):
        result = build_test_map(tmp_path, [])
        assert "generated_at" in result
        assert result["generated_at"]

    def test_output_is_json_serialisable(self, tmp_path):
        _write(tmp_path / "src" / "foo.py", "x = 1\n")
        _write(tmp_path / "tests" / "test_foo.py", "def test_x(): pass\n")
        result = build_test_map(
            tmp_path,
            [_file("src/foo.py"), _file("tests/test_foo.py")],
            required_checks=["lint"],
        )
        serialised = json.dumps(result)
        parsed = json.loads(serialised)
        assert parsed["$schema"] == "vibecode/test-map/v1"
        assert isinstance(parsed["tests"], list)
        assert isinstance(parsed["rules"], list)

    def test_tests_entries_have_path_and_kind(self, tmp_path):
        _write(tmp_path / "tests" / "test_foo.py", "def test_x(): pass\n")
        result = build_test_map(tmp_path, [_file("tests/test_foo.py")])
        assert len(result["tests"]) == 1
        assert "path" in result["tests"][0]
        assert "kind" in result["tests"][0]

    def test_rules_entries_have_required_fields(self, tmp_path):
        _write(tmp_path / "src" / "foo.py", "x = 1\n")
        _write(tmp_path / "tests" / "test_foo.py", "def test_x(): pass\n")
        result = build_test_map(
            tmp_path, [_file("src/foo.py"), _file("tests/test_foo.py")]
        )
        for rule in result["rules"]:
            assert "path_pattern" in rule
            assert "required_checks" in rule
            assert "reason" in rule


# ---------------------------------------------------------------------------
# write_test_map
# ---------------------------------------------------------------------------


class TestWriteTestMap:
    def test_creates_output_file(self, tmp_path):
        _write(tmp_path / "tests" / "test_foo.py", "def test_x(): pass\n")
        out = tmp_path / ".vibecode" / "index" / "test_map.json"
        write_test_map(tmp_path, [_file("tests/test_foo.py")], out)
        assert out.exists()

    def test_output_is_valid_json(self, tmp_path):
        _write(tmp_path / "tests" / "test_foo.py", "def test_x(): pass\n")
        out = tmp_path / "test_map.json"
        write_test_map(tmp_path, [_file("tests/test_foo.py")], out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["$schema"] == "vibecode/test-map/v1"

    def test_creates_parent_directories(self, tmp_path):
        out = tmp_path / "deep" / "nested" / "test_map.json"
        write_test_map(tmp_path, [], out)
        assert out.exists()
