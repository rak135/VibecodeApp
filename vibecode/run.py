"""Run an OpenCode (or other platform) agent session for a repository.

Flow:
  1. Check git status (abort or warn on dirty tree).
  2. Generate or refresh the index if missing or stale.
  3. Generate the context pack and platform prompt.
  4. Invoke the configured platform command with the prompt on stdin.
  5. Capture stdout / stderr / exit code.
  6. Run post-run checks: guard, required checks, handoff validation.
  7. Write session metadata and summary under .vibecode/runs/<timestamp>/.
  8. Print concise result.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vibecode.adapters.opencode import check_opencode
from vibecode.check import CheckRun, run_checks, write_check_results
from vibecode.config import load_config
from vibecode.context import cmd_context
from vibecode.diff_summary import DiffSummary, diff_summarise
from vibecode.guard import GuardResult, _load_test_map, evaluate_project_guard, write_guard_result
from vibecode.git_state import GitState, current_git_commit, inspect_git_state
from vibecode.handoff import HandoffResult, validate_handoff_files
from vibecode.indexer import check_inventory_health, cmd_index
from vibecode.permissions import PROFILES, profile_path
from vibecode.run_plan import build_run_plan


def _get_opencode_command(config: Any | None, env: dict[str, str]) -> str | None:
    """Resolve the OpenCode command from config or environment."""
    # Check environment variable first.
    env_cmd = env.get("OPENCODE_COMMAND")
    if env_cmd:
        return env_cmd

    # Fall back to the default binary name.
    default_cmd = "opencode"
    if shutil.which(default_cmd):
        return default_cmd

    return None


@dataclass
class RunSummary:
    """Post-run summary combining agent results and quality checks."""

    session_id: str
    started_at: str
    finished_at: str
    platform: str
    profile: str
    repo_root: str
    task: str
    dirty: bool
    index_fresh: bool
    command: str | None
    exit_code: int | None
    stdout: str
    stderr: str
    agent_status: str  # "success", "failure", "error"
    guard: GuardResult | None = None
    checks: CheckRun | None = None
    handoff: HandoffResult | None = None
    diff: DiffSummary | None = None
    error: str | None = None

    @property
    def overall_status(self) -> str:
        """Overall run status: 'success', 'failure', 'incomplete', or 'error'."""
        if self.agent_status == "error" or self.error:
            return "error"
        if self.guard and not self.guard.passed:
            return "failure"
        if self.checks and self.checks.has_required_failures:
            return "failure"
        if self.handoff and not self.handoff.passed:
            return "incomplete"
        if self.agent_status != "success":
            return "failure"
        return "success"

    def as_dict(self) -> dict:
        data: dict[str, Any] = {
            "$schema": "vibecode/run-summary/v1",
            "session_id": self.session_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "platform": self.platform,
            "profile": self.profile,
            "repo_root": self.repo_root,
            "task": self.task,
            "dirty": self.dirty,
            "index_fresh": self.index_fresh,
            "command": self.command,
            "exit_code": self.exit_code,
            "agent_status": self.agent_status,
            "overall_status": self.overall_status,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }
        if self.guard:
            data["guard"] = self.guard.as_dict()
        if self.checks:
            data["checks"] = self.checks.as_dict()
        if self.handoff:
            data["handoff"] = self.handoff.as_dict()
        if self.diff:
            data["diff"] = self.diff.as_dict()
        if self.error:
            data["error"] = self.error
        return data


def _write_run_metadata(
    vibecode_dir: Path,
    session_id: str,
    plan: Any,
    command: str | None,
    exit_code: int | None,
    stdout: str,
    stderr: str,
    error: str | None = None,
) -> Path:
    """Write a JSON run record under .vibecode/runs/<session_id>.json."""
    runs_dir = vibecode_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    record = {
        "$schema": "vibecode/run/v1",
        "session_id": session_id,
        "started_at": plan.metadata.get("started_at", datetime.now(tz=timezone.utc).isoformat()),
        "finished_at": datetime.now(tz=timezone.utc).isoformat(),
        "platform": plan.metadata.get("platform", "opencode"),
        "profile": plan.metadata.get("profile", "safe"),
        "repo_root": plan.repo_root,
        "task": plan.task,
        "dirty": plan.dirty,
        "index_fresh": plan.index_fresh,
        "command": command,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "preflight_errors": [
            {"level": e.level, "message": e.message} for e in plan.preflight_errors
        ],
        "preflight_warnings": [
            {"level": w.level, "message": w.message} for w in plan.preflight_warnings
        ],
    }
    if error:
        record["error"] = error

    out_path = runs_dir / f"{session_id}.json"
    out_path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out_path


def _write_run_summary(vibecode_dir: Path, summary: RunSummary) -> Path:
    """Write the run summary JSON under .vibecode/runs/<session_id>/summary.json."""
    summary_dir = vibecode_dir / "runs" / summary.session_id
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_path = summary_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary.as_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return summary_path


def _run_git_check(root: Path, allow_dirty: bool) -> tuple[bool, list[str]]:
    """Check git status.  Returns (clean_ok, list_of_messages)."""
    messages: list[str] = []
    try:
        git_state = inspect_git_state(root)
    except Exception as exc:
        messages.append(f"Could not inspect git state: {exc}")
        return False, messages

    if not git_state.is_git_repo:
        messages.append("Not a git repository.  Run 'git init' first, or pass --allow-dirty to bypass.")
        return False, messages

    if git_state.changed_paths:
        dirty_count = len(git_state.changed_paths)
        if allow_dirty:
            # Warn but still allow the run.
            messages.append(
                f"Git working tree is dirty — {dirty_count} changed file(s). "
                "Consider committing or stashing."
            )
            return True, messages
        else:
            messages.append(
                f"Git working tree is dirty — {dirty_count} changed file(s): "
                + ", ".join(git_state.changed_paths[:8])
                + (" ..." if dirty_count > 8 else "")
                + "\nCommit or stash changes first, or pass --allow-dirty."
            )
            return False, messages

    return True, messages


def _validate_permission_profile(root: Path, profile_name: str) -> tuple[bool, str | None]:
    """Validate that a selected run permission profile exists before launch."""
    if profile_name not in PROFILES:
        known = ", ".join(sorted(PROFILES))
        return False, f"Unknown permission profile '{profile_name}'. Known profiles: {known}."

    rel = profile_path(profile_name)
    target = root / Path(rel)
    if not target.exists():
        return False, f"Permission profile '{profile_name}' is missing at {rel}."

    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"Permission profile '{profile_name}' is not valid JSON: {exc}"
    if not isinstance(data, dict):
        return False, f"Permission profile '{profile_name}' must be a JSON object."
    return True, None


def _changed_path_set(git_state: GitState | None) -> set[str]:
    if not git_state:
        return set()
    return set(git_state.changed_paths) | set(git_state.diff_name_only) | set(git_state.untracked_paths)


def _agent_delta_git_state(before: GitState | None, after: GitState | None) -> GitState | None:
    """Return a git state containing only paths changed after the agent baseline."""
    if after is None:
        return None
    if before is None or not before.is_git_repo:
        return after

    before_paths = _changed_path_set(before)

    def only_new(paths: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(path for path in paths if path not in before_paths)

    status_paths = tuple(
        entry for entry in after.status_paths if entry.path not in before_paths
    )

    return GitState(
        is_git_repo=after.is_git_repo,
        status_paths=status_paths,
        changed_paths=tuple(entry.path for entry in status_paths),
        staged_paths=only_new(after.staged_paths),
        unstaged_paths=only_new(after.unstaged_paths),
        untracked_paths=only_new(after.untracked_paths),
        deleted_paths=only_new(after.deleted_paths),
        diff_name_only=only_new(after.diff_name_only),
        staged_diff_name_only=only_new(after.staged_diff_name_only),
        diff_stat=after.diff_stat,
        staged_diff_stat=after.staged_diff_stat,
        error=after.error,
    )


def _run_post_checks(
    root: Path,
    vibecode_dir: Path,
    git_state: GitState | None,
    session_id: str,
    task: str = "",
) -> tuple[GuardResult | None, CheckRun | None, HandoffResult | None]:
    """Run post-agent quality checks: guard, required checks, handoff validation.

    Returns the results of each check (may be None if the check was skipped
    due to an error). Individual failures do not raise here — the caller
    interprets the results via RunSummary.overall_status.
    """
    guard_result: GuardResult | None = None
    check_result: CheckRun | None = None
    handoff_result: HandoffResult | None = None

    # --- Post-check 1: Guard ---
    try:
        if git_state and git_state.is_git_repo:
            test_map = _load_test_map(vibecode_dir)
            guard_result = evaluate_project_guard(git_state, vibecode_dir, task=task, test_map=test_map)
            try:
                write_guard_result(guard_result, vibecode_dir, root)
            except Exception:
                pass
        else:
            print("Warning: skipped guard (not a git repository).", file=sys.stderr)
    except Exception as exc:
        print(f"Warning: guard check failed with error: {exc}", file=sys.stderr)

    # --- Post-check 2: Required checks ---
    try:
        check_result = run_checks(root)
        write_check_results(check_result, vibecode_dir)
    except Exception as exc:
        print(f"Warning: required checks failed with error: {exc}", file=sys.stderr)

    # --- Post-check 3: Handoff validation ---
    try:
        if git_state and git_state.is_git_repo:
            diff_paths = git_state.diff_name_only + git_state.untracked_paths
            handoff_result = validate_handoff_files(root, diff=diff_paths)
        else:
            print("Warning: skipped handoff-check (not a git repository).", file=sys.stderr)
    except Exception as exc:
        print(f"Warning: handoff-check failed with error: {exc}", file=sys.stderr)

    return guard_result, check_result, handoff_result


def cmd_run(args) -> int:
    """CLI entry point for ``vibecode run``."""
    repo_arg = getattr(args, "repo_root", None)
    task = getattr(args, "task", None) or ""
    platform = getattr(args, "platform", "opencode")
    profile = getattr(args, "profile", None)
    profile_name = profile or "safe"
    allow_dirty = getattr(args, "allow_dirty", False)
    no_index = getattr(args, "no_index", False)

    if not repo_arg:
        print("Error: repo root is required.", file=sys.stderr)
        return 1

    # repo_arg is already a resolved Path (normalised by the CLI dispatcher).
    root: Path = repo_arg
    vibecode_dir = root / ".vibecode"
    session_id = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")

    if not (vibecode_dir / "project.yaml").exists():
        print("Error: no .vibecode/project.yaml found. Run 'vibecode init' first.", file=sys.stderr)
        return 1

    profile_ok, profile_error = _validate_permission_profile(root, profile_name)
    if not profile_ok:
        print(f"Error: {profile_error}", file=sys.stderr)
        return 1

    # ------------------------------------------------------------------
    # 1. Git status check
    # ------------------------------------------------------------------
    clean_ok, messages = _run_git_check(root, allow_dirty)
    if not clean_ok and not allow_dirty:
        for msg in messages:
            print(f"Error: {msg}", file=sys.stderr)
        return 1

    if messages:
        for msg in messages:
            print(f"Warning: {msg}", file=sys.stderr)

    # Capture early state for preflight/dirty comparison. The agent baseline is
    # captured later, after Vibecode writes context/runtime files.
    initial_git_state = None
    try:
        initial_git_state = inspect_git_state(root)
    except Exception as exc:
        print(f"Warning: could not inspect git state for post-run checks: {exc}", file=sys.stderr)

    # ------------------------------------------------------------------
    # 2. Ensure index is fresh (generate / refresh if missing or stale)
    # ------------------------------------------------------------------
    index_path = vibecode_dir / "current" / "last_index.json"
    if not no_index and (not index_path.exists() or (root / ".vibecode" / "project.yaml").exists()):
        # Check if index looks stale: older than 5 minutes or git commit changed.
        stale = False
        if index_path.exists():
            try:
                import json as _json
                record = _json.loads(index_path.read_text(encoding="utf-8"))
                started = record.get("started_at", "")
                if started:
                    from datetime import datetime as _dt, timezone as _tz
                    started_dt = _dt.fromisoformat(started)
                    age = (_dt.now(tz=_tz.utc) - started_dt).total_seconds()
                    if age > 300:  # 5 minutes
                        stale = True
                # Check if the git commit has changed since the index was built.
                if not stale:
                    recorded_commit = record.get("git_commit")
                    if recorded_commit and recorded_commit != "unknown":
                        current_commit = current_git_commit(root)
                        if current_commit != "unknown" and current_commit != recorded_commit:
                            print(
                                f"Index was built for commit {recorded_commit}, "
                                f"but HEAD is now {current_commit} — re-indexing.",
                                file=sys.stderr,
                            )
                            stale = True
            except Exception:
                stale = True

        if not index_path.exists() or stale:
            print("Index is missing or stale — running 'vibecode index' first.", file=sys.stderr)
            rc = cmd_index(type("Args", (), {"repo_root": str(root), "debug": False})())
            if rc != 0:
                print("Error: index generation failed.", file=sys.stderr)
                return 1

    if not index_path.exists():
        print("Error: no index found.  Run 'vibecode index' first.", file=sys.stderr)
        return 1

    # Verify inventory health — fail early if inventory is broken.
    inventory_err = check_inventory_health(root)
    if inventory_err:
        print(f"Error: {inventory_err}", file=sys.stderr)
        return 1

    # ------------------------------------------------------------------
    # 3. Generate context pack + platform prompt
    # ------------------------------------------------------------------
    # Reuse cmd_context which writes context_pack.md and optionally the
    # platform-specific prompt file.
    context_rc = cmd_context(type("Args", (), {
        "context_arg": None,
        "task_option": task,
        "repo": str(root),
        "platform": platform,
        "task": None,
    })())
    if context_rc != 0:
        print("Error: context pack generation failed.", file=sys.stderr)
        return 1

    context_pack_path = vibecode_dir / "current" / "context_pack.md"
    prompt_path = vibecode_dir / "current" / "opencode_prompt.md"

    if not context_pack_path.exists():
        print("Error: context pack was not written.", file=sys.stderr)
        return 1

    # ------------------------------------------------------------------
    # 4. Resolve the platform command
    # ------------------------------------------------------------------
    cfg = None
    try:
        cfg = load_config(vibecode_dir)
    except Exception:
        pass

    command = _get_opencode_command(cfg, os.environ)
    if command is None:
        print(
            "Error: OpenCode command not found. "
            "Install OpenCode or set the OPENCODE_COMMAND environment variable.",
            file=sys.stderr,
        )
        # Write metadata even on command-not-found so callers can inspect it.
        _write_run_metadata(
            vibecode_dir, session_id,
            build_run_plan(root, task=task, platform=platform, profile_name=profile_name, allow_dirty=allow_dirty),
            command=None, exit_code=-1, stdout="", stderr="OpenCode command not found.",
        )
        return 1

    # Verify the command can actually run.
    status = check_opencode(command)
    if not status:
        print(f"Error: OpenCode check failed — {status.message}", file=sys.stderr)
        _write_run_metadata(
            vibecode_dir, session_id,
            build_run_plan(root, task=task, platform=platform, profile_name=profile_name, allow_dirty=allow_dirty),
            command=command, exit_code=-1, stdout="", stderr=status.message,
        )
        return 1

    # ------------------------------------------------------------------
    # 5. Invoke the platform command with the prompt on stdin
    # ------------------------------------------------------------------
    prompt_content = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else context_pack_path.read_text(encoding="utf-8")

    run_plan = build_run_plan(root, task=task, platform=platform, profile_name=profile_name, allow_dirty=allow_dirty)

    if run_plan.preflight_errors:
        for e in run_plan.preflight_errors:
            print(f"Error: [{e.level}] {e.message}", file=sys.stderr)
        _write_run_metadata(
            vibecode_dir, session_id, run_plan,
            command=command, exit_code=-1, stdout="", stderr="Preflight errors detected.",
            error="Preflight errors: " + "; ".join(e.message for e in run_plan.preflight_errors),
        )
        return 1

    try:
        pre_agent_git_state = inspect_git_state(root)
    except Exception as exc:
        pre_agent_git_state = initial_git_state
        print(f"Warning: could not inspect pre-agent git state: {exc}", file=sys.stderr)

    print(f"Running {command} ...", file=sys.stderr)
    print(f"  session:  {session_id}", file=sys.stderr)
    print(f"  task:     {task}", file=sys.stderr)
    print(f"  prompt:   {prompt_path.relative_to(root)}", file=sys.stderr)
    print("", file=sys.stderr)

    try:
        result = subprocess.run(
            command,
            input=prompt_content,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(root),
            shell=True,
        )
        exit_code = result.returncode
        stdout = result.stdout
        stderr = result.stderr
    except subprocess.TimeoutExpired:
        exit_code = -1
        stdout = ""
        stderr = "Command timed out after 300 seconds."
    except OSError as exc:
        exit_code = -1
        stdout = ""
        stderr = f"Failed to execute {command}: {exc}"

    agent_status = "success" if exit_code == 0 else "failure"

    # ------------------------------------------------------------------
    # 6. Show agent results
    # ------------------------------------------------------------------
    if stdout:
        print(stdout, end="")
    if stderr:
        print(stderr, end="", file=sys.stderr)

    if exit_code != 0:
        print(f"\nAgent exited with code {exit_code}.", file=sys.stderr)

    # -------------------------------------------------------------------------
    # 7. Post-run quality checks (guard, required checks, handoff)
    # -------------------------------------------------------------------------
    print("\nRunning post-run checks ...", file=sys.stderr)

    post_run_git_state = None
    try:
        post_run_git_state = inspect_git_state(root)
    except Exception as exc:
        print(f"Warning: could not inspect post-run git state: {exc}", file=sys.stderr)

    agent_git_state = _agent_delta_git_state(pre_agent_git_state, post_run_git_state)

    guard_result, check_result, handoff_result = _run_post_checks(
        root, vibecode_dir, agent_git_state, session_id, task=task,
    )

    # -------------------------------------------------------------------------
    # 7b. Diff summary — compare agent baseline and post-run git state
    # -------------------------------------------------------------------------
    diff_summary = diff_summarise(pre_agent_git_state, post_run_git_state, repo_root=root)

    # -------------------------------------------------------------------------
    # 8. Write session metadata and summary
    # -------------------------------------------------------------------------
    started_at = run_plan.metadata.get("started_at", datetime.now(tz=timezone.utc).isoformat())

    summary = RunSummary(
        session_id=session_id,
        started_at=started_at,
        finished_at=datetime.now(tz=timezone.utc).isoformat(),
        platform=platform,
        profile=profile_name,
        repo_root=str(root),
        task=task,
        dirty=run_plan.dirty,
        index_fresh=run_plan.index_fresh,
        command=command,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        agent_status=agent_status,
        guard=guard_result,
        checks=check_result,
        handoff=handoff_result,
        diff=diff_summary,
    )

    # Write legacy metadata (backward-compatible) and new nested summary.
    _write_run_metadata(
        vibecode_dir, session_id, run_plan,
        command=command, exit_code=exit_code,
        stdout=stdout, stderr=stderr,
    )
    summary_path = _write_run_summary(vibecode_dir, summary)
    print(f"\nRun summary written: {summary_path.relative_to(root)}", file=sys.stderr)

    # -------------------------------------------------------------------------
    # 9. Print concise result
    # -------------------------------------------------------------------------
    overall = summary.overall_status
    print(f"\n{'=' * 50}", file=sys.stderr)
    print(f"  RUN {overall.upper()}", file=sys.stderr)
    print(f"{'=' * 50}", file=sys.stderr)

    if guard_result and not guard_result.passed:
        errors = tuple(f for f in guard_result.findings if f.severity == "error")
        warnings = tuple(f for f in guard_result.findings if f.severity == "warning")
        print(f"  Guard: {len(errors)} error(s), {len(warnings)} warning(s)", file=sys.stderr)
    elif guard_result:
        print("  Guard: passed", file=sys.stderr)

    if check_result:
        print(f"  Checks: {check_result.passed}/{check_result.total} passed"
              f"  ({check_result.failed} failed, {check_result.warnings} warnings)", file=sys.stderr)

    if handoff_result and not handoff_result.passed:
        print(f"  Handoff: {len(handoff_result.issues)} issue(s)", file=sys.stderr)
    elif handoff_result:
        print("  Handoff: passed", file=sys.stderr)

    # Print diff summary
    if diff_summary.changed_files:
        print("", file=sys.stderr)
        print(diff_summary.as_text(), file=sys.stderr)

    print(f"{'=' * 50}\n", file=sys.stderr)

    # ------------------------------------------------------------------
    # 10. Exit code
    # ------------------------------------------------------------------
    if overall == "failure":
        return 1
    if overall == "error":
        return 1
    if overall == "incomplete":
        return 2
    return 0
