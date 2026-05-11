"""Textual TUI live monitor for vibecode run sessions.

Launches a split-pane terminal UI:
  - Left pane: OpenCode agent stdout/stderr stream (EVENT_AGENT_PROCESS events).
  - Right pane: Vibecode event spine (lifecycle, guard, checks, handoff, …).
  - Status bar: agent status, guard status, checks status, run artifact path.

The monitor runs RunController in a daemon thread and routes events to the TUI
via Textual's call_from_thread() bridge.

Note: this is a streaming-output monitor (text mode), not a PTY.  Full
interactive terminal control requires running OpenCode directly.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Label, RichLog, Static

from vibecode.events import (
    VibecodeEvent,
    EVENT_AGENT_PROCESS,
    EVENT_CHECK,
    EVENT_CONTEXT,
    EVENT_GUARD,
    EVENT_GUARD_FINDING,
    EVENT_PROMPT,
    EVENT_RUN_LIFECYCLE,
)


# ---------------------------------------------------------------------------
# Pure formatting helpers (testable without a TUI)
# ---------------------------------------------------------------------------


def format_agent_line(event: VibecodeEvent) -> str:
    """Format an EVENT_AGENT_PROCESS event for the agent output pane.

    Returns a plain string suitable for ``RichLog.write()``.
    """
    data = event.data or {}
    phase = data.get("phase", "stdout")
    # For live stdout/stderr lines the message is already stripped of trailing
    # newlines by _read_stream; fall back to the raw text field if present.
    text = event.message.rstrip("\n\r")
    if phase == "stderr":
        return f"[stderr] {text}"
    if phase in ("started", "finished", "preflight_failed"):
        return f"[{phase.upper()}] {text}"
    return text


def format_vibecode_line(event: VibecodeEvent) -> str:
    """Format any non-agent VibecodeEvent for the event pane.

    Returns a plain string suitable for ``RichLog.write()``.
    """
    ts = event.timestamp.strftime("%H:%M:%S")
    data = event.data or {}

    if event.type == EVENT_CONTEXT:
        snapshot = data.get("snapshot_path")
        fallback = data.get("path")
        artifact = snapshot or fallback
        if artifact:
            return f"[{ts}] {event.level.name:7s} {event.type}: {event.message}  ({artifact})"
        return f"[{ts}] {event.level.name:7s} {event.type}: {event.message}"

    if event.type == EVENT_PROMPT:
        snapshot = data.get("snapshot_path")
        fallback = data.get("path")
        artifact = snapshot or fallback
        platform = data.get("platform", "")
        profile = data.get("profile", "")
        extra = "  ".join(
            p for p in [f"({artifact})" if artifact else "", platform, profile] if p
        )
        if extra:
            return f"[{ts}] {event.level.name:7s} {event.type}: {event.message}  {extra}"
        return f"[{ts}] {event.level.name:7s} {event.type}: {event.message}"

    if event.type == EVENT_GUARD_FINDING:
        severity = data.get("severity", "warning")
        category = data.get("category", "")
        path_ = data.get("path", "")
        title = data.get("title", event.message)
        fix = data.get("recommended_fix", "")
        tests = data.get("required_tests", [])
        parts = [severity.upper()]
        if category:
            parts.append(category)
        if path_:
            parts.append(path_)
        parts.append(title)
        if fix:
            parts.append(f"fix: {fix[:80]}")
        if tests:
            parts.append(f"tests: {', '.join(tests[:3])}")
        detail = " | ".join(parts)
        return f"[{ts}] {event.level.name:7s} {event.type}: {detail}"

    return f"[{ts}] {event.level.name:7s} {event.type}: {event.message}"


def route_event(event: VibecodeEvent) -> str:
    """Return ``'agent'`` for agent process events, ``'event'`` for all others."""
    return "agent" if event.type == EVENT_AGENT_PROCESS else "event"


# ---------------------------------------------------------------------------
# Event sink bridge
# ---------------------------------------------------------------------------


class TUIEventSink:
    """Routes events from the RunController thread into the MonitorApp.

    Uses Textual's ``call_from_thread`` to safely transfer calls from the
    worker thread to the Textual event loop.
    """

    def __init__(self, app: "MonitorApp") -> None:
        self._app = app

    def emit(self, event: VibecodeEvent) -> None:
        self._app.call_from_thread(self._app.handle_vibecode_event, event)


# ---------------------------------------------------------------------------
# Textual TUI application
# ---------------------------------------------------------------------------


class MonitorApp(App):
    """Live TUI monitor for a vibecode run session.

    Splits the terminal into an agent-output pane (left) and a Vibecode event
    pane (right).  A status bar at the bottom shows agent status, guard status,
    checks status, and the run artifact directory.
    """

    CSS_PATH = Path(__file__).with_name("tui_theme.tcss")
    TITLE = "Vibecode Monitor"
    BINDINGS = [
        Binding("q", "app.exit", "Quit"),
    ]

    def __init__(
        self,
        repo_root: Path,
        task: str,
        platform: str,
        profile: str,
        allow_dirty: bool,
        no_index: bool,
        guard_mode: str,
        session_id: str | None = None,
    ) -> None:
        super().__init__()
        self._repo_root = repo_root
        self._task = task
        self._platform = platform
        self._profile = profile
        self._allow_dirty = allow_dirty
        self._no_index = no_index
        self._guard_mode = guard_mode
        self._session_id = session_id
        self._run_thread: threading.Thread | None = None
        # Status fields updated by event routing or post-run callbacks.
        self._agent_status = "waiting"
        self._guard_status = "—"
        self._check_status = "—"
        self._run_path = "—"
        self._guard_errors = 0
        self._guard_warnings = 0

    # ------------------------------------------------------------------
    # Compose
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        repo = str(self._repo_root)
        task_short = self._task[:70] + ("…" if len(self._task) > 70 else "")
        yield Label(
            f"repo: {repo}  |  platform: {self._platform}  |  profile: {self._profile}",
            id="monitor-header",
        )
        yield Label(f"task: {task_short}", id="monitor-task")
        with Horizontal(id="monitor-panes"):
            with Vertical(id="agent-pane"):
                yield Label("Agent (stdout / stderr)", id="agent-pane-label")
                yield RichLog(id="agent-log", highlight=False, markup=False)
            with Vertical(id="event-pane"):
                yield Label("Vibecode Events", id="event-pane-label")
                yield RichLog(id="event-log", highlight=False, markup=False)
        with Horizontal(id="monitor-status-bar"):
            yield Static("", id="status-agent")
            yield Static("", id="status-guard")
            yield Static("", id="status-checks")
            yield Static("", id="status-path")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_status()
        sink = TUIEventSink(self)
        from vibecode.run import RunController

        controller = RunController(
            root=self._repo_root,
            task=self._task,
            platform=self._platform,
            profile_name=self._profile,
            allow_dirty=self._allow_dirty,
            no_index=self._no_index,
            guard_mode=self._guard_mode,
            sink=sink,
            session_id=self._session_id,
        )

        def _worker() -> None:
            try:
                summary, _rc = controller.execute()
                if summary is not None:
                    self.call_from_thread(self._on_run_finished, summary)
                else:
                    self.call_from_thread(self._on_run_error, "Run aborted (see event pane)")
            except Exception as exc:  # noqa: BLE001
                self.call_from_thread(self._on_run_error, str(exc))

        self._run_thread = threading.Thread(
            target=_worker, daemon=True, name="monitor-run"
        )
        self._run_thread.start()

    # ------------------------------------------------------------------
    # Event routing (called on TUI thread via call_from_thread)
    # ------------------------------------------------------------------

    def handle_vibecode_event(self, event: VibecodeEvent) -> None:
        """Route an event to the correct pane and update the status bar."""
        pane = route_event(event)
        if pane == "agent":
            line = format_agent_line(event)
            self.query_one("#agent-log", RichLog).write(line)
        else:
            line = format_vibecode_line(event)
            self.query_one("#event-log", RichLog).write(line)

        # Track coarse status from lifecycle/guard/check events.
        if event.type == EVENT_RUN_LIFECYCLE:
            data = event.data or {}
            if data.get("phase") == "started":
                self._agent_status = "running"
                self._refresh_status()
        elif event.type == EVENT_GUARD_FINDING:
            data = event.data or {}
            sev = data.get("severity", "warning")
            if sev == "error":
                self._guard_errors += 1
            else:
                self._guard_warnings += 1
        elif event.type == EVENT_GUARD:
            data = event.data or {}
            if data.get("phase") == "completed":
                passed = data.get("passed", True)
                if passed:
                    self._guard_status = "✓ passed"
                else:
                    errs = data.get("errors", self._guard_errors)
                    warns = data.get("warnings", self._guard_warnings)
                    parts = []
                    if errs:
                        parts.append(f"{errs} errors")
                    if warns:
                        parts.append(f"{warns} warnings")
                    self._guard_status = f"✗ {', '.join(parts)}" if parts else "✗ findings"
                self._refresh_status()
        elif event.type == EVENT_CHECK:
            data = event.data or {}
            if data.get("phase") == "completed":
                passed = data.get("passed", True)
                self._check_status = "✓ passed" if passed else "✗ failed"
                self._refresh_status()

    def _on_run_finished(self, summary: Any) -> None:
        self._agent_status = summary.overall_status
        if summary.guard is not None:
            if summary.guard.passed:
                self._guard_status = "✓ passed"
            else:
                errs = getattr(summary.guard, "errors", self._guard_errors)
                warns = getattr(summary.guard, "warnings", self._guard_warnings)
                parts = []
                if errs:
                    parts.append(f"{errs} errors")
                if warns:
                    parts.append(f"{warns} warnings")
                self._guard_status = f"✗ {', '.join(parts)}" if parts else "✗ findings"
        if summary.checks is not None:
            self._check_status = (
                "✗ failed" if summary.checks.has_required_failures else "✓ passed"
            )
        from vibecode.session_log import RunSession

        session = RunSession(self._repo_root, summary.session_id)
        self._run_path = str(session.run_dir)
        self._refresh_status()

    def _on_run_error(self, error: str) -> None:
        self._agent_status = f"error: {error[:60]}"
        self._refresh_status()

    def _refresh_status(self) -> None:
        self.query_one("#status-agent", Static).update(f"Agent: {self._agent_status}")
        self.query_one("#status-guard", Static).update(f"Guard: {self._guard_status}")
        self.query_one("#status-checks", Static).update(f"Checks: {self._check_status}")
        self.query_one("#status-path", Static).update(f"Run: {self._run_path}")


# ---------------------------------------------------------------------------
# CLI command entry point
# ---------------------------------------------------------------------------


def cmd_monitor(args: Any) -> int:
    """Launch the live monitor TUI.

    Args is expected to have attributes set by the CLI parser:
    ``repo_root``, ``task``, ``platform``, ``profile``, ``allow_dirty``,
    ``no_index``, ``guard_mode``.
    """
    repo_root = Path(args.repo_root)
    task: str = getattr(args, "task", "") or ""
    platform: str = getattr(args, "platform", "opencode") or "opencode"
    profile: str = getattr(args, "profile", None) or "safe"
    allow_dirty: bool = bool(getattr(args, "allow_dirty", False))
    no_index: bool = bool(getattr(args, "no_index", False))
    guard_mode: str = getattr(args, "guard_mode", "advisory") or "advisory"

    MonitorApp(
        repo_root=repo_root,
        task=task,
        platform=platform,
        profile=profile,
        allow_dirty=allow_dirty,
        no_index=no_index,
        guard_mode=guard_mode,
    ).run()
    return 0
