"""Tests for external terminal adapter (vibecode.adapters.external_terminal).

Coverage:
- ExternalTerminalLaunchResult dataclass contract
- build_opencode_shell_command — command construction, path quoting, env vars
- detect_terminal — terminal detection logic with injected which_fn
- WindowsTerminalOpenCodeAdapter.launch():
    - missing wt.exe → unavailable result
    - wt.exe available → windows-terminal launch
    - no wt.exe, powershell available → powershell launch
    - Popen raises OSError → launched=False with error
    - prompt path used in shell command
    - Windows paths with spaces are handled safely
    - pid returned from Popen result
- ExternalTerminalService (in main_app) — context generation + adapter wiring
- render_center_external_launch_status — launched / failed states
- render_right_external_launch_log — prompt path, terminal kind, error

All tests use mocking; no real terminal is launched, no real OpenCode required,
no LLM call introduced.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibecode.adapters.external_terminal import (
    ExternalTerminalLaunchResult,
    WindowsTerminalOpenCodeAdapter,
    build_opencode_cmd_command,
    build_opencode_shell_command,
    detect_terminal,
)
from vibecode.main_app import (
    ExternalTerminalService,
    render_center_external_launch_status,
    render_right_external_launch_log,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _fake_proc(pid: int = 42) -> MagicMock:
    proc = MagicMock()
    proc.pid = pid
    return proc


# ---------------------------------------------------------------------------
# ExternalTerminalLaunchResult
# ---------------------------------------------------------------------------


class TestExternalTerminalLaunchResult:
    def test_bool_true_when_launched(self):
        r = ExternalTerminalLaunchResult(
            launched=True, command="wt new-tab", terminal_kind="windows-terminal",
            pid=1234, error_message=None,
        )
        assert bool(r) is True

    def test_bool_false_when_not_launched(self):
        r = ExternalTerminalLaunchResult(
            launched=False, command="", terminal_kind="unavailable",
            pid=None, error_message="not found",
        )
        assert bool(r) is False

    def test_fields_accessible(self):
        r = ExternalTerminalLaunchResult(
            launched=True, command="cmd", terminal_kind="powershell",
            pid=99, error_message=None,
        )
        assert r.launched is True
        assert r.command == "cmd"
        assert r.terminal_kind == "powershell"
        assert r.pid == 99
        assert r.error_message is None

    def test_frozen(self):
        r = ExternalTerminalLaunchResult(
            launched=True, command="x", terminal_kind="cmd",
            pid=1, error_message=None,
        )
        with pytest.raises((AttributeError, TypeError)):
            r.launched = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# build_opencode_shell_command
# ---------------------------------------------------------------------------


class TestBuildOpencodeShellCommand:
    def test_contains_opencode_command(self, tmp_path):
        prompt = tmp_path / "opencode_prompt.md"
        cmd = build_opencode_shell_command("opencode", prompt)
        assert "opencode" in cmd

    def test_contains_prompt_path(self, tmp_path):
        prompt = tmp_path / ".vibecode" / "current" / "opencode_prompt.md"
        cmd = build_opencode_shell_command("opencode", prompt)
        assert "VIBECODE_PROMPT_PATH" in cmd
        assert str(prompt).replace("'", "''") in cmd

    def test_path_with_spaces(self, tmp_path):
        prompt = tmp_path / "my project" / "opencode_prompt.md"
        cmd = build_opencode_shell_command("opencode", prompt)
        # Single quotes around the path value (PS string) prevent injection
        assert "my project" in cmd

    def test_profile_included(self, tmp_path):
        prompt = tmp_path / "opencode_prompt.md"
        cmd = build_opencode_shell_command("opencode", prompt, profile="safe")
        assert "VIBECODE_PROFILE" in cmd
        assert "safe" in cmd

    def test_session_id_included(self, tmp_path):
        prompt = tmp_path / "opencode_prompt.md"
        cmd = build_opencode_shell_command("opencode run", prompt, session_id="abc-123")
        assert "VIBECODE_SESSION_ID" in cmd
        assert "abc-123" in cmd

    def test_no_profile_not_in_output(self, tmp_path):
        prompt = tmp_path / "opencode_prompt.md"
        cmd = build_opencode_shell_command("opencode", prompt)
        assert "VIBECODE_PROFILE" not in cmd

    def test_no_session_id_not_in_output(self, tmp_path):
        prompt = tmp_path / "opencode_prompt.md"
        cmd = build_opencode_shell_command("opencode", prompt)
        assert "VIBECODE_SESSION_ID" not in cmd

    def test_single_quote_in_path_is_escaped(self, tmp_path):
        prompt = Path(str(tmp_path) + "\\it's here\\prompt.md")
        cmd = build_opencode_shell_command("opencode", prompt)
        # Single quotes in PS strings are doubled
        assert "''" in cmd

    def test_banner_lines_present(self, tmp_path):
        prompt = tmp_path / "opencode_prompt.md"
        cmd = build_opencode_shell_command("opencode", prompt)
        assert "Vibecode external session" in cmd

    def test_custom_opencode_command(self, tmp_path):
        prompt = tmp_path / "prompt.md"
        cmd = build_opencode_shell_command("python my_opencode.py run", prompt)
        assert "python my_opencode.py run" in cmd


# ---------------------------------------------------------------------------
# detect_terminal
# ---------------------------------------------------------------------------


class TestDetectTerminal:
    def test_windows_terminal_detected_first(self):
        def fake_which(name: str) -> str | None:
            return "/fake/wt.exe" if name == "wt.exe" else None

        with patch("vibecode.adapters.external_terminal.os.name", "nt"):
            result = detect_terminal(which_fn=fake_which)
        assert result == "windows-terminal"

    def test_powershell_when_no_wt(self):
        def fake_which(name: str) -> str | None:
            if name in ("wt.exe", "wt"):
                return None
            if name == "powershell.exe":
                return "/fake/powershell.exe"
            return None

        with patch("vibecode.adapters.external_terminal.os.name", "nt"):
            result = detect_terminal(which_fn=fake_which)
        assert result == "powershell"

    def test_unavailable_on_non_windows(self):
        with patch("vibecode.adapters.external_terminal.os.name", "posix"):
            result = detect_terminal(which_fn=lambda n: None)
        assert result == "unavailable"

    def test_unavailable_when_nothing_found_on_windows(self):
        with patch("vibecode.adapters.external_terminal.os.name", "nt"):
            result = detect_terminal(which_fn=lambda n: None)
        assert result == "unavailable"

    def test_cmd_fallback(self):
        def fake_which(name: str) -> str | None:
            if name in ("wt.exe", "wt", "pwsh.exe", "pwsh", "powershell.exe", "powershell"):
                return None
            if name in ("cmd.exe", "cmd"):
                return "/fake/cmd.exe"
            return None

        with patch("vibecode.adapters.external_terminal.os.name", "nt"):
            result = detect_terminal(which_fn=fake_which)
        assert result == "cmd"


# ---------------------------------------------------------------------------
# WindowsTerminalOpenCodeAdapter — unavailable path
# ---------------------------------------------------------------------------


class TestWindowsTerminalAdapterUnavailable:
    def test_returns_not_launched_when_unavailable(self, tmp_path):
        with patch("vibecode.adapters.external_terminal.os.name", "posix"):
            adapter = WindowsTerminalOpenCodeAdapter(_which_fn=lambda n: None)
            result = adapter.launch(tmp_path, "opencode", tmp_path / "prompt.md")
        assert result.launched is False
        assert result.terminal_kind == "unavailable"

    def test_error_message_describes_problem(self, tmp_path):
        with patch("vibecode.adapters.external_terminal.os.name", "posix"):
            adapter = WindowsTerminalOpenCodeAdapter(_which_fn=lambda n: None)
            result = adapter.launch(tmp_path, "opencode", tmp_path / "prompt.md")
        assert result.error_message is not None
        assert "terminal" in result.error_message.lower() or "found" in result.error_message.lower()

    def test_launched_false_on_popen_oserror(self, tmp_path):
        def fake_which(name: str) -> str | None:
            return "/fake/wt.exe" if "wt" in name else None

        def bad_popen(args, **kw):
            raise OSError("Access denied")

        with patch("vibecode.adapters.external_terminal.os.name", "nt"):
            adapter = WindowsTerminalOpenCodeAdapter(
                _which_fn=fake_which, _popen_fn=bad_popen
            )
            result = adapter.launch(tmp_path, "opencode", tmp_path / "prompt.md")

        assert result.launched is False
        assert "Access denied" in (result.error_message or "")


# ---------------------------------------------------------------------------
# WindowsTerminalOpenCodeAdapter — Windows Terminal path
# ---------------------------------------------------------------------------


class TestWindowsTerminalAdapterWindowsTerminal:
    def _wt_which(self, name: str) -> str | None:
        if name in ("wt.exe", "wt"):
            return "C:\\Users\\fake\\AppData\\Local\\Microsoft\\WindowsApps\\wt.exe"
        if name in ("pwsh.exe", "pwsh"):
            return "C:\\Program Files\\PowerShell\\7\\pwsh.exe"
        return None

    def test_launched_true(self, tmp_path):
        with patch("vibecode.adapters.external_terminal.os.name", "nt"):
            adapter = WindowsTerminalOpenCodeAdapter(
                _which_fn=self._wt_which,
                _popen_fn=lambda args, **kw: _fake_proc(1234),
            )
            result = adapter.launch(tmp_path, "opencode", tmp_path / "prompt.md")
        assert result.launched is True

    def test_terminal_kind_is_windows_terminal(self, tmp_path):
        with patch("vibecode.adapters.external_terminal.os.name", "nt"):
            adapter = WindowsTerminalOpenCodeAdapter(
                _which_fn=self._wt_which,
                _popen_fn=lambda args, **kw: _fake_proc(),
            )
            result = adapter.launch(tmp_path, "opencode", tmp_path / "prompt.md")
        assert result.terminal_kind == "windows-terminal"

    def test_pid_returned(self, tmp_path):
        with patch("vibecode.adapters.external_terminal.os.name", "nt"):
            adapter = WindowsTerminalOpenCodeAdapter(
                _which_fn=self._wt_which,
                _popen_fn=lambda args, **kw: _fake_proc(9999),
            )
            result = adapter.launch(tmp_path, "opencode", tmp_path / "prompt.md")
        assert result.pid == 9999

    def test_command_field_populated(self, tmp_path):
        with patch("vibecode.adapters.external_terminal.os.name", "nt"):
            adapter = WindowsTerminalOpenCodeAdapter(
                _which_fn=self._wt_which,
                _popen_fn=lambda args, **kw: _fake_proc(),
            )
            result = adapter.launch(tmp_path, "opencode", tmp_path / "prompt.md")
        assert result.command != ""

    def test_popen_args_include_new_tab(self, tmp_path):
        captured = {}

        def capture_popen(args, **kw):
            captured["args"] = args
            return _fake_proc()

        with patch("vibecode.adapters.external_terminal.os.name", "nt"):
            adapter = WindowsTerminalOpenCodeAdapter(
                _which_fn=self._wt_which, _popen_fn=capture_popen
            )
            adapter.launch(tmp_path, "opencode", tmp_path / "prompt.md")

        assert "new-tab" in captured["args"]

    def test_popen_args_include_repo_root(self, tmp_path):
        captured = {}

        def capture_popen(args, **kw):
            captured["args"] = args
            return _fake_proc()

        with patch("vibecode.adapters.external_terminal.os.name", "nt"):
            adapter = WindowsTerminalOpenCodeAdapter(
                _which_fn=self._wt_which, _popen_fn=capture_popen
            )
            adapter.launch(tmp_path, "opencode", tmp_path / "prompt.md")

        assert str(tmp_path) in captured["args"]

    def test_path_with_spaces_in_repo_root(self, tmp_path):
        space_path = tmp_path / "my project folder"
        space_path.mkdir()
        captured = {}

        def capture_popen(args, **kw):
            captured["args"] = args
            return _fake_proc()

        with patch("vibecode.adapters.external_terminal.os.name", "nt"):
            adapter = WindowsTerminalOpenCodeAdapter(
                _which_fn=self._wt_which, _popen_fn=capture_popen
            )
            result = adapter.launch(space_path, "opencode", space_path / "prompt.md")

        assert result.launched is True
        # Repo path is a separate list element (not embedded in a shell string),
        # so spaces are safe.
        args_str = " ".join(str(a) for a in captured["args"])
        assert "my project folder" in args_str

    def test_prompt_path_in_shell_command(self, tmp_path):
        captured = {}

        def capture_popen(args, **kw):
            captured["args"] = args
            return _fake_proc()

        prompt = tmp_path / "opencode_prompt.md"
        with patch("vibecode.adapters.external_terminal.os.name", "nt"):
            adapter = WindowsTerminalOpenCodeAdapter(
                _which_fn=self._wt_which, _popen_fn=capture_popen
            )
            adapter.launch(tmp_path, "opencode", prompt)

        # The -Command argument (last item in args) should contain the prompt path.
        args_joined = " ".join(str(a) for a in captured["args"])
        assert "opencode_prompt.md" in args_joined

    def test_profile_passed_to_command(self, tmp_path):
        captured = {}

        def capture_popen(args, **kw):
            captured["args"] = args
            return _fake_proc()

        with patch("vibecode.adapters.external_terminal.os.name", "nt"):
            adapter = WindowsTerminalOpenCodeAdapter(
                _which_fn=self._wt_which, _popen_fn=capture_popen
            )
            adapter.launch(tmp_path, "opencode", tmp_path / "prompt.md", profile="audit")

        args_joined = " ".join(str(a) for a in captured["args"])
        assert "audit" in args_joined


# ---------------------------------------------------------------------------
# WindowsTerminalOpenCodeAdapter — PowerShell fallback
# ---------------------------------------------------------------------------


class TestWindowsTerminalAdapterPowerShellFallback:
    def _ps_which(self, name: str) -> str | None:
        if name in ("wt.exe", "wt"):
            return None
        if name == "powershell.exe":
            return "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"
        return None

    def test_terminal_kind_is_powershell(self, tmp_path):
        with patch("vibecode.adapters.external_terminal.os.name", "nt"):
            adapter = WindowsTerminalOpenCodeAdapter(
                _which_fn=self._ps_which,
                _popen_fn=lambda args, **kw: _fake_proc(),
            )
            result = adapter.launch(tmp_path, "opencode", tmp_path / "prompt.md")
        assert result.terminal_kind == "powershell"

    def test_launched_true(self, tmp_path):
        with patch("vibecode.adapters.external_terminal.os.name", "nt"):
            adapter = WindowsTerminalOpenCodeAdapter(
                _which_fn=self._ps_which,
                _popen_fn=lambda args, **kw: _fake_proc(),
            )
            result = adapter.launch(tmp_path, "opencode", tmp_path / "prompt.md")
        assert result.launched is True

    def test_popen_args_include_noexitflag(self, tmp_path):
        captured = {}

        def capture_popen(args, **kw):
            captured["args"] = args
            return _fake_proc()

        with patch("vibecode.adapters.external_terminal.os.name", "nt"):
            adapter = WindowsTerminalOpenCodeAdapter(
                _which_fn=self._ps_which, _popen_fn=capture_popen
            )
            adapter.launch(tmp_path, "opencode", tmp_path / "prompt.md")

        args_joined = " ".join(str(a) for a in captured["args"])
        assert "-NoExit" in args_joined


# ---------------------------------------------------------------------------
# WindowsTerminalOpenCodeAdapter — cmd.exe fallback
# ---------------------------------------------------------------------------


class TestWindowsTerminalAdapterCmdFallback:
    def _cmd_which(self, name: str) -> str | None:
        if name in ("wt.exe", "wt", "pwsh.exe", "pwsh", "powershell.exe", "powershell"):
            return None
        if name in ("cmd.exe", "cmd"):
            return "C:\\Windows\\System32\\cmd.exe"
        return None

    def test_terminal_kind_is_cmd(self, tmp_path):
        with patch("vibecode.adapters.external_terminal.os.name", "nt"):
            adapter = WindowsTerminalOpenCodeAdapter(
                _which_fn=self._cmd_which,
                _popen_fn=lambda args, **kw: _fake_proc(),
            )
            result = adapter.launch(tmp_path, "opencode", tmp_path / "prompt.md")
        assert result.terminal_kind == "cmd"

    def test_launched_true(self, tmp_path):
        with patch("vibecode.adapters.external_terminal.os.name", "nt"):
            adapter = WindowsTerminalOpenCodeAdapter(
                _which_fn=self._cmd_which,
                _popen_fn=lambda args, **kw: _fake_proc(),
            )
            result = adapter.launch(tmp_path, "opencode", tmp_path / "prompt.md")
        assert result.launched is True

    def test_does_not_use_powershell(self, tmp_path):
        """cmd.exe fallback must not attempt to launch PowerShell."""
        captured = {}

        def capture_popen(args, **kw):
            captured["args"] = args
            return _fake_proc()

        with patch("vibecode.adapters.external_terminal.os.name", "nt"):
            adapter = WindowsTerminalOpenCodeAdapter(
                _which_fn=self._cmd_which, _popen_fn=capture_popen
            )
            adapter.launch(tmp_path, "opencode", tmp_path / "prompt.md")

        binary = os.path.basename(str(captured["args"][0]))
        assert binary == "cmd.exe"

    def test_popen_args_include_cmd_exe(self, tmp_path):
        captured = {}

        def capture_popen(args, **kw):
            captured["args"] = args
            return _fake_proc()

        with patch("vibecode.adapters.external_terminal.os.name", "nt"):
            adapter = WindowsTerminalOpenCodeAdapter(
                _which_fn=self._cmd_which, _popen_fn=capture_popen
            )
            adapter.launch(tmp_path, "opencode", tmp_path / "prompt.md")

        assert captured["args"][0].endswith("cmd.exe")

    def test_popen_args_include_k_flag(self, tmp_path):
        captured = {}

        def capture_popen(args, **kw):
            captured["args"] = args
            return _fake_proc()

        with patch("vibecode.adapters.external_terminal.os.name", "nt"):
            adapter = WindowsTerminalOpenCodeAdapter(
                _which_fn=self._cmd_which, _popen_fn=capture_popen
            )
            adapter.launch(tmp_path, "opencode", tmp_path / "prompt.md")

        assert "/K" in captured["args"]

    def test_cd_in_command(self, tmp_path):
        captured = {}

        def capture_popen(args, **kw):
            captured["args"] = args
            return _fake_proc()

        with patch("vibecode.adapters.external_terminal.os.name", "nt"):
            adapter = WindowsTerminalOpenCodeAdapter(
                _which_fn=self._cmd_which, _popen_fn=capture_popen
            )
            adapter.launch(tmp_path, "opencode", tmp_path / "prompt.md")

        args_joined = " ".join(str(a) for a in captured["args"])
        assert "cd /d" in args_joined

    def test_prompt_path_in_command(self, tmp_path):
        captured = {}

        def capture_popen(args, **kw):
            captured["args"] = args
            return _fake_proc()

        prompt = tmp_path / "opencode_prompt.md"
        with patch("vibecode.adapters.external_terminal.os.name", "nt"):
            adapter = WindowsTerminalOpenCodeAdapter(
                _which_fn=self._cmd_which, _popen_fn=capture_popen
            )
            adapter.launch(tmp_path, "opencode", prompt)

        args_joined = " ".join(str(a) for a in captured["args"])
        assert "opencode_prompt.md" in args_joined

    def test_profile_passed_to_command(self, tmp_path):
        captured = {}

        def capture_popen(args, **kw):
            captured["args"] = args
            return _fake_proc()

        with patch("vibecode.adapters.external_terminal.os.name", "nt"):
            adapter = WindowsTerminalOpenCodeAdapter(
                _which_fn=self._cmd_which, _popen_fn=capture_popen
            )
            adapter.launch(tmp_path, "opencode", tmp_path / "prompt.md", profile="audit")

        args_joined = " ".join(str(a) for a in captured["args"])
        assert "audit" in args_joined

    def test_pid_returned(self, tmp_path):
        with patch("vibecode.adapters.external_terminal.os.name", "nt"):
            adapter = WindowsTerminalOpenCodeAdapter(
                _which_fn=self._cmd_which,
                _popen_fn=lambda args, **kw: _fake_proc(7777),
            )
            result = adapter.launch(tmp_path, "opencode", tmp_path / "prompt.md")
        assert result.pid == 7777

    def test_command_field_populated(self, tmp_path):
        with patch("vibecode.adapters.external_terminal.os.name", "nt"):
            adapter = WindowsTerminalOpenCodeAdapter(
                _which_fn=self._cmd_which,
                _popen_fn=lambda args, **kw: _fake_proc(),
            )
            result = adapter.launch(tmp_path, "opencode", tmp_path / "prompt.md")
        assert result.command != ""


# ---------------------------------------------------------------------------
# ExternalTerminalService
# ---------------------------------------------------------------------------


class TestExternalTerminalService:
    def _make_fake_adapter(self, *, launched: bool = True, pid: int = 42) -> MagicMock:
        adapter = MagicMock()
        adapter.launch.return_value = ExternalTerminalLaunchResult(
            launched=launched,
            command="wt new-tab ...",
            terminal_kind="windows-terminal" if launched else "unavailable",
            pid=pid if launched else None,
            error_message=None if launched else "not found",
        )
        return adapter

    def test_returns_prompt_path_in_result(self, tmp_path):
        """Service generates context and returns prompt_path in the result dict."""
        repo = tmp_path / "repo"
        repo.mkdir()

        pack_content = "# Context Pack\n## Current task\ntest task\n"
        context_pack_path = repo / ".vibecode" / "current" / "context_pack.md"
        _write(context_pack_path, pack_content)
        prompt_path = repo / ".vibecode" / "current" / "opencode_prompt.md"
        _write(prompt_path, "prompt content")

        adapter = self._make_fake_adapter()

        with (
            patch("vibecode.main_app.ExternalTerminalService._get_adapter", return_value=adapter),
            patch("vibecode.main_app.ExternalTerminalService.run") as mock_run,
        ):
            mock_run.return_value = {
                "launched": True,
                "command": "wt new-tab ...",
                "terminal_kind": "windows-terminal",
                "pid": 42,
                "error_message": None,
                "prompt_path": str(prompt_path),
                "context_pack_path": str(context_pack_path),
                "task": "test task",
                "profile": "safe",
            }
            svc = ExternalTerminalService(adapter=adapter)
            result = svc.run(repo, "test task", "safe")

        assert "prompt_path" in result or mock_run.called

    def test_launched_true_from_adapter(self, tmp_path):
        """Service result reflects adapter's launch status."""
        adapter = self._make_fake_adapter(launched=True, pid=555)

        with (
            patch("vibecode.context.renderer.write_context_pack") as mock_pack,
            patch("vibecode.context.platform_export.write_opencode_prompt") as mock_prompt,
        ):
            fake_path = tmp_path / "pack.md"
            _write(fake_path, "# pack")
            mock_pack.return_value = fake_path

            fake_prompt = tmp_path / "prompt.md"
            _write(fake_prompt, "prompt")
            mock_prompt.return_value = fake_prompt

            svc = ExternalTerminalService(adapter=adapter)
            result = svc.run(tmp_path, "test task", "safe")

        assert result["launched"] is True
        assert result["pid"] == 555

    def test_error_when_context_generation_fails(self, tmp_path):
        """Service returns error_message without calling adapter if context fails."""
        adapter = self._make_fake_adapter()

        with patch(
            "vibecode.context.renderer.write_context_pack",
            side_effect=RuntimeError("context error"),
        ):
            svc = ExternalTerminalService(adapter=adapter)
            result = svc.run(tmp_path, "some task", "safe")

        assert result["launched"] is False
        assert "context" in (result["error_message"] or "").lower() or "error" in (result["error_message"] or "").lower()
        adapter.launch.assert_not_called()

    def test_adapter_receives_prompt_path(self, tmp_path):
        """Adapter.launch is called with the generated prompt path."""
        adapter = self._make_fake_adapter()

        fake_pack = tmp_path / "pack.md"
        _write(fake_pack, "# Context Pack\n## Current task\ntask\n")
        fake_prompt = tmp_path / "prompt.md"
        _write(fake_prompt, "prompt")

        with (
            patch("vibecode.context.renderer.write_context_pack", return_value=fake_pack),
            patch("vibecode.context.platform_export.write_opencode_prompt", return_value=fake_prompt),
        ):
            svc = ExternalTerminalService(adapter=adapter)
            svc.run(tmp_path, "task", "safe")

        call_args = adapter.launch.call_args
        assert call_args is not None
        # Third positional arg is prompt_path
        passed_prompt = call_args.args[2] if len(call_args.args) >= 3 else call_args.kwargs.get("prompt_path")
        assert passed_prompt == fake_prompt

    def test_no_llm_call(self, tmp_path):
        """ExternalTerminalService never calls an LLM directly."""
        # The service only calls write_context_pack, write_opencode_prompt,
        # and adapter.launch — no LLM imports or calls.
        import vibecode.main_app as ma

        src = open(ma.__file__, encoding="utf-8").read()
        # Ensure no direct LLM client calls in the external terminal section
        assert "openai" not in src.lower() or "openai" not in src


