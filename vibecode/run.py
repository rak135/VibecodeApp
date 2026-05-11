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

Permission profiles
-------------------
The ``--profile`` flag selects a Vibecode-side advisory profile (``safe``,
``fast``, or ``audit``).  Vibecode validates the profile exists on disk and
records it in run plans and session metadata.  It does **not** pass the
profile to OpenCode or constrain OpenCode tool permissions -- those are
controlled by the user's OpenCode configuration (``opencode.json``, agent
definitions, or the ``OPENCODE_PERMISSION`` environment variable).

Profiles are preflight metadata that Vibecode validates, records, and may
use in future integration surfaces (e.g. translating to OpenCode-compatible
permission objects).

Trust model
-----------
The platform command (resolved from the ``OPENCODE_COMMAND`` environment
variable, or the default ``opencode`` binary name) is a **trusted local
shell command** configured by the user.  It runs through the system shell
(``shell=True``) because on Windows ``.cmd`` and ``.bat`` wrappers require
shell execution, and user-configured commands may include compound syntax
(e.g. ``python path/to/opencode.py``).

If this trust assumption is not acceptable for your environment, restrict
``OPENCODE_COMMAND`` to a simple binary path (no spaces or shell
metacharacters) and run ``vibecode`` in a sandboxed or containerised
context.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vibecode.adapters.opencode import check_opencode, resolve_opencode_command
from vibecode.check import CheckRun, run_checks, write_check_results
from vibecode.config import load_config
from vibecode.context import cmd_context
from vibecode.diff_summary import DiffSummary, diff_summarise
from vibecode.events import (
    EventLevel,
    EventSink,
    MultiEventSink,
    NullEventSink,
    create_event,
    EVENT_AGENT_PROCESS,
    EVENT_CHECK,
    EVENT_CONTEXT,
    EVENT_GIT_PREFLIGHT,
    EVENT_GUARD,
    EVENT_GUARD_FINDING,
    EVENT_HANDOFF,
    EVENT_INDEX_CHECK,
    EVENT_PROMPT,
    EVENT_RUN_LIFECYCLE,
    EVENT_SUMMARY,
)
from vibecode.guard import GuardFinding, GuardResult, _load_test_map, evaluate_project_guard, write_guard_result, write_guard_report_md
from vibecode.git_state import GitState, current_git_commit, inspect_git_state
from vibecode.handoff import HandoffResult, validate_handoff_files
from vibecode.indexer import check_inventory_health, cmd_index, compute_current_file_set_fingerprint
from vibecode.permissions import PROFILES, profile_path
from vibecode.process_runner import run_streaming
from vibecode.run_plan import build_run_plan, _classify_dirty_paths
from vibecode.session_log import RunSession


