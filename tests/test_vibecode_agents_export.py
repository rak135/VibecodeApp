"""Tests for agent instructions export."""

from __future__ import annotations

from pathlib import Path

from vibecode.cli import main
from vibecode.context.agents_export import (
    AGENTS_GENERATED_PATH,
    AGENTS_MARKER_END,
    AGENTS_MARKER_START,
    AGENTS_ROOT_PATH,
    _is_vibecode_managed,
    _update_marker_block,
    render_agents_block,
    render_agents_file,
    write_agents_export,
)


# ---------------------------------------------------------------------------
# render_agents_block
# ---------------------------------------------------------------------------


def test_render_agents_block_before_start_section():
    block = render_agents_block()
    assert "## Before you start" in block


def test_render_agents_block_references_cli_context_command():
    block = render_agents_block()
    assert "vibecode.cli context" in block
    assert "--task" in block
    assert "Relevant files with reasons" in block


def test_render_agents_block_does_not_reference_stale_context_pack():
    block = render_agents_block()
    assert ".vibecode/current/context_pack.md" not in block


def test_render_agents_block_source_of_truth_section():
    block = render_agents_block()
    assert "## Source of truth" in block
    assert "PRD.json" in block


def test_render_agents_block_references_architecture_files():
    block = render_agents_block()
    assert "INVARIANTS.md" in block
    assert "STRUCTURE.md" in block


def test_render_agents_block_references_handoff():
    block = render_agents_block()
    assert ".vibecode/handoff/NOW.md" in block


def test_render_agents_block_rules_section():
    block = render_agents_block()
    assert "## Rules" in block
    assert "unrelated refactors" in block
    assert "protected files" in block
    assert "README" in block
    assert "required checks" in block
    assert "handoff" in block


def test_render_agents_block_readme_rule_is_manual_docs_scoped():
    block = render_agents_block()
    assert "Do not edit README unless the task explicitly scopes README/docs" in block
    assert "Do not update README outside marked generated blocks" not in block


def test_render_agents_block_do_not_edit_paths_include_run_metadata():
    block = render_agents_block()
    assert ".vibecode/runs/*" in block


def test_render_agents_block_lists_available_commands():
    block = render_agents_block()
    expected_commands = [
        "init",
        "index",
        "context",
        "map",
        "validate",
        "guard",
        "check",
        "handoff-check",
        "run",
        "run-plan",
        "history",
        "project",
        "export-agents",
    ]
    assert "## Available commands" in block
    for command in expected_commands:
        assert f"`vibecode {command}`" in block


def test_render_agents_block_command_order_matches_top_level_help():
    block = render_agents_block()
    commands = [
        "init",
        "index",
        "context",
        "map",
        "validate",
        "guard",
        "check",
        "handoff-check",
        "run",
        "run-plan",
        "history",
        "project",
        "export-agents",
    ]
    positions = [block.index(f"`vibecode {command}`") for command in commands]
    assert positions == sorted(positions)


def test_render_agents_block_does_not_describe_implemented_commands_as_pending():
    block = render_agents_block().lower()
    assert "planned" not in block
    assert "not wired" not in block
    assert "not started" not in block


def test_render_agents_block_is_short():
    block = render_agents_block()
    assert len(block.splitlines()) < 50, "Generated block should remain concise"


def test_render_agents_block_mentions_vibecode_source_of_truth():
    block = render_agents_block()
    assert ".vibecode/" in block


# ---------------------------------------------------------------------------
# render_agents_file
# ---------------------------------------------------------------------------


def test_render_agents_file_contains_markers():
    content = render_agents_file()
    assert AGENTS_MARKER_START in content
    assert AGENTS_MARKER_END in content


def test_render_agents_file_markers_wrap_block():
    content = render_agents_file()
    start = content.index(AGENTS_MARKER_START)
    end = content.index(AGENTS_MARKER_END)
    assert start < end


def test_render_agents_file_contains_block_content():
    content = render_agents_file()
    assert "## Before you start" in content
    assert "## Rules" in content


def test_committed_agents_md_matches_rendered_file():
    repo_root = Path(__file__).resolve().parents[1]
    assert (repo_root / AGENTS_ROOT_PATH).read_text(encoding="utf-8") == render_agents_file()


