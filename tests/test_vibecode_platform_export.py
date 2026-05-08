"""Tests for platform-specific prompt export."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from vibecode.cli import main
from vibecode.context.platform_export import render_opencode_prompt, write_opencode_prompt


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _minimal_repo(tmp_path: Path) -> None:
    _write(
        tmp_path / ".vibecode" / "project.yaml",
        "# vibecode project configuration\n"
        "# schema: vibecode/project/v1\n"
        "project:\n"
        "  id: testproject\n"
        "  name: Test Project\n"
        "  root: .\n"
        "indexing:\n"
        "  include: []\n"
        "  exclude: []\n"
        "protected_paths: []\n"
        "risk_rules: []\n",
    )
    _write(
        tmp_path / ".vibecode" / "architecture" / "INVARIANTS.md",
        "# Invariants\n\n- Generated indexes are not source of truth.\n",
    )
    _write(tmp_path / ".vibecode" / "index" / "file_inventory.json", '{"files": []}\n')


# ---------------------------------------------------------------------------
# render_opencode_prompt unit tests
# ---------------------------------------------------------------------------


def test_render_opencode_prompt_contains_preamble():
    content = render_opencode_prompt("# Context Pack\n")
    assert content.startswith("You are working inside a Vibecode-controlled repository.")


def test_render_opencode_prompt_contains_pre_edit_instructions():
    content = render_opencode_prompt("# Context Pack\n")
    assert "## Pre-edit instructions" in content
    assert "Read the task carefully" in content
    assert "protected or require confirmation" in content
    assert "Prefer narrow" in content


def test_render_opencode_prompt_contains_post_edit_instructions():
    content = render_opencode_prompt("# Context Pack\n")
    assert "## Post-edit instructions" in content
    assert "Summarize each file you changed" in content
    assert "List every test or check you ran" in content
    assert "Update the handoff document" in content


def test_render_opencode_prompt_embeds_context_pack():
    pack = "# Vibecode Context Pack\n\n## Current task\n\ndo something\n"
    content = render_opencode_prompt(pack)
    assert "# Vibecode Context Pack" in content
    assert "## Current task" in content
    assert "do something" in content


def test_render_opencode_prompt_separator_between_wrapper_and_pack():
    content = render_opencode_prompt("## Current task\n\ntest\n")
    assert "\n---\n" in content


# ---------------------------------------------------------------------------
# write_opencode_prompt integration
# ---------------------------------------------------------------------------


def test_write_opencode_prompt_creates_file(tmp_path):
    pack_content = "# Vibecode Context Pack\n\n## Current task\n\nexample\n"
    out = write_opencode_prompt(tmp_path, pack_content)
    assert out == tmp_path / ".vibecode" / "current" / "opencode_prompt.md"
    assert out.exists()


def test_write_opencode_prompt_content_correct(tmp_path):
    pack_content = "# Pack\n\nsome content\n"
    write_opencode_prompt(tmp_path, pack_content)
    text = (tmp_path / ".vibecode" / "current" / "opencode_prompt.md").read_text(encoding="utf-8")
    assert "You are working inside a Vibecode-controlled repository." in text
    assert "some content" in text


# ---------------------------------------------------------------------------
# CLI integration: vibecode context --platform opencode
# ---------------------------------------------------------------------------


def test_context_platform_opencode_creates_prompt_file(tmp_path):
    _minimal_repo(tmp_path)
    rc = main(["context", str(tmp_path), "--task", "add opencode support", "--platform", "opencode"])
    assert rc == 0
    prompt_path = tmp_path / ".vibecode" / "current" / "opencode_prompt.md"
    assert prompt_path.exists()


def test_context_platform_opencode_prompt_contains_wrapper(tmp_path):
    _minimal_repo(tmp_path)
    main(["context", str(tmp_path), "--task", "build the feature", "--platform", "opencode"])
    content = (tmp_path / ".vibecode" / "current" / "opencode_prompt.md").read_text(encoding="utf-8")
    assert "You are working inside a Vibecode-controlled repository." in content
    assert "## Pre-edit instructions" in content
    assert "## Post-edit instructions" in content


def test_context_platform_opencode_prompt_contains_context_pack(tmp_path):
    _minimal_repo(tmp_path)
    task = "embed context pack test"
    main(["context", str(tmp_path), "--task", task, "--platform", "opencode"])
    content = (tmp_path / ".vibecode" / "current" / "opencode_prompt.md").read_text(encoding="utf-8")
    assert "# Vibecode Context Pack" in content
    assert task in content


def test_context_without_platform_does_not_create_prompt_file(tmp_path):
    _minimal_repo(tmp_path)
    main(["context", str(tmp_path), "--task", "no platform"])
    prompt_path = tmp_path / ".vibecode" / "current" / "opencode_prompt.md"
    assert not prompt_path.exists()


def test_context_platform_opencode_does_not_launch_subprocess(tmp_path, monkeypatch):
    """No agent runtime must be spawned when generating the prompt."""
    launched: list[tuple] = []

    original_run = subprocess.run

    def patched_run(*args, **kwargs):  # noqa: ANN002
        launched.append(args)
        return original_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", patched_run)

    _minimal_repo(tmp_path)
    main(["context", str(tmp_path), "--task", "no subprocess", "--platform", "opencode"])

    # Ensure none of the subprocess calls involved opencode
    for call_args in launched:
        cmd = call_args[0] if call_args else []
        if isinstance(cmd, (list, tuple)):
            assert not any("opencode" in str(part).lower() for part in cmd)
        else:
            assert "opencode" not in str(cmd).lower()
