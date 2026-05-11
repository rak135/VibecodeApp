"""Inspect previous observable runs from their artifacts.

Provides helpers to list run sessions and display a human-readable
summary of a selected run, with optional event-replay.

Artifacts read (all optional / gracefully handled):
  .vibecode/runs/<session_id>/summary.json
  .vibecode/runs/<session_id>/metadata.json
  .vibecode/runs/<session_id>/events.jsonl
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from vibecode.events import VibecodeEvent


# ---------------------------------------------------------------------------
# Artifact loading helpers
# ---------------------------------------------------------------------------


def list_runs(runs_dir: Path) -> list[dict[str, Any]]:
    """Return a list of run-info dicts, most-recent first.

    Each dict has at minimum ``session_id`` and ``run_dir``.  When
    ``summary.json`` is present the dict also contains ``task``,
    ``platform``, ``profile``, ``started_at``, ``finished_at``,
    ``overall_status``, and ``exit_code``.
    """
    if not runs_dir.is_dir():
        return []

    result: list[dict[str, Any]] = []
    for entry in runs_dir.iterdir():
        if not entry.is_dir():
            continue
        info: dict[str, Any] = {"session_id": entry.name, "run_dir": entry}
        summary, _load_error = load_run_summary(entry)
        if summary:
            for key in (
                "task",
                "platform",
                "profile",
                "started_at",
                "finished_at",
                "overall_status",
                "exit_code",
            ):
                if key in summary:
                    info[key] = summary[key]
        result.append(info)

    result.sort(key=lambda d: d["session_id"], reverse=True)
    return result


def load_run_summary(run_dir: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Load ``summary.json`` from *run_dir*.

    Returns ``(data, error)`` where *error* describes why loading failed
    (``"missing"``, ``"corrupt"``, ``"unreadable"``) or ``None`` on success.
    Callers that only need data can unpack ``data, _ = load_run_summary(...)``.
    """
    path = run_dir / "summary.json"
    if not path.exists():
        path = run_dir / "metadata.json"
    if not path.exists():
        return None, "missing"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError:
        return None, f"{path.name} is corrupt"
    except OSError:
        return None, f"{path.name} could not be read"


def load_run_events(events_path: Path) -> tuple[list[VibecodeEvent], list[str], bool]:
    """Parse ``events.jsonl``, returning ``(events, errors, file_exists)``.

    Corrupt lines are skipped and their error messages collected.  The
    function never raises — callers can decide how to surface errors.
    *file_exists* is ``False`` when ``events.jsonl`` is missing, ``True``
    when the file was found (even if parsing yielded zero valid events).
    """
    events: list[VibecodeEvent] = []
    errors: list[str] = []

    if not events_path.exists():
        return events, errors, False

    try:
        text = events_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        errors.append(f"Cannot read events.jsonl: {exc}")
        return events, errors, True

    for lineno, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            events.append(VibecodeEvent.from_json(line))
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"Line {lineno}: {exc}")

    return events, errors, True


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _artifact_paths(run_dir: Path) -> list[tuple[str, Path]]:
    """Return (label, path) pairs for artifacts that actually exist."""
    candidates: list[tuple[str, str]] = [
        ("summary", "summary.json"),
        ("metadata", "metadata.json"),
        ("events", "events.jsonl"),
        ("guard report (json)", "guard_report.json"),
        ("guard report (md)", "guard_report.md"),
        ("checks report", "checks_report.json"),
        ("handoff report (json)", "handoff_report.json"),
        ("handoff report (md)", "handoff_report.md"),
        ("agent stdout", "agent_stdout.log"),
        ("agent stderr", "agent_stderr.log"),
        ("context pack", "context_pack.md"),
        ("opencode prompt", "opencode_prompt.md"),
    ]
    return [(label, run_dir / name) for label, name in candidates if (run_dir / name).exists()]


