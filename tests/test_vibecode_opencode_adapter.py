"""Tests for the OpenCode adapter (vibecode.adapters.opencode).

All tests use mocking to avoid requiring a real OpenCode installation.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from vibecode.adapters.opencode import (
    OpenCodeStatus,
    _default_command,
    check_opencode,
    resolve_opencode_command,
)


# ---------------------------------------------------------------------------
# _default_command
# ---------------------------------------------------------------------------


class TestDefaultCommand:
    def test_returns_non_interactive_opencode_run(self):
        assert _default_command() == "opencode run"


# ---------------------------------------------------------------------------
# check_opencode — binary not found
# ---------------------------------------------------------------------------


class TestBinaryNotFound:
    @patch("vibecode.adapters.opencode.shutil.which", return_value=None)
    def test_missing_command(self, _which):
        status = check_opencode("nonexistent-cmd")
        assert status.available is False
        assert "not found on PATH" in status.message
        assert status.command == "nonexistent-cmd"

    @patch("vibecode.adapters.opencode.shutil.which", return_value=None)
    def test_default_missing(self, _which):
        status = check_opencode()
        assert status.available is False
        assert "not found on PATH" in status.message

    @patch("vibecode.adapters.opencode.shutil.which", return_value=None)
    def test_actionable_error_suggests_install(self, _which):
        status = check_opencode()
        assert "Install OpenCode" in status.message or "OPENCODE_COMMAND" in status.message


# ---------------------------------------------------------------------------
# check_opencode — binary found, version check succeeds
# ---------------------------------------------------------------------------


class TestBinaryFound:
    @patch("vibecode.adapters.opencode.shutil.which", return_value="/usr/bin/opencode")
    @patch("vibecode.adapters.opencode.subprocess.run")
    def test_available_with_version(self, mock_run, _which):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="OpenCode 1.2.3\n", stderr=""
        )

        status = check_opencode()
        assert status.available is True
        assert "OpenCode 1.2.3" in status.message
        assert "/usr/bin/opencode" in status.message

    @patch("vibecode.adapters.opencode.shutil.which", return_value="/fake/opencode")
    @patch("vibecode.adapters.opencode.subprocess.run")
    def test_available_even_with_empty_version(self, mock_run, _which):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        status = check_opencode()
        assert status.available is True
        assert "(unknown version)" in status.message


# ---------------------------------------------------------------------------
# check_opencode — binary found, version check fails
# ---------------------------------------------------------------------------


class TestBinaryFails:
    @patch("vibecode.adapters.opencode.shutil.which", return_value="/usr/bin/opencode")
    @patch("vibecode.adapters.opencode.subprocess.run")
    def test_nonzero_exit_code(self, mock_run, _which):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="fatal: missing config"
        )

        status = check_opencode()
        assert status.available is False
        assert "exit code 1" in status.message
        assert "fatal: missing config" in status.message

    @patch("vibecode.adapters.opencode.shutil.which", return_value="/usr/bin/opencode")
    @patch("vibecode.adapters.opencode.subprocess.run")
    def test_oserror_during_execution(self, mock_run, _which):
        mock_run.side_effect = OSError("Permission denied")

        status = check_opencode()
        assert status.available is False
        assert "Permission denied" in status.message


# ---------------------------------------------------------------------------
# check_opencode — timeout
# ---------------------------------------------------------------------------


class TestTimeout:
    @patch("vibecode.adapters.opencode.shutil.which", return_value="/usr/bin/opencode")
    def test_timeout_during_version_check(self, _which):
        import subprocess

        with patch(
            "vibecode.adapters.opencode.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="opencode", timeout=10),
        ):
            status = check_opencode()
            assert status.available is False
            assert "timed out" in status.message.lower()


# ---------------------------------------------------------------------------
# check_opencode — explicit command parameter
# ---------------------------------------------------------------------------


class TestExplicitCommand:
    @patch("vibecode.adapters.opencode.shutil.which", return_value=None)
    def test_uses_explicit_command(self, _which):
        status = check_opencode("/custom/path/opencode")
        assert status.command == "/custom/path/opencode"
        assert "/custom/path/opencode" in status.message

    @patch("vibecode.adapters.opencode.shutil.which", return_value="/custom/opencode")
    @patch("vibecode.adapters.opencode.subprocess.run")
    def test_explicit_command_found(self, mock_run, _which):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="v2.0.0\n", stderr=""
        )

        status = check_opencode("/custom/opencode")
        assert status.available is True
        assert "v2.0.0" in status.message


# ---------------------------------------------------------------------------
# OpenCodeStatus dataclass
# ---------------------------------------------------------------------------


class TestOpenCodeStatus:
    def test_frozen_dataclass(self):
        status = OpenCodeStatus(available=True, command="opencode", message="ok")
        assert status.available is True
        assert status.command == "opencode"
        assert status.message == "ok"

    def test_unavailable_status(self):
        status = OpenCodeStatus(available=False, command="opencode", message="missing")
        assert status.available is False

    def test_bool_conversion(self):
        status = OpenCodeStatus(available=True, command="opencode", message="ok")
        assert bool(status) is True

        status = OpenCodeStatus(available=False, command="opencode", message="missing")
        assert bool(status) is False


# ---------------------------------------------------------------------------
# resolve_opencode_command — env override and PATH discovery
# ---------------------------------------------------------------------------


class TestResolveOpencodeCommand:
    def test_env_override_simple_binary(self):
        """OPENCODE_COMMAND with a simple binary is returned as-is."""
        result = resolve_opencode_command({"OPENCODE_COMMAND": "/usr/local/bin/opencode"})
        assert result == "/usr/local/bin/opencode"

    def test_env_override_compound_command(self):
        """OPENCODE_COMMAND with a compound value (binary + args) is returned as-is."""
        result = resolve_opencode_command({"OPENCODE_COMMAND": "python /path/to/opencode.py"})
        assert result == "python /path/to/opencode.py"

    def test_env_override_with_space_in_value(self):
        """OPENCODE_COMMAND='opencode run' override is honoured without PATH lookup."""
        result = resolve_opencode_command({"OPENCODE_COMMAND": "opencode run"})
        assert result == "opencode run"

    @patch("vibecode.adapters.opencode.shutil.which", return_value="/usr/bin/opencode")
    def test_default_returns_opencode_run_when_binary_found(self, _which):
        """Without OPENCODE_COMMAND, returns 'opencode run' when opencode is on PATH."""
        result = resolve_opencode_command({})
        assert result == "opencode run"

    @patch("vibecode.adapters.opencode.shutil.which", return_value=None)
    def test_default_returns_none_when_binary_missing(self, _which):
        """Without OPENCODE_COMMAND, returns None when opencode is not on PATH."""
        result = resolve_opencode_command({})
        assert result is None

    @patch("vibecode.adapters.opencode.shutil.which")
    def test_default_checks_only_executable_not_compound_string(self, mock_which):
        """The default binary lookup must call which('opencode'), NOT which('opencode run').

        Regression test: resolving the default command must split 'opencode run' and
        check only the executable part so shutil.which is never given a string with a
        space (which would always return None on most platforms).
        """
        mock_which.return_value = None
        resolve_opencode_command({})

        # which() must have been called at most once, and never with a string
        # that contains a space (i.e. never with the whole "opencode run" string).
        for call in mock_which.call_args_list:
            arg = call.args[0] if call.args else call.kwargs.get("name", "")
            assert " " not in arg, (
                f"shutil.which called with compound string {arg!r}; "
                "only the executable part ('opencode') should be checked."
            )

    def test_env_override_wins_over_missing_path(self):
        """OPENCODE_COMMAND is returned even when the binary is absent from PATH."""
        # No PATH mocking needed: env_cmd takes priority before any PATH lookup.
        result = resolve_opencode_command({"OPENCODE_COMMAND": "my-custom-opencode"})
        assert result == "my-custom-opencode"


# ---------------------------------------------------------------------------
# check_opencode — compound command parsing (shlex-based)
# ---------------------------------------------------------------------------


class TestCompoundCommandParsing:
    """Verify that compound commands are parsed safely with shlex, not str.split."""

    @patch("vibecode.adapters.opencode.shutil.which", return_value="/usr/bin/python")
    @patch("vibecode.adapters.opencode.subprocess.run")
    def test_quoted_windows_path_parsed_correctly(self, mock_run, _which):
        """Quoted path like '"C:\\Program Files\\OpenCode\\opencode.cmd" run'
        must parse binary as the full quoted path, not 'C:\\Program'."""
        mock_run.return_value = MagicMock(returncode=0, stdout="v1.0\n", stderr="")

        status = check_opencode('"C:\\Program Files\\OpenCode\\opencode.cmd" run')

        # shlex.split turns the quoted path into one token:
        # ['C:\\Program Files\\OpenCode\\opencode.cmd', 'run']
        # The binary should be the full path, not a truncated fragment.
        assert status.available is True

    @patch("vibecode.adapters.opencode.shutil.which", return_value="/usr/bin/python")
    def test_missing_local_script_detected(self, _which):
        """Compound command 'python missing_opencode.py' where the script
        path looks local should fail the availability check."""
        status = check_opencode("python ./missing_opencode.py")
        assert status.available is False
        assert "not found" in status.message.lower()
        assert "missing_opencode.py" in status.message

    @patch("vibecode.adapters.opencode.shutil.which", return_value="/usr/bin/python")
    def test_non_pathlike_arg_skips_existence_check(self, _which):
        """Compound command 'python some_module' where the arg does not look
        like a path should not check existence (module/-m style invocation)."""
        status = check_opencode("python some_module")
        assert status.available is True

    @patch("vibecode.adapters.opencode.shutil.which", return_value="/usr/bin/python")
    def test_missing_absolute_script_detected(self, _which):
        """Compound command with an absolute missing script path should fail."""
        status = check_opencode("python /nonexistent/path/to/wrapper.py")
        assert status.available is False
        assert "/nonexistent/path/to/wrapper.py" in status.message

    def test_malformed_quoting_returns_unavailable(self):
        """Unterminated quote in command string should produce a safe error."""
        status = check_opencode('opencode "unterminated')
        assert status.available is False
        assert "could not be parsed" in status.message.lower()
