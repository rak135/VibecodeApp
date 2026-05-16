"""External terminal adapter for launching interactive OpenCode sessions.

Phase 2: bridges the Vibecode TUI control panel with a real external terminal
window so OpenCode can run interactively without faking a PTY inside Textual.

Usage pattern
-------------
1. Generate the Vibecode context pack and OpenCode prompt (existing tooling).
2. Construct a :class:`WindowsTerminalOpenCodeAdapter` (or custom adapter).
3. Call ``adapter.launch(repo_root, opencode_command, prompt_path, ...)`` to
   open an external terminal with OpenCode running in the repo directory.
4. Inspect the returned :class:`ExternalTerminalLaunchResult` to display
   status in the TUI.

Terminal detection order on Windows
------------------------------------
1. ``wt.exe`` / ``wt`` — Windows Terminal (preferred).
2. ``pwsh.exe`` / ``pwsh`` — PowerShell 7+.
3. ``powershell.exe`` / ``powershell`` — Windows PowerShell 5.
4. ``cmd.exe`` / ``cmd`` — Command Prompt (minimal fallback).

If none of the above are found (or when running on a non-Windows OS in CI),
the result reports ``terminal_kind="unavailable"`` and ``launched=False``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExternalTerminalLaunchResult:
    """Result of an external terminal launch attempt."""

    launched: bool
    """True when the terminal process was started successfully."""

    command: str
    """Human-readable representation of the launch command (for TUI display)."""

    terminal_kind: str
    """One of ``'windows-terminal'``, ``'powershell'``, ``'cmd'``,
    ``'unavailable'``."""

    pid: int | None
    """OS process ID of the launched terminal, or ``None`` if unavailable."""

    error_message: str | None
    """Error description when ``launched`` is ``False``, else ``None``."""

    def __bool__(self) -> bool:
        return self.launched


# ---------------------------------------------------------------------------
# Command-construction helpers (pure, testable)
# ---------------------------------------------------------------------------


def _quote_ps_single(value: str) -> str:
    """Escape a string for use inside PowerShell single-quoted strings."""
    return value.replace("'", "''")


def build_opencode_shell_command(
    opencode_command: str,
    prompt_path: Path,
    *,
    profile: str | None = None,
    session_id: str | None = None,
) -> str:
    """Return a PowerShell command string that sets context and starts OpenCode.

    The returned string is suitable as the argument to ``powershell -Command``.
    It sets ``VIBECODE_PROMPT_PATH`` (and optional profile / session env vars),
    prints a startup banner, and runs *opencode_command*.

    Parameters
    ----------
    opencode_command:
        The OpenCode invocation string (e.g. ``"opencode"`` or
        ``"opencode run"``).
    prompt_path:
        Absolute path to the generated ``opencode_prompt.md`` file.
    profile:
        Optional Vibecode profile label (e.g. ``"safe"`` or ``"audit"``).
    session_id:
        Optional session / run ID to propagate into the external environment.
    """
    prompt_str = _quote_ps_single(str(prompt_path))
    parts: list[str] = [
        f"$env:VIBECODE_PROMPT_PATH = '{prompt_str}';",
    ]
    if profile:
        parts.append(f"$env:VIBECODE_PROFILE = '{_quote_ps_single(profile)}';")
    if session_id:
        parts.append(f"$env:VIBECODE_SESSION_ID = '{_quote_ps_single(session_id)}';")
    parts += [
        "Write-Host '--- Vibecode external session ---';",
        f"Write-Host 'Prompt: {prompt_str}';",
    ]
    if profile:
        parts.append(f"Write-Host 'Profile: {_quote_ps_single(profile)}';")
    parts.append("Write-Host '---------------------------------';")
    parts.append(opencode_command)
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Terminal detection
# ---------------------------------------------------------------------------


def detect_terminal(
    which_fn: Callable[[str], str | None] | None = None,
) -> str:
    """Return the best available terminal kind on the current platform.

    Returns one of ``'windows-terminal'``, ``'powershell'``, ``'cmd'``,
    or ``'unavailable'``.

    Parameters
    ----------
    which_fn:
        Optional replacement for :func:`shutil.which` (for testing).
    """
    w = which_fn if which_fn is not None else shutil.which
    if os.name == "nt":
        if w("wt.exe") or w("wt"):
            return "windows-terminal"
        if w("pwsh.exe") or w("pwsh"):
            return "powershell"
        if w("powershell.exe") or w("powershell"):
            return "powershell"
        if w("cmd.exe") or w("cmd"):
            return "cmd"
    return "unavailable"


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class WindowsTerminalOpenCodeAdapter:
    """Launch an OpenCode session in an external terminal on Windows.

    Attempts Windows Terminal first, then PowerShell, then cmd.exe.  All
    errors are captured and returned in :class:`ExternalTerminalLaunchResult`;
    this method never raises.

    Dependency injection
    --------------------
    Pass ``_which_fn`` and ``_popen_fn`` in tests to avoid spawning real
    terminal processes or requiring ``wt.exe`` to be installed.

    Example::

        def fake_which(name):
            return "/fake/wt.exe" if "wt" in name else None

        def fake_popen(args, **kw):
            return FakeProc(pid=1234)

        adapter = WindowsTerminalOpenCodeAdapter(
            _which_fn=fake_which, _popen_fn=fake_popen
        )
        result = adapter.launch(repo_root, "opencode", prompt_path)
        assert result.launched
        assert result.pid == 1234
    """

    def __init__(
        self,
        *,
        _which_fn: Callable[[str], str | None] | None = None,
        _popen_fn: Callable | None = None,
    ) -> None:
        self._which: Callable[[str], str | None] = _which_fn or shutil.which
        self._popen: Callable = _popen_fn or subprocess.Popen

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _detect(self) -> str:
        return detect_terminal(which_fn=self._which)

    def _find_ps(self) -> str:
        """Return the best available PowerShell binary path."""
        for name in ("pwsh.exe", "pwsh", "powershell.exe", "powershell"):
            found = self._which(name)
            if found:
                return found
        return "powershell.exe"

    def _find_wt(self) -> str:
        """Return the wt.exe path."""
        return self._which("wt.exe") or self._which("wt") or "wt.exe"  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def launch(
        self,
        repo_root: Path,
        opencode_command: str,
        prompt_path: Path,
        *,
        profile: str | None = None,
        session_id: str | None = None,
        env: dict[str, str] | None = None,
    ) -> ExternalTerminalLaunchResult:
        """Launch *opencode_command* in an external terminal.

        Parameters
        ----------
        repo_root:
            Repository working directory for the terminal session.
        opencode_command:
            OpenCode invocation string (e.g. ``"opencode"``).
        prompt_path:
            Path to the generated ``opencode_prompt.md`` used as context.
        profile:
            Optional profile label (``"safe"`` / ``"audit"``).
        session_id:
            Optional run / session ID injected into the terminal environment.
        env:
            Optional environment mapping.  When ``None`` the child process
            inherits the current environment.

        Returns
        -------
        ExternalTerminalLaunchResult
            Structured result; always returned — never raised.
        """
        terminal = self._detect()

        if terminal == "unavailable":
            return ExternalTerminalLaunchResult(
                launched=False,
                command="",
                terminal_kind="unavailable",
                pid=None,
                error_message=(
                    "No supported terminal emulator found. "
                    "Install Windows Terminal (wt.exe) or ensure "
                    "PowerShell is available on PATH."
                ),
            )

        shell_cmd = build_opencode_shell_command(
            opencode_command,
            prompt_path,
            profile=profile,
            session_id=session_id,
        )
        repo_str = str(repo_root)

        if terminal == "windows-terminal":
            wt = self._find_wt()
            ps = self._find_ps()
            args = [wt, "new-tab", "-d", repo_str, "--", ps, "-NoExit", "-Command", shell_cmd]
            display = (
                f"{os.path.basename(wt)} new-tab -d \"{repo_str}\" "
                f"-- {os.path.basename(ps)} -NoExit -Command <opencode_cmd>"
            )
        else:
            # PowerShell (pwsh or powershell.exe) without Windows Terminal.
            ps = self._find_ps()
            repo_ps = _quote_ps_single(repo_str)
            args = [ps, "-NoExit", "-Command", f"Set-Location '{repo_ps}'; {shell_cmd}"]
            display = (
                f"{os.path.basename(ps)} -NoExit -Command "
                f"\"Set-Location '{repo_str}'; <opencode_cmd>\""
            )

        try:
            proc = self._popen(args, env=env)
            return ExternalTerminalLaunchResult(
                launched=True,
                command=display,
                terminal_kind=terminal,
                pid=proc.pid,
                error_message=None,
            )
        except Exception as exc:  # noqa: BLE001
            return ExternalTerminalLaunchResult(
                launched=False,
                command=display,
                terminal_kind=terminal,
                pid=None,
                error_message=str(exc),
            )
