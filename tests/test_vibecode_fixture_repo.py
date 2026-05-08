"""Tests exercising the main indexer behaviour against a real fixture repository.

The fixture lives at tests/fixtures/sample_repo/ and contains:
- Python backend with class / function (backend/main.py)
- Python test file (tests/test_main.py)
- TSX frontend screen with React component (frontend/screens/HomeScreen.tsx)
- TSX test file (frontend/screens/HomeScreen.test.tsx)
- package.json with a test script
- pyproject.toml
- README.md
- dummy node_modules/.venv directories that must NOT be indexed
- a high-risk engine module (engine/matching.py)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vibecode.indexer.inventory import build_inventory
from vibecode.indexer.scanner import scan
from vibecode.indexer.symbol_map import build_symbol_map
from vibecode.indexer.test_map import build_test_map

# ---------------------------------------------------------------------------
# Fixture path
# ---------------------------------------------------------------------------

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "sample_repo"

# Expected source files (relative POSIX paths)
EXPECTED_SOURCE_FILES = {
    "README.md",
    "pyproject.toml",
    "package.json",
    "backend/main.py",
    "tests/test_main.py",
    "frontend/screens/HomeScreen.tsx",
    "frontend/screens/HomeScreen.test.tsx",
    "engine/matching.py",
}

EXCLUDED_PATH_FRAGMENTS = {"node_modules", ".venv"}


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------


@pytest.fixture()
def fixture_files(monkeypatch):
    """Scan the fixture repo with git disabled; return the list of IndexedFile."""
    monkeypatch.setattr("vibecode.indexer.scanner._is_git_repo", lambda _root: False)
    return scan(FIXTURE_ROOT)


# ---------------------------------------------------------------------------
# File inventory
# ---------------------------------------------------------------------------


class TestFixtureInventory:
    def test_expected_source_files_are_indexed(self, fixture_files):
        paths = {f.path for f in fixture_files}
        for expected in EXPECTED_SOURCE_FILES:
            assert expected in paths, f"expected {expected!r} in inventory"

    def test_node_modules_excluded(self, fixture_files):
        paths = {f.path for f in fixture_files}
        assert not any("node_modules" in p for p in paths)

    def test_venv_excluded(self, fixture_files):
        paths = {f.path for f in fixture_files}
        assert not any(".venv" in p for p in paths)

    def test_inventory_build_succeeds(self, fixture_files):
        inv = build_inventory("sample", FIXTURE_ROOT, fixture_files)
        assert inv["$schema"] == "vibecode/file-inventory/v1"
        assert isinstance(inv["files"], list)
        assert len(inv["files"]) >= len(EXPECTED_SOURCE_FILES)

    def test_engine_matching_flagged_high_risk(self, fixture_files):
        inv = build_inventory("sample", FIXTURE_ROOT, fixture_files)
        by_path = {r["path"]: r for r in inv["files"]}
        assert "engine/matching.py" in by_path
        assert by_path["engine/matching.py"]["risk_level"] == "high"

    def test_test_files_flagged_as_test(self, fixture_files):
        inv = build_inventory("sample", FIXTURE_ROOT, fixture_files)
        by_path = {r["path"]: r for r in inv["files"]}
        assert by_path["tests/test_main.py"]["is_test"] is True
        assert by_path["frontend/screens/HomeScreen.test.tsx"]["is_test"] is True

    def test_python_files_have_correct_language(self, fixture_files):
        inv = build_inventory("sample", FIXTURE_ROOT, fixture_files)
        by_path = {r["path"]: r for r in inv["files"]}
        assert by_path["backend/main.py"]["language"] == "python"
        assert by_path["engine/matching.py"]["language"] == "python"

    def test_tsx_file_has_correct_language(self, fixture_files):
        inv = build_inventory("sample", FIXTURE_ROOT, fixture_files)
        by_path = {r["path"]: r for r in inv["files"]}
        assert by_path["frontend/screens/HomeScreen.tsx"]["language"] == "typescriptreact"

    def test_pyproject_toml_flagged_as_config(self, fixture_files):
        inv = build_inventory("sample", FIXTURE_ROOT, fixture_files)
        by_path = {r["path"]: r for r in inv["files"]}
        assert by_path["pyproject.toml"]["is_config"] is True

    def test_package_json_flagged_as_config(self, fixture_files):
        inv = build_inventory("sample", FIXTURE_ROOT, fixture_files)
        by_path = {r["path"]: r for r in inv["files"]}
        assert by_path["package.json"]["is_config"] is True

    def test_readme_flagged_as_doc(self, fixture_files):
        inv = build_inventory("sample", FIXTURE_ROOT, fixture_files)
        by_path = {r["path"]: r for r in inv["files"]}
        assert by_path["README.md"]["is_doc"] is True


# ---------------------------------------------------------------------------
# Symbol map
# ---------------------------------------------------------------------------


class TestFixtureSymbolMap:
    def test_python_backend_in_symbol_map(self, fixture_files):
        result = build_symbol_map(FIXTURE_ROOT, fixture_files)
        paths = {f["path"] for f in result["files"]}
        assert "backend/main.py" in paths

    def test_tsx_screen_in_symbol_map(self, fixture_files):
        result = build_symbol_map(FIXTURE_ROOT, fixture_files)
        paths = {f["path"] for f in result["files"]}
        assert "frontend/screens/HomeScreen.tsx" in paths

    def test_engine_matching_in_symbol_map(self, fixture_files):
        result = build_symbol_map(FIXTURE_ROOT, fixture_files)
        paths = {f["path"] for f in result["files"]}
        assert "engine/matching.py" in paths

    def test_python_class_symbol_extracted(self, fixture_files):
        result = build_symbol_map(FIXTURE_ROOT, fixture_files)
        by_path = {f["path"]: f for f in result["files"]}
        names = {s["name"] for s in by_path["backend/main.py"]["symbols"]}
        assert "UserService" in names

    def test_python_function_symbol_extracted(self, fixture_files):
        result = build_symbol_map(FIXTURE_ROOT, fixture_files)
        by_path = {f["path"]: f for f in result["files"]}
        names = {s["name"] for s in by_path["backend/main.py"]["symbols"]}
        assert "health_check" in names

    def test_tsx_component_symbol_extracted(self, fixture_files):
        result = build_symbol_map(FIXTURE_ROOT, fixture_files)
        by_path = {f["path"]: f for f in result["files"]}
        names = {s["name"] for s in by_path["frontend/screens/HomeScreen.tsx"]["symbols"]}
        assert "HomeScreen" in names

    def test_tsx_component_has_component_kind(self, fixture_files):
        result = build_symbol_map(FIXTURE_ROOT, fixture_files)
        by_path = {f["path"]: f for f in result["files"]}
        kinds = {s["name"]: s["kind"] for s in by_path["frontend/screens/HomeScreen.tsx"]["symbols"]}
        assert kinds["HomeScreen"] == "component"

    def test_matching_engine_class_extracted(self, fixture_files):
        result = build_symbol_map(FIXTURE_ROOT, fixture_files)
        by_path = {f["path"]: f for f in result["files"]}
        names = {s["name"] for s in by_path["engine/matching.py"]["symbols"]}
        assert "MatchingEngine" in names


# ---------------------------------------------------------------------------
# Test map
# ---------------------------------------------------------------------------


class TestFixtureTestMap:
    def test_python_source_maps_to_test_file(self, fixture_files):
        result = build_test_map(FIXTURE_ROOT, fixture_files)
        rule = next(
            (r for r in result["rules"] if r["path_pattern"] == "backend/main.py"), None
        )
        assert rule is not None
        assert "tests/test_main.py" in rule["required_checks"]

    def test_tsx_screen_maps_to_test_file(self, fixture_files):
        result = build_test_map(FIXTURE_ROOT, fixture_files)
        rule = next(
            (r for r in result["rules"] if r["path_pattern"] == "frontend/screens/HomeScreen.tsx"),
            None,
        )
        assert rule is not None
        assert "frontend/screens/HomeScreen.test.tsx" in rule["required_checks"]

    def test_python_test_is_discovered(self, fixture_files):
        result = build_test_map(FIXTURE_ROOT, fixture_files)
        test_paths = {t["path"] for t in result["tests"]}
        assert "tests/test_main.py" in test_paths

    def test_tsx_test_is_discovered(self, fixture_files):
        result = build_test_map(FIXTURE_ROOT, fixture_files)
        test_paths = {t["path"] for t in result["tests"]}
        assert "frontend/screens/HomeScreen.test.tsx" in test_paths

    def test_schema_marker_present(self, fixture_files):
        result = build_test_map(FIXTURE_ROOT, fixture_files)
        assert result["$schema"] == "vibecode/test-map/v1"

    def test_package_json_has_test_script(self):
        import json
        pkg = json.loads((FIXTURE_ROOT / "package.json").read_text(encoding="utf-8"))
        assert "test" in pkg.get("scripts", {})
