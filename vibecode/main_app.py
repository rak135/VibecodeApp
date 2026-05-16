"""Main TUI application for vibecode.

Provides the primary three-column control shell launched by ``vibecode`` with
no subcommand, and by the explicit ``vibecode tui [repo]`` alias.

Phase 1 scope: three-column layout with status, agent console placeholder,
and event log.  No embedded PTY.  No LLM calls.

Columns:
  Left   — repo status and action menu.
  Center — agent console placeholder (OpenCode; Phase 1: output area only).
  Right  — Vibecode event log (refresh, index, guard, check summaries).
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical
    from textual.screen import Screen
    from textual.widgets import Footer, Input, Label, RichLog, Static

    _TEXTUAL_AVAILABLE = True
except ImportError:
    _TEXTUAL_AVAILABLE = False


# ---------------------------------------------------------------------------
# Constant text blocks
# ---------------------------------------------------------------------------

_ACTIONS_TEXT = (
    "Actions:\n"
    "  [R] Refresh / Rebuild Vibecode layer\n"
    "  [L] Reload right-panel debug state\n"
    "  [I] Inspect repo map\n"
    "  [C] Create context for task\n"
    "  [A] Run audit profile\n"
    "  [S] Run safe agent profile\n"
    "  [E] Launch external terminal\n"
    "  [G] Run guard\n"
    "  [T] Run tests/checks\n"
    "  [H] Handoff check\n"
    "  [Q] Quit"
)

def _make_center_placeholder(provider_name: str, available: bool | None = None, status_msg: str = "") -> str:
    """Return center-panel placeholder text for *provider_name*.

    When *available* is not None, an availability line is included.
    """
    lines = [
        f"Provider: {provider_name}",
    ]
    if available is not None:
        status_line = f"Status:   {'available' if available else 'unavailable'}"
        if not available and status_msg:
            status_line += f" ({status_msg})"
        lines.append(status_line)
    lines += [
        "Current task: none",
        "",
        "─── Phase 1 / Phase 2 ───",
        "No command running.",
        "",
        "Options:",
        "  [A]/[S] — Vibecode-orchestrated run with event streaming",
        f"  [E]     — Launch {provider_name} in external Windows Terminal",
        "",
        "Note: An interactive terminal is not implemented inside the TUI.",
        "Use [E] to open a real terminal window for a fully interactive",
        f"{provider_name} session.  The TUI remains the Vibecode cockpit.",
        "Use 'vibecode monitor' for orchestrated run with live output.",
    ]
    return "\n".join(lines)


# Module-level constant kept for backward compatibility with tests and imports.
_CENTER_PLACEHOLDER = _make_center_placeholder("OpenCode")


# ---------------------------------------------------------------------------
# Context preview helpers (testable without Textual)
# ---------------------------------------------------------------------------


def _get_section_content(content: str, section_heading: str) -> list[str]:
    """Return non-empty, non-blockquote lines from a markdown ## section."""
    lines = content.splitlines()
    in_section = False
    result: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## ") and section_heading.lower() in stripped.lower():
            in_section = True
            continue
        if in_section and stripped.startswith("## "):
            break
        if in_section and stripped and not stripped.startswith(">"):
            result.append(stripped)
    return result


def _extract_file_paths(content: str) -> list[str]:
    """Return up to 10 file paths from the 'Relevant files' section."""
    paths: list[str] = []
    for line in _get_section_content(content, "Relevant files with reasons"):
        m = re.match(r"-\s+`([^`]+)`", line)
        if m:
            paths.append(m.group(1))
    return paths[:10]


def _extract_architecture_docs(content: str) -> list[str]:
    """Return architecture doc paths from 'Relevant architecture' section.

    Only top-level bullets are captured; nested (indented) source-file
    bullets are excluded to avoid misclassifying source files as docs.
    """
    docs: list[str] = []
    lines = content.splitlines()
    in_section = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## ") and "Relevant architecture".lower() in stripped.lower():
            in_section = True
            continue
        if in_section and stripped.startswith("## "):
            break
        if in_section and stripped and not stripped.startswith(">"):
            # Only match top-level bullets — the original line must start
            # with "- " (no leading whitespace) to exclude nested
            # source-file bullets that happen to match the same pattern.
            if not line.startswith("- "):
                continue
            m = re.match(r"-\s+`([^`]+)`", stripped)
            if m:
                docs.append(m.group(1))
    return docs


def _extract_required_checks_from_pack(content: str) -> list[str]:
    """Return up to 5 check commands from 'Required checks' section."""
    checks: list[str] = []
    for line in _get_section_content(content, "Required checks"):
        m = re.search(r"`([^`]+)`", line)
        if m:
            checks.append(m.group(1))
    return checks[:5]


def _extract_protected_paths_from_pack(content: str) -> list[str]:
    """Return up to 8 protected path names from 'Protected paths' section."""
    paths: list[str] = []
    for line in _get_section_content(content, "Protected paths"):
        m = re.match(r"-\s+`([^`]+)`", line)
        if m:
            paths.append(m.group(1))
    return paths[:8]


def _extract_pack_warnings(content: str) -> list[str]:
    """Return warning lines from the context pack (e.g. truncation notices)."""
    warnings: list[str] = []
    for line in content.splitlines():
        if "Context limit reached" in line:
            warnings.append("Context limit reached; some sections omitted.")
        elif "WARNING:" in line and line.strip().startswith("-"):
            warnings.append(line.strip().lstrip("- "))
    return warnings[:5]


@dataclass(frozen=True)
class TuiEventRecord:
    """Small immutable event record used by the right-panel debug model."""

    timestamp: str
    category: str
    level: str
    message: str


class TuiEventLog:
    """Bounded in-memory event log for right-panel debug summaries."""

    def __init__(self, *, max_entries: int = 120, max_message_chars: int = 240) -> None:
        self._max_entries = max(1, max_entries)
        self._max_message_chars = max(40, max_message_chars)
        self._records: list[TuiEventRecord] = []

    def add(
        self,
        message: str,
        *,
        category: str = "event",
        level: str = "info",
        timestamp: datetime | None = None,
    ) -> None:
        text = (message or "").replace("\r", "").strip()
        if len(text) > self._max_message_chars:
            text = text[: self._max_message_chars - 1] + "…"
        ts = (timestamp or datetime.now(tz=timezone.utc)).strftime("%H:%M:%S")
        self._records.append(
            TuiEventRecord(timestamp=ts, category=category, level=level.lower(), message=text)
        )
        overflow = len(self._records) - self._max_entries
        if overflow > 0:
            del self._records[:overflow]

    def latest(self, limit: int = 8) -> list[TuiEventRecord]:
        capped = max(1, limit)
        return list(self._records[-capped:])


def _shorten_path(path: str, max_chars: int = 92) -> str:
    if len(path) <= max_chars:
        return path
    head = max_chars // 2 - 2
    tail = max_chars - head - 3
    return f"{path[:head]}...{path[-tail:]}"


def _summarize_text_file(
    path: Path,
    *,
    max_bytes: int = 4096,
    max_lines: int = 12,
    tail: bool = False,
) -> tuple[str, bool]:
    """Return a bounded summary of *path* and whether truncation occurred."""
    if not path.exists():
        return "(missing)", False
    try:
        with path.open("rb") as handle:
            truncated = False
            if tail:
                handle.seek(0, os.SEEK_END)
                size = handle.tell()
                if size > max_bytes:
                    handle.seek(-max_bytes, os.SEEK_END)
                    truncated = True
                else:
                    handle.seek(0)
                raw = handle.read(max_bytes)
            else:
                raw = handle.read(max_bytes + 1)
                if len(raw) > max_bytes:
                    raw = raw[:max_bytes]
                    truncated = True
        text = raw.decode("utf-8", errors="replace")
    except OSError as exc:
        return (f"(unreadable: {exc})", False)

    lines = text.splitlines()
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        truncated = True
    summary = "\n".join(lines).strip()
    if not summary:
        summary = "(empty)"
    return summary, truncated