def _get_opencode_command(config: Any | None, env: dict[str, str]) -> str | None:
    """Resolve the OpenCode command from config or environment."""
    return resolve_opencode_command(env)


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
    # Guard enforcement mode: "advisory" (default) or "strict".
    # In advisory mode, guard findings are reported but never cause run failure.
    # In strict mode, guard errors cause overall_status "failure".
    guard_mode: str = "advisory"

    @property
    def overall_status(self) -> str:
        """Overall run status: 'success', 'needs_review', 'failure', 'incomplete', or 'error'."""
        if self.agent_status == "error" or self.error:
            return "error"
        # In strict mode, guard errors block the run (hard-fail).
        if self.guard_mode == "strict" and self.guard and not self.guard.passed:
            return "failure"
        if self.checks and self.checks.has_required_failures:
            return "failure"
        if self.handoff and not self.handoff.passed:
            return "incomplete"
        if self.agent_status != "success":
            return "failure"
        # In advisory mode (default), guard errors surface as 'needs_review' only —
        # they are fully reported with preserved severity but do not block the run.
        if self.guard and not self.guard.passed:
            return "needs_review"
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
            "guard_mode": self.guard_mode,
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
    session_dir: Path,
    session_id: str,
    plan: Any,
    command: str | None,
    exit_code: int | None,
    stdout: str,
    stderr: str,
    error: str | None = None,
) -> Path:
    """Write a JSON run record under .vibecode/runs/<session_id>/metadata.json."""
    session_dir.mkdir(parents=True, exist_ok=True)

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

    out_path = session_dir / "metadata.json"
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
        _setup_paths, source_paths = _classify_dirty_paths(git_state.changed_paths)
        if allow_dirty:
            if not source_paths:
                messages.append(
                    f"Vibecode onboarding baseline is pending — {dirty_count} setup file(s). "
                    "Review and commit/stash the Vibecode baseline before running an external agent."
                )
            else:
                messages.append(
                    f"Git working tree is dirty — {dirty_count} changed file(s). "
                    "Consider committing or stashing."
                )
            return True, messages
        if not source_paths:
            messages.append(
                f"Vibecode onboarding baseline is pending — {dirty_count} setup file(s): "
                + ", ".join(git_state.changed_paths[:8])
                + (" ..." if dirty_count > 8 else "")
                + "\nReview and commit/stash the Vibecode baseline before running an external agent, "
                "or pass --allow-dirty only when deliberately running on an uncommitted baseline."
            )
            return False, messages
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


def _exit_code_for_status(overall: str) -> int:
    if overall in ("failure", "error"):
        return 1
    if overall == "incomplete":
        return 2
    return 0


