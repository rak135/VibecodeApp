"""Tests for RepoResolutionService, RepoStatus, and RepoStatusService."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from vibecode.repo_resolution import RepoResolutionService
from vibecode.repo_status import (
    RepoStatus,
    RepoStatusService,
    _GENERATED_INDEX_FILES,
    _MANUAL_TRUTH_FILES,
)


# ---------------------------------------------------------------------------
# RepoResolutionService
# ---------------------------------------------------------------------------


class TestRepoResolutionExplicitPath:
    def test_explicit_path_returned_as_absolute(self, tmp_path):
        svc = RepoResolutionService()
        result = svc.resolve(explicit_path=str(tmp_path))
        assert result == tmp_path.resolve()

    def test_explicit_dot_resolves_to_cwd(self):
        svc = RepoResolutionService()
        result = svc.resolve(explicit_path=".")
        assert result == Path(".").resolve()

    def test_explicit_path_beats_active_registry(self, tmp_path, monkeypatch):
        """Explicit path must win even when a registry active project exists."""
        from vibecode import registry as reg_mod

        monkeypatch.setattr(
            reg_mod.ProjectRegistry,
            "pick",
            lambda self, name: Path("/some/other/path"),
        )
        svc = RepoResolutionService()
        result = svc.resolve(explicit_path=str(tmp_path))
        assert result == tmp_path.resolve()


class TestRepoResolutionRegistryFallback:
    def test_registry_used_when_no_explicit_path(self, tmp_path, monkeypatch):
        from vibecode import registry as reg_mod

        monkeypatch.setattr(
            reg_mod.ProjectRegistry,
            "pick",
            lambda self, name: tmp_path,
        )
        svc = RepoResolutionService()
        result = svc.resolve()
        assert result == tmp_path.resolve()

    def test_falls_back_to_cwd_when_registry_has_no_active(self, monkeypatch, tmp_path):
        """When registry raises FileNotFoundError, fall back to cwd."""
        monkeypatch.setenv("VIBECODE_HOME", str(tmp_path / "no_vibecode_home"))
        svc = RepoResolutionService()
        result = svc.resolve()
        assert result == Path(".").resolve()


class TestRepoResolutionCwdFallback:
    def test_cwd_used_when_registry_raises(self, monkeypatch):
        from vibecode import registry as reg_mod

        def _raise(self, name):
            raise FileNotFoundError("no active project")

        monkeypatch.setattr(reg_mod.ProjectRegistry, "pick", _raise)
        svc = RepoResolutionService()
        result = svc.resolve()
        assert result == Path(".").resolve()

    def test_resolution_priority_explicit_over_cwd(self, tmp_path, monkeypatch):
        """Explicit path wins over cwd even when registry is empty."""
        from vibecode import registry as reg_mod

        monkeypatch.setattr(
            reg_mod.ProjectRegistry,
            "pick",
            lambda self, name: (_ for _ in ()).throw(FileNotFoundError()),
        )
        svc = RepoResolutionService()
        result = svc.resolve(explicit_path=str(tmp_path))
        assert result == tmp_path.resolve()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_vibecode_dir(root: Path) -> Path:
    vdir = root / ".vibecode"
    vdir.mkdir()
    return vdir


# ---------------------------------------------------------------------------
# RepoStatus — missing .vibecode
# ---------------------------------------------------------------------------


class TestRepoStatusMissingVibecode:
    def test_vibecode_dir_not_present(self, tmp_path):
        svc = RepoStatusService()
        status = svc.get_status(tmp_path)
        assert status.vibecode_dir_exists is False

    def test_all_manual_truth_absent(self, tmp_path):
        svc = RepoStatusService()
        status = svc.get_status(tmp_path)
        assert status.manual_truth_count == 0
        assert all(not v for v in status.manual_truth.values())

    def test_all_generated_index_absent(self, tmp_path):
        svc = RepoStatusService()
        status = svc.get_status(tmp_path)
        assert status.generated_index_count == 0

    def test_context_pack_absent(self, tmp_path):
        svc = RepoStatusService()
        status = svc.get_status(tmp_path)
        assert status.context_pack_exists is False

    def test_check_results_absent(self, tmp_path):
        svc = RepoStatusService()
        status = svc.get_status(tmp_path)
        assert status.check_results_exist is False

    def test_opencode_prompt_absent(self, tmp_path):
        svc = RepoStatusService()
        status = svc.get_status(tmp_path)
        assert status.opencode_prompt_exists is False

    def test_index_freshness_missing(self, tmp_path):
        svc = RepoStatusService()
        status = svc.get_status(tmp_path)
        assert status.index_freshness == "missing"


# ---------------------------------------------------------------------------
# RepoStatus — partial .vibecode
# ---------------------------------------------------------------------------


class TestRepoStatusPartialVibecode:
    def test_vibecode_dir_present_but_empty(self, tmp_path):
        _make_vibecode_dir(tmp_path)
        svc = RepoStatusService()
        status = svc.get_status(tmp_path)
        assert status.vibecode_dir_exists is True
        assert status.manual_truth_count == 0

    def test_project_yaml_detected(self, tmp_path):
        vdir = _make_vibecode_dir(tmp_path)
        (vdir / "project.yaml").write_text("project_id: test\n", encoding="utf-8")
        svc = RepoStatusService()
        status = svc.get_status(tmp_path)
        assert status.manual_truth[".vibecode/project.yaml"] is True

    def test_some_manual_truth_present(self, tmp_path):
        vdir = _make_vibecode_dir(tmp_path)
        (vdir / "project.yaml").write_text("", encoding="utf-8")
        arch = vdir / "architecture"
        arch.mkdir()
        (arch / "OVERVIEW.md").write_text("", encoding="utf-8")
        svc = RepoStatusService()
        status = svc.get_status(tmp_path)
        assert status.manual_truth_count == 2


# ---------------------------------------------------------------------------
# RepoStatus — complete manual truth
# ---------------------------------------------------------------------------


class TestRepoStatusCompleteManualTruth:
    def test_all_manual_truth_present(self, tmp_path):
        for rel in _MANUAL_TRUTH_FILES:
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("", encoding="utf-8")
        svc = RepoStatusService()
        status = svc.get_status(tmp_path)
        assert status.manual_truth_count == len(_MANUAL_TRUTH_FILES)
        assert all(status.manual_truth.values())


# ---------------------------------------------------------------------------
# RepoStatus — generated index
# ---------------------------------------------------------------------------


class TestRepoStatusGeneratedIndex:
    def test_generated_index_absent(self, tmp_path):
        _make_vibecode_dir(tmp_path)
        svc = RepoStatusService()
        status = svc.get_status(tmp_path)
        assert status.generated_index_count == 0

    def test_generated_index_present(self, tmp_path):
        for rel in _GENERATED_INDEX_FILES:
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("{}", encoding="utf-8")
        svc = RepoStatusService()
        status = svc.get_status(tmp_path)
        assert status.generated_index_count == len(_GENERATED_INDEX_FILES)


# ---------------------------------------------------------------------------
# RepoStatus — current context files
# ---------------------------------------------------------------------------


class TestRepoStatusContextFiles:
    def test_context_pack_present(self, tmp_path):
        cp = tmp_path / ".vibecode" / "current" / "context_pack.md"
        cp.parent.mkdir(parents=True, exist_ok=True)
        cp.write_text("# ctx", encoding="utf-8")
        svc = RepoStatusService()
        status = svc.get_status(tmp_path)
        assert status.context_pack_exists is True

    def test_context_pack_absent_after_creation(self, tmp_path):
        cp = tmp_path / ".vibecode" / "current" / "context_pack.md"
        cp.parent.mkdir(parents=True, exist_ok=True)
        cp.write_text("# ctx", encoding="utf-8")
        cp.unlink()
        svc = RepoStatusService()
        status = svc.get_status(tmp_path)
        assert status.context_pack_exists is False

    def test_check_results_present(self, tmp_path):
        cr = tmp_path / ".vibecode" / "current" / "check_results.json"
        cr.parent.mkdir(parents=True, exist_ok=True)
        cr.write_text("{}", encoding="utf-8")
        svc = RepoStatusService()
        status = svc.get_status(tmp_path)
        assert status.check_results_exist is True

    def test_opencode_prompt_present(self, tmp_path):
        op = tmp_path / ".vibecode" / "current" / "opencode_prompt.md"
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text("prompt", encoding="utf-8")
        svc = RepoStatusService()
        status = svc.get_status(tmp_path)
        assert status.opencode_prompt_exists is True


# ---------------------------------------------------------------------------
# RepoStatus — git state
# ---------------------------------------------------------------------------


class TestRepoStatusGitState:
    def test_git_state_is_valid_literal(self, tmp_path):
        svc = RepoStatusService()
        status = svc.get_status(tmp_path)
        assert status.git_state in ("clean", "dirty", "unknown")

    def test_git_state_clean_on_empty_output(self, tmp_path, monkeypatch):
        def fake_run(cmd, **kwargs):
            class R:
                returncode = 0
                stdout = ""
                stderr = ""

            return R()

        monkeypatch.setattr(subprocess, "run", fake_run)
        svc = RepoStatusService()
        status = svc.get_status(tmp_path)
        assert status.git_state == "clean"

    def test_git_state_dirty_when_changes_present(self, tmp_path, monkeypatch):
        def fake_run(cmd, **kwargs):
            class R:
                returncode = 0
                stdout = " M somefile.py\n"
                stderr = ""

            return R()

        monkeypatch.setattr(subprocess, "run", fake_run)
        svc = RepoStatusService()
        status = svc.get_status(tmp_path)
        assert status.git_state == "dirty"

    def test_git_state_unknown_on_nonzero_returncode(self, tmp_path, monkeypatch):
        def fake_run(cmd, **kwargs):
            class R:
                returncode = 128
                stdout = ""
                stderr = "not a git repo"

            return R()

        monkeypatch.setattr(subprocess, "run", fake_run)
        svc = RepoStatusService()
        status = svc.get_status(tmp_path)
        assert status.git_state == "unknown"

    def test_git_state_unknown_on_oserror(self, tmp_path, monkeypatch):
        def fake_run(cmd, **kwargs):
            raise OSError("no git")

        monkeypatch.setattr(subprocess, "run", fake_run)
        svc = RepoStatusService()
        status = svc.get_status(tmp_path)
        assert status.git_state == "unknown"

    def test_git_state_unknown_on_subprocess_error(self, tmp_path, monkeypatch):
        def fake_run(cmd, **kwargs):
            raise subprocess.SubprocessError("timeout")

        monkeypatch.setattr(subprocess, "run", fake_run)
        svc = RepoStatusService()
        status = svc.get_status(tmp_path)
        assert status.git_state == "unknown"


# ---------------------------------------------------------------------------
# RepoStatus — index freshness
# ---------------------------------------------------------------------------


class TestRepoStatusIndexFreshness:
    def test_freshness_missing_without_last_index(self, tmp_path):
        svc = RepoStatusService()
        status = svc.get_status(tmp_path)
        assert status.index_freshness == "missing"

    def test_freshness_missing_without_file_inventory(self, tmp_path):
        li = tmp_path / ".vibecode" / "current" / "last_index.json"
        li.parent.mkdir(parents=True, exist_ok=True)
        li.write_text("{}", encoding="utf-8")
        svc = RepoStatusService()
        status = svc.get_status(tmp_path)
        assert status.index_freshness == "missing"

    def test_freshness_fresh_when_check_returns_true(self, tmp_path, monkeypatch):
        li = tmp_path / ".vibecode" / "current" / "last_index.json"
        li.parent.mkdir(parents=True, exist_ok=True)
        li.write_text("{}", encoding="utf-8")
        fi = tmp_path / ".vibecode" / "index" / "file_inventory.json"
        fi.parent.mkdir(parents=True, exist_ok=True)
        fi.write_text("{}", encoding="utf-8")
        import vibecode.indexer as idx

        monkeypatch.setattr(idx, "check_index_freshness", lambda root: (True, "fresh"))
        svc = RepoStatusService()
        status = svc.get_status(tmp_path)
        assert status.index_freshness == "fresh"

    def test_freshness_stale_when_check_returns_false(self, tmp_path, monkeypatch):
        li = tmp_path / ".vibecode" / "current" / "last_index.json"
        li.parent.mkdir(parents=True, exist_ok=True)
        li.write_text("{}", encoding="utf-8")
        fi = tmp_path / ".vibecode" / "index" / "file_inventory.json"
        fi.parent.mkdir(parents=True, exist_ok=True)
        fi.write_text("{}", encoding="utf-8")
        import vibecode.indexer as idx

        monkeypatch.setattr(idx, "check_index_freshness", lambda root: (False, "stale"))
        svc = RepoStatusService()
        status = svc.get_status(tmp_path)
        assert status.index_freshness == "stale"

    def test_freshness_unknown_when_check_raises(self, tmp_path, monkeypatch):
        li = tmp_path / ".vibecode" / "current" / "last_index.json"
        li.parent.mkdir(parents=True, exist_ok=True)
        li.write_text("{}", encoding="utf-8")
        fi = tmp_path / ".vibecode" / "index" / "file_inventory.json"
        fi.parent.mkdir(parents=True, exist_ok=True)
        fi.write_text("{}", encoding="utf-8")
        import vibecode.indexer as idx

        monkeypatch.setattr(idx, "check_index_freshness", lambda root: (_ for _ in ()).throw(RuntimeError("boom")))
        svc = RepoStatusService()
        status = svc.get_status(tmp_path)
        assert status.index_freshness == "unknown"


# ---------------------------------------------------------------------------
# RepoStatus model invariants
# ---------------------------------------------------------------------------


class TestRepoStatusModel:
    def test_repo_path_stored(self, tmp_path):
        svc = RepoStatusService()
        status = svc.get_status(tmp_path)
        assert status.repo_path == tmp_path

    def test_manual_truth_keys_match_constants(self, tmp_path):
        svc = RepoStatusService()
        status = svc.get_status(tmp_path)
        assert set(status.manual_truth.keys()) == set(_MANUAL_TRUTH_FILES)

    def test_generated_index_keys_match_constants(self, tmp_path):
        svc = RepoStatusService()
        status = svc.get_status(tmp_path)
        assert set(status.generated_index.keys()) == set(_GENERATED_INDEX_FILES)

    def test_manual_truth_count_matches_present_files(self, tmp_path):
        vdir = _make_vibecode_dir(tmp_path)
        (vdir / "project.yaml").write_text("", encoding="utf-8")
        svc = RepoStatusService()
        status = svc.get_status(tmp_path)
        present = sum(1 for v in status.manual_truth.values() if v)
        assert status.manual_truth_count == present

    def test_generated_index_count_matches_present_files(self, tmp_path):
        for rel in list(_GENERATED_INDEX_FILES)[:3]:
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("{}", encoding="utf-8")
        svc = RepoStatusService()
        status = svc.get_status(tmp_path)
        assert status.generated_index_count == 3
