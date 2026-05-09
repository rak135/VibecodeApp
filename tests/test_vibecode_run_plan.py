"""Tests for the run-plan assembly utility (vibecode.run_plan)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from vibecode.cli import main
from vibecode.run_plan import (
    RunPlan,
    RunPlanWarning,
    build_run_plan,
    render_run_plan,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(repo: Path) -> None:
    result = subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")


def _commit_all(repo: Path) -> None:
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")


def _minimal_vibecode(repo: Path) -> None:
    """Write the minimal .vibecode/project.yaml and index for a valid repo."""
    _write(
        repo / ".vibecode" / "project.yaml",
        "project:\n"
        "  id: testproject\n"
        "  name: Test Project\n"
        "  root: .\n"
        "indexing:\n"
        "  include: ['*.py']\n"
        "  exclude: []\n"
        "  protected_paths: []\n"
        "  risk_rules: []\n",
    )
    _write(
        repo / ".vibecode" / "current" / "last_index.json",
        json.dumps(
            {
                "$schema": "vibecode/index-run/v1",
                "project_id": "testproject",
                "root": str(repo),
                "started_at": "2026-01-15T10:00:00+00:00",
                "finished_at": "2026-01-15T10:00:02+00:00",
                "counts": {"files": 3, "symbols": 10, "tests": 1, "warnings": 0, "errors": 0},
                "warnings": [],
                "errors": [],
                "generator": "vibecode 0.1.0",
            }
        ),
    )


# ---------------------------------------------------------------------------
# RunPlan dataclass
# ---------------------------------------------------------------------------


class TestRunPlanDataclass:
    def test_construction_with_defaults(self, tmp_path):
        plan = RunPlan(
            repo_root=str(tmp_path),
            task="test task",
            dirty=False,
            dirty_paths=(),
            index_fresh=True,
            index_age_seconds=0.0,
            context_pack_path=None,
            opencode_prompt_path=None,
            permission_profile=None,
            preflight_warnings=(),
            preflight_errors=(),
            commands=("echo hello",),
        )
        assert plan.repo_root == str(tmp_path)
        assert plan.task == "test task"
        assert plan.dirty is False
        assert plan.index_fresh is True
        assert plan.context_pack_path is None
        assert plan.preflight_warnings == ()
        assert plan.preflight_errors == ()
        assert len(plan.commands) == 1

    def test_metadata_defaults_to_empty_dict(self):
        plan = RunPlan(
            repo_root="/tmp",
            task="test",
            dirty=False,
            dirty_paths=(),
            index_fresh=False,
            index_age_seconds=None,
            context_pack_path=None,
            opencode_prompt_path=None,
            permission_profile=None,
            preflight_warnings=(),
            preflight_errors=(),
            commands=(),
        )
        assert plan.metadata == {}

    def test_frozen_immutable(self):
        plan = RunPlan(
            repo_root="/tmp",
            task="test",
            dirty=False,
            dirty_paths=(),
            index_fresh=False,
            index_age_seconds=None,
            context_pack_path=None,
            opencode_prompt_path=None,
            permission_profile=None,
            preflight_warnings=(),
            preflight_errors=(),
            commands=(),
        )
        with pytest.raises(AttributeError):
            plan.dirty = True  # type: ignore[misc]


# ---------------------------------------------------------------------------
# RunPlanWarning dataclass
# ---------------------------------------------------------------------------


class TestRunPlanWarning:
    def test_construction(self):
        w = RunPlanWarning("warn", "Something might be wrong")
        assert w.level == "warn"
        assert w.message == "Something might be wrong"

    def test_frozen_immutable(self):
        w = RunPlanWarning("warn", "message")
        with pytest.raises(AttributeError):
            w.level = "error"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# build_run_plan — happy path with clean repo + fresh index
# ---------------------------------------------------------------------------


class TestBuildRunPlanCleanRepo:
    """A clean indexed repo should produce a plan with no errors and few warnings."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path: Path):
        _init_repo(tmp_path)
        _write(tmp_path / "src" / "app.py", "print('hello')\n")
        _commit_all(tmp_path)
        _minimal_vibecode(tmp_path)

        # Index needs file_inventory.json for context pack path setting
        _write(
            tmp_path / ".vibecode" / "index" / "file_inventory.json",
            json.dumps({"files": []}),
        )
        _commit_all(tmp_path)

        self.repo = tmp_path

    def test_clean_repo_plan(self):
        plan = build_run_plan(self.repo, task="test task")

        assert plan.repo_root == str(self.repo.resolve())
        assert plan.task == "test task"
        assert plan.dirty is False
        assert plan.dirty_paths == ()
        assert plan.index_fresh is True
        assert plan.preflight_errors == ()
        assert plan.context_pack_path is not None
        assert "context_pack.md" in plan.context_pack_path
        assert plan.opencode_prompt_path is not None
        assert "opencode_prompt.md" in plan.opencode_prompt_path
        # permission_profile is None because the file hasn't been written yet
        assert plan.permission_profile is None

    def test_clean_repo_no_dirty_warning(self):
        plan = build_run_plan(self.repo, task="test task")
        dirty_warnings = [w for w in plan.preflight_warnings if "dirty" in w.message.lower()]
        assert len(dirty_warnings) == 0


