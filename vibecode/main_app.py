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
import sys
import threading
from pathlib import Path

try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical
    from textual.widgets import Footer, Label, RichLog, Static

    _TEXTUAL_AVAILABLE = True
except ImportError:
    _TEXTUAL_AVAILABLE = False


# ---------------------------------------------------------------------------
# Constant text blocks
# ---------------------------------------------------------------------------

_ACTIONS_TEXT = (
    "Actions:\n"
    "  [R] Refresh / Rebuild Vibecode layer\n"
    "  [I] Inspect repo map\n"
    "  [C] Create context for task\n"
    "  [A] Run audit profile\n"
    "  [S] Run safe agent profile\n"
    "  [G] Run guard\n"
    "  [T] Run tests/checks\n"
    "  [H] Handoff check\n"
    "  [Q] Quit"
)

_CENTER_PLACEHOLDER = (
    "Provider: OpenCode\n"
    "Current task: none\n\n"
    "─── Phase 1 placeholder ───\n"
    "No command running.\n\n"
    "Note: A fully embedded interactive terminal is not\n"
    "implemented in Phase 1.  Use 'vibecode monitor'\n"
    "to run an agent session with live output."
)


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

if _TEXTUAL_AVAILABLE:

    class VibecodeMainApp(App):
        """Primary three-column control shell for vibecode.

        Left panel  — status overview and action menu.
        Center panel— agent console (Phase 1: placeholder + output area).
        Right panel — Vibecode event log.
        """

        TITLE = "VibecodeApp"
        CSS_PATH = Path(__file__).with_name("tui_theme.tcss")
        BINDINGS = [
            Binding("r", "refresh_repo", "Refresh"),
            Binding("i", "inspect_map", "Inspect map"),
            Binding("c", "cmd_context", "Context"),
            Binding("a", "cmd_audit", "Audit"),
            Binding("s", "cmd_safe", "Safe run"),
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
        ) -> None:
            super().__init__()
            self._repo_path = repo_path
            self._status = status
            self._refresh_service = refresh_service

        def _get_refresh_service(self) -> object:
            if self._refresh_service is None:
                from vibecode.refresh import VibecodeRefreshService

                self._refresh_service = VibecodeRefreshService(self._repo_path)
            return self._refresh_service

        # ------------------------------------------------------------------
        # Compose
        # ------------------------------------------------------------------

        def compose(self) -> ComposeResult:
            left_text = render_left_panel(self._repo_path, self._status)
            yield Label("VibecodeApp — Control Shell", id="main-tui-title")
            with Horizontal(id="tui-columns"):
                with Vertical(id="left-panel"):
                    yield Label("Status / Actions", id="left-panel-label")
                    yield Static(left_text, id="left-status")
                with Vertical(id="center-panel"):
                    yield Label("Agent Console", id="center-panel-label")
                    yield Static(_CENTER_PLACEHOLDER, id="center-status")
                    yield RichLog(id="center-output", highlight=False, markup=False)
                with Vertical(id="right-panel"):
                    yield Label("Vibecode Events", id="right-panel-label")
                    yield RichLog(id="main-event-log", highlight=False, markup=False)
            yield Footer()

        def on_mount(self) -> None:
            self._log_event("[ready] VibecodeApp started.")
            self._log_event(f"[repo]  {self._repo_path}")

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

        def action_inspect_map(self) -> None:
            """Load repo map into the center output area."""
            map_file = self._repo_path / ".vibecode" / "index" / "repo_tree.generated.md"
            if not map_file.exists():
                self._log_event("[I] Repo map not found. Run 'vibecode index' first.")
                return
            try:
                content = map_file.read_text(encoding="utf-8")
                center = self.query_one("#center-output", RichLog)
                center.clear()
                center.write(content[:4000])
                self._log_event("[I] Repo map loaded into center panel.")
            except Exception as exc:  # noqa: BLE001
                self._log_event(f"[I] Failed to read map: {exc}")

        def action_cmd_context(self) -> None:
            self._log_not_impl("C", "Create context")

        def action_cmd_audit(self) -> None:
            self._log_not_impl("A", "Audit profile")

        def action_cmd_safe(self) -> None:
            self._log_not_impl("S", "Safe agent profile")

        def action_cmd_guard(self) -> None:
            self._log_not_impl("G", "Guard")

        def action_cmd_tests(self) -> None:
            self._log_not_impl("T", "Tests/checks")

        def action_cmd_handoff(self) -> None:
            self._log_not_impl("H", "Handoff check")

        # ------------------------------------------------------------------
        # Internal helpers
        # ------------------------------------------------------------------

        def _log_event(self, message: str) -> None:
            try:
                self.query_one("#main-event-log", RichLog).write(message)
            except Exception:  # noqa: BLE001
                pass

        def _log_not_impl(self, key: str, label: str) -> None:
            self._log_event(f"[{key}] {label}: not implemented yet.")

        def _on_refresh_done(self, report: object) -> None:
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
            nxt = report.next_recommended_action  # type: ignore[attr-defined]
            if nxt:
                self._log_event(f"    → {nxt}")

            # Re-read status and refresh left panel.
            try:
                from vibecode.repo_status import RepoStatusService

                new_status = RepoStatusService().get_status(self._repo_path)
                self._status = new_status
                self.query_one("#left-status", Static).update(
                    render_left_panel(self._repo_path, new_status)
                )
            except Exception as exc:  # noqa: BLE001
                self._log_event(f"    status refresh failed: {exc}")

        def _on_refresh_error(self, error: str) -> None:
            self._log_event(f"[R] Refresh failed: {error}")

else:

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
