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