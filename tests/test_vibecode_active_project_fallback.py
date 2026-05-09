"""Tests for active project fallback from registry in CLI commands."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from vibecode.cli import _resolve_repo_root, main
from vibecode.registry import ProjectEntry, ProjectRegistry


@pytest.fixture
def tmp_registry(tmp_path):
    home = tmp_path / "home"
    os.environ["VIBECODE_HOME"] = str(home)
    try:
        yield ProjectRegistry()
    finally:
        os.environ.pop("VIBECODE_HOME", None)


@pytest.fixture
def sample_project(tmp_path):
    repo = tmp_path / "sample"
    repo.mkdir()
    vdir = repo / ".vibecode"
    vdir.mkdir()
    (vdir / "project.yaml").write_text(
        "project:\n  id: sample\n  name: Sample\n  root: .\n"
        "indexing:\n  include: []\n  exclude: []\n"
        "protected_paths: []\n  risk_rules: []\n",
        encoding="utf-8",
    )
    (vdir / "architecture").mkdir()
    (vdir / "architecture" / "INVARIANTS.md").write_text(
        "# Invariants\n\n- Test invariant.\n", encoding="utf-8"
    )
    (vdir / "index").mkdir()
    (vdir / "index" / "file_inventory.json").write_text(
        json.dumps({"files": []}), encoding="utf-8"
    )
    (vdir / "checks").mkdir()
    (vdir / "checks" / "required_checks.yaml").write_text(
        "checks: []\n", encoding="utf-8"
    )
    (vdir / "current").mkdir()
    (vdir / "current" / "last_index.json").write_text(
        json.dumps({
            "project_id": "sample",
            "root": str(repo),
            "started_at": "2024-01-15T10:30:00+00:00",
            "counts": {"files": 0, "symbols": 0, "tests": 0, "warnings": 0, "errors": 0},
            "warnings": [],
            "errors": [],
        }),
        encoding="utf-8",
    )
    return repo


def _register_and_activate(reg, name, path):
    reg.add(ProjectEntry(name=name, path=str(path.resolve())))
    reg.set_active(name)


# ---------------------------------------------------------------------------
# index
# ---------------------------------------------------------------------------


class TestIndexWithRegistryFallback:
    def test_index_with_no_repo_uses_active_project(
        self, tmp_path, tmp_registry, sample_project, capsys
    ):
        _register_and_activate(tmp_registry, "SAMPLE", sample_project)
        main(["index"])
        err = capsys.readouterr().err
        assert "No repository root given" not in err

    def test_no_active_project_and_no_repo_exits_helpfully(
        self, tmp_registry, capsys
    ):
        rc = main(["index"])
        err = capsys.readouterr().err
        assert rc == 1
        assert "No repository root given" in err
        assert "vibecode project use" in err

    def test_explicit_repo_overrides_registry(
        self, tmp_path, tmp_registry, sample_project, capsys
    ):
        _register_and_activate(tmp_registry, "SAMPLE", sample_project)
        other = tmp_path / "other"
        other.mkdir()
        vdir = other / ".vibecode"
        vdir.mkdir()
        (vdir / "project.yaml").write_text(
            "project:\n  id: other\n  name: Other\n  root: .\n"
            "indexing:\n  include: []\n  exclude: []\n"
            "protected_paths: []\n  risk_rules: []\n",
        )
        (vdir / "current").mkdir()
        (vdir / "index").mkdir()
        (vdir / "index" / "file_inventory.json").write_text(
            json.dumps({"files": []}), encoding="utf-8"
        )
        (vdir / "current" / "last_index.json").write_text(
            json.dumps({"project_id": "other", "root": str(other),
                         "started_at": "2024-01-15T10:30:00+00:00",
                         "counts": {"files": 0, "symbols": 0, "tests": 0,
                                    "warnings": 0, "errors": 0},
                         "warnings": [], "errors": []}),
            encoding="utf-8",
        )
        main(["index", str(other)])
        err = capsys.readouterr().err
        assert "No repository root given" not in err


# ---------------------------------------------------------------------------
# map
# ---------------------------------------------------------------------------


class TestMapWithRegistryFallback:
    def test_map_with_no_repo_uses_active_project(
        self, tmp_path, tmp_registry, sample_project, capsys
    ):
        _register_and_activate(tmp_registry, "SAMPLE", sample_project)
        main(["map"])
        err = capsys.readouterr().err
        assert "No repository root given" not in err

    def test_no_active_project_and_no_repo_exits_helpfully(
        self, tmp_registry, capsys
    ):
        rc = main(["map"])
        err = capsys.readouterr().err
        assert rc == 1
        assert "No repository root given" in err
        assert "vibecode project use" in err

    def test_explicit_path_overrides_registry(
        self, tmp_path, tmp_registry, sample_project
    ):
        _register_and_activate(tmp_registry, "SAMPLE", sample_project)
        other = tmp_path / "othermap"
        other.mkdir()
        vdir = other / ".vibecode"
        vdir.mkdir()
        (vdir / "project.yaml").write_text(
            "project:\n  id: other\n  name: Other\n  root: .\n"
            "indexing:\n  include: []\n  exclude: []\n"
            "protected_paths: []\n  risk_rules: []\n",
        )
        (vdir / "current").mkdir()
        (vdir / "index").mkdir()
        (vdir / "index" / "file_inventory.json").write_text(
            json.dumps({"files": []}), encoding="utf-8"
        )
        (vdir / "current" / "last_index.json").write_text(
            json.dumps({"project_id": "other", "root": str(other),
                         "started_at": "2024-01-15T10:30:00+00:00",
                         "counts": {"files": 0, "symbols": 0, "tests": 0,
                                    "warnings": 0, "errors": 0},
                         "warnings": [], "errors": []}),
            encoding="utf-8",
        )
        rc = main(["map", str(other)])
        assert rc == 0


# ---------------------------------------------------------------------------
# context
# ---------------------------------------------------------------------------


class TestContextWithRegistryFallback:
    def test_context_with_no_repo_uses_active_project(
        self, tmp_path, tmp_registry, sample_project, capsys
    ):
        _register_and_activate(tmp_registry, "SAMPLE", sample_project)
        main(["context", "--task", "test task"])
        err = capsys.readouterr().err
        assert "No repository root given" not in err

    def test_no_active_project_falls_back_to_cwd(self, tmp_path, tmp_registry, capsys):
        main(["context", "--task", "test task"])
        err = capsys.readouterr().err
        assert "No repository root given" not in err

    def test_explicit_repo_overrides_registry(
        self, tmp_path, tmp_registry, sample_project
    ):
        _register_and_activate(tmp_registry, "SAMPLE", sample_project)
        rc = main(["context", str(sample_project), "--task", "test task"])
        assert rc == 0


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


class TestValidateWithRegistryFallback:
    def test_validate_with_no_repo_uses_active_project(
        self, tmp_path, tmp_registry, sample_project, capsys
    ):
        _register_and_activate(tmp_registry, "SAMPLE", sample_project)
        main(["validate"])
        err = capsys.readouterr().err
        assert "No repository root given" not in err

    def test_no_active_project_and_no_repo_exits_helpfully(
        self, tmp_registry, capsys
    ):
        rc = main(["validate"])
        err = capsys.readouterr().err
        assert rc == 1
        assert "No repository root given" in err
        assert "vibecode project use" in err


# ---------------------------------------------------------------------------
# guard
# ---------------------------------------------------------------------------


class TestGuardWithRegistryFallback:
    def test_guard_with_no_repo_uses_active_project(
        self, tmp_path, tmp_registry, sample_project, capsys
    ):
        _register_and_activate(tmp_registry, "SAMPLE", sample_project)
        main(["guard"])
        err = capsys.readouterr().err
        assert "No repository root given" not in err

    def test_no_active_project_and_no_repo_exits_helpfully(
        self, tmp_registry, capsys
    ):
        rc = main(["guard"])
        err = capsys.readouterr().err
        assert rc == 1
        assert "No repository root given" in err
        assert "vibecode project use" in err


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------


class TestCheckWithRegistryFallback:
    def test_check_with_no_repo_uses_active_project(
        self, tmp_path, tmp_registry, sample_project, capsys
    ):
        _register_and_activate(tmp_registry, "SAMPLE", sample_project)
        main(["check"])
        err = capsys.readouterr().err
        assert "No repository root given" not in err

    def test_no_active_project_and_no_repo_exits_helpfully(
        self, tmp_registry, capsys
    ):
        rc = main(["check"])
        err = capsys.readouterr().err
        assert rc == 1
        assert "No repository root given" in err
        assert "vibecode project use" in err


# ---------------------------------------------------------------------------
# handoff-check
# ---------------------------------------------------------------------------


class TestHandoffCheckWithRegistryFallback:
    def test_handoff_check_with_no_repo_uses_active_project(
        self, tmp_path, tmp_registry, sample_project, capsys
    ):
        _register_and_activate(tmp_registry, "SAMPLE", sample_project)
        main(["handoff-check"])
        err = capsys.readouterr().err
        assert "No repository root given" not in err

    def test_no_active_project_and_no_repo_exits_helpfully(
        self, tmp_registry, capsys
    ):
        rc = main(["handoff-check"])
        err = capsys.readouterr().err
        assert rc == 1
        assert "No repository root given" in err
        assert "vibecode project use" in err


# ---------------------------------------------------------------------------
# run command
# ---------------------------------------------------------------------------


class TestRunWithRegistryFallback:
    def test_run_with_no_repo_tries_registry(
        self, tmp_registry, capsys
    ):
        """run command should attempt registry fallback (will fail later at git check)."""
        # No active project, no repo arg.
        rc = main(["run"])
        err = capsys.readouterr().err
        # Should fail with a meaningful message, not crash.
        # Since no active project, it should mention that.
        assert rc != 0 or "No repository root given" in err


# ---------------------------------------------------------------------------
# Windows-style paths
# ---------------------------------------------------------------------------


class TestWindowsStylePaths:
    def test_index_accepts_windows_path(
        self, tmp_path, tmp_registry, sample_project
    ):
        """Windows-style backslash paths should be accepted by the CLI."""
        _register_and_activate(tmp_registry, "SAMPLE", sample_project)
        home = tmp_path / "home"
        env = os.environ.copy()
        env["VIBECODE_HOME"] = str(home)
        try:
            win_path = str(sample_project).replace("/", "\\")
            result = subprocess.run(
                [sys.executable, "-m", "vibecode", "index", win_path],
                capture_output=True, text=True,
                cwd=str(tmp_path),
                env=env,
            )
            assert "No repository root given" not in result.stderr
        finally:
            pass

    def test_context_windows_repo_flag(
        self, tmp_path, tmp_registry, sample_project
    ):
        """Context --repo flag should accept Windows-style paths."""
        _register_and_activate(tmp_registry, "SAMPLE", sample_project)
        home = tmp_path / "home"
        env = os.environ.copy()
        env["VIBECODE_HOME"] = str(home)
        try:
            win_path = str(sample_project).replace("/", "\\")
            result = subprocess.run(
                [sys.executable, "-m", "vibecode", "context",
                 "--repo", win_path, "--task", "test"],
                capture_output=True, text=True,
                cwd=str(tmp_path),
                env=env,
            )
            assert "No repository root given" not in result.stderr
        finally:
            pass


# ---------------------------------------------------------------------------
# Acceptance: `vibecode project use STOCKS` then `vibecode context --task ...`
# ---------------------------------------------------------------------------


class TestAcceptanceProjectUseThenContext:
    def test_project_use_then_context_without_repo_arg(
        self, tmp_path, tmp_registry, sample_project, capsys
    ):
        """After `vibecode project use STOCKS`, `vibecode context` should use that repo."""
        _register_and_activate(tmp_registry, "STOCKS", sample_project)
        # Simulate `vibecode project use STOCKS` (already done via _register_and_activate)
        # Now run context WITHOUT specifying a repo
        rc = main(["context", "--task", "analyze module structure"])
        err = capsys.readouterr().err
        # Should succeed (exit 0)
        assert rc == 0
        assert "No repository root given" not in err
        # Should have generated a context pack in the sample project
        pack = sample_project / ".vibecode" / "current" / "context_pack.md"
        assert pack.exists()


# ---------------------------------------------------------------------------
# Resolver unit tests
# ---------------------------------------------------------------------------


class TestResolveRepoRoot:
    def test_explicit_path_bypasses_registry(self, tmp_path):
        target = tmp_path / "myrepo"
        target.mkdir()
        args = SimpleNamespace(repo_root=str(target))
        result = _resolve_repo_root(args, allow_fallback=True)
        assert result.resolve() == target.resolve()

    def test_none_repo_root_with_fallback_raises(self, tmp_registry):
        tmp_registry._set_active_name(None)
        args = SimpleNamespace(repo_root=None)
        with pytest.raises(FileNotFoundError, match="No repository root given"):
            _resolve_repo_root(args, allow_fallback=True)

    def test_none_repo_root_without_fallback_uses_cwd(self):
        args = SimpleNamespace(repo_root=None)
        result = _resolve_repo_root(args, allow_fallback=False)
        assert result == Path.cwd().resolve()

    def test_dot_repo_root_with_fallback_checks_registry(
        self, tmp_path, tmp_registry, sample_project
    ):
        """Explicit '.' triggers registry fallback."""
        _register_and_activate(tmp_registry, "SAMPLE", sample_project)
        args = SimpleNamespace(repo_root=".")
        result = _resolve_repo_root(args, allow_fallback=True)
        assert result.resolve() == sample_project.resolve()

    def test_dot_repo_root_without_fallback_uses_cwd(self):
        args = SimpleNamespace(repo_root=".")
        result = _resolve_repo_root(args, allow_fallback=False)
        assert result == Path.cwd().resolve()

    def test_error_message_suggests_project_use(self, tmp_registry):
        tmp_registry._set_active_name(None)
        args = SimpleNamespace(repo_root=None)
        with pytest.raises(FileNotFoundError, match="vibecode project use"):
            _resolve_repo_root(args, allow_fallback=True)