class RunController:
    """Orchestrates a vibecode run session with structured event emissions.

    Parameters
    ----------
    root:
        Absolute path to the repository root.
    task:
        Task description for the context pack.
    platform:
        Target platform (e.g. ``"opencode"``).
    profile_name:
        Advisory permission profile name.
    allow_dirty:
        Allow running on a dirty git working tree (warn only).
    no_index:
        Skip automatic index generation / refresh.
    guard_mode:
        Guard enforcement mode. ``"advisory"`` (default): guard findings are
        reported with full severity but do not block the run — the overall
        status becomes ``"needs_review"`` instead of ``"failure"``.
        ``"strict"``: guard errors cause ``"failure"`` and a non-zero exit.
    sink:
        Event sink; defaults to :class:`~vibecode.events.NullEventSink` when
        ``None``.
    session_id:
        Override the session identifier (useful for tests).
    """

    def __init__(
        self,
        root: Path,
        task: str,
        platform: str,
        profile_name: str,
        allow_dirty: bool,
        no_index: bool,
        guard_mode: str = "advisory",
        sink: "EventSink | None" = None,
        session_id: str | None = None,
    ) -> None:
        self.root = root
        self.task = task
        self.platform = platform
        self.profile_name = profile_name
        self.allow_dirty = allow_dirty
        self.no_index = no_index
        if guard_mode not in ("advisory", "strict"):
            raise ValueError(f"guard_mode must be 'advisory' or 'strict', got {guard_mode!r}")
        self.guard_mode = guard_mode
        self.sink: EventSink = sink if sink is not None else NullEventSink()
        self.session_id = session_id or datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _emit(
        self,
        type_: str,
        level: EventLevel,
        message: str,
        *,
        data: dict[str, Any] | None = None,
    ) -> None:
        event = create_event(self.session_id, type_, level, message, data=data)
        self.sink.emit(event)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(self) -> tuple["RunSummary | None", int]:
        """Execute the run session.

        Returns
        -------
        tuple[RunSummary | None, int]
            The run summary (or ``None`` on early abort) and the process exit
            code (0 = success, 1 = failure/error, 2 = incomplete).
        """
        root = self.root
        vibecode_dir = root / ".vibecode"
        session = RunSession(root, self.session_id)
        jsonl_sink = session.create_event_sink()
        sinks: list[EventSink] = [jsonl_sink]
        if not isinstance(self.sink, NullEventSink):
            sinks.append(self.sink)
        self.sink = MultiEventSink(sinks)

        self._emit(
            EVENT_RUN_LIFECYCLE, EventLevel.INFO, "Run started",
            data={"phase": "started", "task": self.task, "platform": self.platform,
                  "profile": self.profile_name},
        )

        # ---- Prerequisites ----
        if not (vibecode_dir / "project.yaml").exists():
            print("Error: no .vibecode/project.yaml found. Run 'vibecode init' first.", file=sys.stderr)
            self._emit(EVENT_RUN_LIFECYCLE, EventLevel.ERROR, "Run aborted: no project.yaml",
                       data={"phase": "finished", "status": "error", "error": "no_project_yaml"})
            return None, 1

        profile_ok, profile_error = _validate_permission_profile(root, self.profile_name)
        if not profile_ok:
            print(f"Error: {profile_error}", file=sys.stderr)
            self._emit(EVENT_RUN_LIFECYCLE, EventLevel.ERROR, f"Run aborted: {profile_error}",
                       data={"phase": "finished", "status": "error", "error": "invalid_profile"})
            return None, 1

        # ----------------------------------------------------------------
        # 1. Git preflight
        # ----------------------------------------------------------------
        self._emit(EVENT_GIT_PREFLIGHT, EventLevel.INFO, "Git preflight started",
                   data={"phase": "started"})
        clean_ok, messages = _run_git_check(root, self.allow_dirty)
        if not clean_ok and not self.allow_dirty:
            for msg in messages:
                print(f"Error: {msg}", file=sys.stderr)
                self._emit(EVENT_GIT_PREFLIGHT, EventLevel.ERROR, msg,
                           data={"phase": "warning", "blocking": True})
            self._emit(EVENT_GIT_PREFLIGHT, EventLevel.ERROR, "Git preflight failed",
                       data={"phase": "completed", "passed": False})
            self._emit(EVENT_RUN_LIFECYCLE, EventLevel.ERROR, "Run aborted: git preflight failed",
                       data={"phase": "finished", "status": "error"})
            return None, 1

        for msg in messages:
            print(f"Warning: {msg}", file=sys.stderr)
            self._emit(EVENT_GIT_PREFLIGHT, EventLevel.WARNING, msg,
                       data={"phase": "warning", "blocking": False})
        self._emit(EVENT_GIT_PREFLIGHT, EventLevel.INFO, "Git preflight completed",
                   data={"phase": "completed", "passed": True, "dirty": bool(messages)})

        initial_git_state = None
        try:
            initial_git_state = inspect_git_state(root)
        except Exception as exc:
            print(f"Warning: could not inspect git state for post-run checks: {exc}", file=sys.stderr)

        # ----------------------------------------------------------------
        # 2. Index check
        # ----------------------------------------------------------------
        self._emit(EVENT_INDEX_CHECK, EventLevel.INFO, "Index check started",
                   data={"phase": "started"})
        index_path = vibecode_dir / "current" / "last_index.json"
        if not self.no_index and (not index_path.exists() or (vibecode_dir / "project.yaml").exists()):
            stale = False
            if index_path.exists():
                try:
                    record = json.loads(index_path.read_text(encoding="utf-8"))
                    started = record.get("started_at", "")
                    if started:
                        started_dt = datetime.fromisoformat(started)
                        age = (datetime.now(tz=timezone.utc) - started_dt).total_seconds()
                        if age > 300:
                            stale = True
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
                    if not stale:
                        recorded_fingerprint = record.get("file_set_fingerprint")
                        if recorded_fingerprint:
                            include = None
                            exclude = None
                            try:
                                _cfg = load_config(vibecode_dir)
                                include = _cfg.include
                                exclude = _cfg.exclude
                            except Exception:
                                pass
                            current_fingerprint = compute_current_file_set_fingerprint(
                                root, include=include, exclude=exclude
                            )
                            if current_fingerprint is not None and current_fingerprint != recorded_fingerprint:
                                print(
                                    "Indexed file set has changed since the last index "
                                    "-- running 'vibecode index' to refresh.",
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
                    self._emit(EVENT_INDEX_CHECK, EventLevel.ERROR, "Index generation failed",
                               data={"phase": "completed", "fresh": False})
                    self._emit(EVENT_RUN_LIFECYCLE, EventLevel.ERROR,
                               "Run aborted: index generation failed",
                               data={"phase": "finished", "status": "error"})
                    return None, 1

        if not index_path.exists():
            print("Error: no index found.  Run 'vibecode index' first.", file=sys.stderr)
            self._emit(EVENT_INDEX_CHECK, EventLevel.ERROR, "No index found",
                       data={"phase": "completed", "fresh": False})
            self._emit(EVENT_RUN_LIFECYCLE, EventLevel.ERROR, "Run aborted: no index",
                       data={"phase": "finished", "status": "error"})
            return None, 1

        inventory_err = check_inventory_health(root)
        if inventory_err:
            print(f"Error: {inventory_err}", file=sys.stderr)
            self._emit(EVENT_INDEX_CHECK, EventLevel.ERROR,
                       f"Inventory health check failed: {inventory_err}",
                       data={"phase": "completed", "fresh": False})
            self._emit(EVENT_RUN_LIFECYCLE, EventLevel.ERROR, "Run aborted: inventory error",
                       data={"phase": "finished", "status": "error"})
            return None, 1

        self._emit(EVENT_INDEX_CHECK, EventLevel.INFO, "Index check completed",
                   data={"phase": "completed", "fresh": True})

        # ----------------------------------------------------------------
        # 3. Context pack + prompt
        # ----------------------------------------------------------------
        self._emit(EVENT_CONTEXT, EventLevel.INFO, "Context pack generation started",
                   data={"phase": "started"})
        context_rc = cmd_context(type("Args", (), {
            "context_arg": None,
            "task_option": self.task,
            "repo": str(root),
            "platform": self.platform,
            "task": None,
        })())
        if context_rc != 0:
            print("Error: context pack generation failed.", file=sys.stderr)
            self._emit(EVENT_CONTEXT, EventLevel.ERROR, "Context pack generation failed",
                       data={"phase": "written", "success": False})
            self._emit(EVENT_RUN_LIFECYCLE, EventLevel.ERROR,
                       "Run aborted: context pack failed",
                       data={"phase": "finished", "status": "error"})
            return None, 1

        context_pack_path = vibecode_dir / "current" / "context_pack.md"
        prompt_path = vibecode_dir / "current" / "opencode_prompt.md"

        if not context_pack_path.exists():
            print("Error: context pack was not written.", file=sys.stderr)
            self._emit(EVENT_CONTEXT, EventLevel.ERROR, "Context pack file not found",
                       data={"phase": "written", "success": False})
            self._emit(EVENT_RUN_LIFECYCLE, EventLevel.ERROR,
                       "Run aborted: context pack not found",
                       data={"phase": "finished", "status": "error"})
            return None, 1

        self._emit(EVENT_CONTEXT, EventLevel.INFO, "Context pack written",
                   data={"phase": "written", "success": True, "path": str(context_pack_path)})

        session.snapshot_prompt()
        session.snapshot_context_pack()

        self._emit(EVENT_PROMPT, EventLevel.INFO, "Prompt written",
                   data={"phase": "written", "path": str(prompt_path)})

        # ----------------------------------------------------------------
        # 4. Resolve platform command
        # ----------------------------------------------------------------
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
            _write_run_metadata(
                session.run_dir, self.session_id,
                build_run_plan(root, task=self.task, platform=self.platform,
                               profile_name=self.profile_name, allow_dirty=self.allow_dirty),
                command=None, exit_code=-1, stdout="", stderr="OpenCode command not found.",
            )
            self._emit(EVENT_AGENT_PROCESS, EventLevel.ERROR, "Agent command not found",
                       data={"phase": "preflight_failed", "error": "command_not_found",
                             "status": "error"})
            self._emit(EVENT_RUN_LIFECYCLE, EventLevel.ERROR,
                       "Run aborted: agent command not found",
                       data={"phase": "finished", "status": "error"})
            return None, 1

        status = check_opencode(command)
        if not status:
            print(f"Error: OpenCode check failed — {status.message}", file=sys.stderr)
            _write_run_metadata(
                session.run_dir, self.session_id,
                build_run_plan(root, task=self.task, platform=self.platform,
                               profile_name=self.profile_name, allow_dirty=self.allow_dirty),
                command=command, exit_code=-1, stdout="", stderr=status.message,
            )
            self._emit(EVENT_AGENT_PROCESS, EventLevel.ERROR,
                       f"Agent check failed: {status.message}",
                       data={"phase": "preflight_failed", "error": "check_failed",
                             "status": "error"})
            self._emit(EVENT_RUN_LIFECYCLE, EventLevel.ERROR,
                       "Run aborted: agent check failed",
                       data={"phase": "finished", "status": "error"})
            return None, 1

        # ----------------------------------------------------------------
        # 5. Invoke platform agent
        # ----------------------------------------------------------------
        prompt_content = (
            prompt_path.read_text(encoding="utf-8")
            if prompt_path.exists()
            else context_pack_path.read_text(encoding="utf-8")
        )
        run_plan = build_run_plan(
            root, task=self.task, platform=self.platform,
            profile_name=self.profile_name, allow_dirty=self.allow_dirty,
        )

        if run_plan.preflight_errors:
            for e in run_plan.preflight_errors:
                print(f"Error: [{e.level}] {e.message}", file=sys.stderr)
            _write_run_metadata(
                session.run_dir, self.session_id, run_plan,
                command=command, exit_code=-1, stdout="", stderr="Preflight errors detected.",
                error="Preflight errors: " + "; ".join(e.message for e in run_plan.preflight_errors),
            )
            self._emit(EVENT_RUN_LIFECYCLE, EventLevel.ERROR, "Run aborted: preflight errors",
                       data={"phase": "finished", "status": "error"})
            return None, 1

        try:
            pre_agent_git_state = inspect_git_state(root)
        except Exception as exc:
            pre_agent_git_state = initial_git_state
            print(f"Warning: could not inspect pre-agent git state: {exc}", file=sys.stderr)

        print(f"Running {command} ...", file=sys.stderr)
        print(f"  session:  {self.session_id}", file=sys.stderr)
        print(f"  task:     {self.task}", file=sys.stderr)
        print(f"  prompt:   {prompt_path.relative_to(root)}", file=sys.stderr)
        print("", file=sys.stderr)

        self._emit(EVENT_AGENT_PROCESS, EventLevel.INFO, f"Agent started: {command}",
                   data={"phase": "started", "command": command, "session_id": self.session_id})

        try:
            # shell=True: the command is a trusted local executable configured
            # by the user via OPENCODE_COMMAND (or the default 'opencode').
            # Windows .cmd/.bat wrappers and compound commands require shell
            # execution.  See the module-level trust-model documentation.
            # run_streaming uses Popen + two reader threads so that stdout and
            # stderr are drained concurrently (deadlock-safe on Windows) and
            # live EVENT_AGENT_PROCESS events are emitted for each line.
            proc_result = run_streaming(
                command,
                stdin_content=prompt_content,
                session_id=self.session_id,
                cwd=root,
                sink=self.sink,
                stdout_log=session.agent_stdout_log,
                stderr_log=session.agent_stderr_log,
                timeout=300.0,
            )
            exit_code = proc_result.exit_code
            stdout = proc_result.stdout
            stderr = proc_result.stderr
        except OSError as exc:
            exit_code = -1
            stdout = ""
            stderr = f"Failed to execute {command}: {exc}"
            session.ensure_dir()
            session.agent_stdout_log.write_text("", encoding="utf-8")
            session.agent_stderr_log.write_text(stderr, encoding="utf-8")

        agent_status = "success" if exit_code == 0 else "failure"
        agent_level = EventLevel.INFO if exit_code == 0 else EventLevel.ERROR
        self._emit(EVENT_AGENT_PROCESS, agent_level, f"Agent finished (exit_code={exit_code})",
                   data={"phase": "finished", "exit_code": exit_code, "status": agent_status})

        if stdout:
            print(stdout, end="")
        if stderr:
            print(stderr, end="", file=sys.stderr)
        if exit_code != 0:
            print(f"\nAgent exited with code {exit_code}.", file=sys.stderr)

        # ----------------------------------------------------------------
        # 6. Post-run quality checks
        # ----------------------------------------------------------------
        print("\nRunning post-run checks ...", file=sys.stderr)

        post_run_git_state = None
        try:
            post_run_git_state = inspect_git_state(root)
        except Exception as exc:
            print(f"Warning: could not inspect post-run git state: {exc}", file=sys.stderr)

        agent_git_state = _agent_delta_git_state(pre_agent_git_state, post_run_git_state)

        # Guard
        guard_result: GuardResult | None = None
        guard_error: str | None = None
        self._emit(EVENT_GUARD, EventLevel.INFO, "Guard started", data={"phase": "started"})
        try:
            if agent_git_state and agent_git_state.is_git_repo:
                test_map = _load_test_map(vibecode_dir)
                guard_result = evaluate_project_guard(
                    agent_git_state, vibecode_dir, task=self.task, test_map=test_map
                )
                try:
                    write_guard_result(guard_result, vibecode_dir, root)
                except Exception:
                    pass
            else:
                print("Warning: skipped guard (not a git repository).", file=sys.stderr)
        except Exception as exc:
            guard_error = str(exc)
            print(f"Warning: guard check failed with error: {exc}", file=sys.stderr)

        if guard_result is None and guard_error:
            self._emit(
                EVENT_GUARD, EventLevel.ERROR, f"Guard failed: {guard_error}",
                data={"phase": "completed", "passed": False, "status": "error",
                      "error": guard_error},
            )
            guard_result = GuardResult(findings=(
                GuardFinding(
                    rule_id="guard-evaluation-error",
                    path=".",
                    severity="error",
                    message=f"Guard evaluation failed: {guard_error}",
                    category="guard",
                    title="Guard evaluation error",
                    why_it_matters=(
                        "The guard check could not complete. "
                        "Repository changes may not have been validated."
                    ),
                    evidence=guard_error,
                    recommended_fix=(
                        "Check the error message, fix the underlying issue, "
                        "and re-run guard."
                    ),
                ),
            ))
            try:
                write_guard_result(guard_result, vibecode_dir, root)
            except Exception:
                pass

        if guard_result is None:
            self._emit(
                EVENT_GUARD, EventLevel.INFO, "Guard skipped (not a git repository)",
                data={"phase": "completed", "passed": True, "findings": 0},
            )
        else:
            # Emit one event per finding for the monitor panel.
            for finding in guard_result.findings:
                self._emit(
                    EVENT_GUARD_FINDING,
                    EventLevel.ERROR if finding.severity == "error" else EventLevel.WARNING,
                    finding.title or finding.message,
                    data={
                        "rule_id": finding.rule_id,
                        "severity": finding.severity,
                        "category": finding.resolved_category,
                        "path": finding.path,
                        "title": finding.title or finding.message,
                        "message": finding.message,
                        "why_it_matters": finding.why_it_matters,
                        "recommended_fix": finding.recommended_fix,
                        "evidence": finding.evidence,
                        "required_tests": list(finding.required_tests),
                    },
                )

            guard_passed = guard_result.passed
            self._emit(
                EVENT_GUARD,
                EventLevel.INFO if guard_passed else EventLevel.WARNING,
                "Guard completed",
                data={
                    "phase": "completed",
                    "passed": guard_passed,
                    "findings": len(guard_result.findings),
                    "errors": sum(1 for f in guard_result.findings if f.severity == "error"),
                    "warnings": sum(1 for f in guard_result.findings if f.severity == "warning"),
                    "counts_by_severity": guard_result.counts_by_severity(),
                    "counts_by_category": guard_result.counts_by_category(),
                },
            )

        # Required checks
        check_result: CheckRun | None = None
        check_error: str | None = None
        self._emit(EVENT_CHECK, EventLevel.INFO, "Checks started", data={"phase": "started"})
        try:
            check_result = run_checks(root)
            write_check_results(check_result, vibecode_dir)
        except Exception as exc:
            check_error = str(exc)
            print(f"Warning: required checks failed with error: {exc}", file=sys.stderr)

        if check_result is None and check_error:
            self._emit(
                EVENT_CHECK, EventLevel.ERROR, f"Checks failed: {check_error}",
                data={"phase": "completed", "passed": False, "status": "error",
                      "error": check_error},
            )
        elif check_result is None:
            self._emit(
                EVENT_CHECK, EventLevel.INFO, "Checks completed",
                data={"phase": "completed", "passed": True, "total": 0, "failed": 0},
            )
        else:
            checks_passed = not check_result.has_required_failures
            self._emit(
                EVENT_CHECK,
                EventLevel.INFO if checks_passed else EventLevel.WARNING,
                "Checks completed",
                data={"phase": "completed", "passed": checks_passed,
                      "total": check_result.total,
                      "failed": check_result.failed},
            )

        # Handoff
        handoff_result: HandoffResult | None = None
        handoff_error: str | None = None
        self._emit(EVENT_HANDOFF, EventLevel.INFO, "Handoff started", data={"phase": "started"})
        try:
            if agent_git_state and agent_git_state.is_git_repo:
                diff_paths = agent_git_state.diff_name_only + agent_git_state.untracked_paths
                handoff_result = validate_handoff_files(root, diff=diff_paths)
            else:
                print("Warning: skipped handoff-check (not a git repository).", file=sys.stderr)
        except Exception as exc:
            handoff_error = str(exc)
            print(f"Warning: handoff-check failed with error: {exc}", file=sys.stderr)

        if handoff_result is None and handoff_error:
            self._emit(
                EVENT_HANDOFF, EventLevel.ERROR, f"Handoff failed: {handoff_error}",
                data={"phase": "completed", "passed": False, "status": "error",
                      "error": handoff_error},
            )
        elif handoff_result is None:
            self._emit(
                EVENT_HANDOFF, EventLevel.INFO, "Handoff skipped (not a git repository)",
                data={"phase": "completed", "passed": True, "issues": 0},
            )
        else:
            handoff_passed = handoff_result.passed
            self._emit(
                EVENT_HANDOFF,
                EventLevel.INFO if handoff_passed else EventLevel.WARNING,
                "Handoff completed",
                data={"phase": "completed", "passed": handoff_passed,
                      "issues": len(handoff_result.issues)},
            )

        # Persist per-session reports
        session.ensure_dir()
        if guard_result:
            session.guard_report_json.write_text(
                json.dumps(guard_result.as_dict(root=root), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            try:
                write_guard_report_md(
                    guard_result,
                    session.guard_report_md,
                    session_id=self.session_id,
                    root=root,
                )
            except Exception:
                pass
        if check_result:
            session.checks_report_json.write_text(
                json.dumps(check_result.as_dict(), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        if handoff_result:
            session.handoff_report_json.write_text(
                json.dumps(handoff_result.as_dict(), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

        # ---- Diff summary ----
        diff_summary = diff_summarise(pre_agent_git_state, post_run_git_state, repo_root=root)

        # ----------------------------------------------------------------
        # 7. Write session metadata and summary
        # ----------------------------------------------------------------
        started_at = run_plan.metadata.get("started_at", datetime.now(tz=timezone.utc).isoformat())

        summary = RunSummary(
            session_id=self.session_id,
            started_at=started_at,
            finished_at=datetime.now(tz=timezone.utc).isoformat(),
            platform=self.platform,
            profile=self.profile_name,
            repo_root=str(root),
            task=self.task,
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
            guard_mode=self.guard_mode,
        )

        _write_run_metadata(
            session.run_dir, self.session_id, run_plan,
            command=command, exit_code=exit_code,
            stdout=stdout, stderr=stderr,
        )
        summary_path = _write_run_summary(vibecode_dir, summary)
        print(f"\nRun summary written: {summary_path.relative_to(root)}", file=sys.stderr)

        self._emit(EVENT_SUMMARY, EventLevel.INFO, "Run summary written",
                   data={"phase": "written", "path": str(summary_path),
                         "status": summary.overall_status})

        # ----------------------------------------------------------------
        # 8. Print concise result
        # ----------------------------------------------------------------
        overall = summary.overall_status
        print(f"\n{'=' * 50}", file=sys.stderr)
        print(f"  RUN {overall.upper()}", file=sys.stderr)
        print(f"{'=' * 50}", file=sys.stderr)

        if guard_result and not guard_result.passed:
            errors = tuple(f for f in guard_result.findings if f.severity == "error")
            warnings = tuple(f for f in guard_result.findings if f.severity == "warning")
            print(f"  Guard: {len(errors)} error(s), {len(warnings)} warning(s)", file=sys.stderr)
            if self.guard_mode == "advisory":
                print(
                    "  Note: guard mode is advisory — findings logged but run not blocked.",
                    file=sys.stderr,
                )
        elif guard_result:
            print("  Guard: passed", file=sys.stderr)

        if check_result:
            print(
                f"  Checks: {check_result.passed}/{check_result.total} passed"
                f"  ({check_result.failed} failed, {check_result.warnings} warnings)",
                file=sys.stderr,
            )

        if handoff_result and not handoff_result.passed:
            print(f"  Handoff: {len(handoff_result.issues)} issue(s)", file=sys.stderr)
        elif handoff_result:
            print("  Handoff: passed", file=sys.stderr)

        if diff_summary.changed_files:
            print("", file=sys.stderr)
            print(diff_summary.as_text(), file=sys.stderr)

        print(f"{'=' * 50}\n", file=sys.stderr)

        # ---- RunFinished ----
        finish_level = (
            EventLevel.INFO if overall in ("success", "needs_review")
            else EventLevel.ERROR if overall == "error"
            else EventLevel.WARNING
        )
        self._emit(EVENT_RUN_LIFECYCLE, finish_level, f"Run finished: {overall}",
                   data={"phase": "finished", "status": overall})

        return summary, _exit_code_for_status(overall)


def cmd_run(args) -> int:
    """CLI entry point for ``vibecode run``."""
    repo_arg = getattr(args, "repo_root", None)
    task = getattr(args, "task", None) or ""
    platform = getattr(args, "platform", "opencode")
    profile = getattr(args, "profile", None)
    profile_name = profile or "safe"
    allow_dirty = getattr(args, "allow_dirty", False)
    no_index = getattr(args, "no_index", False)
    guard_mode = getattr(args, "guard_mode", "advisory")

    if not repo_arg:
        print("Error: repo root is required.", file=sys.stderr)
        return 1

    root: Path = repo_arg
    controller = RunController(
        root=root,
        task=task,
        platform=platform,
        profile_name=profile_name,
        allow_dirty=allow_dirty,
        no_index=no_index,
        guard_mode=guard_mode,
    )
    _, exit_code = controller.execute()
    return exit_code