class SessionArtifactWatcher:
    """Collect and summarize run/current artifacts for the right debug panel."""

    def __init__(self, repo_root: Path) -> None:
        self._root = Path(repo_root)

    def _latest_session_id(self) -> str | None:
        runs_dir = self._root / ".vibecode" / "runs"
        if not runs_dir.is_dir():
            return None
        sessions = [entry.name for entry in runs_dir.iterdir() if entry.is_dir()]
        if not sessions:
            return None
        return sorted(sessions, reverse=True)[0]

    def snapshot(self, session_id: str | None = None) -> dict[str, Any]:
        from vibecode.session_log import RunSession

        selected_session = session_id or self._latest_session_id()
        session = RunSession(self._root, selected_session) if selected_session else None
        current_dir = self._root / ".vibecode" / "current"

        context_path = session.context_pack_md if session else (current_dir / "context_pack.md")
        prompt_path = session.opencode_prompt_md if session else (current_dir / "opencode_prompt.md")
        events_path = session.events_jsonl if session else None
        summary_path = session.summary_json if session else None
        stdout_path = session.agent_stdout_log if session else None
        stderr_path = session.agent_stderr_log if session else None
        guard_path = session.guard_report_json if session else None
        checks_path = session.checks_report_json if session else None
        handoff_path = session.handoff_report_json if session else None

        entries: list[dict[str, Any]] = []
        for label, path in (
            ("context pack", context_path),
            ("opencode prompt", prompt_path),
            ("events.jsonl", events_path),
            ("summary.json", summary_path),
            ("agent stdout.log", stdout_path),
            ("agent stderr.log", stderr_path),
            ("guard report", guard_path),
            ("checks report", checks_path),
            ("handoff report", handoff_path),
        ):
            if path is None:
                entries.append(
                    {"label": label, "path": "(no active run session)", "exists": False}
                )
            else:
                entries.append({"label": label, "path": str(path), "exists": path.exists()})

        context_summary, context_truncated = _summarize_text_file(context_path, max_lines=8)
        events_summary, events_truncated = (
            _summarize_text_file(events_path, tail=True, max_lines=6)
            if events_path is not None
            else ("(no active run session)", False)
        )
        stderr_summary, stderr_truncated = (
            _summarize_text_file(stderr_path, tail=True, max_lines=4)
            if stderr_path is not None
            else ("(no active run session)", False)
        )

        warnings: list[str] = []
        if not selected_session:
            warnings.append("No run session selected yet.")

        missing = [item["label"] for item in entries if not item["exists"]]
        if missing:
            warnings.append("Missing artifacts: " + ", ".join(missing[:6]) + ("…" if len(missing) > 6 else ""))

        return {
            "session_id": selected_session,
            "run_dir": str(session.run_dir) if session else "",
            "artifacts": entries,
            "context_summary": context_summary,
            "events_summary": events_summary,
            "stderr_summary": stderr_summary,
            "context_truncated": context_truncated,
            "events_truncated": events_truncated,
            "stderr_truncated": stderr_truncated,
            "warnings": warnings,
            "errors": [],
        }


def render_right_debug_cockpit(
    *,
    snapshot: dict[str, Any] | None,
    event_log: TuiEventLog,
    refresh_report: dict[str, Any] | None = None,
    context_preview: dict[str, Any] | None = None,
    run_result: dict[str, Any] | None = None,
    guard_result: dict[str, Any] | None = None,
    check_result: dict[str, Any] | None = None,
    handoff_result: dict[str, Any] | None = None,
    next_action: str = "",
) -> str:
    """Render the structured right-panel debug cockpit (pure, testable)."""
    lines = ["─── Debug Cockpit ───"]
    snapshot = snapshot or {}
    session_id = snapshot.get("session_id") or (run_result or {}).get("session_id") or "—"
    run_dir = snapshot.get("run_dir") or (run_result or {}).get("run_dir") or "—"
    lines.append(f"Session: {session_id}")
    lines.append(f"Run dir: {_shorten_path(str(run_dir))}")

    lines.extend(["", "Artifacts:"])
    for item in (snapshot.get("artifacts") or [])[:9]:
        marker = "ok" if item.get("exists") else "missing"
        lines.append(
            f"  [{marker:7s}] {item.get('label')}: {_shorten_path(str(item.get('path', '')))}"
        )

    lines.extend(["", "Refresh / Rebuild:"])
    if refresh_report:
        lines.append(f"  validation: {refresh_report.get('validation_status', 'unknown')}")
        lines.append(f"  artifacts written: {len(refresh_report.get('generated_artifacts') or [])}")
    else:
        lines.append("  (no refresh report yet)")

    lines.extend(["", "Context preview:"])
    if context_preview:
        task = str(context_preview.get("task", "")).strip()
        if task:
            lines.append(f"  task: {task[:80]}{'…' if len(task) > 80 else ''}")
    context_summary = str(snapshot.get("context_summary", "(missing)"))
    if snapshot.get("context_truncated"):
        context_summary += "\n[truncated]"
    lines.append("  " + context_summary.replace("\n", "\n  "))

    lines.extend(["", "Event/log excerpts:"])
    events_summary = str(snapshot.get("events_summary", "(missing)"))
    if snapshot.get("events_truncated"):
        events_summary += "\n[truncated]"
    lines.append("  events: " + events_summary.replace("\n", "\n  "))
    stderr_summary = str(snapshot.get("stderr_summary", "(missing)"))
    if snapshot.get("stderr_truncated"):
        stderr_summary += "\n[truncated]"
    lines.append("  stderr: " + stderr_summary.replace("\n", "\n  "))

    lines.extend(["", "Validation / post-run:"])
    if run_result:
        lines.append(f"  run: {run_result.get('overall_status', 'unknown')}")
        lines.append(f"  exit: {run_result.get('exit_code')}")
    if guard_result:
        lines.append(
            f"  guard: {'passed' if guard_result.get('passed') else 'failed'} "
            f"(errors={guard_result.get('errors', 0)}, warnings={guard_result.get('warnings', 0)})"
        )
    if check_result:
        lines.append(
            f"  checks: {check_result.get('status', 'unknown')} "
            f"(failed={check_result.get('failed', 0)})"
        )
    if handoff_result:
        lines.append(
            f"  handoff: {'passed' if handoff_result.get('passed') else 'failed'} "
            f"(issues={len(handoff_result.get('issues') or [])})"
        )
    if not any((run_result, guard_result, check_result, handoff_result)):
        lines.append("  (not run yet)")

    lines.extend(["", "Latest Vibecode events:"])
    latest = event_log.latest(8)
    if latest:
        for record in latest:
            lines.append(
                f"  [{record.timestamp}] {record.level.upper():7s} {record.category}: {record.message}"
            )
    else:
        lines.append("  (none)")

    warnings: list[str] = list(snapshot.get("warnings") or [])
    errors: list[str] = list(snapshot.get("errors") or [])
    if refresh_report:
        warnings.extend([str(w) for w in (refresh_report.get("warnings") or [])[:3]])
        errors.extend([str(e) for e in (refresh_report.get("errors") or [])[:3]])

    lines.extend(["", "Warnings / errors:"])
    if warnings:
        for warning in warnings[:4]:
            lines.append(f"  WARN: {warning}")
    if errors:
        for error in errors[:4]:
            lines.append(f"  ERROR: {error}")
    if not warnings and not errors:
        lines.append("  none")

    lines.extend(["", "Next recommended action:"])
    lines.append(f"  {next_action or 'Use [R] refresh, [C] context, or [L] reload debug state.'}")

    return "\n".join(lines)


class InspectMapService:
    """Loads the repo map and file inventory for TUI display.

    Returns a summary dict; does not contain any TUI logic.
    """

    def run(self, repo_root: Path) -> dict:
        """Load the repo map and return a summary dict.

        Keys: content, path, total_files, card_count, high_risk_count,
              stale, error (None on success).
        """
        result: dict = {
            "content": "",
            "path": "",
            "total_files": 0,
            "card_count": 0,
            "high_risk_count": 0,
            "stale": False,
            "error": None,
        }
        map_file = repo_root / ".vibecode" / "index" / "repo_tree.generated.md"
        inventory_file = repo_root / ".vibecode" / "index" / "file_inventory.json"

        if not map_file.exists() and not inventory_file.exists():
            result["error"] = "Index not found. Run [R] Refresh or 'vibecode index'."
            return result

        if map_file.exists():
            try:
                result["content"] = map_file.read_text(encoding="utf-8")
                result["path"] = str(map_file)
            except Exception as exc:  # noqa: BLE001
                result["error"] = f"Failed to read repo map: {exc}"

        if inventory_file.exists():
            try:
                inv_data = json.loads(inventory_file.read_text(encoding="utf-8"))
                result["total_files"] = inv_data.get("total_files", 0)
                cards = inv_data.get("context_cards") or []
                result["card_count"] = len(cards)
            except Exception:  # noqa: BLE001
                pass

        risk_file = repo_root / ".vibecode" / "index" / "risk_report.json"
        if risk_file.exists():
            try:
                risk_data = json.loads(risk_file.read_text(encoding="utf-8"))
                high_risk = sum(
                    1 for item in (risk_data.get("files") or {}).values()
                    if (item.get("risk_level") == "high" or
                        any(h.get("severity") == "high" for h in (item.get("heuristics") or [])))
                )
                result["high_risk_count"] = high_risk
            except Exception:  # noqa: BLE001
                pass

        result["stale"] = self._is_stale(repo_root)

        return result

    @staticmethod
    def _is_stale(repo_root: Path) -> bool:
        try:
            from vibecode.indexer import check_index_freshness

            is_fresh, _detail = check_index_freshness(repo_root)
            return not is_fresh
        except Exception:
            last_index = repo_root / ".vibecode" / "current" / "last_index.json"
            return not last_index.exists()