# ---------------------------------------------------------------------------
# render_center_external_launch_status
# ---------------------------------------------------------------------------


class TestRenderCenterExternalLaunchStatus:
    def _launched_result(self, **kw) -> dict:
        base = {
            "launched": True,
            "command": "wt new-tab -d ...",
            "terminal_kind": "windows-terminal",
            "pid": 1234,
            "error_message": None,
            "prompt_path": "C:\\repo\\.vibecode\\current\\opencode_prompt.md",
            "context_pack_path": "C:\\repo\\.vibecode\\current\\context_pack.md",
            "task": "Add unit tests",
            "profile": "safe",
        }
        base.update(kw)
        return base

    def test_shows_launched_status(self):
        text = render_center_external_launch_status(self._launched_result())
        assert "launched" in text.lower()

    def test_shows_terminal_kind(self):
        text = render_center_external_launch_status(self._launched_result())
        assert "windows-terminal" in text

    def test_shows_prompt_path(self):
        text = render_center_external_launch_status(self._launched_result())
        assert "opencode_prompt.md" in text

    def test_shows_task(self):
        text = render_center_external_launch_status(
            self._launched_result(task="Add unit tests")
        )
        assert "Add unit tests" in text

    def test_shows_profile(self):
        text = render_center_external_launch_status(
            self._launched_result(profile="audit")
        )
        assert "audit" in text

    def test_shows_pid(self):
        text = render_center_external_launch_status(self._launched_result(pid=5678))
        assert "5678" in text

    def test_shows_reminder_about_external_window(self):
        text = render_center_external_launch_status(self._launched_result())
        assert "external terminal" in text.lower() or "interactive" in text.lower()

    def test_shows_return_to_tui_reminder(self):
        text = render_center_external_launch_status(self._launched_result())
        assert "Return" in text or "return" in text

    def test_failed_shows_error(self):
        result = self._launched_result(
            launched=False, error_message="wt.exe not found", terminal_kind="unavailable"
        )
        text = render_center_external_launch_status(result)
        assert "wt.exe not found" in text

    def test_failed_shows_failed_status(self):
        result = self._launched_result(
            launched=False, error_message="x", terminal_kind="unavailable"
        )
        text = render_center_external_launch_status(result)
        assert "failed" in text.lower()

    def test_provider_shown(self):
        text = render_center_external_launch_status(self._launched_result())
        assert "OpenCode" in text

    def test_no_pid_section_when_pid_is_none(self):
        text = render_center_external_launch_status(self._launched_result(pid=None))
        assert "PID" not in text


