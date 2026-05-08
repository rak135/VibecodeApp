"""Tests for vibecode CLI commands."""

from __future__ import annotations

import pytest

from vibecode.cli import create_parser, main


def test_help_exits_zero():
    with pytest.raises(SystemExit) as exc_info:
        create_parser().parse_args(["--help"])
    assert exc_info.value.code == 0


def test_init_help_exits_zero():
    with pytest.raises(SystemExit) as exc_info:
        main(["init", "--help"])
    assert exc_info.value.code == 0


def test_index_help_exits_zero():
    with pytest.raises(SystemExit) as exc_info:
        main(["index", "--help"])
    assert exc_info.value.code == 0


def test_context_help_exits_zero():
    with pytest.raises(SystemExit) as exc_info:
        main(["context", "--help"])
    assert exc_info.value.code == 0


def test_map_help_exits_zero():
    with pytest.raises(SystemExit) as exc_info:
        main(["map", "--help"])
    assert exc_info.value.code == 0


def test_no_command_returns_zero():
    assert main([]) == 0


def test_import_vibecode():
    import vibecode
    assert vibecode.__version__ == "0.1.0"