def render_inspect_map_result(result: dict) -> str:
    """Return right-panel text summarising the repo map (pure, testable)."""
    if result.get("error"):
        return (
            "─── Inspect Repo Map ───\n"
            f"ERROR: {result['error']}\n\n"
            "Hint: Run [R] Refresh to build the index."
        )

    lines = ["─── Repo Map ───"]
    if result.get("path"):
        lines.append(f"Map: {result['path']}")
    if result.get("total_files"):
        lines.append(f"Files: {result['total_files']}")
    if result.get("card_count"):
        lines.append(f"Cards: {result['card_count']}")
    if result.get("high_risk_count"):
        lines.append(f"High-risk: {result['high_risk_count']}")
    if result.get("stale"):
        lines.append("WARN: Index may be stale — run [R] Refresh to update.")

    content = result.get("content", "")
    if content:
        lines.append("")
        # Show first ~3000 chars of the map (summary section)
        snippet = content[:3000]
        if len(content) > 3000:
            snippet += f"\n… ({len(content) - 3000} more chars — see {result.get('path', 'file')})"
        lines.append(snippet)

    return "\n".join(lines)


class GuardService:
    """Runs guard evaluation and returns a summary dict.

    Wraps :func:`evaluate_project_guard` and :func:`write_guard_result`;
    contains no TUI logic.
    """

    def run(self, repo_root: Path) -> dict:
        """Run guard and return a summary dict.

        Keys: passed, errors, warnings, findings_summary (list[str]),
              report_path, error (None on success).
        """
        result: dict = {
            "passed": True,
            "errors": 0,
            "warnings": 0,
            "findings_summary": [],
            "report_path": "",
            "error": None,
        }
        vibecode_dir = repo_root / ".vibecode"

        project_yaml = vibecode_dir / "project.yaml"
        if not project_yaml.exists():
            result["error"] = (
                ".vibecode/project.yaml not found. "
                "Run 'vibecode init' to initialise the project."
            )
            return result

        try:
            from vibecode.git_state import inspect_git_state

            git_state = inspect_git_state(repo_root)
        except Exception as exc:  # noqa: BLE001
            result["error"] = f"Git error: {exc}"
            return result

        if not git_state.is_git_repo:
            result["error"] = "Not a git repository."
            return result

        try:
            from vibecode.guard import evaluate_project_guard, write_guard_result

            guard_result = evaluate_project_guard(git_state, vibecode_dir)
        except Exception as exc:  # noqa: BLE001
            result["error"] = f"Guard evaluation error: {exc}"
            return result

        result["passed"] = guard_result.passed
        result["errors"] = sum(1 for f in guard_result.findings if f.severity == "error")
        result["warnings"] = sum(1 for f in guard_result.findings if f.severity == "warning")

        for finding in guard_result.findings[:20]:
            severity = finding.severity.upper()
            title = (finding.title or finding.message)[:80]
            result["findings_summary"].append(f"  [{severity}] {finding.path}: {title}")

        try:
            report_path = write_guard_result(guard_result, vibecode_dir, repo_root)
            result["report_path"] = str(report_path)
        except Exception:  # noqa: BLE001
            pass

        return result


def render_guard_result_summary(result: dict) -> str:
    """Return right-panel text for a guard run result (pure, testable)."""
    if result.get("error"):
        return (
            "─── Guard ───\n"
            f"ERROR: {result['error']}"
        )

    status = "✓ PASSED" if result.get("passed") else "✗ FAILED"
    lines = [
        "─── Guard ───",
        f"Result: {status}",
        f"Errors: {result.get('errors', 0)}  Warnings: {result.get('warnings', 0)}",
    ]
    if result.get("report_path"):
        lines.append(f"Report: {result['report_path']}")

    findings = result.get("findings_summary") or []
    if findings:
        lines.append("")
        lines.append("Findings:")
        lines.extend(findings)
    else:
        lines.append("No violations found.")

    return "\n".join(lines)


class CheckService:
    """Runs required checks and returns a summary dict.

    Wraps :func:`run_checks` and :func:`write_check_results`;
    contains no TUI logic.
    """

    def run(self, repo_root: Path) -> dict:
        """Run checks and return a summary dict.

        Keys: status, total, passed, failed, warnings,
              results_summary (list[str]), path, error (None on success).
        """
        result: dict = {
            "status": "not-run",
            "total": 0,
            "passed": 0,
            "failed": 0,
            "warnings": 0,
            "results_summary": [],
            "path": "",
            "error": None,
        }
        vibecode_dir = repo_root / ".vibecode"

        checks_yaml = vibecode_dir / "checks" / "required_checks.yaml"
        if not checks_yaml.exists():
            result["error"] = (
                ".vibecode/checks/required_checks.yaml not found. "
                "No checks configured."
            )
            return result

        try:
            from vibecode.check import run_checks, write_check_results

            check_run = run_checks(repo_root)
        except Exception as exc:  # noqa: BLE001
            result["error"] = f"Check execution error: {exc}"
            return result

        result["status"] = "fail" if check_run.has_required_failures else "pass"
        result["total"] = check_run.total
        result["passed"] = check_run.passed
        result["failed"] = check_run.failed
        result["warnings"] = check_run.warnings

        for r in check_run.results:
            label = {"pass": "PASS", "fail": "FAIL", "warn": "WARN"}.get(r.status, "?")
            result["results_summary"].append(
                f"  [{label}] {r.name} (exit {r.exit_code}, {r.duration_seconds:.2f}s)"
            )

        try:
            path = write_check_results(check_run, vibecode_dir)
            result["path"] = str(path)
        except Exception:  # noqa: BLE001
            pass

        return result


def render_check_result_summary(result: dict) -> str:
    """Return right-panel text for a check run result (pure, testable)."""
    if result.get("error"):
        return (
            "─── Checks ───\n"
            f"ERROR: {result['error']}"
        )

    status_label = {"pass": "✓ PASS", "fail": "✗ FAIL"}.get(
        result.get("status", ""), result.get("status", "unknown")
    )
    lines = [
        "─── Checks ───",
        f"Result: {status_label}",
        (
            f"Total: {result.get('total', 0)}  "
            f"Passed: {result.get('passed', 0)}  "
            f"Failed: {result.get('failed', 0)}  "
            f"Warnings: {result.get('warnings', 0)}"
        ),
    ]
    if result.get("path"):
        lines.append(f"Report: {result['path']}")

    summaries = result.get("results_summary") or []
    if summaries:
        lines.append("")
        lines.append("Results:")
        lines.extend(summaries)

    return "\n".join(lines)


class HandoffService:
    """Runs handoff file validation and returns a summary dict.

    Wraps :func:`validate_handoff_files`; contains no TUI logic.
    """

    def run(self, repo_root: Path) -> dict:
        """Run handoff check and return a summary dict.

        Keys: passed, issues (list[dict with file/message]),
              status, error (None on success).
        """
        result: dict = {
            "passed": True,
            "issues": [],
            "status": "ok",
            "error": None,
        }
        vibecode_dir = repo_root / ".vibecode"

        if not vibecode_dir.exists():
            result["error"] = ".vibecode directory not found."
            return result

        try:
            from vibecode.git_state import inspect_git_state

            git_state = inspect_git_state(repo_root)
            diff_paths = (
                list(git_state.diff_name_only) + list(git_state.untracked_paths)
                if git_state.is_git_repo
                else []
            )
        except Exception:  # noqa: BLE001
            diff_paths = []

        try:
            from vibecode.handoff import validate_handoff_files

            handoff_result = validate_handoff_files(repo_root, diff=diff_paths)
        except Exception as exc:  # noqa: BLE001
            result["error"] = f"Handoff validation error: {exc}"
            return result

        result["passed"] = handoff_result.passed
        result["status"] = handoff_result.status
        result["issues"] = [
            {"file": issue.file, "message": issue.message}
            for issue in handoff_result.issues
        ]
        return result


def render_handoff_result_summary(result: dict) -> str:
    """Return right-panel text for a handoff check result (pure, testable)."""
    if result.get("error"):
        return (
            "─── Handoff Check ───\n"
            f"ERROR: {result['error']}"
        )

    status = "✓ PASSED" if result.get("passed") else "✗ FAILED"
    lines = [
        "─── Handoff Check ───",
        f"Result: {status}",
    ]

    issues = result.get("issues") or []
    if issues:
        lines.append(f"Issues ({len(issues)}):")
        for issue in issues:
            lines.append(f"  • {issue.get('file', '')}: {issue.get('message', '')}")
    else:
        lines.append("All handoff files are valid.")

    return "\n".join(lines)


