"""Main TUI application for vibecode.

Provides the primary TUI launched by ``vibecode`` with no subcommand, and
by the explicit ``vibecode tui [repo]`` alias.

Phase 1 scope: CLI routing + testable services.  The TUI screen is a minimal
status view; the full interactive workflow is out of scope here.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.widgets import Footer, Label

    _TEXTUAL_AVAILABLE = True
except ImportError:
    _TEXTUAL_AVAILABLE = False


if _TEXTUAL_AVAILABLE:

    class VibecodeMainApp(App):
        """Primary TUI entrypoint for vibecode."""

        TITLE = "Vibecode"
        CSS_PATH = Path(__file__).with_name("tui_theme.tcss")
        BINDINGS = [
            Binding("q", "app.exit", "Quit"),
        ]

        def __init__(self, repo_path: Path, status: object) -> None:
            super().__init__()
            self._repo_path = repo_path
            self._status = status

        def compose(self) -> ComposeResult:
            from vibecode.repo_status import RepoStatus

            s: RepoStatus = self._status  # type: ignore[assignment]
            vcode = "✓" if s.vibecode_dir_exists else "✗"
            yield Label(f"Repo:      {self._repo_path}", id="main-repo")
            yield Label(
                f".vibecode: {vcode}  git: {s.git_state}  index: {s.index_freshness}",
                id="main-summary",
            )
            yield Label(
                f"Manual truth: {s.manual_truth_count}/{len(s.manual_truth)}  "
                f"Generated: {s.generated_index_count}/{len(s.generated_index)}",
                id="main-detail",
            )
            yield Label("Press Q to quit.", id="main-hint")
            yield Footer()

else:

    class VibecodeMainApp:  # type: ignore[no-redef]
        """Stub when Textual is not installed."""

        def __init__(self, **kwargs: object) -> None:
            pass

        def run(self) -> None:  # pragma: no cover
            pass


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
