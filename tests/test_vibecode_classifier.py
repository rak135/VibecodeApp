"""Tests for the language detector and file-role classifier."""

from __future__ import annotations

import pytest

from vibecode.indexer.classifier import (
    FileRecord,
    classify,
    compute_risk_level,
    detect_language,
    guess_role,
)


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------


class TestDetectLanguage:
    def test_python(self):
        assert detect_language("src/main.py") == "python"

    def test_typescript(self):
        assert detect_language("src/index.ts") == "typescript"

    def test_typescriptreact(self):
        assert detect_language("src/App.tsx") == "typescriptreact"

    def test_javascript(self):
        assert detect_language("src/index.js") == "javascript"

    def test_javascriptreact(self):
        assert detect_language("src/App.jsx") == "javascriptreact"

    def test_markdown(self):
        assert detect_language("README.md") == "markdown"

    def test_json(self):
        assert detect_language("package.json") == "json"

    def test_yaml_yml(self):
        assert detect_language("config.yml") == "yaml"
        assert detect_language("config.yaml") == "yaml"

    def test_toml(self):
        assert detect_language("pyproject.toml") == "toml"

    def test_case_insensitive_extension(self):
        assert detect_language("Script.PY") == "python"

    def test_unknown_extension(self):
        assert detect_language("data.csv") == "unknown"

    def test_no_extension(self):
        assert detect_language("Makefile") == "unknown"

    def test_deeply_nested(self):
        assert detect_language("a/b/c/d/module.py") == "python"


# ---------------------------------------------------------------------------
# Role guessing
# ---------------------------------------------------------------------------


class TestGuessRole:
    # -- test files ----------------------------------------------------------

    def test_tests_directory(self):
        assert guess_role("tests/test_api.py") == "test"

    def test_nested_tests_directory(self):
        assert guess_role("backend/tests/unit/test_models.py") == "test"

    def test_test_prefix_python(self):
        assert guess_role("test_utils.py") == "test"

    def test_test_suffix_python(self):
        assert guess_role("utils_test.py") == "test"

    def test_test_tsx(self):
        assert guess_role("src/App.test.tsx") == "test"

    def test_spec_tsx(self):
        assert guess_role("src/App.spec.tsx") == "test"

    def test_test_ts(self):
        assert guess_role("src/utils.test.ts") == "test"

    def test_spec_js(self):
        assert guess_role("src/utils.spec.js") == "test"

    # -- doc files -----------------------------------------------------------

    def test_readme(self):
        assert guess_role("README.md") == "doc"

    def test_any_md(self):
        assert guess_role("CHANGELOG.md") == "doc"

    def test_docs_directory(self):
        assert guess_role("docs/guide.rst") == "doc"

    def test_nested_docs_directory(self):
        assert guess_role("project/docs/api/reference.md") == "doc"

    # -- config files --------------------------------------------------------

    def test_pyproject_toml(self):
        assert guess_role("pyproject.toml") == "config"

    def test_package_json(self):
        assert guess_role("package.json") == "config"

    def test_tsconfig_json(self):
        assert guess_role("tsconfig.json") == "config"

    def test_vite_config(self):
        assert guess_role("vite.config.ts") == "config"

    def test_vite_config_js(self):
        assert guess_role("vite.config.js") == "config"

    def test_dotenv(self):
        assert guess_role(".env") == "config"

    def test_makefile(self):
        assert guess_role("Makefile") == "config"

    # -- frontend screens ----------------------------------------------------

    def test_screen_tsx(self):
        assert guess_role("ui/frontend/src/screens/HomeScreen.tsx") == "frontend_screen"

    def test_screen_nested(self):
        assert guess_role("src/screens/Dashboard.tsx") == "frontend_screen"

    # -- frontend components -------------------------------------------------

    def test_component_tsx(self):
        assert guess_role("ui/frontend/src/components/Button.tsx") == "frontend_component"

    def test_component_nested(self):
        assert guess_role("src/components/Header.tsx") == "frontend_component"

    # -- backend engine ------------------------------------------------------

    def test_engine_path(self):
        assert guess_role("stock_tax_app/engine/calculator.py") == "backend_engine"

    def test_engine_nested(self):
        assert guess_role("app/engine/rules/validator.py") == "backend_engine"

    # -- backend api ---------------------------------------------------------

    def test_api_path(self):
        assert guess_role("api/views.py") == "backend_api"

    def test_routes_path(self):
        assert guess_role("routes/user_routes.py") == "backend_api"

    def test_server_path(self):
        assert guess_role("server/handlers.py") == "backend_api"

    # -- generated -----------------------------------------------------------

    def test_dist_directory(self):
        assert guess_role("dist/bundle.js") == "generated"

    def test_pycache(self):
        assert guess_role("src/__pycache__/module.pyc") == "generated"

    def test_pyc_extension(self):
        assert guess_role("src/module.pyc") == "generated"

    # -- script --------------------------------------------------------------

    def test_shell_script(self):
        assert guess_role("scripts/deploy.sh") == "script"

    def test_powershell_script(self):
        assert guess_role("scripts/setup.ps1") == "script"

    # -- unknown -------------------------------------------------------------

    def test_unknown_plain_python(self):
        # A plain .py file outside any special directory gets "unknown"
        assert guess_role("main.py") == "unknown"

    def test_unknown_csv(self):
        assert guess_role("data/report.csv") == "unknown"