def format_run_list(runs: list[dict[str, Any]]) -> str:
    """Return a human-readable listing of available runs."""
    if not runs:
        return "No runs found."

    lines: list[str] = []
    for run in runs:
        sid = run["session_id"]
        status = run.get("overall_status", "—")
        task = (run.get("task") or "").strip()
        task_snippet = (task[:60] + "…") if len(task) > 60 else task
        platform = run.get("platform", "—")
        started = run.get("started_at", "—")
        line = f"  {sid}  [{status}]  {platform}"
        if started != "—":
            line += f"  started={started}"
        if task_snippet:
            line += f"  task={task_snippet!r}"
        lines.append(line)

    return "Run sessions (most recent first):\n" + "\n".join(lines)


def format_run_show(
    summary: dict[str, Any],
    run_dir: Path,
    *,
    events: list[VibecodeEvent] | None = None,
    event_errors: list[str] | None = None,
    show_events: bool = False,
) -> str:
    """Return a human-readable summary for a single run."""
    lines: list[str] = []
    sep = "─" * 60

    lines.append(sep)
    lines.append(f"Run: {summary.get('session_id', run_dir.name)}")
    lines.append(sep)

    # Core metadata
    task = (summary.get("task") or "").strip()
    lines.append(f"Task         : {task or '(none)'}")
    lines.append(f"Platform     : {summary.get('platform', '—')}")
    lines.append(f"Profile      : {summary.get('profile', '—')}")
    lines.append(f"Started      : {summary.get('started_at', '—')}")
    lines.append(f"Finished     : {summary.get('finished_at', '—')}")
    lines.append(f"Exit code    : {summary.get('exit_code', '—')}")
    lines.append(f"Agent status : {summary.get('agent_status', '—')}")
    lines.append(f"Guard mode   : {summary.get('guard_mode', '—')}")
    lines.append(f"Overall      : {summary.get('overall_status', '—')}")

    # Guard counts
    guard = summary.get("guard")
    if isinstance(guard, dict):
        passed_g = guard.get("passed", "—")
        counts = guard.get("counts_by_severity", {})
        errors_c = counts.get("error", 0)
        warnings_c = counts.get("warning", 0)
        infos = counts.get("info", 0)
        lines.append(
            f"Guard        : {'passed' if passed_g else 'failed'}"
            f"  errors={errors_c} warnings={warnings_c} info={infos}"
        )
        if not passed_g:
            findings = guard.get("findings", [])
            if findings:
                lines.append("")
                lines.append("Guard findings:")
                for f in findings[:10]:
                    title = f.get("title") or f.get("message", "")
                    path = f.get("path", "?")
                    severity = f.get("severity", "?")
                    lines.append(f"  [{severity}] {title}")
                    lines.append(f"    path: {path}")
    else:
        lines.append("Guard        : (not recorded)")

    # Checks status
    checks = summary.get("checks")
    if isinstance(checks, dict):
        total = checks.get("total", 0)
        passed_c = checks.get("passed", 0)
        failed_c = checks.get("failed", 0)
        lines.append(f"Checks       : {passed_c}/{total} passed, {failed_c} failed")
        checks_list = checks.get("checks", [])
        failed_checks = [c for c in checks_list if c.get("status") == "fail"]
        if failed_checks:
            lines.append("")
            lines.append("Failed checks:")
            for c in failed_checks:
                lines.append(f"  {c.get('name', '?')} (exit {c.get('exit_code', '?')})")
    else:
        lines.append("Checks       : (not recorded)")

    # Handoff
    handoff = summary.get("handoff")
    if isinstance(handoff, dict):
        status_h = handoff.get("status", "—")
        passed_h = status_h == "ok"
        lines.append(f"Handoff      : {'passed' if passed_h else 'failed'}")
        if not passed_h:
            issues = handoff.get("issues", handoff.get("issues", []))
            if issues:
                lines.append("")
                lines.append("Handoff issues:")
                for i in issues:
                    lines.append(f"  {i.get('file', '?')}: {i.get('message', '?')}")
    else:
        lines.append("Handoff      : (not recorded)")

    # Top-level error
    error = summary.get("error")
    if isinstance(error, str) and error.strip():
        lines.append("")
        lines.append(f"Error: {error}")

    # Artifact paths
    artifacts = _artifact_paths(run_dir)
    if artifacts:
        lines.append("")
        lines.append("Artifacts:")
        for label, path in artifacts:
            lines.append(f"  {label:<22}: {path}")

    # Events replay
    if show_events and events is not None:
        lines.append("")
        if event_errors:
            lines.append(f"Events ({len(events)} loaded, {len(event_errors)} parse error(s)):")
            for err in event_errors[:5]:
                lines.append(f"  ! {err}")
        else:
            lines.append(f"Events ({len(events)}):")

        for ev in events:
            ts = ev.timestamp.strftime("%H:%M:%S")
            lines.append(f"  [{ts}] {ev.level.name:8s} {ev.type:24s} {ev.message}")

    lines.append(sep)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI command handlers
