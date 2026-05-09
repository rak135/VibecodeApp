"""Run-plan assembly for vibecode.

Builds a structured plan for an OpenCode (or other platform) run without
actually launching an agent.  This lets the user inspect the plan, confirm
preflight checks, and decide whether to proceed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vibecode.config import load_config
from vibecode.git_state import GitState, inspect_git_state


@dataclass(frozen=True)
class RunPlanWarning:
    """A preflight warning or hard failure in the run plan."""

    level: str  # "warn" or "error"
    message: str


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
    preflight_warnings: tuple[RunPlanWarning, ...]
    preflight_errors: tuple[RunPlanWarning, ...]
    commands: tuple[str, ...]
    # Additional metadata for downstream consumers
    metadata: dict[str, Any] = field(default_factory=dict)


def build_run_plan(
    repo_root: Path,
    task: str,
    platform: str = "opencode",
    profile_name: str | None = None,
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
                warnings.append(RunPlanWarning(
                    "warn",
                    f"Git working tree is dirty — {count} changed file(s): "
                    + ", ".join(dirty_paths[:8])
                    + (" ..." if count > 8 else ""),
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

    # --- 4. Context pack path -----------------------------------------------
    context_pack_path: str | None = None
    opencode_prompt_path: str | None = None

    if index_fresh or index_path.exists():
        context_pack_path = str(vibecode_dir / "current" / "context_pack.md")
        if platform == "opencode":
            opencode_prompt_path = str(
                vibecode_dir / "current" / "opencode_prompt.md"
            )

    # --- 5. Permission profile ----------------------------------------------
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

    # --- 6. Assemble commands that would be run ----------------------------
    commands: list[str] = []
    if dirty:
        commands.append("# Repo is dirty — commit or stash changes first for a clean run.")
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

    if not repo_arg:
        print("Error: repo root is required.", file=__import__("sys").stderr)
        return 1

    root = Path(repo_arg).resolve()
    plan = build_run_plan(root, task=task, platform=platform, profile_name=profile)

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