class ContextPreviewService:
    """Generates context artifacts and summarises them for TUI display.

    Wraps the existing :func:`write_context_pack` and
    :func:`write_opencode_prompt` functions; does not duplicate their logic.
    """

    def run(self, repo_root: Path, task: str) -> dict:
        """Generate context for *task* and return a preview dict.

        The returned dict always has the following keys::

            task, platform, context_pack_path, opencode_prompt_path,
            relevant_files, architecture_docs, required_checks,
            protected_files, warnings, error

        *error* is ``None`` on success; a string on failure.
        """
        from vibecode.context.platform_export import (
            OPENCODE_PROMPT_PATH,
            write_opencode_prompt,
        )
        from vibecode.context.renderer import CURRENT_CONTEXT_PACK, write_context_pack

        result: dict = {
            "task": task,
            "platform": "opencode",
            "context_pack_path": str(repo_root / CURRENT_CONTEXT_PACK),
            "opencode_prompt_path": str(repo_root / OPENCODE_PROMPT_PATH),
            "relevant_files": [],
            "architecture_docs": [],
            "required_checks": [],
            "protected_files": [],
            "warnings": [],
            "error": None,
        }
        try:
            pack_path = write_context_pack(repo_root, task)
            content = pack_path.read_text(encoding="utf-8")
            opencode_path = write_opencode_prompt(repo_root, content)
            result["context_pack_path"] = str(pack_path)
            result["opencode_prompt_path"] = str(opencode_path)
            result["relevant_files"] = _extract_file_paths(content)
            result["architecture_docs"] = _extract_architecture_docs(content)
            result["required_checks"] = _extract_required_checks_from_pack(content)
            result["protected_files"] = _extract_protected_paths_from_pack(content)
            result["warnings"] = _extract_pack_warnings(content)
        except Exception as exc:  # noqa: BLE001
            result["error"] = str(exc)
        return result


def render_center_context_status(
    task: str,
    context_pack_path: str,
    opencode_prompt_path: str,
    *,
    provider_name: str = "OpenCode",
) -> str:
    """Return center panel text when context is ready (pure, testable)."""
    task_short = task[:100] + ("…" if len(task) > 100 else "")
    return (
        f"Provider: {provider_name}\n"
        f"Current task: {task_short}\n\n"
        f"Context pack:\n  {context_pack_path}\n\n"
        f"{provider_name} prompt:\n  {opencode_prompt_path}\n\n"
        "Status: context ready\n\n"
        "─── Next steps ───\n"
        "[A] Audit profile   — press A to launch agent with audit rules\n"
        "[S] Safe profile    — press S to launch agent with safe-mode rules\n"
    )


def render_context_preview(preview: dict) -> str:
    """Return right-panel preview text summarising generated context (pure)."""
    task_text = preview.get("task", "")
    task_short = task_text[:80] + ("…" if len(task_text) > 80 else "")
    lines = [
        "─── Context Preview ───",
        f"Task:     {task_short}",
        f"Platform: {preview.get('platform', 'opencode')}",
        "",
        f"Pack:   {preview.get('context_pack_path', '')}",
        f"Prompt: {preview.get('opencode_prompt_path', '')}",
    ]

    files = preview.get("relevant_files") or []
    if files:
        lines += ["", "Relevant files:"] + [f"  {f}" for f in files[:8]]

    arch = preview.get("architecture_docs") or []
    if arch:
        lines += ["", "Architecture docs:"] + [f"  {d}" for d in arch[:4]]

    checks = preview.get("required_checks") or []
    if checks:
        lines += ["", "Required checks:"] + [f"  {c}" for c in checks[:4]]

    protected = preview.get("protected_files") or []
    if protected:
        lines += ["", "Protected/risky files:"] + [f"  {p}" for p in protected[:5]]

    for w in preview.get("warnings") or []:
        lines += ["", f"WARN: {w}"]

    if preview.get("error"):
        lines += ["", f"ERROR: {preview['error']}"]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# AgentRunService and run rendering helpers
# ---------------------------------------------------------------------------


def _load_abort_error(session) -> str:
    """Read the specific abort reason from the session summary.json on disk.

    Returns the ``error`` field if the summary exists and contains one,
    otherwise a generic fallback message.
    """
    try:
        if session.summary_json.exists():
            data = json.loads(session.summary_json.read_text(encoding="utf-8"))
            return data.get("error", "Run aborted — see run directory for details.")
    except Exception:
        pass
    return "Run aborted — see run directory for details."


class AgentRunService:
    """Wraps RunController to execute agent runs from the TUI ([A] / [S]).

    The optional *controller_factory* kwarg accepts any callable with the same
    signature as :class:`~vibecode.run.RunController` — used in tests to inject
    a fake factory that avoids needing a real OpenCode binary.
    """

    def __init__(self, controller_factory: object | None = None) -> None:
        self._controller_factory = controller_factory

    def run(
        self,
        repo_root: Path,
        task: str,
        profile: str,
        *,
        allow_dirty: bool = True,
        guard_mode: str = "advisory",
        sink: object | None = None,
        session_id: str | None = None,
    ) -> dict:
        """Execute the agent run.  Designed to be called from a background thread.

        Returns a result dict with keys::

            session_id, task, profile, run_dir,
            overall_status, exit_code,
            context_pack_path, prompt_path,
            guard_passed, guard_errors, guard_warnings,
            checks_passed, handoff_passed,
            artifact_paths, error

        ``error`` is ``None`` on success, a string on failure.
        """
        from vibecode.run import RunController
        from vibecode.session_log import RunSession

        factory = self._controller_factory or RunController
        controller = factory(
            root=repo_root,
            task=task,
            platform="opencode",
            profile_name=profile,
            allow_dirty=allow_dirty,
            no_index=False,
            guard_mode=guard_mode,
            sink=sink,
            session_id=session_id,
        )

        result: dict = {
            "session_id": controller.session_id,
            "task": task,
            "profile": profile,
            "run_dir": None,
            "overall_status": "error",
            "exit_code": None,
            "context_pack_path": None,
            "prompt_path": None,
            "guard_passed": None,
            "guard_errors": 0,
            "guard_warnings": 0,
            "checks_passed": None,
            "handoff_passed": None,
            "artifact_paths": [],
            "error": None,
        }

        try:
            summary, wrapper_exit_code = controller.execute()

            session = RunSession(repo_root, controller.session_id)
            result["run_dir"] = str(session.run_dir)
            if session.context_pack_md.exists():
                result["context_pack_path"] = str(session.context_pack_md)
            if session.opencode_prompt_md.exists():
                result["prompt_path"] = str(session.opencode_prompt_md)

            if summary is not None:
                result["exit_code"] = summary.exit_code
                result["overall_status"] = summary.overall_status
                if summary.guard is not None:
                    result["guard_passed"] = summary.guard.passed
                    result["guard_errors"] = sum(
                        1 for f in summary.guard.findings if f.severity == "error"
                    )
                    result["guard_warnings"] = sum(
                        1 for f in summary.guard.findings if f.severity == "warning"
                    )
                if summary.checks is not None:
                    result["checks_passed"] = not summary.checks.has_required_failures
                if summary.handoff is not None:
                    result["handoff_passed"] = summary.handoff.passed
            else:
                result["exit_code"] = wrapper_exit_code
                result["overall_status"] = "error"
                result["error"] = _load_abort_error(session)

            for attr in (
                "events_jsonl",
                "summary_json",
                "guard_report_json",
                "guard_report_md",
                "checks_report_json",
                "handoff_report_json",
                "metadata_json",
                "agent_stdout_log",
                "agent_stderr_log",
            ):
                p = getattr(session, attr, None)
                if p is not None and p.exists():
                    result["artifact_paths"].append(str(p))

        except Exception as exc:  # noqa: BLE001
            result["error"] = str(exc)

        return result


def render_center_run_status(
    task: str,
    profile: str,
    status: str,
    *,
    session_id: str | None = None,
    run_dir: str | None = None,
    provider_name: str = "OpenCode",
) -> str:
    """Return center panel header text during/after an agent run (pure, testable)."""
    task_short = task[:80] + ("…" if len(task) > 80 else "")
    lines = [
        f"Provider: {provider_name}",
        f"Profile:  {profile}",
        f"Task:     {task_short}",
        "",
        f"Status: {status}",
    ]
    if session_id:
        lines.append(f"Session: {session_id}")
    if run_dir:
        lines.append(f"Run dir: {run_dir}")
    return "\n".join(lines)


def render_right_run_result(result: dict) -> str:
    """Return right-panel text summarising a completed agent run (pure)."""
    lines = [
        "─── Run Result ───",
        f"Session:   {result.get('session_id', '?')}",
        f"Profile:   {result.get('profile', '?')}",
        f"Status:    {result.get('overall_status', 'unknown')}",
        f"Exit code: {result.get('exit_code')}",
    ]

    if result.get("run_dir"):
        lines.append(f"Run dir: {result['run_dir']}")

    guard_passed = result.get("guard_passed")
    if guard_passed is not None:
        g_status = "PASSED" if guard_passed else "FAILED"
        lines.append(
            f"Guard:     {g_status}"
            f" ({result.get('guard_errors', 0)} errors,"
            f" {result.get('guard_warnings', 0)} warnings)"
        )
    else:
        lines.append("Guard:     skipped")

    checks_passed = result.get("checks_passed")
    if checks_passed is not None:
        lines.append(f"Checks:    {'PASSED' if checks_passed else 'FAILED'}")
    else:
        lines.append("Checks:    skipped")

    handoff_passed = result.get("handoff_passed")
    if handoff_passed is not None:
        lines.append(f"Handoff:   {'PASSED' if handoff_passed else 'FAILED'}")
    else:
        lines.append("Handoff:   skipped")

    if result.get("context_pack_path"):
        lines += ["", f"Context pack:  {result['context_pack_path']}"]
    if result.get("prompt_path"):
        lines.append(f"Prompt:        {result['prompt_path']}")

    artifacts = result.get("artifact_paths") or []
    if artifacts:
        lines += ["", "Artifacts:"]
        for path in artifacts[:10]:
            lines.append(f"  {path}")

    if result.get("error"):
        lines += ["", f"ERROR: {result['error']}"]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ExternalTerminalService and rendering helpers (Phase 2)