# ---------------------------------------------------------------------------
# Config file priority over test/doc
# ---------------------------------------------------------------------------


class TestRolePriority:
    def test_config_beats_test_dir(self):
        # pyproject.toml placed inside a tests/ directory is still config
        assert guess_role("tests/pyproject.toml") == "config"

    def test_test_beats_doc(self):
        # A .md file named test_notes.md inside tests/ → test wins (test dir)
        assert guess_role("tests/notes.md") == "test"


# ---------------------------------------------------------------------------
# Risk level
# ---------------------------------------------------------------------------


class TestComputeRiskLevel:
    def test_backend_engine_is_high(self):
        assert compute_risk_level("backend_engine") == "high"

    def test_backend_api_is_high(self):
        assert compute_risk_level("backend_api") == "high"

    def test_frontend_screen_is_medium(self):
        assert compute_risk_level("frontend_screen") == "medium"

    def test_frontend_component_is_medium(self):
        assert compute_risk_level("frontend_component") == "medium"

    def test_script_is_medium(self):
        assert compute_risk_level("script") == "medium"

    def test_test_is_low(self):
        assert compute_risk_level("test") == "low"

    def test_doc_is_low(self):
        assert compute_risk_level("doc") == "low"

    def test_config_is_low(self):
        assert compute_risk_level("config") == "low"

    def test_unknown_is_low(self):
        assert compute_risk_level("unknown") == "low"


# ---------------------------------------------------------------------------
# classify() – full FileRecord
# ---------------------------------------------------------------------------


class TestClassify:
    def test_python_source_file(self):
        rec = classify("stock_tax_app/engine/calculator.py", 1024)
        assert isinstance(rec, FileRecord)
        assert rec.path == "stock_tax_app/engine/calculator.py"
        assert rec.language == "python"
        assert rec.size_bytes == 1024
        assert rec.role_guess == "backend_engine"
        assert rec.is_test is False
        assert rec.is_config is False
        assert rec.is_doc is False
        assert rec.risk_level == "high"

    def test_tsx_component(self):
        rec = classify("ui/frontend/src/components/Button.tsx", 512)
        assert rec.language == "typescriptreact"
        assert rec.role_guess == "frontend_component"
        assert rec.is_test is False
        assert rec.risk_level == "medium"

    def test_markdown_readme(self):
        rec = classify("README.md", 2048)
        assert rec.language == "markdown"
        assert rec.role_guess == "doc"
        assert rec.is_doc is True
        assert rec.is_test is False
        assert rec.risk_level == "low"

    def test_pyproject_toml(self):
        rec = classify("pyproject.toml", 300)
        assert rec.language == "toml"
        assert rec.role_guess == "config"
        assert rec.is_config is True
        assert rec.is_test is False
        assert rec.is_doc is False
        assert rec.risk_level == "low"

    def test_test_python_file(self):
        rec = classify("tests/test_engine.py", 800)
        assert rec.language == "python"
        assert rec.role_guess == "test"
        assert rec.is_test is True
        assert rec.is_config is False
        assert rec.is_doc is False
        assert rec.risk_level == "low"

    def test_tsx_test_file(self):
        rec = classify("src/components/Button.test.tsx", 600)
        assert rec.language == "typescriptreact"
        assert rec.role_guess == "test"
        assert rec.is_test is True
        assert rec.risk_level == "low"

    def test_unknown_extension_does_not_crash(self):
        rec = classify("data/report.csv", 99999)
        assert rec.language == "unknown"
        assert rec.role_guess == "unknown"
        assert rec.risk_level == "low"

    def test_file_with_no_extension_does_not_crash(self):
        rec = classify("scripts/run", 128)
        assert rec.language == "unknown"
        assert isinstance(rec.role_guess, str)

    def test_size_bytes_stored(self):
        rec = classify("main.py", 42)
        assert rec.size_bytes == 42