# ---------------------------------------------------------------------------
# _is_vibecode_managed
# ---------------------------------------------------------------------------


def test_is_vibecode_managed_true_when_both_markers_present():
    content = f"{AGENTS_MARKER_START}\nsome content\n{AGENTS_MARKER_END}\n"
    assert _is_vibecode_managed(content) is True


def test_is_vibecode_managed_false_when_no_markers():
    assert _is_vibecode_managed("# My own AGENTS.md\n\nDo stuff.\n") is False


def test_is_vibecode_managed_false_when_only_start_marker():
    assert _is_vibecode_managed(f"{AGENTS_MARKER_START}\ncontent\n") is False


def test_is_vibecode_managed_false_when_only_end_marker():
    assert _is_vibecode_managed(f"content\n{AGENTS_MARKER_END}\n") is False


# ---------------------------------------------------------------------------
# _update_marker_block
# ---------------------------------------------------------------------------


def test_update_marker_block_replaces_content():
    original = f"prefix\n{AGENTS_MARKER_START}\nold block\n{AGENTS_MARKER_END}\nsuffix\n"
    new_block = "new block\n"
    result = _update_marker_block(original, new_block)
    assert "old block" not in result
    assert "new block" in result


def test_update_marker_block_preserves_surrounding_content():
    original = f"prefix\n{AGENTS_MARKER_START}\nold\n{AGENTS_MARKER_END}\nsuffix\n"
    result = _update_marker_block(original, "new\n")
    assert result.startswith("prefix\n")
    assert result.endswith("suffix\n")


def test_update_marker_block_keeps_markers():
    original = f"{AGENTS_MARKER_START}\nold\n{AGENTS_MARKER_END}\n"
    result = _update_marker_block(original, "new\n")
    assert AGENTS_MARKER_START in result
    assert AGENTS_MARKER_END in result


# ---------------------------------------------------------------------------
# write_agents_export – no existing AGENTS.md
# ---------------------------------------------------------------------------


def test_write_agents_export_always_writes_generated_file(tmp_path):
    gen, _ = write_agents_export(tmp_path)
    assert gen == tmp_path / AGENTS_GENERATED_PATH
    assert gen.exists()


def test_write_agents_export_generated_file_contains_block(tmp_path):
    write_agents_export(tmp_path)
    content = (tmp_path / AGENTS_GENERATED_PATH).read_text(encoding="utf-8")
    assert "## Before you start" in content


def test_write_agents_export_creates_agents_md_when_absent(tmp_path):
    _, agents_md = write_agents_export(tmp_path)
    assert agents_md == tmp_path / AGENTS_ROOT_PATH
    assert (tmp_path / AGENTS_ROOT_PATH).exists()


def test_write_agents_export_agents_md_has_markers(tmp_path):
    write_agents_export(tmp_path)
    content = (tmp_path / AGENTS_ROOT_PATH).read_text(encoding="utf-8")
    assert AGENTS_MARKER_START in content
    assert AGENTS_MARKER_END in content


# ---------------------------------------------------------------------------
# write_agents_export – existing AGENTS.md with markers (update)
# ---------------------------------------------------------------------------


def test_write_agents_export_updates_managed_agents_md(tmp_path):
    agents_md = tmp_path / AGENTS_ROOT_PATH
    agents_md.write_text(
        f"{AGENTS_MARKER_START}\nold content\n{AGENTS_MARKER_END}\n",
        encoding="utf-8",
    )
    _, written = write_agents_export(tmp_path)
    assert written == agents_md
    content = agents_md.read_text(encoding="utf-8")
    assert "old content" not in content
    assert "## Before you start" in content


def test_write_agents_export_update_preserves_surrounding_content(tmp_path):
    agents_md = tmp_path / AGENTS_ROOT_PATH
    agents_md.write_text(
        f"# My Notes\n\n{AGENTS_MARKER_START}\nold\n{AGENTS_MARKER_END}\n\nMore text.\n",
        encoding="utf-8",
    )
    write_agents_export(tmp_path)
    content = agents_md.read_text(encoding="utf-8")
    assert "# My Notes" in content
    assert "More text." in content