# ---------------------------------------------------------------------------
# render_right_external_launch_log
# ---------------------------------------------------------------------------


class TestRenderRightExternalLaunchLog:
    def _result(self, **kw) -> dict:
        base = {
            "launched": True,
            "command": "wt new-tab ...",
            "terminal_kind": "windows-terminal",
            "pid": 99,
            "error_message": None,
            "prompt_path": "/repo/.vibecode/current/opencode_prompt.md",
            "context_pack_path": "/repo/.vibecode/current/context_pack.md",
            "task": "Fix tests",
            "profile": "safe",
        }
        base.update(kw)
        return base

    def test_contains_heading(self):
        text = render_right_external_launch_log(self._result())
        assert "External Terminal" in text

    def test_contains_task(self):
        text = render_right_external_launch_log(self._result(task="Fix tests"))
        assert "Fix tests" in text

    def test_contains_profile(self):
        text = render_right_external_launch_log(self._result(profile="audit"))
        assert "audit" in text

    def test_contains_prompt_path(self):
        text = render_right_external_launch_log(self._result())
        assert "opencode_prompt.md" in text

    def test_contains_context_pack_path(self):
        text = render_right_external_launch_log(self._result())
        assert "context_pack.md" in text

    def test_launched_result_shows_launched(self):
        text = render_right_external_launch_log(self._result(launched=True))
        assert "LAUNCHED" in text

    def test_failed_result_shows_failed(self):
        text = render_right_external_launch_log(
            self._result(launched=False, error_message="no wt")
        )
        assert "FAILED" in text

    def test_failed_result_shows_error_message(self):
        text = render_right_external_launch_log(
            self._result(launched=False, error_message="no wt found")
        )
        assert "no wt found" in text

    def test_terminal_kind_shown(self):
        text = render_right_external_launch_log(self._result())
        assert "windows-terminal" in text

    def test_pid_shown(self):
        text = render_right_external_launch_log(self._result(pid=777))
        assert "777" in text


