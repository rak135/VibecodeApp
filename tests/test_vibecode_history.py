"""Tests for history summary validation."""

from __future__ import annotations

from pathlib import Path

from vibecode.history import (
    HistoryIssue,
    HistoryResult,
    REQUIRED_SECTIONS,
    validate_history_dir,
    validate_history_file,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _history_dir(tmp_path: Path) -> Path:
    return tmp_path / ".vibecode" / "history"


# ── Valid (passing) cases ──────────────────────────────────────────────


def test_complete_summary_passes(tmp_path):
    """A summary with all required sections passes."""
    history = _history_dir(tmp_path)
    _write(
        history / "update-auth.md",
        (
            "# Update Auth\n\n"
            "### Task\n"
            "Add JWT-based auth to the API.\n\n"
            "### Changed files\n"
            "- `src/auth.py`: Added JWT token generation and validation.\n"
            "- `src/api.py`: Added `auth_required` decorator.\n\n"
            "### Behavior changed\n"
            "All `/api/*` endpoints now require a valid `Authorization` header.\n\n"
            "### Tests run\n"
            "- `tests/test_auth.py`: 12 passed, 0 failed.\n"
            "- `tests/test_api.py`: 28 passed, 0 failed.\n\n"
            "### Decisions\n"
            "Chose JWT over session cookies because the API is stateless.\n\n"
            "### Follow-up\n"
            "- Add refresh-token rotation.\n"
            "- Write integration tests for expired tokens.\n"
        ),
    )

    result = validate_history_file(history / "update-auth.md", tmp_path)
    assert result == []


def test_empty_history_dir_passes(tmp_path):
    """No history files → no issues."""
    result = validate_history_dir(tmp_path)

    assert result.passed is True
    assert result.files_checked == 0
    assert result.issues == []


def test_readme_always_skipped(tmp_path):
    """README.md in history dir is never validated as a summary."""
    history = _history_dir(tmp_path)
    _write(history / "README.md", "# Policy\n\nJust a policy file.\n")

    result = validate_history_dir(tmp_path)

    assert result.passed is True
    assert result.files_checked == 0


# ── Missing sections ──────────────────────────────────────────────────


def test_missing_single_section_fails(tmp_path):
    """A summary missing one required section reports it."""
    history = _history_dir(tmp_path)
    content = "# Incomplete\n\n### Task\nDo X.\n\n### Decisions\nPick A.\n"
    _write(history / "incomplete.md", content)

    issues = validate_history_file(history / "incomplete.md", tmp_path)

    assert len(issues) > 0
    # All missing sections should be listed
    missing_names = {"Changed files", "Behavior changed", "Tests run", "Follow-up"}
    for name in missing_names:
        found = any(name in i.message for i in issues)
        assert found, f"Expected '{name}' in issue messages"


def test_all_sections_required(tmp_path):
    """Every section in REQUIRED_SECTIONS must appear."""
    history = _history_dir(tmp_path)
    # Only Task and Decisions — missing 4 others
    content = "# Minimal\n\n### Task\nDo X.\n\n### Decisions\nPick A.\n"
    _write(history / "minimal.md", content)

    issues = validate_history_file(history / "minimal.md", tmp_path)
    assert len(issues) == 1  # one issue listing all missing sections
    issue = issues[0]
    for section in REQUIRED_SECTIONS:
        if section not in ("Task", "Decisions"):
            assert section in issue.message


# ── Placeholder markers ───────────────────────────────────────────────


def test_todo_placeholder_fails(tmp_path):
    content = "# Summary\n\n### Task\nTODO: fill in later.\n\n"
    content += "### Changed files\n- `x.py`.\n\n"
    content += "### Behavior changed\nNo change yet.\n\n"
    content += "### Tests run\nNone.\n\n"
    content += "### Decisions\nTBD.\n\n"
    content += "### Follow-up\nNone.\n"
    history = _history_dir(tmp_path)
    _write(history / "todo.md", content)

    issues = validate_history_file(history / "todo.md", tmp_path)
    assert len(issues) > 0
    assert any("placeholder" in i.message.lower() for i in issues)


def test_html_comment_placeholder_fails(tmp_path):
    content = (
        "# Summary\n"
        "<!-- TODO: write real summary -->\n\n"
        "### Task\nDo X.\n\n"
        "### Changed files\n- `a.py`.\n\n"
        "### Behavior changed\nChanged.\n\n"
        "### Tests run\nPassed.\n\n"
        "### Decisions\nDecided.\n\n"
        "### Follow-up\nNone.\n"
    )
    history = _history_dir(tmp_path)
    _write(history / "comment.md", content)

    issues = validate_history_file(history / "comment.md", tmp_path)
    assert not HistoryResult(root=tmp_path, issues=issues).passed


# ── Heading-only / no body ────────────────────────────────────────────


def test_heading_only_fails(tmp_path):
    """A file that has section headings but no body text fails."""
    content = (
        "# Empty\n\n"
        "### Task\n\n"
        "### Changed files\n\n"
        "### Behavior changed\n\n"
        "### Tests run\n\n"
        "### Decisions\n\n"
        "### Follow-up\n\n"
    )
    history = _history_dir(tmp_path)
    _write(history / "empty.md", content)

    issues = validate_history_file(history / "empty.md", tmp_path)
    assert not HistoryResult(root=tmp_path, issues=issues).passed


# ── validate_history_dir integration ───────────────────────────────────


def test_validate_history_dir_reports_all_issues(tmp_path):
    """validate_history_dir checks all non-README files and aggregates issues."""
    history = _history_dir(tmp_path)
    # Bad file
    _write(
        history / "bad.md",
        "# Bad\n\n### Task\nDo X.\n\n### Decisions\nPick A.\n",
    )
    # Good file
    _write(
        history / "good.md",
        (
            "# Good\n\n### Task\nDo Y.\n\n### Changed files\n- `y.py`.\n\n"
            "### Behavior changed\nBehaves differently.\n\n"
            "### Tests run\nAll pass.\n\n"
            "### Decisions\nChose B.\n\n"
            "### Follow-up\nNone.\n"
        ),
    )
    # README (should be ignored)
    _write(history / "README.md", "# Policy\n")

    result = validate_history_dir(tmp_path)

    assert result.files_checked == 2  # bad + good; README skipped
    assert not result.passed
    # Only the bad file should produce issues
    bad_issues = [i for i in result.issues if "bad.md" in i.file]
    assert len(bad_issues) >= 1
    good_issues = [i for i in result.issues if "good.md" in i.file]
    assert len(good_issues) == 0


def test_history_result_as_dict(tmp_path):
    """HistoryResult serialises cleanly to a dict."""
    issue = HistoryIssue(file="test.md", message="Missing sections.")
    result = HistoryResult(root=tmp_path, issues=[issue], files_checked=1)
    d = result.as_dict()

    assert d["passed"] is False
    assert d["files_checked"] == 1
    assert len(d["issues"]) == 1
    assert d["issues"][0]["file"] == "test.md"
    assert d["root"] == tmp_path.as_posix()


def test_history_result_passing_dict(tmp_path):
    """A clean result serialises with no issues."""
    result = HistoryResult(root=tmp_path)
    d = result.as_dict()

    assert d["passed"] is True
    assert d["issues"] == []