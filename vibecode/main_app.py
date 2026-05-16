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
import re
import sys
import threading
from pathlib import Path

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
) -> str:
    """Return center panel text when context is ready (pure, testable)."""
    task_short = task[:100] + ("…" if len(task) > 100 else "")
    return (
        f"Provider: OpenCode\n"
        f"Current task: {task_short}\n\n"
        f"Context pack:\n  {context_pack_path}\n\n"
        f"OpenCode prompt:\n  {opencode_prompt_path}\n\n"
        "Status: context ready\n\n"
        "─── Next steps ───\n"
        "[A] Audit profile   — run backend not yet wired\n"
        "[S] Safe profile    — run backend not yet wired\n"
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
            context_service: object | None = None,
        ) -> None:
            super().__init__()
            self._repo_path = repo_path
            self._status = status
            self._refresh_service = refresh_service
            self._context_service = context_service
            self._current_task: str | None = None

        def _get_refresh_service(self) -> object:
            if self._refresh_service is None:
                from vibecode.refresh import VibecodeRefreshService

                self._refresh_service = VibecodeRefreshService(self._repo_path)
            return self._refresh_service

        def _get_context_service(self) -> object:
            if self._context_service is None:
                self._context_service = ContextPreviewService()
            return self._context_service

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
            """Prompt for a task and generate context artifacts."""
            if not (self._repo_path / ".vibecode").exists():
                self._log_event(
                    "[C] .vibecode not found. Run 'vibecode init' or [R] Refresh first."
                )
                return
            self.push_screen(ContextInputScreen(), self._on_context_task_received)

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
            if preview.get("error"):
                self._log_event(f"[C] Context generation failed: {preview['error']}")
                self._log_event(render_context_preview(preview))
                return

            # Update center panel with task + artifact paths + status.
            center_text = render_center_context_status(
                preview["task"],
                preview["context_pack_path"],
                preview["opencode_prompt_path"],
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

        def _on_context_error(self, error: str) -> None:
            self._log_event(f"[C] Context generation error: {error}")

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
                for a in list(arts)[:20]:
                    self._log_event(f"      {a}")
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
                ctx_path = self._repo_path / ".vibecode" / "current" / "context_pack.md"
                if ctx_path.exists():
                    self._log_event(f"    context pack: {ctx_path}")
            except Exception as exc:  # noqa: BLE001
                self._log_event(f"    status refresh failed: {exc}")

        def _on_refresh_error(self, error: str) -> None:
            self._log_event(f"[R] Refresh failed: {error}")

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
