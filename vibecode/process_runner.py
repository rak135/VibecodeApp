"""Streaming subprocess runner for agent execution.

Uses two reader threads (one for stdout, one for stderr) to consume process
output concurrently.  This avoids OS-pipe deadlock on Windows when both
streams produce significant output, while emitting live ``EVENT_AGENT_PROCESS``
events and accumulating the full text for log files.

This is a streaming-output MVP — it reads line-by-line in text mode.
Full interactive PTY/ConPTY support is out of scope for this module.
"""

from __future__ import annotations

import os
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from vibecode.events import EVENT_AGENT_PROCESS, EventLevel, EventSink, NullEventSink, create_event


@dataclass
class ProcessResult:
    """Result of a :func:`run_streaming` call."""

    exit_code: int
    stdout: str
    stderr: str


def _kill_process_tree(proc: subprocess.Popen[str]) -> None:
    """Best-effort termination of the shell and child process tree."""
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=10,
            )
            return
        except (OSError, subprocess.TimeoutExpired):
            pass
    proc.kill()


def _read_stream(
    stream: IO[str],
    lines: list[str],
    session_id: str,
    phase: str,
    level: EventLevel,
    sink: EventSink,
) -> None:
    """Thread target: read *stream* line-by-line, accumulate, and emit events.

    Each line (including its trailing newline) is appended to *lines* and
    emitted as an ``EVENT_AGENT_PROCESS`` event with the given *phase* and
    *level*.
    """
    try:
        for line in stream:
            lines.append(line)
            sink.emit(
                create_event(
                    session_id,
                    EVENT_AGENT_PROCESS,
                    level,
                    line.rstrip("\n\r"),
                    data={"phase": phase, "text": line},
                )
            )
    finally:
        stream.close()


def run_streaming(
    command: str,
    stdin_content: str,
    *,
    session_id: str,
    cwd: Path,
    sink: EventSink | None = None,
    stdout_log: Path | None = None,
    stderr_log: Path | None = None,
    timeout: float = 300.0,
) -> ProcessResult:
    """Run *command* with concurrent streaming stdout/stderr capture.

    Opens two reader threads so neither pipe can block the other —
    eliminating the OS-pipe deadlock that ``subprocess.run(capture_output=True)``
    can trigger when both streams produce output on Windows.

    For each stdout line an ``EVENT_AGENT_PROCESS`` event is emitted with
    ``data["phase"] = "stdout"``; for each stderr line ``"phase" = "stderr"``.
    After the process exits the full text is written to *stdout_log* /
    *stderr_log* (if provided) and returned in the :class:`ProcessResult`.

    Parameters
    ----------
    command:
        Shell command string (passed with ``shell=True``).
    stdin_content:
        Text to write to the process stdin before closing.
    session_id:
        Session identifier used when constructing events.
    cwd:
        Working directory for the subprocess.
    sink:
        Event sink for live output events.  Defaults to :class:`NullEventSink`.
    stdout_log:
        Optional path to write the accumulated stdout after the process exits.
    stderr_log:
        Optional path to write the accumulated stderr after the process exits.
    timeout:
        Seconds to wait for the process to finish before killing it.
    """
    effective_sink: EventSink = sink if sink is not None else NullEventSink()

    proc = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(cwd),
        shell=True,
    )

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    def _write_stdin() -> None:
        try:
            if proc.stdin is not None:
                proc.stdin.write(stdin_content)
        finally:
            if proc.stdin is not None:
                proc.stdin.close()

    stdin_thread = threading.Thread(target=_write_stdin, daemon=True, name="runner-stdin")
    stdout_thread = threading.Thread(
        target=_read_stream,
        args=(proc.stdout, stdout_lines, session_id, "stdout", EventLevel.INFO, effective_sink),
        daemon=True,
        name="runner-stdout",
    )
    stderr_thread = threading.Thread(
        target=_read_stream,
        args=(proc.stderr, stderr_lines, session_id, "stderr", EventLevel.WARNING, effective_sink),
        daemon=True,
        name="runner-stderr",
    )

    stdin_thread.start()
    stdout_thread.start()
    stderr_thread.start()

    timed_out = False
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_process_tree(proc)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass

    stdout_thread.join(timeout=10)
    stderr_thread.join(timeout=10)
    stdin_thread.join(timeout=5)

    stdout_text = "".join(stdout_lines)
    stderr_text = "".join(stderr_lines)

    if timed_out:
        stderr_text += f"\nCommand timed out after {timeout} seconds."

    exit_code = proc.returncode if not timed_out else -1

    if stdout_log is not None:
        stdout_log.parent.mkdir(parents=True, exist_ok=True)
        stdout_log.write_text(stdout_text, encoding="utf-8")
    if stderr_log is not None:
        stderr_log.parent.mkdir(parents=True, exist_ok=True)
        stderr_log.write_text(stderr_text, encoding="utf-8")

    return ProcessResult(exit_code=exit_code, stdout=stdout_text, stderr=stderr_text)
