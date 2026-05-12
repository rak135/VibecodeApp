"""OpenCode run adapter.

Detects whether the OpenCode CLI is available and provides a readiness check
without launching a coding session.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from collections.abc import Mapping


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
    """Return the default non-interactive OpenCode command."""
    return "opencode run"


def resolve_opencode_command(env: Mapping[str, str] | None = None) -> str | None:
    """Resolve the OpenCode command used by run and run-plan.

    ``OPENCODE_COMMAND`` wins even when the default ``opencode`` binary is not
    on PATH.  If no explicit command is configured, return the default
    non-interactive command only when its binary can be found on PATH.
    """
    source = env if env is not None else os.environ
    env_cmd = source.get("OPENCODE_COMMAND")
    if env_cmd:
        return env_cmd
    default_cmd = _default_command()
    if shutil.which(shlex.split(default_cmd)[0]):
        return default_cmd
    return None


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

    # Handle compound commands (e.g. "python /path/to/opencode.py")
    # by splitting and checking only the binary portion with shutil.which.
    # Use shlex.split so that quoted Windows paths (e.g.
    # '"C:\Program Files\OpenCode\opencode.cmd" run') are parsed safely.
    # On Windows, posix=False is required so backslashes are not treated
    # as escape characters; on POSIX, posix=True (the default) preserves
    # standard shell semantics.
    try:
        parts = shlex.split(resolved, posix=(os.name != "nt"))
    except ValueError as exc:
        return OpenCodeStatus(
            available=False,
            command=resolved,
            message=f"OpenCode command could not be parsed: {exc}",
        )
    if not parts:
        return OpenCodeStatus(
            available=False,
            command=resolved,
            message="OpenCode command is empty after parsing.",
        )
    binary = parts[0]
    extra_args = parts[1:]

    # 1. Check if the binary exists on PATH.
    binary_path = shutil.which(binary)
    if binary_path is None:
        return OpenCodeStatus(
            available=False,
            command=resolved,
            message=(
                f"OpenCode command '{binary}' not found on PATH. "
                "Install OpenCode or set the OPENCODE_COMMAND environment "
                "variable to the correct binary path."
            ),
        )

    # 2. Verify the real OpenCode binary responds to --version without
    #    launching a session.  Skip this for arbitrary compound commands
    #    (e.g. "python wrapper.py"), because they may not support --version.
    if not extra_args or binary.lower() == "opencode":
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
                message=f"OpenCode command '{binary}' timed out during version check.",
            )
        except OSError as exc:
            return OpenCodeStatus(
                available=False,
                command=resolved,
                message=f"OpenCode command '{binary}' failed to execute: {exc}",
            )

        if result.returncode != 0:
            return OpenCodeStatus(
                available=False,
                command=resolved,
                message=(
                    f"OpenCode command '{binary}' returned exit code "
                    f"{result.returncode} (stderr: {result.stderr.strip() or 'none'})"
                ),
            )

        version = result.stdout.strip() or "(unknown version)"
        return OpenCodeStatus(
            available=True,
            command=resolved,
            message=f"OpenCode found: {version} (at {binary_path})",
        )

    # Compound command — binary exists.
    # If the first extra arg looks like a local script path, verify it exists
    # so that missing wrapper scripts fail early rather than during agent execution.
    if extra_args:
        script_candidate = extra_args[0]
        if "/" in script_candidate or "\\" in script_candidate or script_candidate.startswith("."):
            if not os.path.exists(script_candidate):
                return OpenCodeStatus(
                    available=False,
                    command=resolved,
                    message=(
                        f"OpenCode script '{script_candidate}' not found. "
                        "Check the OPENCODE_COMMAND value or install the wrapper script."
                    ),
                )

    return OpenCodeStatus(
        available=True,
        command=resolved,
        message=f"OpenCode command found: {resolved}",
    )
