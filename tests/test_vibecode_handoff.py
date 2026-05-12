"""Tests for handoff file validation."""

from __future__ import annotations

from pathlib import Path

from vibecode.handoff import validate_handoff_files


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _handoff_dir(tmp_path: Path) -> Path:
    return tmp_path / ".vibecode" / "handoff"


# ── Valid (passing) cases ──────────────────────────────────────────────


def test_valid_now_passes(tmp_path):
    _write(_handoff_dir(tmp_path) / "NOW.md", "# Now\n\nBuilding the auth module.\n")
    _write(_handoff_dir(tmp_path) / "NEXT.md", "# Next\n\nAdd tests for auth.\n")
    _write(_handoff_dir(tmp_path) / "BLOCKERS.md", "# Blockers\n\nNo hard technical blocker.\n")

    result = validate_handoff_files(tmp_path)

    assert result.passed is True
    assert result.issues == []


def test_blockers_explicit_no_blocker_passes(tmp_path):
    _write(_handoff_dir(tmp_path) / "NOW.md", "# Now\n\nWorking on X.\n")
    _write(_handoff_dir(tmp_path) / "NEXT.md", "# Next\n\nDo stuff.\n")
    _write(
        _handoff_dir(tmp_path) / "BLOCKERS.md",
        "# Blockers\n\n- No hard technical blocker.\n",
    )

    result = validate_handoff_files(tmp_path)
    assert result.passed is True


def test_blockers_with_real_blockers_passes(tmp_path):
    _write(_handoff_dir(tmp_path) / "NOW.md", "# Now\n\nWaiting on API.\n")
    _write(_handoff_dir(tmp_path) / "NEXT.md", "# Next\n\nIntegrate API.\n")
    _write(
        _handoff_dir(tmp_path) / "BLOCKERS.md",
        "# Blockers\n\n- Waiting on external API credentials from vendor.\n",
    )

    result = validate_handoff_files(tmp_path)
    assert result.passed is True


def test_missing_handoff_files_fail(tmp_path):
    """All three files missing → three issues."""
    result = validate_handoff_files(tmp_path)

    assert result.passed is False
    assert len(result.issues) == 3
    files = {i.file for i in result.issues}
    assert ".vibecode/handoff/NOW.md" in files
    assert ".vibecode/handoff/NEXT.md" in files
    assert ".vibecode/handoff/BLOCKERS.md" in files


# ── Heading-only cases ────────────────────────────────────────────────


def test_heading_only_now_fails(tmp_path):
    _write(_handoff_dir(tmp_path) / "NOW.md", "# Now\n")
    _write(_handoff_dir(tmp_path) / "NEXT.md", "# Next\n\nDo stuff.\n")
    _write(_handoff_dir(tmp_path) / "BLOCKERS.md", "# Blockers\n\nNo hard blocker.\n")

    result = validate_handoff_files(tmp_path)

    assert result.passed is False
    now_issues = [i for i in result.issues if "NOW" in i.file]
    assert len(now_issues) == 1
    assert "heading" in now_issues[0].message.lower()


def test_heading_only_next_fails(tmp_path):
    _write(_handoff_dir(tmp_path) / "NOW.md", "# Now\n\nWorking on X.\n")
    _write(_handoff_dir(tmp_path) / "NEXT.md", "# Next\n")
    _write(_handoff_dir(tmp_path) / "BLOCKERS.md", "# Blockers\n\nNo hard blocker.\n")

    result = validate_handoff_files(tmp_path)

    assert result.passed is False
    next_issues = [i for i in result.issues if "NEXT" in i.file]
    assert len(next_issues) == 1
    assert "heading" in next_issues[0].message.lower()


def test_heading_only_blockers_fails(tmp_path):
    _write(_handoff_dir(tmp_path) / "NOW.md", "# Now\n\nWorking on X.\n")
    _write(_handoff_dir(tmp_path) / "NEXT.md", "# Next\n\nDo Y.\n")
    _write(_handoff_dir(tmp_path) / "BLOCKERS.md", "# Blockers\n")

    result = validate_handoff_files(tmp_path)

    assert result.passed is False
    blocker_issues = [i for i in result.issues if "BLOCKERS" in i.file]
    assert len(blocker_issues) == 1


def test_is_heading_only():
    from vibecode.handoff import _is_heading_only

    assert _is_heading_only("# Now\n") is True
    assert _is_heading_only("# Blockers\n\n- something\n") is False
    assert _is_heading_only("") is False
    assert _is_heading_only("just text") is False


# ── Placeholder text ──────────────────────────────────────────────────


def test_todo_placeholder_fails(tmp_path):
    _write(_handoff_dir(tmp_path) / "NOW.md", "# Now\n\nTODO: figure this out\n")
    _write(_handoff_dir(tmp_path) / "NEXT.md", "# Next\n\nDo stuff.\n")
    _write(_handoff_dir(tmp_path) / "BLOCKERS.md", "# Blockers\n\nNo hard blocker.\n")

    result = validate_handoff_files(tmp_path)

    assert result.passed is False
    now_issues = [i for i in result.issues if "NOW" in i.file]
    assert any("placeholder" in i.message.lower() for i in now_issues)