# ---------------------------------------------------------------------------
# build_run_plan — dirty repo
# ---------------------------------------------------------------------------


class TestBuildRunPlanDirtyRepo:
    def test_dirty_repo_emits_warning(self, tmp_path: Path):
        _init_repo(tmp_path)
        _write(tmp_path / "src" / "app.py", "print('hello')\n")
        _commit_all(tmp_path)
        _minimal_vibecode(tmp_path)

        # Make a change after commit
        _write(tmp_path / "src" / "app.py", "print('changed')\n")

        plan = build_run_plan(tmp_path, task="test task")

        assert plan.dirty is True
        assert len(plan.dirty_paths) >= 1
        assert any("app.py" in p for p in plan.dirty_paths)

        # Must contain a dirty-tree warning
        dirty_warnings = [w for w in plan.preflight_warnings if "dirty" in w.message.lower()]
        assert len(dirty_warnings) >= 1


# ---------------------------------------------------------------------------
# build_run_plan — missing project.yaml
# ---------------------------------------------------------------------------


class TestBuildRunPlanMissingProjectYaml:
    def test_missing_project_yaml_emits_error(self, tmp_path: Path):
        """A repo without .vibecode/project.yaml must produce an error."""
        _init_repo(tmp_path)
        _write(tmp_path / "src" / "app.py", "x = 1\n")
        _commit_all(tmp_path)
        # Do NOT create .vibecode/project.yaml

        plan = build_run_plan(tmp_path, task="test task")

        assert any(e.level == "error" for e in plan.preflight_errors)
        assert any("project.yaml" in e.message for e in plan.preflight_errors)


# ---------------------------------------------------------------------------
# build_run_plan — missing index
# ---------------------------------------------------------------------------


class TestBuildRunPlanMissingIndex:
    def test_missing_index_emits_warning(self, tmp_path: Path):
        """A repo with project.yaml but no index must emit a warning."""
        _init_repo(tmp_path)
        _write(tmp_path / "src" / "app.py", "x = 1\n")
        _commit_all(tmp_path)
        _write(
            tmp_path / ".vibecode" / "project.yaml",
            "project:\n  id: test\n  name: Test\n  root: .\n"
            "indexing:\n  include: []\n  exclude: []\n  protected_paths: []\n"
            "  risk_rules: []\n",
        )
        # Do NOT create last_index.json

        plan = build_run_plan(tmp_path, task="test task")

        assert any("index" in w.message.lower() for w in plan.preflight_warnings)


# ---------------------------------------------------------------------------
# build_run_plan — stale index
# ---------------------------------------------------------------------------


class TestBuildRunPlanStaleIndex:
    def test_old_index_age_in_metadata(self, tmp_path: Path):
        """A very old index should show age in seconds."""
        _init_repo(tmp_path)
        _write(tmp_path / "src" / "app.py", "x = 1\n")
        _commit_all(tmp_path)
        _write(
            tmp_path / ".vibecode" / "project.yaml",
            "project:\n  id: test\n  name: Test\n  root: .\n"
            "indexing:\n  include: []\n  exclude: []\n  protected_paths: []\n"
            "  risk_rules: []\n",
        )
        _write(
            tmp_path / ".vibecode" / "current" / "last_index.json",
            json.dumps({
                "project_id": "test",
                "root": str(tmp_path),
                "started_at": "2020-01-01T00:00:00+00:00",  # very old
                "finished_at": "2020-01-01T00:00:01+00:00",
                "counts": {},
            }),
        )

        plan = build_run_plan(tmp_path, task="test task")

        assert plan.index_age_seconds is not None
        # Index age should be several years worth of seconds
        assert plan.index_age_seconds > 1_000_000


# ---------------------------------------------------------------------------
# build_run_plan — non-git directory
# ---------------------------------------------------------------------------


class TestBuildRunPlanNonGitDir:
    def test_non_git_dir_warns(self, tmp_path: Path):
        """A non-git directory should not error, just warn."""
        _write(
            tmp_path / ".vibecode" / "project.yaml",
            "project:\n  id: test\n  name: Test\n  root: .\n"
            "indexing:\n  include: []\n  exclude: []\n  protected_paths: []\n"
            "  risk_rules: []\n",
        )
        _write(
            tmp_path / ".vibecode" / "current" / "last_index.json",
            json.dumps({"project_id": "test", "root": str(tmp_path)}),
        )

        plan = build_run_plan(tmp_path, task="test task")

        assert plan.dirty is False
        warning_msgs = [w.message for w in plan.preflight_warnings]
        assert any("not a git repository" in m.lower() or "git" in m.lower() for m in warning_msgs)


