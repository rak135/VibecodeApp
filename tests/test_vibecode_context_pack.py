"""Tests for context pack rendering."""

from __future__ import annotations

import json
from pathlib import Path

from vibecode.cli import main
from vibecode.context.renderer import render_context_pack, DEFAULT_CHAR_LIMIT


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_context_command_writes_agent_ready_context_pack(tmp_path):
    task = 'implement real context pack'
    _write(
        tmp_path / ".vibecode" / "architecture" / "INVARIANTS.md",
        "# Invariants\n\n"
        "- Human-maintained architecture docs are source-controlled.\n"
        "- Generated indexes are not source of truth and must be regenerated.\n"
        "- Runtime/session state must not be committed.\n",
    )
    _write(
        tmp_path / ".vibecode" / "architecture" / "STRUCTURE.md",
        "# Repository Structure\n\n"
        "- `vibecode/cli.py` defines the command-line interface.\n"
        "- `vibecode/context/` owns task relevance and context-pack generation.\n"
        "- `.vibecode/architecture/*.md` contains committed architecture truth.\n",
    )
    _write(
        tmp_path / ".vibecode" / "checks" / "required_checks.yaml",
        "checks:\n"
        "  - name: unit tests\n"
        "    command: python -m pytest\n"
        "    required: true\n"
        "  - name: context command help\n"
        "    command: python -m vibecode.cli context --help\n"
        "    required: true\n",
    )
    _write(tmp_path / ".vibecode" / "handoff" / "NOW.md", "# Now\n\nContext pack task.\n")
    _write(tmp_path / ".vibecode" / "index" / "file_inventory.json", '{"files": []}\n')
    _write(
        tmp_path / ".vibecode" / "index" / "test_map.json",
        '{"rules": [{"path_pattern": "**", "required_checks": ["python -m pytest"]}]}\n',
    )
    _write(tmp_path / ".vibecode" / "index" / "repo_tree.generated.md", "# generated\n")
    _write(tmp_path / "vibecode" / "context" / "__init__.py", "def context():\n    return 'pack'\n")
    _write(tmp_path / "vibecode" / "context" / "renderer.py", "def render():\n    return 'pack'\n")
    _write(tmp_path / "vibecode" / "cli.py", "def main():\n    return 0\n")
    _write(tmp_path / "tests" / "test_vibecode_context_pack.py", "def test_context_pack():\n    assert True\n")
    _write(
        tmp_path / "vibecode" / "context" / "long_source.py",
        "\n".join(f"# long source line {index}" for index in range(200)),
    )

    assert main(["context", str(tmp_path), "--task", task]) == 0

    pack_path = tmp_path / ".vibecode" / "current" / "context_pack.md"
    assert pack_path.exists()
    content = pack_path.read_text(encoding="utf-8")

    assert "## Project" in content
    assert "## Current task\n\nimplement real context pack" in content
    assert "## Must preserve / invariants" in content
    assert "## Relevant architecture" in content
    assert "## Relevant files with reasons" in content
    assert "## Risky/protected files not allowed or requiring confirmation" in content
    assert "## Handoff required" in content
    assert "## Working rule" in content
    assert "- Human-maintained architecture docs are source-controlled." in content
    assert "- Generated indexes are not source of truth and must be regenerated." in content
    assert "`vibecode/context/__init__.py`" in content
    assert "`vibecode/context/renderer.py`" in content
    assert "`vibecode/cli.py`" in content
    assert "`tests/test_vibecode_context_pack.py`" in content
    assert "`.vibecode/architecture/STRUCTURE.md`" in content
    assert "unit tests: `python -m pytest`" in content
    assert "context command help: `python -m vibecode.cli context --help`" in content
    assert "test map required check: `python -m pytest`" in content
    assert "Do not edit `.vibecode/current/*`" in content
    assert "Generated indexes are derived" in content
    assert "# long source line 199" not in content


def test_legacy_context_command_shape_still_works(tmp_path):
    _write(
        tmp_path / ".vibecode" / "architecture" / "INVARIANTS.md",
        "# Invariants\n\n- Generated indexes are not source of truth and must be regenerated.\n",
    )

    assert main(["context", "legacy task", "--repo", str(tmp_path)]) == 0

    content = (tmp_path / ".vibecode" / "current" / "context_pack.md").read_text(
        encoding="utf-8"
    )
    assert "## Current task\n\nlegacy task" in content