def test_describing_todo_markers_is_not_placeholder(tmp_path):
    _write(
        _handoff_dir(tmp_path) / "NOW.md",
        "# Now\n\nRisk analysis records TODO/FIXME facts from source comments.\n",
    )
    _write(_handoff_dir(tmp_path) / "NEXT.md", "# Next\n\nKeep validating handoff state.\n")
    _write(_handoff_dir(tmp_path) / "BLOCKERS.md", "# Blockers\n\nNo hard blocker.\n")

    result = validate_handoff_files(tmp_path)

    assert result.passed is True


def test_tbd_placeholder_fails(tmp_path):
    _write(_handoff_dir(tmp_path) / "NOW.md", "# Now\n\nTBD\n")
    _write(_handoff_dir(tmp_path) / "NEXT.md", "# Next\n\nDo stuff.\n")
    _write(_handoff_dir(tmp_path) / "BLOCKERS.md", "# Blockers\n\nNo hard blocker.\n")

    result = validate_handoff_files(tmp_path)
    assert result.passed is False


def test_placeholder_word_fails(tmp_path):
    _write(_handoff_dir(tmp_path) / "NEXT.md", "# Next\n\nplaceholder text here\n")
    _write(_handoff_dir(tmp_path) / "NOW.md", "# Now\n\nWorking.\n")
    _write(_handoff_dir(tmp_path) / "BLOCKERS.md", "# Blockers\n\nNo hard blocker.\n")

    result = validate_handoff_files(tmp_path)
    assert result.passed is False


def test_html_comment_placeholder_fails(tmp_path):
    _write(
        _handoff_dir(tmp_path) / "BLOCKERS.md",
        "# Blockers\n\n<!-- TODO: fill in blockers -->\n",
    )
    _write(_handoff_dir(tmp_path) / "NOW.md", "# Now\n\nWorking.\n")
    _write(_handoff_dir(tmp_path) / "NEXT.md", "# Next\n\nDo stuff.\n")

    result = validate_handoff_files(tmp_path)
    assert result.passed is False


# ── Empty bullets ─────────────────────────────────────────────────────


def test_empty_bullet_fails(tmp_path):
    _write(_handoff_dir(tmp_path) / "NOW.md", "# Now\n\n- \n")
    _write(_handoff_dir(tmp_path) / "NEXT.md", "# Next\n\nDo stuff.\n")
    _write(_handoff_dir(tmp_path) / "BLOCKERS.md", "# Blockers\n\nNo hard blocker.\n")

    result = validate_handoff_files(tmp_path)
    assert result.passed is False
    now_issues = [i for i in result.issues if "NOW" in i.file]
    assert any("empty bullet" in i.message.lower() for i in now_issues)


def test_empty_dash_bullet_fails(tmp_path):
    _write(_handoff_dir(tmp_path) / "NEXT.md", "# Next\n\n-\n")
    _write(_handoff_dir(tmp_path) / "NOW.md", "# Now\n\nWorking.\n")
    _write(_handoff_dir(tmp_path) / "BLOCKERS.md", "# Blockers\n\nNo hard blocker.\n")

    result = validate_handoff_files(tmp_path)
    assert result.passed is False


# ── Multi-issue: several problems at once ─────────────────────────────


def test_multiple_issues_reported(tmp_path):
    _write(_handoff_dir(tmp_path) / "NOW.md", "# Now\n")
    _write(_handoff_dir(tmp_path) / "NEXT.md", "# Next\n\nTODO:\n")
    _write(_handoff_dir(tmp_path) / "BLOCKERS.md", "# Blockers\n")

    result = validate_handoff_files(tmp_path)

    assert result.passed is False
    # NOW: heading-only
    # NEXT: heading-only + placeholder
    # BLOCKERS: heading-only
    assert len(result.issues) >= 3


# ── Result dict serialisation ─────────────────────────────────────────


def test_result_as_dict(tmp_path):
    _write(_handoff_dir(tmp_path) / "NOW.md", "# Now\n")
    _write(_handoff_dir(tmp_path) / "NEXT.md", "# Next\n\nDo X.\n")
    _write(_handoff_dir(tmp_path) / "BLOCKERS.md", "# Blockers\n\nNo hard blocker.\n")

    result = validate_handoff_files(tmp_path)
    d = result.as_dict()

    assert d["status"] == "error"
    assert isinstance(d["issues"], list)
    assert any("NOW" in i["file"] for i in d["issues"])


def test_passing_result_as_dict(tmp_path):
    _write(_handoff_dir(tmp_path) / "NOW.md", "# Now\n\nConcrete work.\n")
    _write(_handoff_dir(tmp_path) / "NEXT.md", "# Next\n\nConcrete next.\n")
    _write(_handoff_dir(tmp_path) / "BLOCKERS.md", "# Blockers\n\nNo hard technical blocker.\n")

    result = validate_handoff_files(tmp_path)
    d = result.as_dict()

    assert d["status"] == "ok"
    assert d["issues"] == []


