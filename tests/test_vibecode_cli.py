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


def test_handoff_check_help_exits_zero():
    with pytest.raises(SystemExit) as exc_info:
        main(["handoff-check", "--help"])
    assert exc_info.value.code == 0


def test_run_help_exits_zero():
    with pytest.raises(SystemExit) as exc_info:
        main(["run", "--help"])
    assert exc_info.value.code == 0


def test_run_plan_help_exits_zero():
    with pytest.raises(SystemExit) as exc_info:
        main(["run-plan", "--help"])
    assert exc_info.value.code == 0


def test_export_agents_help_exits_zero():
    with pytest.raises(SystemExit) as exc_info:
        main(["export-agents", "--help"])
    assert exc_info.value.code == 0


def test_monitor_help_exits_zero():
    with pytest.raises(SystemExit) as exc_info:
        main(["monitor", "--help"])
    assert exc_info.value.code == 0


def test_dashboard_help_exits_zero():
    with pytest.raises(SystemExit) as exc_info:
        main(["dashboard", "--help"])
    assert exc_info.value.code == 0


def test_no_command_routes_to_tui(monkeypatch):
    """main([]) must route to TUI bootstrap rather than printing help."""
    import vibecode.main_app as ma

    called = []
    monkeypatch.setattr(ma, "cmd_tui", lambda args: called.append(args) or 0)
    assert main([]) == 0
    assert len(called) == 1


def test_import_vibecode():
    import vibecode
    assert vibecode.__version__ == "0.1.0"


# ---------------------------------------------------------------------------
# Optional Textual dependency — CLI guard tests
# ---------------------------------------------------------------------------


def test_base_cli_help_works_when_textual_unavailable():
    """Top-level --help must not import Textual."""
    import vibecode.monitor_app as mon_mod
    import vibecode.tui_app as tui_mod

    original_mon = mon_mod._TEXTUAL_AVAILABLE
    original_tui = tui_mod._TEXTUAL_AVAILABLE
    try:
        mon_mod._TEXTUAL_AVAILABLE = False
        tui_mod._TEXTUAL_AVAILABLE = False
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0
    finally:
        mon_mod._TEXTUAL_AVAILABLE = original_mon
        tui_mod._TEXTUAL_AVAILABLE = original_tui


def test_non_monitor_command_works_when_textual_unavailable():
    """Non-TUI commands must work when Textual is absent."""
    import vibecode.monitor_app as mon_mod
    import vibecode.tui_app as tui_mod

    original_mon = mon_mod._TEXTUAL_AVAILABLE
    original_tui = tui_mod._TEXTUAL_AVAILABLE
    try:
        mon_mod._TEXTUAL_AVAILABLE = False
        tui_mod._TEXTUAL_AVAILABLE = False
        with pytest.raises(SystemExit) as exc_info:
            main(["guard", "--help"])
        assert exc_info.value.code == 0
    finally:
        mon_mod._TEXTUAL_AVAILABLE = original_mon
        tui_mod._TEXTUAL_AVAILABLE = original_tui


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_index_missing_repo_root_exits_nonzero_with_readable_message(tmp_path, capsys):
    missing = tmp_path / "nonexistent"
    rc = main(["index", str(missing)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "nonexistent" in err
    assert "Traceback" not in err


def test_map_missing_repo_root_exits_nonzero_with_readable_message(tmp_path, capsys):
    missing = tmp_path / "nonexistent"
    rc = main(["map", str(missing)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "nonexistent" in err
    assert "Traceback" not in err


def test_index_missing_project_yaml_suggests_init(tmp_path, capsys):
    rc = main(["index", str(tmp_path)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "vibecode init" in err
    assert "Traceback" not in err


def test_context_missing_repo_root_exits_nonzero_with_readable_message(tmp_path, capsys):
    missing = tmp_path / "nonexistent"
    rc = main(["context", str(missing), "--task", "test task"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "nonexistent" in err
    assert "Traceback" not in err


def test_context_missing_project_yaml_suggests_init(tmp_path, capsys):
    rc = main(["context", str(tmp_path), "--task", "test task"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "vibecode init" in err
    assert "Traceback" not in err


def test_debug_flag_shows_traceback_on_invalid_yaml(tmp_path, capsys):
    vdir = tmp_path / ".vibecode"
    vdir.mkdir()
    (vdir / "project.yaml").write_text("key: [unclosed\n", encoding="utf-8")
    rc = main(["--debug", "index", str(tmp_path)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "Traceback" in err


def test_no_debug_flag_hides_traceback_on_invalid_yaml(tmp_path, capsys):
    vdir = tmp_path / ".vibecode"
    vdir.mkdir()
    (vdir / "project.yaml").write_text("key: [unclosed\n", encoding="utf-8")
    rc = main(["index", str(tmp_path)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "Error" in err
    assert "Traceback" not in err
