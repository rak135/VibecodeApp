"""Tests for the OpenCode adapter (vibecode.adapters.opencode).

All tests use mocking to avoid requiring a real OpenCode installation.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from vibecode.adapters.opencode import (
    OpenCodeStatus,
    _default_command,
    check_opencode,
)


# ---------------------------------------------------------------------------
# _default_command
# ---------------------------------------------------------------------------


class TestDefaultCommand:
    def test_returns_opencode(self):
        assert _default_command() == "opencode"


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