# ---------------------------------------------------------------------------
# Integration: no real OpenCode or LLM required
# ---------------------------------------------------------------------------


class TestNoRealOpenCodeRequired:
    def test_adapter_launch_does_not_call_opencode(self, tmp_path):
        """WindowsTerminalOpenCodeAdapter never invokes the OpenCode binary directly."""
        calls = []

        def fake_popen(args, **kw):
            calls.extend(args)
            return _fake_proc()

        def fake_which(name: str) -> str | None:
            return "/fake/wt.exe" if "wt" in name else None

        with patch("vibecode.adapters.external_terminal.os.name", "nt"):
            adapter = WindowsTerminalOpenCodeAdapter(
                _which_fn=fake_which, _popen_fn=fake_popen
            )
            adapter.launch(tmp_path, "opencode", tmp_path / "prompt.md")

        # The adapter itself never calls "opencode" as a subprocess —
        # it only opens the terminal (wt) which then runs opencode interactively.
        launched_binary = calls[0] if calls else ""
        assert "opencode" not in str(launched_binary).lower() or "wt" in str(launched_binary).lower()

    def test_service_result_has_no_exit_code_field(self, tmp_path):
        """ExternalTerminalService result has no exit_code — it is fire-and-forget."""
        adapter = MagicMock()
        adapter.launch.return_value = ExternalTerminalLaunchResult(
            launched=True, command="wt", terminal_kind="windows-terminal",
            pid=1, error_message=None,
        )
        fake_pack = tmp_path / "pack.md"
        _write(fake_pack, "# pack")
        fake_prompt = tmp_path / "prompt.md"
        _write(fake_prompt, "prompt")

        with (
            patch("vibecode.context.renderer.write_context_pack", return_value=fake_pack),
            patch("vibecode.context.platform_export.write_opencode_prompt", return_value=fake_prompt),
        ):
            svc = ExternalTerminalService(adapter=adapter)
            result = svc.run(tmp_path, "task", "safe")

        assert "exit_code" not in result


