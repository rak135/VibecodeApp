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


def test_map_reads_generated_repo_tree(tmp_path, capsys):
    tree = tmp_path / ".vibecode" / "index" / "repo_tree.generated.md"
    tree.parent.mkdir(parents=True)
    tree.write_text("# Repository Tree\n\nfrom generated index\n", encoding="utf-8")

    assert main(["map", str(tmp_path)]) == 0
    captured = capsys.readouterr()

    assert "from generated index" in captured.out
    assert not (tmp_path / ".vibecode" / "current" / "repo_tree.md").exists()


def test_map_without_generated_repo_tree_exits_nonzero(tmp_path, capsys):
    assert main(["map", str(tmp_path)]) == 1
    captured = capsys.readouterr()

    assert "Run `vibecode index` first" in captured.err


def test_no_command_returns_zero():
    assert main([]) == 0


def test_import_vibecode():
    import vibecode
    assert vibecode.__version__ == "0.1.0"
