"""Tests for entrypoint detection and entrypoints.md generation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecode.indexer.entrypoints import (
    detect_entrypoints,
    render_entrypoints,
    write_entrypoints,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, content: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# detect_entrypoints – Python backend
# ---------------------------------------------------------------------------


class TestDetectBackend:
    def test_main_py_at_root(self, tmp_path):
        _write(tmp_path / "main.py", "def main(): pass\n")
        data = detect_entrypoints(tmp_path)
        paths = [e["path"] for e in data["backend"]]
        assert "main.py" in paths

    def test_app_py_at_root(self, tmp_path):
        _write(tmp_path / "app.py", "from flask import Flask\napp = Flask(__name__)\n")
        data = detect_entrypoints(tmp_path)
        paths = [e["path"] for e in data["backend"]]
        assert "app.py" in paths

    def test_fastapi_bootstrap_detected(self, tmp_path):
        _write(tmp_path / "main.py", "from fastapi import FastAPI\napp = FastAPI()\n")
        data = detect_entrypoints(tmp_path)
        entry = next(e for e in data["backend"] if e["path"] == "main.py")
        assert "FastAPI" in entry["description"]

    def test_flask_bootstrap_detected(self, tmp_path):
        _write(tmp_path / "app.py", "from flask import Flask\napp = Flask(__name__)\n")
        data = detect_entrypoints(tmp_path)
        entry = next(e for e in data["backend"] if e["path"] == "app.py")
        assert "Flask" in entry["description"]

    def test_wsgi_and_asgi_detected(self, tmp_path):
        _write(tmp_path / "wsgi.py")
        _write(tmp_path / "asgi.py")
        data = detect_entrypoints(tmp_path)
        paths = [e["path"] for e in data["backend"]]
        assert "wsgi.py" in paths
        assert "asgi.py" in paths

    def test_manage_py_detected(self, tmp_path):
        _write(tmp_path / "manage.py", "#!/usr/bin/env python\n")
        data = detect_entrypoints(tmp_path)
        paths = [e["path"] for e in data["backend"]]
        assert "manage.py" in paths

    def test_backend_subdir_main_py(self, tmp_path):
        _write(tmp_path / "backend" / "main.py", "from fastapi import FastAPI\napp = FastAPI()\n")
        data = detect_entrypoints(tmp_path)
        paths = [e["path"] for e in data["backend"]]
        assert "backend/main.py" in paths

    def test_no_backend_files_returns_empty(self, tmp_path):
        _write(tmp_path / "utils.py")
        data = detect_entrypoints(tmp_path)
        assert data["backend"] == []

    def test_nonexistent_backend_not_hallucinated(self, tmp_path):
        # no Python files at all
        data = detect_entrypoints(tmp_path)
        assert data["backend"] == []


# ---------------------------------------------------------------------------
# detect_entrypoints – Frontend
# ---------------------------------------------------------------------------


class TestDetectFrontend:
    def test_main_tsx(self, tmp_path):
        _write(tmp_path / "src" / "main.tsx", "import React from 'react';\n")
        data = detect_entrypoints(tmp_path)
        paths = [e["path"] for e in data["frontend"]]
        assert "src/main.tsx" in paths

    def test_app_tsx(self, tmp_path):
        _write(tmp_path / "src" / "App.tsx", "export default function App() {}\n")
        data = detect_entrypoints(tmp_path)
        paths = [e["path"] for e in data["frontend"]]
        assert "src/App.tsx" in paths

    def test_vite_config_ts(self, tmp_path):
        _write(tmp_path / "vite.config.ts", "export default {};\n")
        data = detect_entrypoints(tmp_path)
        paths = [e["path"] for e in data["frontend"]]
        assert "vite.config.ts" in paths

    def test_vite_config_js(self, tmp_path):
        _write(tmp_path / "vite.config.js", "module.exports = {};\n")
        data = detect_entrypoints(tmp_path)
        paths = [e["path"] for e in data["frontend"]]
        assert "vite.config.js" in paths

    def test_no_frontend_returns_empty(self, tmp_path):
        _write(tmp_path / "main.py")
        data = detect_entrypoints(tmp_path)
        assert data["frontend"] == []

    def test_nonexistent_frontend_not_hallucinated(self, tmp_path):
        data = detect_entrypoints(tmp_path)
        assert data["frontend"] == []


# ---------------------------------------------------------------------------
# detect_entrypoints – CLI / Scripts
# ---------------------------------------------------------------------------


class TestDetectCliScripts:
    def test_cli_py_at_root(self, tmp_path):
        _write(tmp_path / "cli.py", "def main(): pass\n")
        data = detect_entrypoints(tmp_path)
        names = [s["name"] for s in data["cli_scripts"]]
        assert "cli.py" in names

    def test_pyproject_scripts(self, tmp_path):
        _write(tmp_path / "pyproject.toml", (
            "[build-system]\n"
            "requires = [\"setuptools\"]\n"
            "\n"
            "[project.scripts]\n"
            "myapp = \"myapp.cli:main\"\n"
            "myapp-worker = \"myapp.worker:run\"\n"
        ))
        data = detect_entrypoints(tmp_path)
        names = [s["name"] for s in data["cli_scripts"]]
        targets = [s["target"] for s in data["cli_scripts"]]
        assert "myapp" in names
        assert "myapp.cli:main" in targets
        assert "myapp-worker" in names

    def test_pyproject_scripts_source(self, tmp_path):
        _write(tmp_path / "pyproject.toml", (
            "[project.scripts]\n"
            "tool = \"mypkg.cli:main\"\n"
        ))
        data = detect_entrypoints(tmp_path)
        script = next(s for s in data["cli_scripts"] if s["name"] == "tool")
        assert script["source"] == "pyproject.toml"

    def test_package_json_scripts(self, tmp_path):
        _write(
            tmp_path / "package.json",
            json.dumps({"scripts": {"build": "tsc", "dev": "vite", "test": "jest"}}),
        )
        data = detect_entrypoints(tmp_path)
        names = [s["name"] for s in data["cli_scripts"]]
        assert "build" in names
        assert "dev" in names
        assert "test" in names

    def test_package_json_scripts_source(self, tmp_path):
        _write(tmp_path / "package.json", json.dumps({"scripts": {"start": "node index.js"}}))
        data = detect_entrypoints(tmp_path)
        script = next(s for s in data["cli_scripts"] if s["name"] == "start")
        assert script["source"] == "package.json"

    def test_package_json_without_scripts_key(self, tmp_path):
        _write(tmp_path / "package.json", json.dumps({"name": "myapp", "version": "1.0.0"}))
        data = detect_entrypoints(tmp_path)
        # should not crash, no scripts from package.json
        sources = [s["source"] for s in data["cli_scripts"]]
        assert "package.json" not in sources

    def test_shell_scripts_in_scripts_dir(self, tmp_path):
        _write(tmp_path / "scripts" / "deploy.sh", "#!/bin/bash\n")
        _write(tmp_path / "scripts" / "seed.sh", "#!/bin/bash\n")
        data = detect_entrypoints(tmp_path)
        names = [s["name"] for s in data["cli_scripts"]]
        assert "deploy.sh" in names
        assert "seed.sh" in names

    def test_no_scripts_returns_empty(self, tmp_path):
        _write(tmp_path / "README.md", "# hello\n")
        data = detect_entrypoints(tmp_path)
        assert data["cli_scripts"] == []


# ---------------------------------------------------------------------------
# detect_entrypoints – Runtime/Config
# ---------------------------------------------------------------------------


class TestDetectRuntimeConfig:
    def test_dockerfile(self, tmp_path):
        _write(tmp_path / "Dockerfile", "FROM python:3.12\n")
        data = detect_entrypoints(tmp_path)
        paths = [e["path"] for e in data["runtime_config"]]
        assert "Dockerfile" in paths

    def test_docker_compose_yml(self, tmp_path):
        _write(tmp_path / "docker-compose.yml", "version: '3'\n")
        data = detect_entrypoints(tmp_path)
        paths = [e["path"] for e in data["runtime_config"]]
        assert "docker-compose.yml" in paths

    def test_docker_compose_yaml(self, tmp_path):
        _write(tmp_path / "docker-compose.yaml", "version: '3'\n")
        data = detect_entrypoints(tmp_path)
        paths = [e["path"] for e in data["runtime_config"]]
        assert "docker-compose.yaml" in paths

    def test_makefile(self, tmp_path):
        _write(tmp_path / "Makefile", ".PHONY: build\nbuild:\n\tpython -m build\n")
        data = detect_entrypoints(tmp_path)
        paths = [e["path"] for e in data["runtime_config"]]
        assert "Makefile" in paths

    def test_no_runtime_config_returns_empty(self, tmp_path):
        data = detect_entrypoints(tmp_path)
        assert data["runtime_config"] == []


# ---------------------------------------------------------------------------
# render_entrypoints
# ---------------------------------------------------------------------------


class TestRenderEntrypoints:
    def test_heading_present(self, tmp_path):
        data = detect_entrypoints(tmp_path)
        output = render_entrypoints(tmp_path, data)
        assert output.startswith("# Entrypoints")

    def test_root_name_in_output(self, tmp_path):
        data = detect_entrypoints(tmp_path)
        output = render_entrypoints(tmp_path, data)
        assert tmp_path.name in output

    def test_all_section_headings_present(self, tmp_path):
        data = detect_entrypoints(tmp_path)
        output = render_entrypoints(tmp_path, data)
        assert "## Backend" in output
        assert "## Frontend" in output
        assert "## CLI/Scripts" in output
        assert "## Runtime/Config" in output

    def test_not_detected_for_empty_sections(self, tmp_path):
        data = detect_entrypoints(tmp_path)
        output = render_entrypoints(tmp_path, data)
        assert output.count("not detected") == 4

    def test_backend_entry_rendered(self, tmp_path):
        _write(tmp_path / "main.py", "def main(): pass\n")
        data = detect_entrypoints(tmp_path)
        output = render_entrypoints(tmp_path, data)
        assert "`main.py`" in output

    def test_frontend_entry_rendered(self, tmp_path):
        _write(tmp_path / "src" / "main.tsx")
        data = detect_entrypoints(tmp_path)
        output = render_entrypoints(tmp_path, data)
        assert "`src/main.tsx`" in output

    def test_package_json_script_rendered(self, tmp_path):
        _write(tmp_path / "package.json", json.dumps({"scripts": {"build": "tsc"}}))
        data = detect_entrypoints(tmp_path)
        output = render_entrypoints(tmp_path, data)
        assert "`build`" in output
        assert "package.json" in output

    def test_dockerfile_rendered(self, tmp_path):
        _write(tmp_path / "Dockerfile", "FROM python:3.12\n")
        data = detect_entrypoints(tmp_path)
        output = render_entrypoints(tmp_path, data)
        assert "`Dockerfile`" in output

    def test_mixed_fixture_main_py_and_main_tsx(self, tmp_path):
        """Fixture with main.py and main.tsx – both should appear."""
        _write(tmp_path / "main.py", "def main(): pass\n")
        _write(tmp_path / "src" / "main.tsx", "import React from 'react';\n")
        data = detect_entrypoints(tmp_path)
        output = render_entrypoints(tmp_path, data)
        assert "`main.py`" in output
        assert "`src/main.tsx`" in output

    def test_not_detected_sections_say_not_detected_not_empty(self, tmp_path):
        """Sections with no data must not be blank – they must say 'not detected'."""
        _write(tmp_path / "main.py")
        data = detect_entrypoints(tmp_path)
        output = render_entrypoints(tmp_path, data)
        # Frontend, CLI/Scripts, Runtime/Config should all say "not detected"
        assert output.count("not detected") == 3


# ---------------------------------------------------------------------------
# write_entrypoints
# ---------------------------------------------------------------------------


class TestWriteEntrypoints:
    def test_file_created(self, tmp_path):
        out = tmp_path / ".vibecode" / "index" / "entrypoints.md"
        write_entrypoints(tmp_path, out)
        assert out.exists()

    def test_file_content_is_markdown(self, tmp_path):
        out = tmp_path / ".vibecode" / "index" / "entrypoints.md"
        write_entrypoints(tmp_path, out)
        content = out.read_text(encoding="utf-8")
        assert "# Entrypoints" in content

    def test_parent_dirs_created_automatically(self, tmp_path):
        deep_out = tmp_path / "a" / "b" / "c" / "entrypoints.md"
        write_entrypoints(tmp_path, deep_out)
        assert deep_out.exists()

    def test_fixture_with_package_json_scripts(self, tmp_path):
        _write(tmp_path / "package.json", json.dumps({"scripts": {"start": "node server.js"}}))
        out = tmp_path / "entrypoints.md"
        write_entrypoints(tmp_path, out)
        content = out.read_text(encoding="utf-8")
        assert "`start`" in content
        assert "package.json" in content

    def test_nonexistent_entrypoints_not_present_in_output(self, tmp_path):
        """Only real files should appear; invented paths must not."""
        _write(tmp_path / "main.py")
        out = tmp_path / "entrypoints.md"
        write_entrypoints(tmp_path, out)
        content = out.read_text(encoding="utf-8")
        # These files don't exist – they must NOT appear in the output
        assert "src/main.tsx" not in content
        assert "Dockerfile" not in content
        assert "docker-compose" not in content