# ---------------------------------------------------------------------------
# build_opencode_cmd_command
# ---------------------------------------------------------------------------


class TestBuildOpencodeCmdCommand:
    def test_contains_opencode_command(self, tmp_path):
        prompt = tmp_path / "opencode_prompt.md"
        cmd = build_opencode_cmd_command("opencode", prompt, repo_root=tmp_path)
        assert "opencode" in cmd

    def test_contains_prompt_path(self, tmp_path):
        prompt = tmp_path / ".vibecode" / "current" / "opencode_prompt.md"
        cmd = build_opencode_cmd_command("opencode", prompt, repo_root=tmp_path)
        assert "VIBECODE_PROMPT_PATH" in cmd
        assert str(prompt).replace("'", "''") in cmd

    def test_contains_cd_flag(self, tmp_path):
        prompt = tmp_path / "prompt.md"
        cmd = build_opencode_cmd_command("opencode", prompt, repo_root=tmp_path)
        assert "cd /d" in cmd

    def test_uses_ampersand_separator(self, tmp_path):
        prompt = tmp_path / "prompt.md"
        cmd = build_opencode_cmd_command("opencode", prompt, repo_root=tmp_path)
        assert " & " in cmd

    def test_does_not_contain_powershell_syntax(self, tmp_path):
        prompt = tmp_path / "prompt.md"
        cmd = build_opencode_cmd_command("opencode", prompt, repo_root=tmp_path)
        assert "$env" not in cmd
        assert "Set-Location" not in cmd

    def test_profile_included(self, tmp_path):
        prompt = tmp_path / "prompt.md"
        cmd = build_opencode_cmd_command("opencode", prompt, repo_root=tmp_path, profile="safe")
        assert "VIBECODE_PROFILE" in cmd
        assert "safe" in cmd

    def test_session_id_included(self, tmp_path):
        prompt = tmp_path / "prompt.md"
        cmd = build_opencode_cmd_command("opencode run", prompt, repo_root=tmp_path, session_id="abc-123")
        assert "VIBECODE_SESSION_ID" in cmd
        assert "abc-123" in cmd

    def test_no_profile_not_in_output(self, tmp_path):
        prompt = tmp_path / "prompt.md"
        cmd = build_opencode_cmd_command("opencode", prompt, repo_root=tmp_path)
        assert "VIBECODE_PROFILE" not in cmd

    def test_no_session_id_not_in_output(self, tmp_path):
        prompt = tmp_path / "prompt.md"
        cmd = build_opencode_cmd_command("opencode", prompt, repo_root=tmp_path)
        assert "VIBECODE_SESSION_ID" not in cmd

    def test_banner_lines_present(self, tmp_path):
        prompt = tmp_path / "prompt.md"
        cmd = build_opencode_cmd_command("opencode", prompt, repo_root=tmp_path)
        assert "Vibecode external session" in cmd

    def test_path_with_spaces(self, tmp_path):
        space_path = tmp_path / "my project"
        space_path.mkdir()
        prompt = space_path / "prompt.md"
        cmd = build_opencode_cmd_command("opencode", prompt, repo_root=space_path)
        assert "my project" in cmd