# ── Architecture change without handoff history ────────────────────────


def _make_valid_handoff(root: Path) -> None:
    """Create valid handoff files so that only the architecture check is exercised."""
    handoff_dir = root / ".vibecode" / "handoff"
    _write(handoff_dir / "NOW.md", "# Now\n\nConcrete current state.\n")
    _write(handoff_dir / "NEXT.md", "# Next\n\nConcrete next steps.\n")
    _write(handoff_dir / "BLOCKERS.md", "# Blockers\n\nNo hard blocker.\n")


def test_architecture_change_without_handoff_fails(tmp_path):
    """Changing an architecture doc without updating handoff/history fails."""
    _make_valid_handoff(tmp_path)
    result = validate_handoff_files(
        tmp_path,
        diff=[".vibecode/architecture/INVARIANTS.md"],
    )

    assert result.passed is False
    issues = [i for i in result.issues if i.file.startswith(".vibecode/architecture/")]
    assert len(issues) == 1
    assert "handoff" in issues[0].message.lower()
    assert "history" in issues[0].message.lower()


def test_architecture_change_with_handoff_now_passes(tmp_path):
    """Changing an architecture doc while also updating NOW.md passes."""
    _make_valid_handoff(tmp_path)
    result = validate_handoff_files(
        tmp_path,
        diff=[".vibecode/architecture/INVARIANTS.md", ".vibecode/handoff/NOW.md"],
    )

    assert result.passed is True


def test_architecture_change_with_handoff_next_passes(tmp_path):
    """Changing an architecture doc while also updating NEXT.md passes."""
    _make_valid_handoff(tmp_path)
    result = validate_handoff_files(
        tmp_path,
        diff=[".vibecode/architecture/STRUCTURE.md", ".vibecode/handoff/NEXT.md"],
    )

    assert result.passed is True


def test_architecture_change_with_handoff_blockers_passes(tmp_path):
    """Changing an architecture doc while also updating BLOCKERS.md passes."""
    _make_valid_handoff(tmp_path)
    result = validate_handoff_files(
        tmp_path,
        diff=[".vibecode/architecture/OVERVIEW.md", ".vibecode/handoff/BLOCKERS.md"],
    )

    assert result.passed is True


def test_architecture_change_with_history_passes(tmp_path):
    """Changing an architecture doc while also updating a history file passes."""
    _make_valid_handoff(tmp_path)
    _write(tmp_path / ".vibecode" / "history" / "architecture-summary.md", "# Summary\n\nChange described.\n")
    result = validate_handoff_files(
        tmp_path,
        diff=[
            ".vibecode/architecture/INVARIANTS.md",
            ".vibecode/history/architecture-summary.md",
        ],
    )

    assert result.passed is True


def test_non_architecture_change_without_handoff_passes(tmp_path):
    """Changing a source file (not architecture) does not require handoff."""
    _make_valid_handoff(tmp_path)
    result = validate_handoff_files(
        tmp_path,
        diff=["vibecode/handoff.py"],
    )

    assert result.passed is True


def test_architecture_change_with_only_history_subdir_fails(tmp_path):
    """A history file nested in a subdirectory does NOT satisfy the requirement."""
    _make_valid_handoff(tmp_path)
    result = validate_handoff_files(
        tmp_path,
        diff=[
            ".vibecode/architecture/INVARIANTS.md",
            ".vibecode/history/subdir/notes.md",
        ],
    )

    # The subdirectory history file doesn't match the pattern
    # (only top-level .md files in .vibecode/history/ count)
    assert result.passed is False


def test_architecture_change_with_handoff_and_source_passes(tmp_path):
    """Architecture doc changed alongside handoff and source: OK."""
    _make_valid_handoff(tmp_path)
    result = validate_handoff_files(
        tmp_path,
        diff=[
            ".vibecode/architecture/DATA_FLOW.md",
            ".vibecode/handoff/NOW.md",
            "vibecode/some_module.py",
            "tests/test_something.py",
        ],
    )

    assert result.passed is True


def test_no_diff_passes(tmp_path):
    """Empty diff — no architecture changes, so no extra requirement."""
    _make_valid_handoff(tmp_path)
    result = validate_handoff_files(
        tmp_path,
        diff=[],
    )

    assert result.passed is True


def test_multiple_architecture_changes_without_handoff_fail(tmp_path):
    """Multiple architecture docs changed without handoff/history → failures."""
    _make_valid_handoff(tmp_path)
    result = validate_handoff_files(
        tmp_path,
        diff=[
            ".vibecode/architecture/INVARIANTS.md",
            ".vibecode/architecture/STRUCTURE.md",
        ],
    )

    assert result.passed is False
    issues = [i for i in result.issues if i.file.startswith(".vibecode/architecture/")]
    assert len(issues) == 2
    files = {i.file for i in issues}
    assert ".vibecode/architecture/INVARIANTS.md" in files
    assert ".vibecode/architecture/STRUCTURE.md" in files
