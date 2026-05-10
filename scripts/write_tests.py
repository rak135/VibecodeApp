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
        "counts": {"files": 3, "symbols": 10, "tests": 1, "warnings": 0, "errors": 0},
        "warnings": [],
        "errors": [],
        "generator": "vibecode 0.1.0",
        "git_commit": git_commit,
    }

    index_path = current_dir / "last_index.json"
    index_path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return index_path


class TestCheckIndexFreshness:
    """Unit tests for the check_index_freshness function."""

    def test_no_index_file_returns_stale(self, tmp_path):
        """When no last_index.json exists, index is considered stale."""
        fresh, detail = check_index_freshness(tmp_path)
        assert fresh is False
        assert "No index found" in detail

    def test_invalid_json_returns_stale(self, tmp_path):
        """When last_index.json contains invalid JSON, index is stale."""
        current_dir = tmp_path / ".vibecode" / "current"
        current_dir.mkdir(parents=True, exist_ok=True)
        (current_dir / "last_index.json").write_text("!!invalid!!\n", encoding="utf-8")

        fresh, detail = check_index_freshness(tmp_path)
        assert fresh is False
        assert "Cannot parse" in detail

    def test_fresh_index_returns_true(self, tmp_path):
        """A recently-created index with matching git commit is fresh."""
        _init_git(tmp_path)
        _git_add_commit(tmp_path)
        head = _get_head_commit(tmp_path)
        _make_index(tmp_path, git_commit=head)

        fresh, detail = check_index_freshness(tmp_path)
        assert fresh is True, "Expected fresh, got: {}".format(detail)
        assert detail == "fresh"

    def test_stale_by_age_returns_false(self, tmp_path):
        """An index older than max_age_seconds is stale."""
        _init_git(tmp_path)
        _git_add_commit(tmp_path)
        old_time = (datetime.now(tz=timezone.utc) - timedelta(hours=1)).isoformat()
        _make_index(tmp_path, started_at=old_time)

        fresh, detail = check_index_freshness(tmp_path, max_age_seconds=300.0)
        assert fresh is False
        assert "s old" in detail

    def test_stale_by_commit_mismatch_returns_false(self, tmp_path):
        """An index built for a different git commit is stale."""
        _init_git(tmp_path)
        _git_add_commit(tmp_path)
        _make_index(tmp_path, git_commit="oldcommitthatdoesnotmatch")

        fresh, detail = check_index_freshness(tmp_path)
        assert fresh is False, "Expected stale, got: {}".format(detail)
        assert "re-index" in detail.lower()

    def test_unknown_git_commit_in_index_is_ok(self, tmp_path):
        """An index with git_commit=unknown skips commit comparison."""
        _init_git(tmp_path)
        _git_add_commit(tmp_path)
        _make_index(tmp_path, git_commit="unknown")

        fresh, detail = check_index_freshness(tmp_path)
        assert fresh is True
        assert detail == "fresh"

    def test_unknown_current_commit_is_ok(self, tmp_path):
        """When current HEAD cant be resolved (not a git repo), skip commit comparison."""
        _make_index(tmp_path, git_commit="abc1234")
        fresh, detail = check_index_freshness(tmp_path)
        assert fresh is True
        assert detail == "fresh"

    def test_index_missing_git_commit_field_is_fresh(self, tmp_path):
        """Index record without git_commit field is considered fresh."""
        _init_git(tmp_path)
        _git_add_commit(tmp_path)
        _make_index(tmp_path, git_commit="abc1234")

        index_path = tmp_path / ".vibecode" / "current" / "last_index.json"
        record = json.loads(index_path.read_text(encoding="utf-8"))
        del record["git_commit"]
        index_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

        fresh, detail = check_index_freshness(tmp_path)
        assert fresh is True
        assert detail == "fresh"


class TestCheckIndexFreshnessIntegration:
    """Integration tests using a real vibecode project setup."""

    def test_fresh_after_index_command(self, tmp_path):
        """After running vibecode index, the index should be fresh."""
        _init_git(tmp_path)
        vibecode_dir = tmp_path / ".vibecode"
        vibecode_dir.mkdir(parents=True, exist_ok=True)
        (vibecode_dir / "project.yaml").write_text(
            "project:\n  id: test\n  name: test\n  root: .\n"
            "indexing:\n  include: ['*.py']\n  exclude: []\n"
            "protected_paths: []\n  risk_rules: []\n",
            encoding="utf-8",
        )
        (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
        _git_add_commit(tmp_path)

        from vibecode.indexer import cmd_index

        rc = cmd_index(SimpleNamespace(repo_root=str(tmp_path), debug=False))
        assert rc == 0

        fresh, detail = check_index_freshness(tmp_path)
        assert fresh is True, "Expected fresh, got: {}".format(detail)

    def test_stale_after_new_commit(self, tmp_path):
        """After making a new commit post-index, the index should be stale."""
        _init_git(tmp_path)
        vibecode_dir = tmp_path / ".vibecode"
        vibecode_dir.mkdir(parents=True, exist_ok=True)
        (vibecode_dir / "project.yaml").write_text(
            "project:\n  id: test\n  name: test\n  root: .\n"
            "indexing:\n  include: ['*.py']\n  exclude: []\n"
            "protected_paths: []\n  risk_rules: []\n",
            encoding="utf-8",
        )
        (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
        _git_add_commit(tmp_path)

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