# ---------------------------------------------------------------------------


class ExternalTerminalService:
    """Generate context and launch OpenCode in an external terminal.

    Wraps :class:`~vibecode.adapters.external_terminal.WindowsTerminalOpenCodeAdapter`;
    contains no TUI logic.

    The optional *adapter* kwarg accepts any object implementing the
    :meth:`launch` interface — used in tests to inject a fake adapter that
    avoids spawning real terminal processes.
    """

    def __init__(self, adapter: object | None = None) -> None:
        self._adapter = adapter

    def _get_adapter(self) -> object:
        if self._adapter is None:
            from vibecode.adapters.external_terminal import WindowsTerminalOpenCodeAdapter

            self._adapter = WindowsTerminalOpenCodeAdapter()
        return self._adapter

    def run(
        self,
        repo_root: Path,
        task: str,
        profile: str = "safe",
        *,
        opencode_command: str | None = None,
        session_id: str | None = None,
        env: dict | None = None,
    ) -> dict:
        """Generate context and launch an external terminal for *task*.

        Returns a result dict with keys::

            launched, command, terminal_kind, pid, error_message,
            prompt_path, context_pack_path, task, profile

        ``error_message`` is ``None`` on success, a string on failure.
        ``launched`` is ``True`` when the terminal process was started.
        """
        result: dict = {
            "launched": False,
            "command": "",
            "terminal_kind": "",
            "pid": None,
            "error_message": None,
            "prompt_path": "",
            "context_pack_path": "",
            "task": task,
            "profile": profile,
        }

        # Ensure the OpenCode prompt file is up-to-date before launch.
        try:
            from vibecode.context.platform_export import write_opencode_prompt
            from vibecode.context.renderer import write_context_pack

            pack_path = write_context_pack(repo_root, task)
            content = pack_path.read_text(encoding="utf-8")
            prompt_path = write_opencode_prompt(repo_root, content)
            result["context_pack_path"] = str(pack_path)
            result["prompt_path"] = str(prompt_path)
        except Exception as exc:  # noqa: BLE001
            result["error_message"] = f"Context generation failed: {exc}"
            return result

        # Resolve opencode command.
        if opencode_command is None:
            from vibecode.adapters.opencode import resolve_opencode_command

            opencode_command = resolve_opencode_command() or "opencode"

        adapter = self._get_adapter()
        launch_result = adapter.launch(  # type: ignore[attr-defined]
            repo_root,
            opencode_command,
            prompt_path,
            profile=profile,
            session_id=session_id,
            env=env,
        )

        result["launched"] = launch_result.launched
        result["command"] = launch_result.command
        result["terminal_kind"] = launch_result.terminal_kind
        result["pid"] = launch_result.pid
        result["error_message"] = launch_result.error_message
        return result


def render_center_external_launch_status(result: dict, *, provider_name: str = "OpenCode") -> str:
    """Return center panel text after an external terminal launch (pure, testable)."""
    task = result.get("task", "")
    task_short = task[:80] + ("…" if len(task) > 80 else "")
    profile = result.get("profile", "")
    lines = [
        f"Provider: {provider_name}",
        f"Profile:  {profile}",
        f"Task:     {task_short}",
        "",
    ]
    if result.get("launched"):
        terminal = result.get("terminal_kind", "?")
        pid = result.get("pid")
        pid_str = f" (PID {pid})" if pid else ""
        lines += [
            f"Status: external terminal launched ({terminal}){pid_str}",
            "",
            "─── Interactive session active ───",
            "The interactive OpenCode session is running in the",
            "external terminal window.",
            "",
            f"Prompt: {result.get('prompt_path', '')}",
            "",
            "Return here for Vibecode guard, checks, and handoff.",
        ]
    else:
        lines += [
            "Status: launch failed",
            "",
            f"Error: {result.get('error_message') or 'unknown error'}",
        ]
    return "\n".join(lines)