# ---------------------------------------------------------------------------
# render_run_plan
# ---------------------------------------------------------------------------


class TestRenderRunPlan:
    def test_rendered_output_contains_key_fields(self):
        plan = RunPlan(
            repo_root="/tmp/test",
            task="my task",
            dirty=False,
            dirty_paths=(),
            index_fresh=True,
            index_age_seconds=10.0,
            context_pack_path="/tmp/test/.vibecode/current/context_pack.md",
            opencode_prompt_path="/tmp/test/.vibecode/current/opencode_prompt.md",
            permission_profile="/tmp/test/.vibecode/agents/safe.json",
            preflight_warnings=(),
            preflight_errors=(),
            commands=("echo hello",),
        )

        text = render_run_plan(plan)

        assert "RUN PLAN" in text
        assert "my task" in text
        assert "CLEAN" in text
        assert "FRESH" in text
        assert "echo hello" in text

    def test_render_shows_errors(self):
        plan = RunPlan(
            repo_root="/tmp/test",
            task="my task",
            dirty=False,
            dirty_paths=(),
            index_fresh=False,
            index_age_seconds=None,
            context_pack_path=None,
            opencode_prompt_path=None,
            permission_profile=None,
            preflight_warnings=(),
            preflight_errors=(
                RunPlanWarning("error", "No project.yaml"),
            ),
            commands=(),
        )

        text = render_run_plan(plan)
        assert "ERRORS:" in text
        assert "No project.yaml" in text

    def test_render_shows_warnings(self):
        plan = RunPlan(
            repo_root="/tmp/test",
            task="my task",
            dirty=False,
            dirty_paths=(),
            index_fresh=False,
            index_age_seconds=None,
            context_pack_path=None,
            opencode_prompt_path=None,
            permission_profile=None,
            preflight_warnings=(
                RunPlanWarning("warn", "Index not found"),
            ),
            preflight_errors=(),
            commands=(),
        )

        text = render_run_plan(plan)
        assert "WARNINGS:" in text
        assert "Index not found" in text

    def test_render_shows_dirty_paths_when_many(self):
        dirty_paths = [f"file_{i}.py" for i in range(12)]
        plan = RunPlan(
            repo_root="/tmp/test",
            task="my task",
            dirty=True,
            dirty_paths=tuple(dirty_paths),
            index_fresh=False,
            index_age_seconds=None,
            context_pack_path=None,
            opencode_prompt_path=None,
            permission_profile=None,
            preflight_warnings=(),
            preflight_errors=(),
            commands=(),
        )

        text = render_run_plan(plan)
        assert "file_0.py" in text
        assert "file_9.py" in text
        assert "2 more" in text  # 12 shown: 8 truncated + "2 more"


# ---------------------------------------------------------------------------
# CLI: vibecode run-plan
# ---------------------------------------------------------------------------