# ---------------------------------------------------------------------------
# Length-limit tests
# ---------------------------------------------------------------------------

def _minimal_repo(tmp_path: Path) -> None:
    """Write the bare minimum fixture files used by renderer helpers."""
    _write(
        tmp_path / ".vibecode" / "architecture" / "INVARIANTS.md",
        "# Invariants\n\n"
        "- Human-maintained architecture docs are source-controlled.\n"
        "- Generated indexes are not source of truth.\n",
    )
    _write(tmp_path / ".vibecode" / "index" / "file_inventory.json", '{"files": []}\n')


def test_context_pack_fits_within_default_limit(tmp_path):
    """A normal context pack must not exceed DEFAULT_CHAR_LIMIT."""
    _minimal_repo(tmp_path)
    content = render_context_pack(tmp_path, "check length limit")
    assert len(content) <= DEFAULT_CHAR_LIMIT


def test_extremely_long_history_is_omitted_within_limit(tmp_path):
    """A tight limit must drop the handoff section before invariants."""
    _minimal_repo(tmp_path)
    # Also add architecture docs to bulk up total size (priority 8)
    for i in range(15):
        _write(
            tmp_path / ".vibecode" / "architecture" / f"ARCH_{i:02d}.md",
            f"# Architecture doc {i}\n\n"
            + "\n".join(f"- detail {j}: some longer description here" for j in range(10)),
        )
    _write(tmp_path / ".vibecode" / "handoff" / "NOW.md", "# Now\n\n" + "\n".join(
        f"- history entry {i}: " + "x" * 120 for i in range(500)
    ))

    # Use a tight limit that forces truncation
    tight_limit = 3_000
    content = render_context_pack(tmp_path, "check history truncation", char_limit=tight_limit)

    assert len(content) <= tight_limit
    # Invariants (priority 2) must remain
    assert "## Must preserve / invariants" in content
    assert "- Human-maintained architecture docs are source-controlled." in content
    # Truncation notice must be present
    assert "Context limit reached" in content
    # Handoff (priority 10) must be the first section mentioned as omitted
    assert "*Handoff required*" in content


def test_must_preserve_stays_when_lower_priority_sections_removed(tmp_path):
    """Invariants section must survive while lower-priority sections are dropped first."""
    _minimal_repo(tmp_path)
    # Bloat the architecture section (priority 8) with many docs
    for i in range(20):
        _write(
            tmp_path / ".vibecode" / "architecture" / f"ARCH_{i:02d}.md",
            f"# Architecture {i}\n\n"
            + "\n".join(f"- detail {j}: description text here" for j in range(10)),
        )
    _write(
        tmp_path / ".vibecode" / "handoff" / "NOW.md",
        "# Now\n\n" + "\n".join(f"- item {i}" for i in range(50)),
    )

    # Use a tight limit that forces truncation of lower-priority sections
    tight_limit = 3_000
    content = render_context_pack(tmp_path, "must preserve invariants", char_limit=tight_limit)

    assert len(content) <= tight_limit
    assert "## Must preserve / invariants" in content
    assert "- Human-maintained architecture docs are source-controlled." in content
    assert "Context limit reached" in content
    # Handoff (priority 10) and/or architecture (priority 8) must be omitted
    omitted_section = "*Handoff required*" in content or "*Relevant architecture*" in content
    assert omitted_section


def test_truncation_notice_names_omitted_sections(tmp_path):
    """When sections are dropped, the notice must list their names."""
    _minimal_repo(tmp_path)
    bloat = "\n".join(f"- entry {i}: " + "a" * 100 for i in range(600))
    _write(tmp_path / ".vibecode" / "handoff" / "NOW.md", "# Now\n\n" + bloat)

    content = render_context_pack(tmp_path, "check omission notice", char_limit=5_000)

    if "Context limit reached" in content:
        assert "*Handoff required*" in content