def test_write_agents_export_managed_agents_md_is_idempotent(tmp_path):
    agents_md = tmp_path / AGENTS_ROOT_PATH
    agents_md.write_text(render_agents_file(), encoding="utf-8")
    before = agents_md.read_text(encoding="utf-8")
    _, written = write_agents_export(tmp_path)
    assert written == agents_md
    assert agents_md.read_text(encoding="utf-8") == before


# ---------------------------------------------------------------------------
# write_agents_export – existing AGENTS.md without markers (skip / force)
# ---------------------------------------------------------------------------


def test_write_agents_export_skips_unmanaged_agents_md(tmp_path):
    agents_md = tmp_path / AGENTS_ROOT_PATH
    original = "# Hand-written AGENTS.md\n\nDo not overwrite me.\n"
    agents_md.write_text(original, encoding="utf-8")
    _, written = write_agents_export(tmp_path)
    assert written is None
    assert agents_md.read_text(encoding="utf-8") == original


def test_write_agents_export_force_overwrites_unmanaged_agents_md(tmp_path):
    agents_md = tmp_path / AGENTS_ROOT_PATH
    agents_md.write_text("# Hand-written AGENTS.md\n", encoding="utf-8")
    _, written = write_agents_export(tmp_path, force=True)
    assert written == agents_md
    content = agents_md.read_text(encoding="utf-8")
    assert AGENTS_MARKER_START in content
    assert "## Before you start" in content


def test_write_agents_export_force_still_writes_generated(tmp_path):
    (tmp_path / AGENTS_ROOT_PATH).write_text("# existing\n", encoding="utf-8")
    gen, _ = write_agents_export(tmp_path, force=True)
    assert gen.exists()


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


def test_cli_export_agents_returns_zero(tmp_path):
    rc = main(["export-agents", str(tmp_path)])
    assert rc == 0


def test_cli_export_agents_creates_generated_file(tmp_path):
    main(["export-agents", str(tmp_path)])
    assert (tmp_path / AGENTS_GENERATED_PATH).exists()


def test_cli_export_agents_creates_agents_md(tmp_path):
    main(["export-agents", str(tmp_path)])
    assert (tmp_path / AGENTS_ROOT_PATH).exists()


def test_cli_export_agents_does_not_overwrite_unmanaged(tmp_path):
    original = "# Hand-written\n\nDo not touch.\n"
    (tmp_path / AGENTS_ROOT_PATH).write_text(original, encoding="utf-8")
    main(["export-agents", str(tmp_path)])
    assert (tmp_path / AGENTS_ROOT_PATH).read_text(encoding="utf-8") == original


def test_cli_export_agents_force_overwrites_unmanaged(tmp_path):
    (tmp_path / AGENTS_ROOT_PATH).write_text("# Hand-written\n", encoding="utf-8")
    rc = main(["export-agents", str(tmp_path), "--force"])
    assert rc == 0
    content = (tmp_path / AGENTS_ROOT_PATH).read_text(encoding="utf-8")
    assert AGENTS_MARKER_START in content


def test_cli_export_agents_managed_agents_md_returns_zero(tmp_path):
    agents_md = tmp_path / AGENTS_ROOT_PATH
    agents_md.write_text(
        f"{AGENTS_MARKER_START}\nold content\n{AGENTS_MARKER_END}\n",
        encoding="utf-8",
    )
    rc = main(["export-agents", str(tmp_path)])
    assert rc == 0
    assert "old content" not in agents_md.read_text(encoding="utf-8")


def test_cli_export_agents_manual_without_force_returns_nonzero(tmp_path):
    (tmp_path / AGENTS_ROOT_PATH).write_text("# Hand-written\n\nDo not touch.\n", encoding="utf-8")
    rc = main(["export-agents", str(tmp_path)])
    assert rc != 0


def test_cli_export_agents_manual_without_force_still_writes_generated(tmp_path):
    (tmp_path / AGENTS_ROOT_PATH).write_text("# Hand-written\n", encoding="utf-8")
    main(["export-agents", str(tmp_path)])
    assert (tmp_path / AGENTS_GENERATED_PATH).exists()


def test_cli_export_agents_default_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc = main(["export-agents"])
    assert rc == 0
    assert (tmp_path / AGENTS_GENERATED_PATH).exists()