def render_right_external_launch_log(result: dict) -> str:
    """Return right-panel log text for an external terminal launch (pure)."""
    lines = [
        "─── External Terminal Launch ───",
        f"Task:    {result.get('task', '?')}",
        f"Profile: {result.get('profile', '?')}",
    ]
    if result.get("context_pack_path"):
        lines.append(f"Context: {result['context_pack_path']}")
    if result.get("prompt_path"):
        lines.append(f"Prompt:  {result['prompt_path']}")

    if result.get("launched"):
        lines.append(f"Terminal: {result.get('terminal_kind', '?')}")
        if result.get("pid"):
            lines.append(f"PID:     {result['pid']}")
        if result.get("command"):
            lines.append(f"Command: {result['command']}")
        lines.append("Result:  LAUNCHED")
    else:
        lines.append("Result:  FAILED")
        if result.get("error_message"):
            lines.append(f"Error:   {result['error_message']}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Pure rendering helpers (testable without Textual)
# ---------------------------------------------------------------------------


def _manual_files_label(status: object) -> str:
    total = len(status.manual_truth)  # type: ignore[attr-defined]
    present = status.manual_truth_count  # type: ignore[attr-defined]
    if total == 0 or present == 0:
        return "missing"
    return "ok" if present == total else "warn"


def _checks_label_from_disk(repo_path: Path) -> str:
    """Read check_results.json and return a status string."""
    cr = repo_path / ".vibecode" / "current" / "check_results.json"
    try:
        data = json.loads(cr.read_text(encoding="utf-8"))
        s = data.get("status", "unknown")
        return "pass" if s == "ok" else ("fail" if s in ("fail", "error") else s)
    except Exception:  # noqa: BLE001
        return "warn"


def render_status_lines(
    repo_path: Path,
    status: object,
    *,
    checks_str: str | None = None,
) -> list[str]:
    """Return left-panel status lines derived from *status*.

    Pure when *checks_str* is provided; reads ``check_results.json`` otherwise.
    Exported for tests.
    """
    vcode = "yes" if status.vibecode_dir_exists else "no"  # type: ignore[attr-defined]
    manual = _manual_files_label(status)
    index = status.index_freshness  # type: ignore[attr-defined]
    context = "ready" if status.context_pack_exists else "missing"  # type: ignore[attr-defined]
    git = status.git_state  # type: ignore[attr-defined]
    if checks_str is None:
        checks_str = (
            _checks_label_from_disk(repo_path)
            if status.check_results_exist  # type: ignore[attr-defined]
            else "not run"
        )
    return [
        f"  .vibecode exists: {vcode}",
        f"  manual files: {manual}",
        f"  generated index: {index}",
        f"  current context: {context}",
        f"  checks: {checks_str}",
        f"  git state: {git}",
    ]


def render_left_panel(
    repo_path: Path,
    status: object,
    *,
    checks_str: str | None = None,
) -> str:
    """Return the complete left-panel text for *repo_path* and *status*.

    Pure when *checks_str* is provided; reads disk otherwise.
    Exported for tests.
    """
    lines = render_status_lines(repo_path, status, checks_str=checks_str)
    status_block = "\n".join(lines)
    return (
        "VibecodeApp\n\n"
        f"Active repo:\n  {repo_path}\n\n"
        f"Status:\n{status_block}\n\n"
        f"{_ACTIONS_TEXT}"
    )


# ---------------------------------------------------------------------------
# Textual TUI application
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Event sink bridge (main TUI)
# ---------------------------------------------------------------------------


class MainAppEventSink:
    """Routes VibecodeEvents from the RunController thread into VibecodeMainApp.

    Uses Textual's ``call_from_thread`` to safely transfer calls from the
    background worker thread to the Textual event loop.
    """

    def __init__(self, app: "VibecodeMainApp") -> None:
        self._app = app

    def emit(self, event: object) -> None:
        self._app.call_from_thread(self._app.handle_run_event, event)


if _TEXTUAL_AVAILABLE:

    class ContextInputScreen(Screen):
        """Single-field input screen for entering a task description."""

        BINDINGS = [
            Binding("escape", "cancel", "Cancel"),
        ]

        def compose(self) -> ComposeResult:
            yield Label(
                "Enter task description (Enter to confirm, Escape to cancel):",
                id="context-input-label",
            )
            yield Input(
                placeholder="e.g. Add pagination to the user list endpoint",
                id="context-input",
            )

        def on_mount(self) -> None:
            self.query_one("#context-input", Input).focus()

        def on_input_submitted(self, event: Input.Submitted) -> None:
            task = event.value.strip()
            self.dismiss(task or None)

        def action_cancel(self) -> None:
            self.dismiss(None)

    class VibecodeMainApp(App):
        """Primary three-column control shell for vibecode.

        Left panel  — status overview and action menu.
        Center panel— agent console (Phase 1 / Phase 2).
        Right panel — Vibecode event log.
        """

        TITLE = "VibecodeApp"
        CSS_PATH = Path(__file__).with_name("tui_theme.tcss")
        BINDINGS = [
            Binding("r", "refresh_repo", "Refresh"),
            Binding("l", "reload_debug", "Reload debug"),
            Binding("i", "inspect_map", "Inspect map"),
            Binding("c", "cmd_context", "Context"),
            Binding("a", "cmd_audit", "Audit"),
            Binding("s", "cmd_safe", "Safe run"),
            Binding("e", "cmd_external", "External terminal"),
            Binding("g", "cmd_guard", "Guard"),
            Binding("t", "cmd_tests", "Tests"),
            Binding("h", "cmd_handoff", "Handoff"),
            Binding("q", "app.exit", "Quit"),
        ]

        def __init__(
            self,
            repo_path: Path,
            status: object,
            refresh_service: object | None = None,
            context_service: object | None = None,
            inspect_service: object | None = None,
            guard_service: object | None = None,
            check_service: object | None = None,
            handoff_service: object | None = None,
            run_service: object | None = None,
            external_terminal_service: object | None = None,
            provider: object | None = None,
        ) -> None:
            super().__init__()
            self._repo_path = repo_path
            self._status = status
            self._refresh_service = refresh_service
            self._context_service = context_service
            self._inspect_service = inspect_service
            self._guard_service = guard_service
            self._check_service = check_service
            self._handoff_service = handoff_service
            self._run_service = run_service
            self._external_terminal_service = external_terminal_service
            if provider is not None:
                self._provider = provider
            else:
                from vibecode.adapters.provider import get_default_provider
                self._provider = get_default_provider()
            self._provider_status = self._provider.check_availability()  # type: ignore[attr-defined]
            self._current_task: str | None = None
            self._pending_run_profile: str | None = None
            self._pending_external_profile: str | None = None
            self._event_model = TuiEventLog()
            self._artifact_watcher = SessionArtifactWatcher(self._repo_path)
            self._artifact_snapshot: dict[str, Any] = self._artifact_watcher.snapshot()
            self._refresh_report: dict[str, Any] | None = None
            self._last_context_preview: dict[str, Any] | None = None
            self._last_run_result: dict[str, Any] | None = None
            self._last_guard_result: dict[str, Any] | None = None
            self._last_check_result: dict[str, Any] | None = None
            self._last_handoff_result: dict[str, Any] | None = None
            self._next_recommended_action = "Use [R] refresh, [C] context, or [L] reload debug state."

        def _get_refresh_service(self) -> object:
            if self._refresh_service is None:
                from vibecode.refresh import VibecodeRefreshService

                self._refresh_service = VibecodeRefreshService(self._repo_path)
            return self._refresh_service

        def _get_context_service(self) -> object:
            if self._context_service is None:
                self._context_service = ContextPreviewService()
            return self._context_service

        def _get_inspect_service(self) -> object:
            if self._inspect_service is None:
                self._inspect_service = InspectMapService()
            return self._inspect_service

        def _get_guard_service(self) -> object:
            if self._guard_service is None:
                self._guard_service = GuardService()
            return self._guard_service

        def _get_check_service(self) -> object:
            if self._check_service is None:
                self._check_service = CheckService()
            return self._check_service

        def _get_handoff_service(self) -> object:
            if self._handoff_service is None:
                self._handoff_service = HandoffService()
            return self._handoff_service

        def _get_run_service(self) -> object:
            if self._run_service is None:
                self._run_service = AgentRunService()
            return self._run_service

        def _get_external_terminal_service(self) -> object:
            if self._external_terminal_service is None:
                self._external_terminal_service = ExternalTerminalService()
            return self._external_terminal_service

        # ------------------------------------------------------------------
        # Compose
        # ------------------------------------------------------------------

        def compose(self) -> ComposeResult:
            left_text = render_left_panel(self._repo_path, self._status)
            provider_name = self._provider.display_name  # type: ignore[attr-defined]
            provider_status = self._provider_status  # type: ignore[attr-defined]
            placeholder = _make_center_placeholder(
                provider_name,
                available=provider_status.available,  # type: ignore[attr-defined]
                status_msg=provider_status.message,  # type: ignore[attr-defined]
            )
            yield Label("VibecodeApp — Control Shell", id="main-tui-title")
            with Horizontal(id="tui-columns"):
                with Vertical(id="left-panel"):
                    yield Label("Status / Actions", id="left-panel-label")
                    yield Static(left_text, id="left-status")
                with Vertical(id="center-panel"):
                    yield Label("Agent Console", id="center-panel-label")
                    yield Static(placeholder, id="center-status")
                    yield RichLog(id="center-output", highlight=False, markup=False)
                with Vertical(id="right-panel"):
                    yield Label("Vibecode Debug", id="right-panel-label")
                    yield Static("", id="right-debug-cockpit")
                    yield Label("Event Stream", id="right-stream-label")
                    yield RichLog(id="main-event-log", highlight=False, markup=False)
            yield Footer()

        def on_mount(self) -> None:
            self._log_event("[ready] VibecodeApp started.")
            self._log_event(f"[repo]  {self._repo_path}")
            self._refresh_debug_cockpit()

        # ------------------------------------------------------------------
        # Actions
        # ------------------------------------------------------------------

        def action_refresh_repo(self) -> None:
            """Trigger a Vibecode refresh / rebuild in a background thread."""
            self._log_event("[R] Refresh started...")
            svc = self._get_refresh_service()

            def _worker() -> None:
                try:
                    report = svc.refresh()  # type: ignore[attr-defined]
                    self.call_from_thread(self._on_refresh_done, report)
                except Exception as exc:  # noqa: BLE001
                    self.call_from_thread(self._on_refresh_error, str(exc))

            threading.Thread(target=_worker, daemon=True, name="tui-refresh").start()

        def action_reload_debug(self) -> None:
            """Manual reload of right-panel artifact/session state."""
            self._log_event("[L] Reloading right-panel debug state...")
            self._artifact_snapshot = self._artifact_watcher.snapshot(
                self._artifact_snapshot.get("session_id")
            )
            self._refresh_debug_cockpit()
            self._log_event("[L] Right-panel debug state refreshed.")

        def action_inspect_map(self) -> None:
            """Load repo map summary into the right panel."""
            self._log_event("[I] Inspecting repo map...")
            svc = self._get_inspect_service()

            def _worker() -> None:
                try:
                    result = svc.run(self._repo_path)  # type: ignore[attr-defined]
                    self.call_from_thread(self._on_inspect_done, result)
                except Exception as exc:  # noqa: BLE001
                    self.call_from_thread(self._on_inspect_error, str(exc))

            threading.Thread(target=_worker, daemon=True, name="tui-inspect").start()

        def action_cmd_context(self) -> None:
            """Prompt for a task and generate context artifacts."""
            if not (self._repo_path / ".vibecode").exists():
                self._log_event(
                    "[C] .vibecode not found. Run 'vibecode init' or [R] Refresh first."
                )
                return
            self.push_screen(ContextInputScreen(), self._on_context_task_received)

        def action_cmd_audit(self) -> None:
            """Prompt for a task (or reuse current) and start an audit-profile run."""
            if not self._provider.supports_internal_run:  # type: ignore[attr-defined]
                self._log_event(f"[A] Internal run not supported by {self._provider.display_name}.")  # type: ignore[attr-defined]
                return
            if not self._provider_status:  # type: ignore[attr-defined]
                self._log_event(f"[A] Provider unavailable: {self._provider_status.message}")  # type: ignore[attr-defined]
                return
            self._start_run("audit")

        def action_cmd_safe(self) -> None:
            """Prompt for a task (or reuse current) and start a safe-profile run."""
            if not self._provider.supports_internal_run:  # type: ignore[attr-defined]
                self._log_event(f"[S] Internal run not supported by {self._provider.display_name}.")  # type: ignore[attr-defined]
                return
            if not self._provider_status:  # type: ignore[attr-defined]
                self._log_event(f"[S] Provider unavailable: {self._provider_status.message}")  # type: ignore[attr-defined]
                return
            self._start_run("safe")

        def action_cmd_external(self) -> None:
            """Prompt for a task (or reuse current) and launch in external terminal."""
            if not self._provider.supports_external_launch:  # type: ignore[attr-defined]
                self._log_event(f"[E] External launch not supported by {self._provider.display_name}.")  # type: ignore[attr-defined]
                return
            if not self._provider_status:  # type: ignore[attr-defined]
                self._log_event(f"[E] Provider unavailable: {self._provider_status.message}")  # type: ignore[attr-defined]
                return
            self._start_external("safe")

        def action_cmd_guard(self) -> None:
            """Run guard and show results in right panel."""
            self._log_event("[G] Running guard...")
            svc = self._get_guard_service()

            def _worker() -> None:
                try:
                    result = svc.run(self._repo_path)  # type: ignore[attr-defined]
                    self.call_from_thread(self._on_guard_done, result)
                except Exception as exc:  # noqa: BLE001
                    self.call_from_thread(self._on_guard_error, str(exc))

            threading.Thread(target=_worker, daemon=True, name="tui-guard").start()

        def action_cmd_tests(self) -> None:
            """Run required checks and show results in right panel."""
            self._log_event("[T] Running checks...")
            svc = self._get_check_service()

            def _worker() -> None:
                try:
                    result = svc.run(self._repo_path)  # type: ignore[attr-defined]
                    self.call_from_thread(self._on_check_done, result)
                except Exception as exc:  # noqa: BLE001
                    self.call_from_thread(self._on_check_error, str(exc))

            threading.Thread(target=_worker, daemon=True, name="tui-checks").start()

        def action_cmd_handoff(self) -> None:
            """Run handoff check and show results in right panel."""
            self._log_event("[H] Running handoff check...")
            svc = self._get_handoff_service()

            def _worker() -> None:
                try:
                    result = svc.run(self._repo_path)  # type: ignore[attr-defined]
                    self.call_from_thread(self._on_handoff_done, result)
                except Exception as exc:  # noqa: BLE001
                    self.call_from_thread(self._on_handoff_error, str(exc))

            threading.Thread(target=_worker, daemon=True, name="tui-handoff").start()

        # ------------------------------------------------------------------
        # Internal helpers
        # ------------------------------------------------------------------

        def _refresh_debug_cockpit(self) -> None:
            """Render/update the right debug cockpit panel."""
            text = render_right_debug_cockpit(
                snapshot=self._artifact_snapshot,
                event_log=self._event_model,
                refresh_report=self._refresh_report,
                context_preview=self._last_context_preview,
                run_result=self._last_run_result,
                guard_result=self._last_guard_result,
                check_result=self._last_check_result,
                handoff_result=self._last_handoff_result,
                next_action=self._next_recommended_action,
            )
            try:
                self.query_one("#right-debug-cockpit", Static).update(text)
            except Exception:  # noqa: BLE001
                pass

        def _log_event(
            self,
            message: str,
            *,
            category: str = "event",
            level: str = "info",
        ) -> None:
            try:
                self.query_one("#main-event-log", RichLog).write(message)
            except Exception:  # noqa: BLE001
                pass
            self._event_model.add(message, category=category, level=level)
            self._refresh_debug_cockpit()

        def _on_inspect_done(self, result: dict) -> None:
            self._log_event(render_inspect_map_result(result))
            if result.get("error"):
                self._log_event("[I] Repo map unavailable.")
            else:
                self._log_event("[I] Repo map loaded.")

        def _on_inspect_error(self, error: str) -> None:
            self._log_event(f"[I] Inspect failed: {error}")

        def _on_guard_done(self, result: dict) -> None:
            self._last_guard_result = result
            self._log_event(render_guard_result_summary(result))
            status_text = (
                "[G] Guard: PASSED" if result.get("passed") else
                f"[G] Guard: FAILED ({result.get('errors', 0)} errors, {result.get('warnings', 0)} warnings)"
            )
            if result.get("error"):
                status_text = f"[G] Guard error: {result['error'][:60]}"
            self._log_event(status_text)
            self._refresh_debug_cockpit()
            self._refresh_left_panel()

        def _on_guard_error(self, error: str) -> None:
            self._log_event(f"[G] Guard failed: {error}")

        def _on_check_done(self, result: dict) -> None:
            self._last_check_result = result
            self._log_event(render_check_result_summary(result))
            if result.get("error"):
                status_text = f"[T] Checks error: {result['error'][:60]}"
            elif result.get("failed", 0):
                status_text = f"[T] Checks FAILED ({result['failed']} required failures)"
            else:
                status_text = f"[T] Checks PASSED ({result.get('passed', 0)}/{result.get('total', 0)})"
            self._log_event(status_text)
            self._refresh_debug_cockpit()
            self._refresh_left_panel()

        def _on_check_error(self, error: str) -> None:
            self._log_event(f"[T] Checks failed: {error}")

        def _on_handoff_done(self, result: dict) -> None:
            self._last_handoff_result = result
            self._log_event(render_handoff_result_summary(result))
            if result.get("error"):
                status_text = f"[H] Handoff error: {result['error'][:60]}"
            elif result.get("passed"):
                status_text = "[H] Handoff check: PASSED"
            else:
                status_text = f"[H] Handoff check: FAILED ({len(result.get('issues', []))} issues)"
            self._log_event(status_text)
            self._refresh_debug_cockpit()

        def _on_handoff_error(self, error: str) -> None:
            self._log_event(f"[H] Handoff check failed: {error}")

        def _refresh_left_panel(self) -> None:
            """Re-read repo status and update the left panel."""
            try:
                from vibecode.repo_status import RepoStatusService

                new_status = RepoStatusService().get_status(self._repo_path)
                self._status = new_status
                self.query_one("#left-status", Static).update(
                    render_left_panel(self._repo_path, new_status)
                )
            except Exception:  # noqa: BLE001
                pass

        def _on_context_task_received(self, task: str | None) -> None:
            """Called when ContextInputScreen is dismissed."""
            if not task:
                self._log_event("[C] Context creation cancelled.")
                return
            self._current_task = task
            self._log_event(f"[C] Generating context for: {task[:60]}{'…' if len(task) > 60 else ''}")
            svc = self._get_context_service()

            def _worker() -> None:
                try:
                    preview = svc.run(self._repo_path, task)  # type: ignore[attr-defined]
                    self.call_from_thread(self._on_context_done, preview)
                except Exception as exc:  # noqa: BLE001
                    self.call_from_thread(self._on_context_error, str(exc))

            threading.Thread(target=_worker, daemon=True, name="tui-context").start()

        def _on_context_done(self, preview: dict) -> None:
            """Update center and right panels after context generation."""
            self._last_context_preview = preview
            if preview.get("error"):
                self._log_event(f"[C] Context generation failed: {preview['error']}")
                self._log_event(render_context_preview(preview))
                self._artifact_snapshot = self._artifact_watcher.snapshot(
                    self._artifact_snapshot.get("session_id")
                )
                return

            # Update center panel with task + artifact paths + status.
            center_text = render_center_context_status(
                preview["task"],
                preview["context_pack_path"],
                preview["opencode_prompt_path"],
                provider_name=self._provider.display_name,  # type: ignore[attr-defined]
            )
            try:
                self.query_one("#center-status", Static).update(center_text)
            except Exception:  # noqa: BLE001
                pass

            # Write context preview into the event log (right panel).
            self._log_event(render_context_preview(preview))
            self._log_event(
                f"[C] Context ready — task: {preview['task'][:60]}"
                f"{'…' if len(preview['task']) > 60 else ''}"
            )
            self._artifact_snapshot = self._artifact_watcher.snapshot(
                self._artifact_snapshot.get("session_id")
            )
            self._next_recommended_action = "Use [A] or [S] to run with this context."
            self._refresh_debug_cockpit()

        def _on_context_error(self, error: str) -> None:
            self._log_event(f"[C] Context generation error: {error}")

        def _start_run(self, profile: str) -> None:
            """Kick off an agent run in a background thread.

            Prompts for a task first if :attr:`_current_task` is not set.
            """
            if not self._current_task:
                self._pending_run_profile = profile
                self.push_screen(ContextInputScreen(), self._on_run_task_received_for_run)
                return
            self._pending_run_profile = None
            task = self._current_task
            key = profile[0].upper()
            self._log_event(
                f"[{key}] Starting {profile!r} run: "
                f"{task[:60]}{'…' if len(task) > 60 else ''}"
            )
            svc = self._get_run_service()
            sink = MainAppEventSink(self)

            center_text = render_center_run_status(
                task, profile, "running...",
                provider_name=self._provider.display_name,  # type: ignore[attr-defined]
            )
            try:
                self.query_one("#center-status", Static).update(center_text)
                self.query_one("#center-output", RichLog).clear()
            except Exception:  # noqa: BLE001
                pass

            def _worker() -> None:
                try:
                    result = svc.run(  # type: ignore[attr-defined]
                        self._repo_path,
                        task,
                        profile,
                        allow_dirty=True,
                        sink=sink,
                    )
                    self.call_from_thread(self._on_run_done, result)
                except Exception as exc:  # noqa: BLE001
                    self.call_from_thread(self._on_run_error, str(exc))

            threading.Thread(
                target=_worker, daemon=True, name=f"tui-run-{profile}"
            ).start()

        def _on_run_task_received_for_run(self, task: str | None) -> None:
            """Called when ContextInputScreen is dismissed during a run action."""
            profile = self._pending_run_profile
            self._pending_run_profile = None
            if not task:
                key = profile[0].upper() if profile else "A/S"
                self._log_event(f"[{key}] Run cancelled — no task entered.")
                return
            self._current_task = task
            if profile:
                self._start_run(profile)

        def handle_run_event(self, event: object) -> None:
            """Route a VibecodeEvent from the run worker into the TUI panels."""
            from vibecode.monitor_app import (
                format_agent_line,
                format_vibecode_line,
                route_event,
            )

            pane = route_event(event)  # type: ignore[arg-type]
            if pane == "agent":
                try:
                    self.query_one("#center-output", RichLog).write(
                        format_agent_line(event)  # type: ignore[arg-type]
                    )
                except Exception:  # noqa: BLE001
                    pass
            else:
                category = "vibecode"
                event_type = getattr(event, "type", "")
                if event_type in ("run.context", "run.prompt"):
                    category = "context"
                elif event_type in ("run.guard", "run.check", "run.handoff", "run.guard_finding"):
                    category = "validation"
                self._log_event(
                    format_vibecode_line(event),  # type: ignore[arg-type]
                    category=category,
                    level=getattr(getattr(event, "level", None), "name", "info").lower(),
                )

        def _on_run_done(self, result: dict) -> None:
            """Update panels and refresh status after an agent run completes."""
            self._last_run_result = result
            final_text = render_center_run_status(
                result.get("task", ""),
                result.get("profile", ""),
                result.get("overall_status", "unknown"),
                session_id=result.get("session_id"),
                run_dir=result.get("run_dir"),
                provider_name=self._provider.display_name,  # type: ignore[attr-defined]
            )
            try:
                self.query_one("#center-status", Static).update(final_text)
            except Exception:  # noqa: BLE001
                pass
            self._log_event(render_right_run_result(result))
            profile = result.get("profile", "?")
            status = result.get("overall_status", "?")
            key = profile[0].upper() if profile else "?"
            self._log_event(f"[{key}] Run complete: {status}")
            self._artifact_snapshot = self._artifact_watcher.snapshot(result.get("session_id"))
            self._next_recommended_action = "Review artifacts; run [G], [T], or [H] if needed."
            self._refresh_debug_cockpit()
            self._refresh_left_panel()

        def _on_run_error(self, error: str) -> None:
            """Log an unhandled exception from the run worker."""
            self._log_event(f"[A/S] Run worker error: {error}")
            self._next_recommended_action = "Inspect run artifacts and retry after fixing the error."
            self._refresh_debug_cockpit()

        def _start_external(self, profile: str) -> None:
            """Kick off an external terminal launch in a background thread.

            Prompts for a task first if :attr:`_current_task` is not set.
            """
            if not self._current_task:
                self._pending_external_profile = profile
                self.push_screen(ContextInputScreen(), self._on_external_task_received)
                return
            self._pending_external_profile = None
            task = self._current_task
            self._log_event(
                f"[E] Launching external terminal ({profile!r}): "
                f"{task[:60]}{'…' if len(task) > 60 else ''}"
            )
            svc = self._get_external_terminal_service()

            center_text = (
                f"Provider: {self._provider.display_name}\n"  # type: ignore[attr-defined]
                f"Profile:  {profile}\n"
                f"Task:     {task[:80]}{'…' if len(task) > 80 else ''}\n\n"
                "Status: launching external terminal…"
            )
            try:
                self.query_one("#center-status", Static).update(center_text)
            except Exception:  # noqa: BLE001
                pass

            def _worker() -> None:
                try:
                    result = svc.run(  # type: ignore[attr-defined]
                        self._repo_path, task, profile
                    )
                    self.call_from_thread(self._on_external_done, result)
                except Exception as exc:  # noqa: BLE001
                    self.call_from_thread(self._on_external_error, str(exc))

            threading.Thread(
                target=_worker, daemon=True, name="tui-external"
            ).start()

        def _on_external_task_received(self, task: str | None) -> None:
            """Called when ContextInputScreen is dismissed during external launch."""
            profile = self._pending_external_profile
            self._pending_external_profile = None
            if not task:
                self._log_event("[E] External terminal launch cancelled — no task entered.")
                return
            self._current_task = task
            if profile:
                self._start_external(profile)

        def _on_external_done(self, result: dict) -> None:
            """Update center and right panels after external terminal launch."""
            center_text = render_center_external_launch_status(
                result,
                provider_name=self._provider.display_name,  # type: ignore[attr-defined]
            )
            try:
                self.query_one("#center-status", Static).update(center_text)
            except Exception:  # noqa: BLE001
                pass
            self._log_event(render_right_external_launch_log(result))
            if result.get("launched"):
                self._log_event(
                    f"[E] External terminal launched ({result.get('terminal_kind', '?')})"
                )
                self._next_recommended_action = "Use the external terminal for interaction, then run [G]/[T]/[H]."
            else:
                self._log_event(
                    f"[E] External terminal launch failed: {result.get('error_message', '?')}"
                )
                self._next_recommended_action = "Fix external launch errors and try [E] again."
            self._artifact_snapshot = self._artifact_watcher.snapshot(
                self._artifact_snapshot.get("session_id")
            )
            self._refresh_debug_cockpit()

        def _on_external_error(self, error: str) -> None:
            """Log an unhandled exception from the external terminal worker."""
            self._log_event(f"[E] External terminal worker error: {error}")

        def _on_refresh_done(self, report: object) -> None:
            self._refresh_report = {
                "validation_status": getattr(report, "validation_status", "unknown"),
                "generated_artifacts": list(getattr(report, "generated_artifacts", []) or []),
                "warnings": list(getattr(report, "warnings", []) or []),
                "errors": list(getattr(report, "errors", []) or []),
                "next_recommended_action": getattr(report, "next_recommended_action", ""),
            }
            self._log_event(
                f"[R] Refresh complete: {report.validation_status}"  # type: ignore[attr-defined]
            )
            for w in list(report.warnings)[:5]:  # type: ignore[attr-defined]
                self._log_event(f"    WARN: {w}")
            for e in list(report.errors)[:5]:  # type: ignore[attr-defined]
                self._log_event(f"    ERROR: {e}")
            arts = list(report.generated_artifacts)  # type: ignore[attr-defined]
            if arts:
                self._log_event(f"    artifacts: {len(arts)} written")
                for a in list(arts)[:20]:
                    self._log_event(f"      {a}")
            nxt = report.next_recommended_action  # type: ignore[attr-defined]
            if nxt:
                self._log_event(f"    → {nxt}")
                self._next_recommended_action = str(nxt)

            # Re-read status and refresh left panel.
            try:
                from vibecode.repo_status import RepoStatusService

                new_status = RepoStatusService().get_status(self._repo_path)
                self._status = new_status
                self.query_one("#left-status", Static).update(
                    render_left_panel(self._repo_path, new_status)
                )
                ctx_path = self._repo_path / ".vibecode" / "current" / "context_pack.md"
                if ctx_path.exists():
                    self._log_event(f"    context pack: {ctx_path}")
            except Exception as exc:  # noqa: BLE001
                self._log_event(f"    status refresh failed: {exc}")
            self._artifact_snapshot = self._artifact_watcher.snapshot(
                self._artifact_snapshot.get("session_id")
            )
            self._refresh_debug_cockpit()

        def _on_refresh_error(self, error: str) -> None:
            self._log_event(f"[R] Refresh failed: {error}")
            self._refresh_report = {
                "validation_status": "error",
                "generated_artifacts": [],
                "warnings": [],
                "errors": [error],
                "next_recommended_action": "Fix refresh errors, then run [L] to reload artifact state.",
            }
            self._next_recommended_action = self._refresh_report["next_recommended_action"]
            self._refresh_debug_cockpit()

else:

    class ContextInputScreen:  # type: ignore[no-redef]
        """Stub when Textual is not installed."""

        def __init__(self, **kwargs: object) -> None:
            pass

    class VibecodeMainApp:  # type: ignore[no-redef]
        """Stub when Textual is not installed."""

        def __init__(self, **kwargs: object) -> None:
            pass

        def run(self) -> None:  # pragma: no cover
            pass


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def cmd_tui(args: object) -> int:
    """Bootstrap and launch the main Vibecode TUI.

    Resolves the repository path (explicit → registry → cwd), computes repo
    status, then launches the TUI.  Returns 1 with an install hint when the
    ``textual`` package is not available.
    """
    from vibecode.repo_resolution import RepoResolutionService
    from vibecode.repo_status import RepoStatusService

    explicit_repo: str | None = getattr(args, "repo", None)
    resolver = RepoResolutionService()
    repo_path = resolver.resolve(explicit_repo)

    status_service = RepoStatusService()
    status = status_service.get_status(repo_path)

    if not _TEXTUAL_AVAILABLE:
        print(
            "Error: the 'textual' package is required to run 'vibecode'.\n"
            "Install it with:  pip install 'vibecode[tui]'\n"
            "  or:            pip install textual",
            file=sys.stderr,
        )
        return 1

    VibecodeMainApp(repo_path=repo_path, status=status).run()
    return 0
