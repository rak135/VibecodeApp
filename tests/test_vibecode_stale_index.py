"""Tests for stale index detection in vibecode."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from vibecode.indexer import check_index_freshness


def _init_git(repo):
    result = subprocess.run(
        ["git", "init", "-b", "main"], cwd=repo, capture_output=True
    )
    if result.returncode != 0:
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo, check=True, capture_output=True,
    )


def _git_add_commit(repo, message="init"):
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo, check=True, capture_output=True,
    )


def _get_head_commit(repo):
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=repo, capture_output=True, text=True,
    )
    return result.stdout.strip()


def _make_index(repo, git_commit="abc1234", started_at=None):
    current_dir = repo / ".vibecode" / "current"
    current_dir.mkdir(parents=True, exist_ok=True)

    if started_at is None:
        started_at = datetime.now(tz=timezone.utc).isoformat()

    record = {
        "$schema": "vibecode/index-run/v1",
        "project_id": "testproject",
        "root": str(repo),
        "started_at": started_at,
        "finished_at": datetime.now(tz=timezone.utc).isoformat(),
        "counts": {"files": 3, "symbols": 10, "tests": 1,
                    "warnings": 0, "errors": 0},
        "warnings": [],
        "errors": [],
        "generator": "vibecode 0.1.0",
        "git_commit": git_commit,
    }

    index_path = current_dir / "last_index.json"
    index_path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8")
    return index_path


def _setup_complete_vibecode(repo):
    """Set up a vibecode project with minimal required files."""
    _init_git(repo)
    vibecode_dir = repo / ".vibecode"
    vibecode_dir.mkdir()

    # project.yaml (minimal, enough for validation to pass)
    arch_dir = vibecode_dir / "architecture"
    arch_dir.mkdir()
    (arch_dir / "INVARIANTS.md").write_text(
        "# Invariants\n\n- Invariant test.\n", encoding="utf-8"
    )
    (arch_dir / "STRUCTURE.md").write_text(
        "# Structure\n\ntest\n", encoding="utf-8"
    )

    lines = [
        "project:",
        "  id: test",
        "  name: test",
        "  root: .",
    ]
    (vibecode_dir / "project.yaml").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )

    # Create a tracked file and commit
    (repo / "app.py").write_text("x = 1\n", encoding="utf-8")
    _git_add_commit(repo, "init")


class TestCheckIndexFreshness:

    def test_no_index_file_returns_stale(self, tmp_path):
        fresh, detail = check_index_freshness(tmp_path)
        assert fresh is False
        assert "No index found" in detail

    def test_invalid_json_returns_stale(self, tmp_path):
        current_dir = tmp_path / ".vibecode" / "current"
        current_dir.mkdir(parents=True, exist_ok=True)
        (current_dir / "last_index.json").write_text("!!invalid!!\n",
                                                       encoding="utf-8")
        fresh, detail = check_index_freshness(tmp_path)
        assert fresh is False
        assert "Cannot parse" in detail

    def test_fresh_index_returns_true(self, tmp_path):
        _setup_complete_vibecode(tmp_path)
        head = _get_head_commit(tmp_path)
        _make_index(tmp_path, git_commit=head)
        fresh, detail = check_index_freshness(tmp_path)
        assert fresh is True, "Expected fresh, got: {}".format(detail)
        assert detail == "fresh"

    def test_stale_by_age_returns_false(self, tmp_path):
        _setup_complete_vibecode(tmp_path)
        old_time = (datetime.now(tz=timezone.utc)
                     - timedelta(hours=1)).isoformat()
        _make_index(tmp_path, started_at=old_time)
        fresh, detail = check_index_freshness(tmp_path,
                                               max_age_seconds=300.0)
        assert fresh is False
        assert "s old" in detail

    def test_stale_by_commit_mismatch_returns_false(self, tmp_path):
        _setup_complete_vibecode(tmp_path)
        _make_index(tmp_path, git_commit="oldcommitthatdoesnotmatch")
        fresh, detail = check_index_freshness(tmp_path)
        assert fresh is False, "Expected stale, got: {}".format(detail)
        assert "re-index" in detail.lower()

    def test_unknown_git_commit_in_index_is_ok(self, tmp_path):
        _setup_complete_vibecode(tmp_path)
        _make_index(tmp_path, git_commit="unknown")
        fresh, detail = check_index_freshness(tmp_path)
        assert fresh is True
        assert detail == "fresh"

    def test_unknown_current_commit_is_ok(self, tmp_path):
        _make_index(tmp_path, git_commit="abc1234")
        fresh, detail = check_index_freshness(tmp_path)
        assert fresh is True
        assert detail == "fresh"

    def test_index_missing_git_commit_field_is_fresh(self, tmp_path):
        _setup_complete_vibecode(tmp_path)
        _make_index(tmp_path, git_commit="abc1234")
        index_path = tmp_path / ".vibecode" / "current" / "last_index.json"
        record = json.loads(index_path.read_text(encoding="utf-8"))
        del record["git_commit"]
        index_path.write_text(json.dumps(record, indent=2),
                              encoding="utf-8")
        fresh, detail = check_index_freshness(tmp_path)
        assert fresh is True
        assert detail == "fresh"


class TestCheckIndexFreshnessIntegration:

    def test_fresh_after_index_command(self, tmp_path):
        _setup_complete_vibecode(tmp_path)
        from vibecode.indexer import cmd_index
        rc = cmd_index(SimpleNamespace(repo_root=str(tmp_path), debug=False))
        assert rc == 0
        fresh, detail = check_index_freshness(tmp_path)
        assert fresh is True, "Expected fresh, got: {}".format(detail)

    def test_stale_after_new_commit(self, tmp_path):
        _setup_complete_vibecode(tmp_path)
        from vibecode.indexer import cmd_index
        rc = cmd_index(SimpleNamespace(repo_root=str(tmp_path), debug=False))
        assert rc == 0
        fresh, _ = check_index_freshness(tmp_path)
        assert fresh is True

        (tmp_path / "app.py").write_text("x = 2\n", encoding="utf-8")
        _git_add_commit(tmp_path, "changed app.py")
        fresh, detail = check_index_freshness(tmp_path)
        assert fresh is False, "Expected stale, got: {}".format(detail)
        assert "re-index" in detail.lower()

    def test_stale_after_adding_source_file(self, tmp_path):
        _setup_complete_vibecode(tmp_path)
        from vibecode.indexer import cmd_index
        rc = cmd_index(SimpleNamespace(repo_root=str(tmp_path), debug=False))
        assert rc == 0
        fresh, _ = check_index_freshness(tmp_path)
        assert fresh is True

        (tmp_path / "new_module.py").write_text("def foo(): pass\n", encoding="utf-8")
        subprocess.run(["git", "add", "new_module.py"], cwd=tmp_path, check=True, capture_output=True)

        fresh, detail = check_index_freshness(tmp_path)
        assert fresh is False, "Expected stale by fingerprint, got: {}".format(detail)
        assert "run 'vibecode index'" in detail.lower()

    def test_stale_after_removing_tracked_file(self, tmp_path):
        _setup_complete_vibecode(tmp_path)
        from vibecode.indexer import cmd_index
        rc = cmd_index(SimpleNamespace(repo_root=str(tmp_path), debug=False))
        assert rc == 0
        fresh, _ = check_index_freshness(tmp_path)
        assert fresh is True

        (tmp_path / "app.py").unlink()
        subprocess.run(["git", "rm", "--cached", "app.py"], cwd=tmp_path, check=True, capture_output=True)

        fresh, detail = check_index_freshness(tmp_path)
        assert fresh is False, "Expected stale by fingerprint, got: {}".format(detail)
        assert "run 'vibecode index'" in detail.lower()

    def test_generated_runtime_change_ignored(self, tmp_path):
        _setup_complete_vibecode(tmp_path)
        from vibecode.indexer import cmd_index
        rc = cmd_index(SimpleNamespace(repo_root=str(tmp_path), debug=False))
        assert rc == 0
        fresh, _ = check_index_freshness(tmp_path)
        assert fresh is True

        current_dir = tmp_path / ".vibecode" / "current"
        current_dir.mkdir(parents=True, exist_ok=True)
        (current_dir / "run_log.txt").write_text("log content\n", encoding="utf-8")

        fresh, detail = check_index_freshness(tmp_path)
        assert fresh is True, "Expected fresh (generated dir ignored), got: {}".format(detail)

    def test_fingerprint_stale_without_commit(self, tmp_path):
        _setup_complete_vibecode(tmp_path)
        from vibecode.indexer import cmd_index
        rc = cmd_index(SimpleNamespace(repo_root=str(tmp_path), debug=False))
        assert rc == 0
        fresh, _ = check_index_freshness(tmp_path)
        assert fresh is True

        (tmp_path / "untracked_helper.py").write_text("x = 42\n", encoding="utf-8")

        fresh, detail = check_index_freshness(tmp_path)
        assert fresh is False, "Expected stale by fingerprint (untracked file), got: {}".format(detail)
        assert "run 'vibecode index'" in detail.lower()

    def test_fresh_after_adding_generated_cache_dir_file(self, tmp_path):
        _setup_complete_vibecode(tmp_path)
        from vibecode.indexer import cmd_index
        rc = cmd_index(SimpleNamespace(repo_root=str(tmp_path), debug=False))
        assert rc == 0
        fresh, _ = check_index_freshness(tmp_path)
        assert fresh is True

        cache_dir = tmp_path / ".vibecode" / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / "data.bin").write_bytes(b"\x00\x01\x02")

        fresh, detail = check_index_freshness(tmp_path)
        assert fresh is True, "Expected fresh (cache dir ignored), got: {}".format(detail)

    def test_fresh_after_adding_log_file(self, tmp_path):
        _setup_complete_vibecode(tmp_path)
        from vibecode.indexer import cmd_index
        rc = cmd_index(SimpleNamespace(repo_root=str(tmp_path), debug=False))
        assert rc == 0
        fresh, _ = check_index_freshness(tmp_path)
        assert fresh is True

        logs_dir = tmp_path / ".vibecode" / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        (logs_dir / "index.log").write_text("index run\n", encoding="utf-8")

        fresh, detail = check_index_freshness(tmp_path)
        assert fresh is True, "Expected fresh (logs dir ignored), got: {}".format(detail)