# ---------------------------------------------------------------------------


def cmd_runs(args: Any) -> int:
    """Dispatch `vibecode runs` sub-commands."""
    sub = getattr(args, "runs_subcommand", None)
    if sub == "list":
        return _cmd_runs_list(args)
    if sub == "show":
        return _cmd_runs_show(args)
    # No subcommand — print help equivalent (list)
    return _cmd_runs_list(args)


def _resolve_runs_dir(args: Any) -> Path:
    """Resolve the .vibecode/runs directory from args or registry."""
    from vibecode.paths import normalise_root
    from vibecode.registry import ProjectRegistry

    raw = getattr(args, "repo", None)
    if raw:
        root = normalise_root(raw)
    else:
        reg = ProjectRegistry()
        try:
            root = normalise_root(str(reg.pick(None)))
        except FileNotFoundError:
            root = normalise_root(".")

    return root / ".vibecode" / "runs"


def _cmd_runs_list(args: Any) -> int:
    runs_dir = _resolve_runs_dir(args)
    runs = list_runs(runs_dir)
    if not runs:
        print(f"No runs found under {runs_dir}.")
    else:
        print(format_run_list(runs))
    return 0


def _cmd_runs_show(args: Any) -> int:
    session_id: str = args.session_id
    runs_dir = _resolve_runs_dir(args)
    run_dir = runs_dir / session_id

    if not run_dir.is_dir():
        # Give a helpful suggestion: list available ids
        available = list_runs(runs_dir)
        print(
            f"Error: run '{session_id}' not found under {runs_dir}.",
            file=sys.stderr,
        )
        if available:
            ids = [r["session_id"] for r in available[:5]]
            print(
                "Available session IDs (most recent first): "
                + ", ".join(ids)
                + ("…" if len(available) > 5 else ""),
                file=sys.stderr,
            )
        return 1

    summary, load_error = load_run_summary(run_dir)
    if summary is None:
        artifacts = _artifact_paths(run_dir)
        if not artifacts:
            print(
                f"Error: run '{session_id}' directory exists but contains no recognised artifacts.",
                file=sys.stderr,
            )
            return 1
        print(f"Run: {session_id}")
        if load_error and load_error != "missing":
            print(f"{load_error}. Available artifacts:")
        else:
            print("No summary.json found. Available artifacts:")
        for label, path in artifacts:
            print(f"  {label:<22}: {path}")
        summary = {"session_id": session_id}

    show_events: bool = getattr(args, "events", False)
    events: list[VibecodeEvent] | None = None
    event_errors: list[str] | None = None

    if show_events:
        events, event_errors, events_file_exists = load_run_events(run_dir / "events.jsonl")
        if not events_file_exists:
            print("events.jsonl not found.", file=sys.stderr)
            events = None
        elif event_errors and not events:
            print(
                f"Warning: events.jsonl could not be parsed ({len(event_errors)} error(s)).",
                file=sys.stderr,
            )
            for err in event_errors[:3]:
                print(f"  ! {err}", file=sys.stderr)

    output = format_run_show(
        summary,
        run_dir,
        events=events,
        event_errors=event_errors,
        show_events=show_events,
    )
    print(output)
    return 0
