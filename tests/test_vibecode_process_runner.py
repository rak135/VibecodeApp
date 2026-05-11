"""Tests for vibecode.process_runner — streaming subprocess runner.

Tests spin up real child processes (Python scripts) and verify that:
- Exit codes are propagated correctly.
- stdout and stderr are captured fully.
- Log files are written with the correct content.
- AgentStdout / AgentStderr events are emitted for each line.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from vibecode.events import EVENT_AGENT_PROCESS, InMemoryEventSink
from vibecode.process_runner import ProcessResult, run_streaming


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_script(tmp_path: Path, name: str, code: str) -> str:
    """Write *code* to *tmp_path/<name>.py* and return a shell command string."""
    script = tmp_path / name
    script.write_text(code, encoding="utf-8")
    # Quote the executable and script path to handle spaces (Windows-safe).
    exe = sys.executable.replace("\\", "\\\\")
    path = str(script).replace("\\", "\\\\")
    return f'"{exe}" "{path}"'


def _stdout_events(sink: InMemoryEventSink) -> list:
    return [
        e for e in sink.events_by_type(EVENT_AGENT_PROCESS)
        if e.data and e.data.get("phase") == "stdout"
    ]


def _stderr_events(sink: InMemoryEventSink) -> list:
    return [
        e for e in sink.events_by_type(EVENT_AGENT_PROCESS)
        if e.data and e.data.get("phase") == "stderr"
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProcessResultDataclass:
    def test_fields(self) -> None:
        r = ProcessResult(exit_code=0, stdout="out", stderr="err")
        assert r.exit_code == 0
        assert r.stdout == "out"
        assert r.stderr == "err"


class TestRunStreamingStdoutOnly:
    def test_exit_code_zero(self, tmp_path: Path) -> None:
        cmd = _make_script(
            tmp_path,
            "out.py",
            "import sys\nsys.stdout.write('hello stdout\\n')\nsys.exit(0)\n",
        )
        result = run_streaming(cmd, "", session_id="s1", cwd=tmp_path)
        assert result.exit_code == 0

    def test_stdout_captured(self, tmp_path: Path) -> None:
        cmd = _make_script(
            tmp_path,
            "out.py",
            "import sys\nsys.stdout.write('line one\\nline two\\n')\nsys.exit(0)\n",
        )
        result = run_streaming(cmd, "", session_id="s1", cwd=tmp_path)
        assert "line one" in result.stdout
        assert "line two" in result.stdout

    def test_stderr_empty(self, tmp_path: Path) -> None:
        cmd = _make_script(
            tmp_path,
            "out.py",
            "import sys\nsys.stdout.write('only stdout\\n')\nsys.exit(0)\n",
        )
        result = run_streaming(cmd, "", session_id="s1", cwd=tmp_path)
        assert result.stderr == ""

    def test_stdout_log_written(self, tmp_path: Path) -> None:
        cmd = _make_script(
            tmp_path,
            "out.py",
            "import sys\nsys.stdout.write('logged line\\n')\nsys.exit(0)\n",
        )
        stdout_log = tmp_path / "stdout.log"
        run_streaming(cmd, "", session_id="s1", cwd=tmp_path, stdout_log=stdout_log)
        assert stdout_log.exists()
        assert "logged line" in stdout_log.read_text(encoding="utf-8")

    def test_stderr_log_written_empty(self, tmp_path: Path) -> None:
        cmd = _make_script(
            tmp_path,
            "out.py",
            "import sys\nsys.stdout.write('ok\\n')\nsys.exit(0)\n",
        )
        stderr_log = tmp_path / "stderr.log"
        run_streaming(cmd, "", session_id="s1", cwd=tmp_path, stderr_log=stderr_log)
        assert stderr_log.exists()
        assert stderr_log.read_text(encoding="utf-8") == ""

    def test_stdout_events_emitted(self, tmp_path: Path) -> None:
        cmd = _make_script(
            tmp_path,
            "out.py",
            "import sys\nsys.stdout.write('event line\\n')\nsys.exit(0)\n",
        )
        sink = InMemoryEventSink()
        run_streaming(cmd, "", session_id="s1", cwd=tmp_path, sink=sink)
        events = _stdout_events(sink)
        assert len(events) >= 1
        texts = [e.data["text"] for e in events]
        assert any("event line" in t for t in texts)

    def test_no_stderr_events(self, tmp_path: Path) -> None:
        cmd = _make_script(
            tmp_path,
            "out.py",
            "import sys\nsys.stdout.write('only stdout\\n')\nsys.exit(0)\n",
        )
        sink = InMemoryEventSink()
        run_streaming(cmd, "", session_id="s1", cwd=tmp_path, sink=sink)
        assert _stderr_events(sink) == []


class TestRunStreamingStderrOnly:
    def test_exit_code_nonzero(self, tmp_path: Path) -> None:
        cmd = _make_script(
            tmp_path,
            "err.py",
            "import sys\nsys.stderr.write('error line\\n')\nsys.exit(2)\n",
        )
        result = run_streaming(cmd, "", session_id="s2", cwd=tmp_path)
        assert result.exit_code == 2

    def test_stderr_captured(self, tmp_path: Path) -> None:
        cmd = _make_script(
            tmp_path,
            "err.py",
            "import sys\nsys.stderr.write('fatal error\\n')\nsys.exit(1)\n",
        )
        result = run_streaming(cmd, "", session_id="s2", cwd=tmp_path)
        assert "fatal error" in result.stderr

    def test_stdout_empty(self, tmp_path: Path) -> None:
        cmd = _make_script(
            tmp_path,
            "err.py",
            "import sys\nsys.stderr.write('error only\\n')\nsys.exit(1)\n",
        )
        result = run_streaming(cmd, "", session_id="s2", cwd=tmp_path)
        assert result.stdout == ""

    def test_stderr_log_written(self, tmp_path: Path) -> None:
        cmd = _make_script(
            tmp_path,
            "err.py",
            "import sys\nsys.stderr.write('logged error\\n')\nsys.exit(1)\n",
        )
        stderr_log = tmp_path / "stderr.log"
        run_streaming(cmd, "", session_id="s2", cwd=tmp_path, stderr_log=stderr_log)
        assert stderr_log.exists()
        assert "logged error" in stderr_log.read_text(encoding="utf-8")

    def test_stderr_events_emitted(self, tmp_path: Path) -> None:
        cmd = _make_script(
            tmp_path,
            "err.py",
            "import sys\nsys.stderr.write('error event\\n')\nsys.exit(1)\n",
        )
        sink = InMemoryEventSink()
        run_streaming(cmd, "", session_id="s2", cwd=tmp_path, sink=sink)
        events = _stderr_events(sink)
        assert len(events) >= 1
        texts = [e.data["text"] for e in events]
        assert any("error event" in t for t in texts)

    def test_no_stdout_events(self, tmp_path: Path) -> None:
        cmd = _make_script(
            tmp_path,
            "err.py",
            "import sys\nsys.stderr.write('err only\\n')\nsys.exit(1)\n",
        )
        sink = InMemoryEventSink()
        run_streaming(cmd, "", session_id="s2", cwd=tmp_path, sink=sink)
        assert _stdout_events(sink) == []


class TestRunStreamingMixed:
    def test_both_streams_captured(self, tmp_path: Path) -> None:
        cmd = _make_script(
            tmp_path,
            "mixed.py",
            (
                "import sys\n"
                "sys.stdout.write('out1\\n')\n"
                "sys.stderr.write('err1\\n')\n"
                "sys.stdout.write('out2\\n')\n"
                "sys.stderr.write('err2\\n')\n"
                "sys.exit(3)\n"
            ),
        )
        result = run_streaming(cmd, "", session_id="s3", cwd=tmp_path)
        assert result.exit_code == 3
        assert "out1" in result.stdout
        assert "out2" in result.stdout
        assert "err1" in result.stderr
        assert "err2" in result.stderr

    def test_both_log_files_written(self, tmp_path: Path) -> None:
        cmd = _make_script(
            tmp_path,
            "mixed.py",
            (
                "import sys\n"
                "sys.stdout.write('stdout content\\n')\n"
                "sys.stderr.write('stderr content\\n')\n"
                "sys.exit(0)\n"
            ),
        )
        stdout_log = tmp_path / "out.log"
        stderr_log = tmp_path / "err.log"
        run_streaming(
            cmd, "", session_id="s3", cwd=tmp_path,
            stdout_log=stdout_log, stderr_log=stderr_log,
        )
        assert "stdout content" in stdout_log.read_text(encoding="utf-8")
        assert "stderr content" in stderr_log.read_text(encoding="utf-8")

    def test_both_event_types_emitted(self, tmp_path: Path) -> None:
        cmd = _make_script(
            tmp_path,
            "mixed.py",
            (
                "import sys\n"
                "sys.stdout.write('so\\n')\n"
                "sys.stderr.write('se\\n')\n"
                "sys.exit(0)\n"
            ),
        )
        sink = InMemoryEventSink()
        run_streaming(cmd, "", session_id="s3", cwd=tmp_path, sink=sink)
        assert len(_stdout_events(sink)) >= 1
        assert len(_stderr_events(sink)) >= 1

    def test_events_carry_session_id(self, tmp_path: Path) -> None:
        cmd = _make_script(
            tmp_path,
            "mixed.py",
            "import sys\nsys.stdout.write('x\\n')\nsys.exit(0)\n",
        )
        sink = InMemoryEventSink()
        run_streaming(cmd, "", session_id="my-session", cwd=tmp_path, sink=sink)
        events = _stdout_events(sink)
        assert all(e.session_id == "my-session" for e in events)


class TestRunStreamingStdin:
    def test_stdin_passed_to_process(self, tmp_path: Path) -> None:
        cmd = _make_script(
            tmp_path,
            "echo_in.py",
            "import sys\ndata = sys.stdin.read()\nsys.stdout.write(data)\nsys.exit(0)\n",
        )
        result = run_streaming(cmd, "hello from stdin\n", session_id="s4", cwd=tmp_path)
        assert "hello from stdin" in result.stdout


class TestRunStreamingLogPaths:
    def test_log_parent_dirs_created(self, tmp_path: Path) -> None:
        cmd = _make_script(
            tmp_path,
            "out.py",
            "import sys\nsys.stdout.write('x\\n')\nsys.exit(0)\n",
        )
        stdout_log = tmp_path / "nested" / "deep" / "stdout.log"
        stderr_log = tmp_path / "nested" / "deep" / "stderr.log"
        run_streaming(
            cmd, "", session_id="s5", cwd=tmp_path,
            stdout_log=stdout_log, stderr_log=stderr_log,
        )
        assert stdout_log.exists()
        assert stderr_log.exists()

    def test_no_logs_when_not_provided(self, tmp_path: Path) -> None:
        cmd = _make_script(
            tmp_path,
            "out.py",
            "import sys\nsys.stdout.write('no log\\n')\nsys.exit(0)\n",
        )
        # Should not raise; no log files should be created in tmp_path
        result = run_streaming(cmd, "", session_id="s5", cwd=tmp_path)
        assert result.exit_code == 0
        assert not (tmp_path / "stdout.log").exists()
        assert not (tmp_path / "stderr.log").exists()


class TestRunStreamingMultiLine:
    def test_multiple_stdout_lines_each_emit_event(self, tmp_path: Path) -> None:
        cmd = _make_script(
            tmp_path,
            "multi.py",
            (
                "import sys\n"
                "for i in range(5):\n"
                "    sys.stdout.write(f'line {i}\\n')\n"
                "sys.exit(0)\n"
            ),
        )
        sink = InMemoryEventSink()
        run_streaming(cmd, "", session_id="s6", cwd=tmp_path, sink=sink)
        events = _stdout_events(sink)
        assert len(events) == 5
        for i in range(5):
            assert any(f"line {i}" in e.data["text"] for e in events)
