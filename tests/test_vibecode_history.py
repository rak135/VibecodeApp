"""Tests for history summary creation and validation."""

from __future__ import annotations

from pathlib import Path

from vibecode.history import (
    HistoryIssue,
    HistoryResult,
    REQUIRED_SECTIONS,
    _sanitise_filename,
    create_summary,
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


def test_not_yet_filled_placeholder_fails(tmp_path):
    content = (
        "# Summary\n\n"
        "### Task\nDo X.\n\n"
        "### Changed files\n_Not yet filled._\n\n"
        "### Behavior changed\nChanged.\n\n"
        "### Tests run\nPassed.\n\n"
        "### Decisions\nDecided.\n\n"
        "### Follow-up\nNone.\n"
    )
    history = _history_dir(tmp_path)
    _write(history / "not-filled.md", content)

    issues = validate_history_file(history / "not-filled.md", tmp_path)

    assert not HistoryResult(root=tmp_path, issues=issues).passed
    assert any("placeholder" in i.message.lower() for i in issues)


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


def test_empty_bullet_section_fails(tmp_path):
    """A section with only an empty bullet is not durable content."""
    content = (
        "# Empty Bullet\n\n"
        "### Task\nDo X.\n\n"
        "### Changed files\n-\n\n"
        "### Behavior changed\nChanged.\n\n"
        "### Tests run\nPassed.\n\n"
        "### Decisions\nDecided.\n\n"
        "### Follow-up\nNone.\n"
    )
    history = _history_dir(tmp_path)
    _write(history / "empty-bullet.md", content)

    issues = validate_history_file(history / "empty-bullet.md", tmp_path)

    assert not HistoryResult(root=tmp_path, issues=issues).passed
    assert any("Changed files" in i.message for i in issues)


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


# ── create_summary utility ────────────────────────────────────────────────


def test_create_summary_generates_file(tmp_path):
    """create_summary produces a markdown file with all required sections."""
    repo = tmp_path / "repo"
    repo.mkdir()

    dest = create_summary(repo, task="Add user login")

    assert dest.exists()
    content = dest.read_text(encoding="utf-8")
    assert "# Add user login" in content
    assert "### Task" in content
    assert "### Changed files" in content
    assert "### Behavior changed" in content
    assert "### Tests run" in content
    assert "### Decisions" in content
    assert "### Follow-up" in content


def test_create_summary_includes_date(tmp_path):
    """The generated summary includes a Date line."""
    repo = tmp_path / "repo"
    repo.mkdir()

    dest = create_summary(repo, task="Test date")
    content = dest.read_text(encoding="utf-8")
    assert "Date: " in content


def test_create_summary_includes_author_when_given(tmp_path):
    """Author line is included only when provided."""
    repo = tmp_path / "repo"
    repo.mkdir()

    dest = create_summary(repo, task="Test", author="Alice <alice@example.com>")
    content = dest.read_text(encoding="utf-8")
    assert "Author: Alice <alice@example.com>" in content

    dest2 = create_summary(repo, task="Test no author")
    content2 = dest2.read_text(encoding="utf-8")
    assert "Author:" not in content2


def test_create_summary_fills_sections(tmp_path):
    """Provided section content appears in the generated file."""
    repo = tmp_path / "repo"
    repo.mkdir()

    dest = create_summary(
        repo,
        task="Refactor auth",
        changed_files="- `auth.py`: Extracted login logic.\n",
        behavior_changed="Login now returns 401 instead of 500.",
        tests_run="`tests/test_auth.py`: 15 passed.",
        decisions="Use bcrypt over SHA-256 for passwords.",
        follow_up="- Add rate limiting.\n",
    )
    content = dest.read_text(encoding="utf-8")
    assert "- `auth.py`: Extracted login logic." in content
    assert "Login now returns 401 instead of 500." in content
    assert "`tests/test_auth.py`: 15 passed." in content
    assert "Use bcrypt over SHA-256 for passwords." in content
    assert "- Add rate limiting." in content


def test_create_summary_uses_placeholder_for_empty_sections(tmp_path):
    """Empty section content gets a placeholder."""
    repo = tmp_path / "repo"
    repo.mkdir()

    dest = create_summary(repo, task="Empty sections")
    content = dest.read_text(encoding="utf-8")
    assert "_Not yet filled._" in content


def test_generated_empty_summary_fails_validation(tmp_path):
    """Generated empty summaries are drafts until filled with durable truth."""
    repo = tmp_path / "repo"
    repo.mkdir()

    dest = create_summary(repo, task="Empty sections")

    issues = validate_history_file(dest, repo)
    assert not HistoryResult(root=repo, issues=issues).passed
    assert any("placeholder" in i.message.lower() for i in issues)


def test_generated_filled_summary_passes_validation(tmp_path):
    """Generated summaries pass once every section contains real content."""
    repo = tmp_path / "repo"
    repo.mkdir()

    dest = create_summary(
        repo,
        task="Document history policy",
        changed_files="- `.vibecode/history/README.md`: Clarified durable memory policy.",
        behavior_changed="History validation now rejects placeholder summaries.",
        tests_run="`python -m pytest tests/test_vibecode_history.py`: passed.",
        decisions="Validate placeholders instead of treating generated drafts as truth.",
        follow_up="No follow-up required.",
    )

    assert validate_history_file(dest, repo) == []


def test_create_summary_does_not_overwrite(tmp_path):
    """Calling create_summary twice produces two distinct files."""
    repo = tmp_path / "repo"
    repo.mkdir()

    dest1 = create_summary(repo, task="First")
    dest2 = create_summary(repo, task="Second")

    assert dest1 != dest2
    assert dest1.exists()
    assert dest2.exists()


def test_create_summary_sanitises_filename(tmp_path):
    """The task string is sanitised to produce a safe filename."""
    repo = tmp_path / "repo"
    repo.mkdir()

    dest = create_summary(repo, task="Fix: broken <html> & CSS!")
    assert dest.name.startswith("20")  # timestamp prefix
    assert "fix" in dest.stem.lower() or "broken" in dest.stem.lower() or "css" in dest.stem.lower()
    assert "!" not in dest.name
    assert "<" not in dest.name
    assert ">" not in dest.name
    assert "&" not in dest.name


def test_sanitise_filename_lowercases_and_replaces_spaces():
    assert _sanitise_filename("My Task") == "my-task"


def test_sanitise_filename_removes_special_chars():
    assert _sanitise_filename("fix: broken <thing>") == "fix-broken-thing"


def test_sanitise_filename_caps_length():
    long_task = "x" * 200
    result = _sanitise_filename(long_task)
    assert len(result) <= 80


def test_sanitise_filename_collapses_multiple_dashes():
    assert _sanitise_filename("a  b   c") == "a-b-c"


# ── CLI: vibecode history new ─────────────────────────────────────────────


def test_history_new_cli_creates_file(tmp_path, capsys):
    """vibecode history new creates a summary file."""
    from vibecode.cli import main

    repo = tmp_path / "repo"
    (repo / ".vibecode").mkdir(parents=True)

    rc = main(["history", "new", "--repo", str(repo), "--task", "Add tests"])
    assert rc == 0

    history_dir = repo / ".vibecode" / "history"
    files = list(history_dir.glob("*.md"))
    assert len(files) == 1
    assert files[0].name.startswith("20")

    content = files[0].read_text(encoding="utf-8")
    assert "# Add tests" in content
    assert "### Task" in content