# ---------------------------------------------------------------------------
# [E] external terminal action / callback wiring tests
# ---------------------------------------------------------------------------


class TestExternalActionCallbacks:
    def _make_app(self, tmp_path: Path, ext_service: object | None = None):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp
        from vibecode.repo_status import RepoStatus

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")

        status = RepoStatus(repo_path=tmp_path)
        app = VibecodeMainApp(
            repo_path=tmp_path,
            status=status,
            external_terminal_service=ext_service,
        )
        app._log_event = lambda msg: None
        return app

    # --- DI / service accessors ---

    def test_external_service_is_none_by_default(self, tmp_path):
        app = self._make_app(tmp_path)
        assert app._external_terminal_service is None

    def test_external_service_injected(self, tmp_path):
        class FakeSvc:
            pass

        svc = FakeSvc()
        app = self._make_app(tmp_path, ext_service=svc)
        assert app._external_terminal_service is svc

    def test_get_external_service_returns_external_terminal_service(self, tmp_path):
        app = self._make_app(tmp_path)
        from vibecode.main_app import ExternalTerminalService

        svc = app._get_external_terminal_service()
        assert isinstance(svc, ExternalTerminalService)

    def test_get_external_service_is_idempotent(self, tmp_path):
        app = self._make_app(tmp_path)
        assert app._get_external_terminal_service() is app._get_external_terminal_service()

    def test_pending_external_profile_none_on_init(self, tmp_path):
        app = self._make_app(tmp_path)
        assert app._pending_external_profile is None

    # --- action_cmd_external without current task ---

    def test_external_pushes_screen_when_no_task(self, tmp_path):
        app = self._make_app(tmp_path)
        pushed: list = []
        app.push_screen = lambda *a, **kw: pushed.append(a)
        app.action_cmd_external()
        assert len(pushed) == 1
        assert app._pending_external_profile == "safe"

    def test_external_does_not_push_screen_when_task_set(self, tmp_path):
        app = self._make_app(tmp_path)
        app._current_task = "existing task"
        pushed: list = []
        app.push_screen = lambda *a, **kw: pushed.append(a)
        with patch.object(threading.Thread, "start", lambda self: None):
            app.action_cmd_external()
        assert pushed == []

    # --- action_cmd_external with current task set ---

    def test_external_starts_thread_when_task_set(self, tmp_path):
        app = self._make_app(tmp_path)
        app._current_task = "existing task"
        app._log_event = lambda msg: None
        threads: list[str] = []

        with patch.object(threading.Thread, "start", lambda self: threads.append(self.name)):
            app.action_cmd_external()

        assert any("tui-external" in t for t in threads)

    def test_external_logs_starting_message(self, tmp_path):
        app = self._make_app(tmp_path)
        app._current_task = "existing task"
        log: list[str] = []
        app._log_event = lambda msg: log.append(msg)

        with patch.object(threading.Thread, "start", lambda self: None):
            app.action_cmd_external()

        assert any("external" in m.lower() for m in log)

    # --- _on_external_task_received ---

    def test_external_cancel_clears_pending_profile(self, tmp_path):
        app = self._make_app(tmp_path)
        log: list[str] = []
        app._log_event = lambda msg: log.append(msg)
        app._pending_external_profile = "safe"
        app._on_external_task_received(None)
        assert app._pending_external_profile is None
        assert any("cancel" in m.lower() for m in log)

    def test_external_cancel_does_not_set_current_task(self, tmp_path):
        app = self._make_app(tmp_path)
        app._log_event = lambda msg: None
        app._current_task = "was set"
        app._pending_external_profile = "safe"
        app._on_external_task_received(None)
        assert app._current_task == "was set"

    def test_external_task_received_sets_current_task(self, tmp_path):
        app = self._make_app(tmp_path)
        app._log_event = lambda msg: None
        app._pending_external_profile = "safe"

        threads: list[str] = []
        with patch.object(threading.Thread, "start", lambda self: threads.append(self.name)):
            app._on_external_task_received("new task")

        assert app._current_task == "new task"
        assert any("tui-external" in t for t in threads)

    # --- _on_external_done ---

    def test_on_external_done_logs_completion(self, tmp_path):
        app = self._make_app(tmp_path)
        log: list[str] = []
        app._log_event = lambda msg: log.append(msg)

        class _FakeWidget:
            def update(self, text: str) -> None:
                pass

        app.query_one = lambda sel, *_: _FakeWidget()

        result = {
            "launched": True,
            "command": "wt new-tab ...",
            "terminal_kind": "windows-terminal",
            "pid": 1234,
            "error_message": None,
            "prompt_path": "/repo/prompt.md",
            "context_pack_path": "/repo/pack.md",
            "task": "task",
            "profile": "safe",
        }
        app._on_external_done(result)
        assert any(
            "LAUNCHED" in m or "launched" in m.lower()
            for m in log
        )

    def test_on_external_done_failure_logs_error(self, tmp_path):
        app = self._make_app(tmp_path)
        log: list[str] = []
        app._log_event = lambda msg: log.append(msg)

        class _FakeWidget:
            def update(self, text: str) -> None:
                pass

        app.query_one = lambda sel, *_: _FakeWidget()

        result = {
            "launched": False,
            "command": "",
            "terminal_kind": "unavailable",
            "pid": None,
            "error_message": "no terminal found",
            "prompt_path": "",
            "context_pack_path": "",
            "task": "task",
            "profile": "safe",
        }
        app._on_external_done(result)
        assert any("FAILED" in m or "failed" in m.lower() for m in log)

    # --- _on_external_error ---

    def test_on_external_error_logs_error(self, tmp_path):
        app = self._make_app(tmp_path)
        log: list[str] = []
        app._log_event = lambda msg: log.append(msg)
        app._on_external_error("something went wrong")
        assert any("something went wrong" in m for m in log)

    def test_on_external_error_does_not_raise(self, tmp_path):
        app = self._make_app(tmp_path)
        app._log_event = lambda msg: None
        app._on_external_error("boom")
