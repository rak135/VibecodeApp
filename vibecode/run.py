"""Run an OpenCode (or other platform) agent session for a repository.

Flow:
  1. Check git status (abort or warn on dirty tree).
  2. Generate or refresh the index if missing or stale.
  3. Generate the context pack and platform prompt.
  4. Invoke the configured platform command with the prompt on stdin.
  5. Capture stdout / stderr / exit code.
  6. Write session metadata under .vibecode/runs/.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any

from vibecode.adapters.opencode import check_opencode
from vibecode.config import load_config
from vibecode.context import cmd_context
from vibecode.git_state import inspect_git_state
from vibecode.indexer import cmd_index
from vibecode.run_plan import build_run_plan, render_run_plan


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


def cmd_run(args) -> int:
    """CLI entry point for ``vibecode run``."""
    repo_arg = getattr(args, "repo_root", None)
    task = getattr(args, "task", None) or ""
    platform = getattr(args, "platform", "opencode")
    profile = getattr(args, "profile", None)
    allow_dirty = getattr(args, "allow_dirty", False)
    no_index = getattr(args, "no_index", False)

    if not repo_arg:
        print("Error: repo root is required.", file=sys.stderr)
        return 1

    # repo_arg is already a resolved Path (normalised by the CLI dispatcher).
    root: Path = repo_arg
    vibecode_dir = root / ".vibecode"
    session_id = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")

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

    # ------------------------------------------------------------------
    # 2. Ensure index is fresh (generate / refresh if missing or stale)
    # ------------------------------------------------------------------
    index_path = vibecode_dir / "current" / "last_index.json"
    if not no_index and (not index_path.exists() or (root / ".vibecode" / "project.yaml").exists()):
        # Check if index looks stale: older than 5 minutes.
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
            build_run_plan(root, task=task, platform=platform, profile_name=profile, allow_dirty=allow_dirty),
            command=None, exit_code=-1, stdout="", stderr="OpenCode command not found.",
        )
        return 1

    # Verify the command can actually run.
    status = check_opencode(command)
    if not status:
        print(f"Error: OpenCode check failed — {status.message}", file=sys.stderr)
        _write_run_metadata(
            vibecode_dir, session_id,
            build_run_plan(root, task=task, platform=platform, profile_name=profile, allow_dirty=allow_dirty),
            command=command, exit_code=-1, stdout="", stderr=status.message,
        )
        return 1

    # ------------------------------------------------------------------
    # 5. Invoke the platform command with the prompt on stdin
    # ------------------------------------------------------------------
    prompt_content = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else context_pack_path.read_text(encoding="utf-8")

    run_plan = build_run_plan(root, task=task, platform=platform, profile_name=profile, allow_dirty=allow_dirty)

    print(f"Running {command} ...", file=sys.stderr)
    print(f"  session:  {session_id}", file=sys.stderr)
    print(f"  task:     {task}", file=sys.stderr)
    print(f"  prompt:   {prompt_path.relative_to(root)}", file=sys.stderr)
    print("", file=sys.stderr)

    try:
        result = subprocess.run(
            [command],
            input=prompt_content,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(root),
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

    # ------------------------------------------------------------------
    # 6. Show results
    # ------------------------------------------------------------------
    if stdout:
        print(stdout, end="")
    if stderr:
        print(stderr, end="", file=sys.stderr)

    # ------------------------------------------------------------------
    # 7. Write session metadata
    # ------------------------------------------------------------------
    metadata_path = _write_run_metadata(
        vibecode_dir, session_id, run_plan,
        command=command, exit_code=exit_code,
        stdout=stdout, stderr=stderr,
    )
    print(f"\nSession metadata written: {metadata_path.relative_to(root)}", file=sys.stderr)

    return 1 if exit_code != 0 else 0