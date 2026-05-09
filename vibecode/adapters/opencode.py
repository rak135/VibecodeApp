"""OpenCode run adapter.

Detects whether the OpenCode CLI is available and provides a readiness check
without launching a coding session.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class OpenCodeStatus:
    """Result of an OpenCode availability check."""

    available: bool
    """True if the configured command was found and responded successfully."""

    command: str
    """The command that was checked (resolved or default)."""

    message: str
    """Human-readable status message."""

    def __bool__(self) -> bool:
        return self.available


def _default_command() -> str:
    """Return the default OpenCode command name."""
    return "opencode"


def check_opencode(command: str | None = None) -> OpenCodeStatus:
    """Check whether OpenCode is available without starting a session.

    Parameters
    ----------
    command:
        Explicit command path or name.  If ``None``, the default ``opencode``
        (or ``opencode.exe`` on Windows) is used.

    Returns
    -------
    OpenCodeStatus
        An object with ``available``, ``command``, and ``message`` fields.
    """
    resolved = command or _default_command()

    # 1. Check if the binary exists on PATH.
    binary_path = shutil.which(resolved)
    if binary_path is None:
        return OpenCodeStatus(
            available=False,
            command=resolved,
            message=(
                f"OpenCode command '{resolved}' not found on PATH. "
                "Install OpenCode or set the OPENCODE_COMMAND environment "
                "variable to the correct binary path."
            ),
        )

    # 2. Verify it responds to --version without launching a session.
    try:
        result = subprocess.run(
            [binary_path, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        return OpenCodeStatus(
            available=False,
            command=resolved,
            message=f"OpenCode command '{resolved}' timed out during version check.",
        )
    except OSError as exc:
        return OpenCodeStatus(
            available=False,
            command=resolved,
            message=f"OpenCode command '{resolved}' failed to execute: {exc}",
        )

    if result.returncode != 0:
        return OpenCodeStatus(
            available=False,
            command=resolved,
            message=(
                f"OpenCode command '{resolved}' returned exit code "
                f"{result.returncode} (stderr: {result.stderr.strip() or 'none'})"
            ),
        )

    version = result.stdout.strip() or "(unknown version)"
    return OpenCodeStatus(
        available=True,
        command=resolved,
        message=f"OpenCode found: {version} (at {binary_path})",
    )