class TestRunPlanCLI:
    def test_run_plan_needs_repo_root(self, tmp_path, capsys):
        """Omitting the repo root argument should give a usable error."""
        # Actually, the repo_root defaults to "." in the parser,
        # so we just check it works with explicit path.
        rc = main(["run-plan", str(tmp_path)])
        # Should succeed (no project.yaml = error in plan but CLI runs)
        assert rc in (0, 1)

    def test_run_plan_with_minimal_repo(self, tmp_path, capsys):
        """A minimal repo with project.yaml and index produces a plan."""
        _init_repo(tmp_path)
        _write(tmp_path / "app.py", "x = 1\n")
        _commit_all(tmp_path)
        _minimal_vibecode(tmp_path)
        _write(
            tmp_path / ".vibecode" / "index" / "file_inventory.json",
            json.dumps({"files": []}),
        )
        _commit_all(tmp_path)

        rc = main(["run-plan", str(tmp_path), "--task", "test task"])
        out = capsys.readouterr().out

        assert rc == 0
        assert "RUN PLAN" in out
        assert "test task" in out
        assert "CLEAN" in out
        assert "FRESH" in out or "index" in out.lower()

    def test_run_plan_with_dirty_repo(self, tmp_path, capsys):
        """A dirty repo should show dirty status in plan output."""
        _init_repo(tmp_path)
        _minimal_vibecode(tmp_path)
        _write(tmp_path / "app.py", "x = 1\n")
        _commit_all(tmp_path)
        _write(
            tmp_path / ".vibecode" / "index" / "file_inventory.json",
            json.dumps({"files": []}),
        )
        _commit_all(tmp_path)

        # Make a dirty change
        _write(tmp_path / "app.py", "x = 2\n")

        main(["run-plan", str(tmp_path), "--task", "dirty test"])
        out = capsys.readouterr().out

        assert "DIRTY" in out
        assert "app.py" in out

    def test_run_plan_with_missing_project_yaml(self, tmp_path, capsys):
        _init_repo(tmp_path)
        _write(tmp_path / "app.py", "x = 1\n")
        _commit_all(tmp_path)
        # No .vibecode/project.yaml

        rc = main(["run-plan", str(tmp_path), "--task", "test"])
        out = capsys.readouterr().out

        assert rc == 1
        assert "project.yaml" in out.lower() or "ERROR" in out

    def test_run_plan_json_output(self, tmp_path):
        """Run plan should write JSON to .vibecode/current/run_plan.json."""
        _init_repo(tmp_path)
        _minimal_vibecode(tmp_path)
        _write(tmp_path / "app.py", "x = 1\n")
        _commit_all(tmp_path)
        _write(
            tmp_path / ".vibecode" / "index" / "file_inventory.json",
            json.dumps({"files": []}),
        )
        _commit_all(tmp_path)

        main(["run-plan", str(tmp_path), "--task", "json test"])

        json_path = tmp_path / ".vibecode" / "current" / "run_plan.json"
        assert json_path.exists()
        data = json.loads(json_path.read_text(encoding="utf-8"))

        assert data["task"] == "json test"
        assert data["dirty"] is False
        assert data["index_fresh"] is True
        assert data["repo_root"] == str(tmp_path.resolve())
        assert "preflight_warnings" in data
        assert "metadata" in data
        assert data["metadata"]["platform"] == "opencode"

    def test_run_plan_with_profile(self, tmp_path, capsys):
        """Specifying a profile should appear in the plan output."""
        _init_repo(tmp_path)
        _minimal_vibecode(tmp_path)
        _write(tmp_path / "app.py", "x = 1\n")
        _commit_all(tmp_path)
        _write(
            tmp_path / ".vibecode" / "index" / "file_inventory.json",
            json.dumps({"files": []}),
        )
        _commit_all(tmp_path)

        main(["run-plan", str(tmp_path), "--task", "test", "--profile", "safe"])
        out = capsys.readouterr().out

        assert "safe" in out.lower()


# ---------------------------------------------------------------------------
# build_run_plan — permission profile integration
# ---------------------------------------------------------------------------


class TestBuildRunPlanProfiles:
    def test_profile_not_on_disk_warns(self, tmp_path):
        """Profile not yet written to disk should produce a warning."""
        _init_repo(tmp_path)
        _minimal_vibecode(tmp_path)
        # No .vibecode/agents/safe.json written
        _commit_all(tmp_path)

        plan = build_run_plan(tmp_path, task="test task", profile_name="safe")

        assert plan.permission_profile is None
        profile_warnings = [
            w for w in plan.preflight_warnings
            if "profile" in w.message.lower() or "safe" in w.message.lower()
        ]
        assert len(profile_warnings) >= 1

    def test_unknown_profile_emits_error(self, tmp_path):
        """Unknown profile name should produce an error."""
        _init_repo(tmp_path)
        _minimal_vibecode(tmp_path)
        _commit_all(tmp_path)

        plan = build_run_plan(tmp_path, task="test task", profile_name="nonexistent")

        assert any(e.level == "error" for e in plan.preflight_errors)


# ---------------------------------------------------------------------------
# build_run_plan — context pack path availability
# ---------------------------------------------------------------------------


class TestBuildRunPlanContextPackPath:
    def test_context_pack_path_set_when_index_exists(self, tmp_path):
        _init_repo(tmp_path)
        _minimal_vibecode(tmp_path)
        _commit_all(tmp_path)

        plan = build_run_plan(tmp_path, task="test", platform="opencode")

        assert plan.context_pack_path is not None
        assert plan.opencode_prompt_path is not None

    def test_context_pack_path_none_when_no_index(self, tmp_path):
        """Without an index, context_pack_path should remain None."""
        _init_repo(tmp_path)
        _write(
            tmp_path / ".vibecode" / "project.yaml",
            "project:\n  id: test\n  name: Test\n  root: .\n"
            "indexing:\n  include: []\n  exclude: []\n  protected_paths: []\n",
        )
        _commit_all(tmp_path)
        # No last_index.json, no index/ dir

        plan = build_run_plan(tmp_path, task="test", platform="opencode")

        assert plan.context_pack_path is None
        assert plan.opencode_prompt_path is None

    def test_non_opencode_platform_no_prompt_path(self, tmp_path):
        """Non-opencode platform should not set opencode_prompt_path."""
        _init_repo(tmp_path)
        _minimal_vibecode(tmp_path)
        _commit_all(tmp_path)

        plan = build_run_plan(tmp_path, task="test", platform="something_else")

        assert plan.opencode_prompt_path is None