def test_high_priority_sections_present_before_lower_in_output(tmp_path):
    """Task and invariants sections appear before architecture in the output."""
    _minimal_repo(tmp_path)
    _write(
        tmp_path / ".vibecode" / "architecture" / "STRUCTURE.md",
        "# Structure\n\n- some architecture detail.\n",
    )
    content = render_context_pack(tmp_path, "ordering check")

    task_pos = content.index("## Current task")
    invariants_pos = content.index("## Must preserve / invariants")
    architecture_pos = content.index("## Relevant architecture")

    assert task_pos < invariants_pos < architecture_pos


# ---------------------------------------------------------------------------
# No-confirmed-invariants warning tests
# ---------------------------------------------------------------------------

def test_context_pack_warns_when_invariants_empty(tmp_path):
    """Empty INVARIANTS.md causes context pack to include the no-invariants warning."""
    _write(tmp_path / ".vibecode" / "architecture" / "INVARIANTS.md", "\n")
    _write(tmp_path / ".vibecode" / "index" / "file_inventory.json", '{"files": []}\n')

    content = render_context_pack(tmp_path, "some task")

    assert "no confirmed invariants" in content
    assert "weak project rules" in content


def test_context_pack_warns_when_invariants_missing(tmp_path):
    """Missing INVARIANTS.md causes context pack to include the no-invariants warning."""
    _write(tmp_path / ".vibecode" / "index" / "file_inventory.json", '{"files": []}\n')

    content = render_context_pack(tmp_path, "some task")

    assert "no confirmed invariants" in content
    assert "weak project rules" in content


def test_context_pack_no_warning_when_invariants_filled(tmp_path):
    """Filled INVARIANTS.md does not trigger the no-invariants warning in context pack."""
    _write(
        tmp_path / ".vibecode" / "architecture" / "INVARIANTS.md",
        "# Invariants\n\n- No package may import from a sibling package.\n",
    )
    _write(tmp_path / ".vibecode" / "index" / "file_inventory.json", '{"files": []}\n')

    content = render_context_pack(tmp_path, "some task")

    assert "no confirmed invariants" not in content
    assert "- No package may import from a sibling package." in content


# ---------------------------------------------------------------------------
# Symbol navigation tests
# ---------------------------------------------------------------------------


def test_long_file_path_and_symbols_appear_not_full_content(tmp_path):
    """A long source file must appear as a path with symbol names, not full content.

    Acceptance criteria (from PRD):
    - path/symbols appear in the context pack as navigation targets,
    - full file content is never embedded.
    """
    long_file_lines = (
        "def alpha_function():\n    pass\n\n"
        "def beta_function():\n    pass\n\n"
        "class GammaClass:\n    pass\n\n"
    ) + "\n".join(
        f"# implementation detail line {i}: " + "x" * 40
        for i in range(200)
    )
    _write(tmp_path / "vibecode" / "context" / "long_module.py", long_file_lines)

    # Register file in inventory so the scorer considers it.
    _write(
        tmp_path / ".vibecode" / "index" / "file_inventory.json",
        json.dumps({"files": [{"path": "vibecode/context/long_module.py"}]}) + "\n",
    )

    # Provide symbol names only — symbol_map never stores file content.
    _write(
        tmp_path / ".vibecode" / "index" / "symbol_map.json",
        json.dumps({
            "$schema": "vibecode/symbol-map/v1",
            "files": [
                {
                    "path": "vibecode/context/long_module.py",
                    "language": "python",
                    "symbols": [
                        {"name": "alpha_function", "kind": "function", "line_start": 1},
                        {"name": "beta_function", "kind": "function", "line_start": 4},
                        {"name": "GammaClass", "kind": "class", "line_start": 7},
                    ],
                }
            ],
        }) + "\n",
    )

    _write(
        tmp_path / ".vibecode" / "architecture" / "INVARIANTS.md",
        "# Invariants\n\n- No full source file content in context packs.\n",
    )

    content = render_context_pack(tmp_path, "context pack navigation for long module")

    # The file path must appear as a navigation target.
    assert "vibecode/context/long_module.py" in content

    # Short symbol names must be present (navigation hints, not file content).
    assert "alpha_function" in content
    assert "beta_function" in content
    assert "GammaClass" in content

    # Full file content must NOT be embedded — check unique identifiable lines.
    assert "implementation detail line 100" not in content
    assert "implementation detail line 199" not in content
