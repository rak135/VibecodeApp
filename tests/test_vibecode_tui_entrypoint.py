"""Tests for vibecode TUI entrypoint routing.

Covers:
- No-argument routing to TUI bootstrap
- Explicit ``vibecode tui [repo]`` alias
- Existing commands are unbroken
- Textual-unavailable error path
"""

from __future__ import annotations

import pytest

from vibecode.cli import create_parser, main


# ---------------------------------------------------------------------------
# No-argument routing
# ---------------------------------------------------------------------------


class TestNoArgRouting:
    def test_no_args_routes_to_cmd_tui(self, monkeypatch):
        """main([]) must dispatch to cmd_tui, not print help."""
        import vibecode.main_app as ma

        called = []
        monkeypatch.setattr(ma, "cmd_tui", lambda args: called.append(args) or 0)
        rc = main([])
        assert rc == 0
        assert len(called) == 1

    def test_no_args_passes_args_without_explicit_repo(self, monkeypatch):
        """When called with no args, cmd_tui receives args with no explicit repo."""
        import vibecode.main_app as ma

        captured = []

        def _capture(args):
            captured.append(getattr(args, "repo", "MISSING"))
            return 0

        monkeypatch.setattr(ma, "cmd_tui", _capture)
        main([])
        # The no-arg path has no 'repo' attribute parsed; None or MISSING are both fine
        assert captured[0] in (None, "MISSING")

    def test_no_args_does_not_print_help(self, monkeypatch, capsys):
        """main([]) must not print argparse help text when routing to TUI."""
        import vibecode.main_app as ma

        monkeypatch.setattr(ma, "cmd_tui", lambda args: 0)
        main([])
        out = capsys.readouterr().out
        assert "usage:" not in out.lower()


# ---------------------------------------------------------------------------
# Explicit tui subcommand
# ---------------------------------------------------------------------------


class TestExplicitTuiSubcommand:
    def test_tui_subcommand_dispatches_to_cmd_tui(self, monkeypatch):
        """vibecode tui must dispatch to cmd_tui."""
        import vibecode.main_app as ma

        called = []
        monkeypatch.setattr(ma, "cmd_tui", lambda args: called.append(args) or 0)
        rc = main(["tui"])
        assert rc == 0
        assert len(called) == 1

    def test_tui_subcommand_with_repo_passes_repo(self, monkeypatch, tmp_path):
        """vibecode tui /path must pass the repo path to cmd_tui."""
        import vibecode.main_app as ma

        captured = []

        def _capture(args):
            captured.append(getattr(args, "repo", None))
            return 0

        monkeypatch.setattr(ma, "cmd_tui", _capture)
        main(["tui", str(tmp_path)])
        assert captured[0] == str(tmp_path)

    def test_tui_without_repo_passes_none(self, monkeypatch):
        """vibecode tui without a path passes repo=None to cmd_tui."""
        import vibecode.main_app as ma

        captured = []

        def _capture(args):
            captured.append(getattr(args, "repo", None))
            return 0

        monkeypatch.setattr(ma, "cmd_tui", _capture)
        main(["tui"])
        assert captured[0] is None

    def test_tui_help_exits_zero(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["tui", "--help"])
        assert exc_info.value.code == 0

    def test_tui_command_registered_in_parser(self):
        """The parser must have a 'tui' subcommand registered."""
        parser = create_parser()
        # Parsing 'tui --help' must raise SystemExit(0), not an error
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["tui", "--help"])
        assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# Existing commands still work
# ---------------------------------------------------------------------------


class TestExistingCommandsUnbroken:
    def test_help_still_works(self):
        with pytest.raises(SystemExit) as exc_info:
            create_parser().parse_args(["--help"])
        assert exc_info.value.code == 0

    def test_init_help_still_works(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["init", "--help"])
        assert exc_info.value.code == 0

    def test_index_help_still_works(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["index", "--help"])
        assert exc_info.value.code == 0

    def test_guard_help_still_works(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["guard", "--help"])
        assert exc_info.value.code == 0

    def test_run_help_still_works(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["run", "--help"])
        assert exc_info.value.code == 0

    def test_context_help_still_works(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["context", "--help"])
        assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# Textual unavailable
# ---------------------------------------------------------------------------


class TestTextualUnavailable:
    def test_cmd_tui_returns_one_when_textual_unavailable(self, tmp_path, capsys):
        import vibecode.main_app as ma

        original = ma._TEXTUAL_AVAILABLE
        try:
            ma._TEXTUAL_AVAILABLE = False

            class FakeArgs:
                repo = str(tmp_path)

            rc = ma.cmd_tui(FakeArgs())
        finally:
            ma._TEXTUAL_AVAILABLE = original

        assert rc == 1
        err = capsys.readouterr().err
        assert "textual" in err.lower()

    def test_cmd_tui_prints_install_hint_when_textual_unavailable(self, tmp_path, capsys):
        import vibecode.main_app as ma

        original = ma._TEXTUAL_AVAILABLE
        try:
            ma._TEXTUAL_AVAILABLE = False

            class FakeArgs:
                repo = str(tmp_path)

            ma.cmd_tui(FakeArgs())
        finally:
            ma._TEXTUAL_AVAILABLE = original

        err = capsys.readouterr().err
        assert "pip install" in err
