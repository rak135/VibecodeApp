"""Run-plan assembly for vibecode.

Builds a structured plan for an OpenCode (or other platform) run without
actually launching an agent.  This lets the user inspect the plan, confirm
preflight checks, and decide whether to proceed.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vibecode.adapters.opencode import check_opencode
from vibecode.config import load_config
from vibecode.git_state import GitState, current_git_commit, inspect_git_state
from vibecode.indexer import check_inventory_health, compute_current_file_set_fingerprint


@dataclass(frozen=True)
class RunPlanWarning:
    """A preflight warning or hard failure in the run plan."""

    level: str  # "warn" or "error"
    message: str


# Critical generated/runtime paths that must be git-ignored for safe operation.
# Each entry is a (display_name, test_path) pair for git check-ignore verification.
_CRITICAL_IGNORE_CHECKS: tuple[tuple[str, str], ...] = (
    (".vibecode/current/", ".vibecode/current/ignore_check_file"),
    (".vibecode/generated/", ".vibecode/generated/ignore_check_file"),
    (".vibecode/runs/", ".vibecode/runs/ignore_check_file"),
    (".vibecode/logs/", ".vibecode/logs/ignore_check_file"),
    (".vibecode/tmp/", ".vibecode/tmp/ignore_check_file"),
    (".vibecode/cache/", ".vibecode/cache/ignore_check_file"),
    (".vibecode/index/*.generated.*", ".vibecode/index/check.generated.md"),
)


def _git_check_ignored(root: Path, test_path: str) -> bool:
    """Return True if *test_path* would be ignored by git's exclude rules."""
    try:
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", test_path],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _git_is_tracked(root: Path, test_path: str) -> bool:
    """Return True if *test_path* is tracked in the git index."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", test_path],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _verify_gitignore_policy(
    root: Path, git_state: GitState | None
) -> list[RunPlanWarning]:
    """Verify critical generated/runtime paths are git-ignored and not tracked.

    Returns a list of ``RunPlanWarning`` errors for any unsafe paths.
    """
    errors: list[RunPlanWarning] = []

    if git_state is None or not git_state.is_git_repo:
        return errors

    for display_name, test_path in _CRITICAL_IGNORE_CHECKS:
        if _git_is_tracked(root, test_path):
            errors.append(
                RunPlanWarning(
                    "error",
                    f"Critical generated/runtime path '{display_name}' is tracked by git. "
                    "Remove it with 'git rm --cached' and ensure .gitignore covers it.",
                )
            )
            continue

        if not _git_check_ignored(root, test_path):
            errors.append(
                RunPlanWarning(
                    "error",
                    f"Critical generated/runtime path '{display_name}' is not git-ignored. "
                    "Add it to .gitignore.",
                )
            )

    return errors


@dataclass(frozen=True)
class RunPlan:
    """Assembled plan for a pending agent run."""

    repo_root: str
    task: str
    dirty: bool
    dirty_paths: tuple[str, ...]
    index_fresh: bool
    index_age_seconds: float | None
    context_pack_path: str | None
    opencode_prompt_path: str | None
    permission_profile: str | None
    commands: tuple[str, ...]
    opencode_available: bool | None = None
    opencode_message: str | None = None
    preflight_warnings: tuple[RunPlanWarning, ...] = ()
    preflight_errors: tuple[RunPlanWarning, ...] = ()
    # Additional metadata for downstream consumers
    metadata: dict[str, Any] = field(default_factory=dict)


def build_run_plan(
    repo_root: Path,
    task: str,
    platform: str = "opencode",
    profile_name: str | None = None,
    allow_dirty: bool = False,
) -> RunPlan:
    """Assemble a run plan for *repo_root* without launching any agent.

    Parameters
    ----------
    repo_root:
        Repository root directory.
    task:
        Task description for the context pack.
    platform:
        Target platform (e.g. ``"opencode"``).
    profile_name:
        Permission profile name (e.g. ``"safe"``, ``"fast"``, ``"audit"``).
        If ``None``, ``"safe"`` is assumed.
    allow_dirty:
        If ``True``, dirty working tree is allowed (warning only).
        If ``False``, a dirty working tree produces a hard error.

    Returns
    -------
    RunPlan
        A frozen plan object with preflight results.
    """
    root = repo_root.resolve()
    warnings: list[RunPlanWarning] = []
    errors: list[RunPlanWarning] = []

    # --- 1. Git status ----------------------------------------------------
    git_state: GitState | None = None
    dirty = False
    dirty_paths: tuple[str, ...] = ()

    try:
        git_state = inspect_git_state(root)
        if git_state.is_git_repo:
            dirty = bool(git_state.changed_paths)
            dirty_paths = git_state.changed_paths
            if dirty:
                count = len(dirty_paths)
                if allow_dirty:
                    warnings.append(RunPlanWarning(
                        "warn",
                        f"Git working tree is dirty — {count} changed file(s): "
                        + ", ".join(dirty_paths[:8])
                        + (" ..." if count > 8 else ""),
                    ))
                else:
                    errors.append(RunPlanWarning(
                        "error",
                        f"Git working tree is dirty — {count} changed file(s): "
                        + ", ".join(dirty_paths[:8])
                        + (" ..." if count > 8 else "")
                        + "  Commit or stash changes first, or pass --allow-dirty.",
                    ))
        else:
            warnings.append(RunPlanWarning(
                "warn", "Directory is not a git repository."
            ))
    except FileNotFoundError:
        warnings.append(RunPlanWarning(
            "warn", "Repository root does not exist."
        ))
    except Exception as exc:
        warnings.append(RunPlanWarning(
            "warn", f"Could not inspect git state: {exc}"
        ))

    # --- 2. Project config -------------------------------------------------
    vibecode_dir = root / ".vibecode"
    project_yaml = vibecode_dir / "project.yaml"

    if not project_yaml.exists():
        errors.append(RunPlanWarning(
            "error",
            "No .vibecode/project.yaml found — run 'vibecode init' first.",
        ))
        cfg = None
    else:
        try:
            cfg = load_config(vibecode_dir)
        except Exception as exc:
            errors.append(RunPlanWarning(
                "error", f"Could not load project.yaml: {exc}"
            ))
            cfg = None

    # --- 3. Index freshness ------------------------------------------------
    index_path = vibecode_dir / "current" / "last_index.json"
    index_fresh = False
    index_age_seconds: float | None = None

    if index_path.exists():
        try:
            record = json.loads(index_path.read_text(encoding="utf-8"))
            started_at = record.get("started_at", "")
            if started_at:
                started_dt = datetime.fromisoformat(started_at)
                index_age_seconds = (
                    datetime.now(tz=timezone.utc) - started_dt
                ).total_seconds()

            # Compare root path — if it changed, the index is stale.
            if cfg is not None:
                recorded_root = record.get("root", "")
                if recorded_root and recorded_root != str(root):
                    warnings.append(RunPlanWarning(
                        "warn",
                        "Index was built for a different root path.",
                    ))
                    index_fresh = False
                else:
                    index_fresh = True
            else:
                index_fresh = True  # Can't compare, assume OK.

            # Compare git commit — if HEAD changed since index, the index is stale.
            if index_fresh:
                recorded_commit = record.get("git_commit")
                if recorded_commit and recorded_commit != "unknown":
                    current_commit = current_git_commit(root)
                    if current_commit != "unknown" and current_commit != recorded_commit:
                        warnings.append(RunPlanWarning(
                            "warn",
                            f"Index was built for commit {recorded_commit}, "
                            f"but HEAD is now {current_commit} — run 'vibecode index'.",
                        ))
                        index_fresh = False

            # Compare file-set fingerprint (detects added/removed files
            # even without a new commit).
            if index_fresh:
                recorded_fingerprint = record.get("file_set_fingerprint")
                if recorded_fingerprint:
                    _inc = cfg.include if cfg else None
                    _exc = cfg.exclude if cfg else None
                    current_fingerprint = compute_current_file_set_fingerprint(root, include=_inc, exclude=_exc)
                    if current_fingerprint is not None and current_fingerprint != recorded_fingerprint:
                        warnings.append(RunPlanWarning(
                            "warn",
                            "Indexed file set has changed since the last index "
                            "— run 'vibecode index' to refresh.",
                        ))
                        index_fresh = False

            # If dirty, index may be stale
            if dirty and index_age_seconds is not None and index_age_seconds > 0:
                warnings.append(RunPlanWarning(
                    "warn",
                    f"Index was built {index_age_seconds:.0f}s ago and repo is dirty — "
                    "consider re-running 'vibecode index'.",
                ))
        except (json.JSONDecodeError, KeyError) as exc:
            warnings.append(RunPlanWarning(
                "warn", f"Could not parse last index record: {exc}"
            ))
    else:
        warnings.append(RunPlanWarning(
            "warn",
            "No index found — run 'vibecode index' before running an agent.",
        ))

    # --- 4. Inventory health check ------------------------------------------
    inventory_err = check_inventory_health(root)
    if inventory_err:
        errors.append(RunPlanWarning("error", inventory_err))

    # --- 5. Context pack path -----------------------------------------------
    context_pack_path: str | None = None
    opencode_prompt_path: str | None = None

    if index_fresh or index_path.exists():
        context_pack_path = str(vibecode_dir / "current" / "context_pack.md")
        if platform == "opencode":
            opencode_prompt_path = str(
                vibecode_dir / "current" / "opencode_prompt.md"
            )

    # --- 6. Permission profile ----------------------------------------------
    profile_name = profile_name or "safe"
    profile_file = vibecode_dir / "agents" / f"{profile_name}.json"
    permission_profile: str | None = None

    if profile_file.exists():
        permission_profile = str(profile_file)
    else:
        from vibecode.permissions import PROFILES as _PROFILES

        if profile_name in _PROFILES:
            warnings.append(RunPlanWarning(
                "warn",
                f"Permission profile '{profile_name}' not yet written to disk "
                f"(expected at {profile_file.relative_to(root).as_posix()}).",
            ))
        else:
            errors.append(RunPlanWarning(
                "error",
                f"Unknown permission profile '{profile_name}'.",
            ))

    # --- 6. OpenCode availability check ---------------------------------------
    opencode_available: bool | None = None
    opencode_message: str | None = None

    if platform == "opencode":
        opencode_status = check_opencode()
        opencode_available = bool(opencode_status)
        opencode_message = opencode_status.message
        if not opencode_status:
            errors.append(RunPlanWarning(
                "error",
                f"OpenCode not available: {opencode_status.message}",
            ))

    # --- 7. Gitignore policy check ------------------------------------------
    if git_state and git_state.is_git_repo:
        ignore_errors = _verify_gitignore_policy(root, git_state)
        errors.extend(ignore_errors)

    # --- 8. Assemble commands that would be run ----------------------------
    commands: list[str] = []
    if dirty and not allow_dirty:
        commands.append("# Repo is dirty — commit or stash changes first for a clean run.")
    if not opencode_available and platform == "opencode":
        commands.append("# OpenCode is not available — install it or set OPENCODE_COMMAND.")
    commands.append(f"# Platform: {platform}")
    commands.append(f"# Permission profile: {profile_name}")
    if context_pack_path:
        commands.append(f"# Context pack: {context_pack_path}")
    if opencode_prompt_path:
        commands.append(f"# OpenCode prompt: {opencode_prompt_path}")
    commands.append(f"# Task: {task}")
    commands.append(f"# Run command would be: vibecode run {root.as_posix()} --platform {platform} --task \"{task}\"")

    preflight_warnings = tuple(warnings)
    preflight_errors = tuple(errors)

    return RunPlan(
        repo_root=str(root),
        task=task,
        dirty=dirty,
        dirty_paths=dirty_paths,
        index_fresh=index_fresh,
        index_age_seconds=index_age_seconds,
        context_pack_path=context_pack_path,
        opencode_prompt_path=opencode_prompt_path,
        permission_profile=permission_profile,
        opencode_available=opencode_available,
        opencode_message=opencode_message,
        preflight_warnings=preflight_warnings,
        preflight_errors=preflight_errors,
        commands=tuple(commands),
        metadata={
            "started_at": datetime.now(tz=timezone.utc).isoformat(),
            "platform": platform,
            "profile": profile_name,
        },
    )


def render_run_plan(plan: RunPlan) -> str:
    """Render a human-readable summary of the run plan."""
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("RUN PLAN")
    lines.append("=" * 60)
    lines.append(f"  Repo root:          {plan.repo_root}")
    lines.append(f"  Task:               {plan.task}")
    lines.append(f"  Platform:           {plan.metadata.get('platform', 'unknown')}")
    lines.append(f"  Permission profile: {plan.permission_profile or '(not found)'}")
    lines.append("")

    status = "DIRTY" if plan.dirty else "CLEAN"
    lines.append(f"  Git status:         {status}")
    if plan.dirty_paths:
        for p in plan.dirty_paths[:10]:
            lines.append(f"    - {p}")
        if len(plan.dirty_paths) > 10:
            lines.append(f"    ... and {len(plan.dirty_paths) - 10} more")

    lines.append("")
    idx_status = "FRESH" if plan.index_fresh else "STALE/MISSING"
    lines.append(f"  Index status:       {idx_status}")
    if plan.index_age_seconds is not None:
        lines.append(f"  Index age:          {plan.index_age_seconds:.0f}s")

    lines.append("")
    lines.append(f"  Context pack path:  {plan.context_pack_path or '(not available)'}")
    lines.append(f"  OpenCode prompt:    {plan.opencode_prompt_path or '(not available)'}")

    if plan.opencode_available is False:
        lines.append("  OpenCode status:    NOT AVAILABLE")
        if plan.opencode_message:
            lines.append(f"                    {plan.opencode_message}")

    if plan.preflight_errors:
        lines.append("")
        lines.append("ERRORS:")
        for err in plan.preflight_errors:
            lines.append(f"  [ERROR] {err.message}")

    if plan.preflight_warnings:
        lines.append("")
        lines.append("WARNINGS:")
        for w in plan.preflight_warnings:
            lines.append(f"  [WARN]  {w.message}")

    lines.append("")
    lines.append("COMMANDS:")
    for cmd in plan.commands:
        lines.append(f"  {cmd}")

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines) + "\n"


def cmd_run_plan(args) -> int:
    """CLI entry point for ``vibecode run-plan``."""
    repo_arg = getattr(args, "repo_root", None)
    task = getattr(args, "task", None) or ""
    platform = getattr(args, "platform", "opencode")
    profile = getattr(args, "profile", None)
    allow_dirty = getattr(args, "allow_dirty", False)

    if not repo_arg:
        print("Error: repo root is required.", file=__import__("sys").stderr)
        return 1

    root = Path(repo_arg).resolve()
    plan = build_run_plan(
        root, task=task, platform=platform, profile_name=profile, allow_dirty=allow_dirty,
    )

    output = render_run_plan(plan)
    print(output)

    # Also write machine-readable JSON to .vibecode/current/
    json_path = root / ".vibecode" / "current" / "run_plan.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_data = {
        "$schema": "vibecode/run-plan/v1",
        "repo_root": plan.repo_root,
        "task": plan.task,
        "dirty": plan.dirty,
        "dirty_paths": plan.dirty_paths,
        "index_fresh": plan.index_fresh,
        "index_age_seconds": plan.index_age_seconds,
        "context_pack_path": plan.context_pack_path,
        "opencode_prompt_path": plan.opencode_prompt_path,
        "permission_profile": plan.permission_profile,
        "opencode_available": plan.opencode_available,
        "opencode_message": plan.opencode_message,
        "preflight_warnings": [
            {"level": w.level, "message": w.message} for w in plan.preflight_warnings
        ],
        "preflight_errors": [
            {"level": e.level, "message": e.message} for e in plan.preflight_errors
        ],
        "commands": plan.commands,
        "metadata": plan.metadata,
    }
    json_path.write_text(json.dumps(json_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return 1 if plan.preflight_errors else 0