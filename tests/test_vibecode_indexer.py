"""Tests for the file indexer / scanner."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from vibecode.indexer.scanner import (
    DEFAULT_SIZE_LIMIT,
    FileStatus,
    IndexedFile,
    _compile_pattern,
    _in_builtin_excluded_dir,
    _match_pattern,
    scan,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, content: str = "# placeholder\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _init_git(repo: Path) -> None:
    """Initialise a minimal git repo for testing."""
    result = subprocess.run(
        ["git", "init", "-b", "main"], cwd=repo, capture_output=True
    )
    if result.returncode != 0:
        # Older git (<2.28) does not support -b; fall back to plain init.
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _git_add_commit(repo: Path, message: str = "init") -> None:
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo,
        check=True,
        capture_output=True,
    )


git_available = pytest.mark.skipif(
    shutil.which("git") is None, reason="git not available"
)


@pytest.fixture()
def plain_dir(tmp_path, monkeypatch):
    """Temporary directory guaranteed to be treated as a non-git directory."""
    monkeypatch.setattr("vibecode.indexer.scanner._is_git_repo", lambda _root: False)
    return tmp_path


# ---------------------------------------------------------------------------
# Pattern compilation
# ---------------------------------------------------------------------------


class TestCompilePattern:
    def test_simple_extension_matches_root(self):
        rx = _compile_pattern("*.py")
        assert rx.match("foo.py")
        assert not rx.match("foo.txt")
        assert not rx.match("src/foo.py")  # * does not cross /

    def test_double_star_prefix_any_depth(self):
        rx = _compile_pattern("**/*.py")
        assert rx.match("foo.py")
        assert rx.match("src/foo.py")
        assert rx.match("a/b/c/foo.py")
        assert not rx.match("foo.txt")

    def test_double_star_suffix(self):
        rx = _compile_pattern(".git/**")
        assert rx.match(".git/config")
        assert rx.match(".git/objects/abc")
        assert not rx.match("src/.git/config")

    def test_literal_path(self):
        rx = _compile_pattern("src/main.py")
        assert rx.match("src/main.py")
        assert not rx.match("src/utils.py")

    def test_midpath_double_star(self):
        rx = _compile_pattern("src/**/*.py")
        assert rx.match("src/foo.py")
        assert rx.match("src/bar/foo.py")
        assert not rx.match("lib/foo.py")


class TestMatchPattern:
    def test_basename_fallback_for_simple_patterns(self):
        assert _match_pattern("src/foo.pyc", "*.pyc")

    def test_no_basename_fallback_for_path_patterns(self):
        assert not _match_pattern("other/foo.py", "src/*.py")

    def test_double_star_matches_at_root_depth(self):
        assert _match_pattern("README.md", "**/*.md")

    def test_double_star_matches_nested(self):
        assert _match_pattern("docs/guide/intro.md", "**/*.md")


# ---------------------------------------------------------------------------
# Builtin-excluded directories
# ---------------------------------------------------------------------------


class TestInBuiltinExcludedDir:
    def test_git_dir(self):
        assert _in_builtin_excluded_dir(".git/config")

    def test_nested_pycache(self):
        assert _in_builtin_excluded_dir("src/__pycache__/foo.pyc")

    def test_normal_file(self):
        assert not _in_builtin_excluded_dir("src/main.py")

    def test_root_level_file(self):
        assert not _in_builtin_excluded_dir("README.md")

    def test_node_modules_nested(self):
        assert _in_builtin_excluded_dir("node_modules/lodash/index.js")


# ---------------------------------------------------------------------------
# Filesystem scan (no git)
# ---------------------------------------------------------------------------


class TestScanFilesystem:
    def test_basic_scan_returns_files(self, plain_dir):
        _write(plain_dir / "main.py")
        _write(plain_dir / "src" / "utils.py")

        results = scan(plain_dir)
        paths = {f.path for f in results}

        assert "main.py" in paths
        assert "src/utils.py" in paths

    def test_posix_paths_no_backslashes(self, plain_dir):
        _write(plain_dir / "a" / "b" / "c.py")
        results = scan(plain_dir)
        assert all("\\" not in f.path for f in results)

    def test_excludes_node_modules(self, plain_dir):
        _write(plain_dir / "main.py")
        _write(plain_dir / "node_modules" / "lib" / "index.js")

        results = scan(plain_dir)
        paths = {f.path for f in results}

        assert "main.py" in paths
        assert not any("node_modules" in p for p in paths)

    def test_excludes_venv_directories(self, plain_dir):
        _write(plain_dir / "app.py")
        _write(plain_dir / ".venv" / "bin" / "python")
        _write(plain_dir / "venv" / "bin" / "activate")

        results = scan(plain_dir)
        paths = {f.path for f in results}

        assert "app.py" in paths
        assert not any(".venv" in p for p in paths)
        assert not any(p.startswith("venv/") for p in paths)

    def test_excludes_pycache(self, plain_dir):
        _write(plain_dir / "main.py")
        _write(plain_dir / "__pycache__" / "main.cpython-311.pyc")

        results = scan(plain_dir)
        paths = {f.path for f in results}

        assert "main.py" in paths
        assert not any("__pycache__" in p for p in paths)

    def test_excludes_other_builtin_dirs(self, plain_dir):
        _write(plain_dir / "src" / "app.py")
        for dirname in ("dist", "build", ".pytest_cache", ".mypy_cache"):
            _write(plain_dir / dirname / "artifact.bin")

        results = scan(plain_dir)
        paths = {f.path for f in results}

        for dirname in ("dist", "build", ".pytest_cache", ".mypy_cache"):
            assert not any(dirname in p for p in paths), f"{dirname} must be excluded"

    def test_status_is_unknown(self, plain_dir):
        _write(plain_dir / "main.py")
        results = scan(plain_dir)
        assert all(f.status == FileStatus.UNKNOWN for f in results)

    def test_user_exclude_rule(self, plain_dir):
        _write(plain_dir / "main.py")
        _write(plain_dir / "main.pyc")

        results = scan(plain_dir, exclude=["*.pyc"])
        paths = {f.path for f in results}

        assert "main.py" in paths
        assert "main.pyc" not in paths

    def test_user_include_rule_filters_other_extensions(self, plain_dir):
        _write(plain_dir / "main.py")
        _write(plain_dir / "README.md")
        _write(plain_dir / "data.csv")

        results = scan(plain_dir, include=["**/*.py", "**/*.md"])
        paths = {f.path for f in results}

        assert "main.py" in paths
        assert "README.md" in paths
        assert "data.csv" not in paths

    def test_size_limit_skips_large_files(self, plain_dir):
        small = plain_dir / "small.py"
        small.write_text("x = 1\n", encoding="utf-8")
        big = plain_dir / "big.bin"
        big.write_bytes(b"x" * (DEFAULT_SIZE_LIMIT + 1))

        results = scan(plain_dir)
        paths = {f.path for f in results}

        assert "small.py" in paths
        assert "big.bin" not in paths

    def test_custom_size_limit(self, plain_dir):
        small = plain_dir / "small.py"
        small.write_bytes(b"x" * 10)
        medium = plain_dir / "medium.py"
        medium.write_bytes(b"x" * 100)

        results = scan(plain_dir, size_limit=50)
        paths = {f.path for f in results}

        assert "small.py" in paths
        assert "medium.py" not in paths

    def test_nested_exclude_pattern(self, plain_dir):
        _write(plain_dir / ".vibecode" / "index" / "snapshot.json")
        _write(plain_dir / ".vibecode" / "project.yaml")

        results = scan(plain_dir, exclude=[".vibecode/index/**"])
        paths = {f.path for f in results}

        assert ".vibecode/project.yaml" in paths
        assert ".vibecode/index/snapshot.json" not in paths


# ---------------------------------------------------------------------------
# Git scan
# ---------------------------------------------------------------------------


@git_available
class TestScanGit:
    def test_tracked_files_are_found(self, tmp_path):
        _init_git(tmp_path)
        _write(tmp_path / "main.py")
        _write(tmp_path / "src" / "utils.py")
        _git_add_commit(tmp_path)

        results = scan(tmp_path)
        paths = {f.path for f in results}

        assert "main.py" in paths
        assert "src/utils.py" in paths

    def test_tracked_status(self, tmp_path):
        _init_git(tmp_path)
        _write(tmp_path / "tracked.py")
        _git_add_commit(tmp_path)

        results = scan(tmp_path)
        by_path = {f.path: f for f in results}

        assert by_path["tracked.py"].status == FileStatus.TRACKED

    def test_untracked_status(self, tmp_path):
        _init_git(tmp_path)
        _write(tmp_path / "tracked.py")
        _git_add_commit(tmp_path)
        # Add a file without staging it
        _write(tmp_path / "untracked.py")

        results = scan(tmp_path)
        by_path = {f.path: f for f in results}

        assert by_path["tracked.py"].status == FileStatus.TRACKED
        assert by_path["untracked.py"].status == FileStatus.UNTRACKED

    def test_git_dir_not_in_results(self, tmp_path):
        _init_git(tmp_path)
        _write(tmp_path / "main.py")
        _git_add_commit(tmp_path)

        results = scan(tmp_path)
        paths = {f.path for f in results}

        assert not any(p.startswith(".git/") or p == ".git" for p in paths)

    def test_node_modules_not_in_results(self, tmp_path):
        _init_git(tmp_path)
        _write(tmp_path / "app.js")
        _write(tmp_path / "node_modules" / "lodash" / "index.js")
        _git_add_commit(tmp_path)

        results = scan(tmp_path)
        paths = {f.path for f in results}

        assert not any("node_modules" in p for p in paths)

    def test_exclude_rules_respected(self, tmp_path):
        _init_git(tmp_path)
        _write(tmp_path / "main.py")
        _write(tmp_path / "main.pyc")
        _git_add_commit(tmp_path)

        results = scan(tmp_path, exclude=["*.pyc"])
        paths = {f.path for f in results}

        assert "main.py" in paths
        assert "main.pyc" not in paths

    def test_include_rules_respected(self, tmp_path):
        _init_git(tmp_path)
        _write(tmp_path / "main.py")
        _write(tmp_path / "README.md")
        _write(tmp_path / "data.csv")
        _git_add_commit(tmp_path)

        results = scan(tmp_path, include=["**/*.py"])
        paths = {f.path for f in results}

        assert "main.py" in paths
        assert "README.md" not in paths
        assert "data.csv" not in paths

    def test_posix_paths_no_backslashes(self, tmp_path):
        _init_git(tmp_path)
        _write(tmp_path / "a" / "b" / "c.py")
        _git_add_commit(tmp_path)

        results = scan(tmp_path)
        assert all("\\" not in f.path for f in results)

    def test_size_limit_skips_large_files(self, tmp_path):
        _init_git(tmp_path)
        small = tmp_path / "small.py"
        small.write_text("x = 1\n", encoding="utf-8")
        big = tmp_path / "big.bin"
        big.write_bytes(b"x" * (DEFAULT_SIZE_LIMIT + 1))
        _git_add_commit(tmp_path)

        results = scan(tmp_path)
        paths = {f.path for f in results}

        assert "small.py" in paths
        assert "big.bin" not in paths

    def test_indexed_file_has_size(self, tmp_path):
        _init_git(tmp_path)
        f = tmp_path / "hello.py"
        f.write_text("print('hello')\n", encoding="utf-8")
        _git_add_commit(tmp_path)

        results = scan(tmp_path)
        by_path = {r.path: r for r in results}

        assert by_path["hello.py"].size == f.stat().st_size
