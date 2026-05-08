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


def test_validate_help_exits_zero():
    with pytest.raises(SystemExit) as exc_info:
        main(["validate", "--help"])
    assert exc_info.value.code == 0


def test_map_shows_index_summary(tmp_path, capsys):
    last_index = tmp_path / ".vibecode" / "current" / "last_index.json"
    last_index.parent.mkdir(parents=True)
    inventory = tmp_path / ".vibecode" / "index" / "file_inventory.json"
    inventory.parent.mkdir(parents=True)

    last_index.write_text(
        __import__("json").dumps({
            "project_id": "myproj",
            "root": str(tmp_path),
            "started_at": "2024-01-15T10:30:00+00:00",
            "counts": {"files": 42, "symbols": 100, "tests": 8, "warnings": 1, "errors": 0},
            "warnings": ["Warning: example unfilled template"],
            "errors": [],
        }),
        encoding="utf-8",
    )
    inventory.write_text(
        __import__("json").dumps({
            "files": [
                {"language": "python", "risk_level": "high"},
                {"language": "python", "risk_level": "low"},
                {"language": "markdown", "risk_level": "low"},
            ]
        }),
        encoding="utf-8",
    )

    assert main(["map", str(tmp_path)]) == 0
    out = capsys.readouterr().out

    assert "myproj" in out
    assert "Files:       42" in out
    assert "Symbols:     100" in out
    assert "Tests:       8" in out
    assert "High-risk:   1" in out
    assert "2024-01-15 10:30:00 UTC" in out
    assert "Warning: example unfilled template" in out
    assert "python" in out


def test_map_without_index_exits_nonzero_and_suggests_index(tmp_path, capsys):
    assert main(["map", str(tmp_path)]) == 1
    err = capsys.readouterr().err

    assert "vibecode index" in err


def test_no_command_returns_zero():
    assert main([]) == 0


def test_import_vibecode():
    import vibecode
    assert vibecode.__version__ == "0.1.0"
