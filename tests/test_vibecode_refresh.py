"""Tests for VibecodeRefreshService.

Acceptance criteria:
- Refresh creates .vibecode when missing.
- Refresh creates missing manual truth files.
- Refresh preserves existing customized manual truth files byte-for-byte.
- Refresh removes disposable/current/generated files.
- Refresh does not delete .vibecode/logs/*.
- Refresh does not delete .vibecode/runs/*.
- Refresh regenerates expected index artifacts or records honest failure.
- Refresh returns a structured report.
- Refresh is idempotent.
- Tests do not require a real OpenCode install.
- Tests do not call any LLM.
"""

from __future__ import annotations

from pathlib import Path

from vibecode.refresh import RefreshReport, VibecodeRefreshService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_minimal_repo(tmp_path: Path) -> Path:
    """Create a minimal Python repo so the indexer has at least one file to scan."""
    (tmp_path / "main.py").write_text("def hello():\n    pass\n", encoding="utf-8")
    return tmp_path


def _minimal_project_yaml(project_id: str = "testproj") -> str:
    return (
        "# vibecode project configuration\n"
        "# schema: vibecode/project/v1\n\n"
        f"project:\n"
        f"  id: {project_id}\n"
        f"  name: Test\n"
        "  root: .\n\n"
        "indexing:\n"
        "  include:\n"
        '    - "*.py"\n'
        "  exclude: []\n\n"
        "protected_paths: []\n"
        "risk_rules: []\n"
    )


# ---------------------------------------------------------------------------
# Tests: creation of .vibecode
# ---------------------------------------------------------------------------


def test_refresh_creates_vibecode_when_missing(tmp_path):
    """Refresh must initialise .vibecode from scratch when it does not exist."""
    _make_minimal_repo(tmp_path)

    svc = VibecodeRefreshService(tmp_path)
    report = svc.refresh()

    assert (tmp_path / ".vibecode").is_dir()
    assert (tmp_path / ".vibecode" / "project.yaml").is_file()
    assert report.vibecode_existed is False
    assert ".vibecode/project.yaml" in report.created_missing_manual_files


def test_refresh_creates_standard_human_maintained_files(tmp_path):
    """Refresh must create the full set of human-maintained truth files."""
    _make_minimal_repo(tmp_path)

    report = VibecodeRefreshService(tmp_path).refresh()

    for rel in (
        ".vibecode/project.yaml",
        ".vibecode/architecture/INVARIANTS.md",
        ".vibecode/architecture/OVERVIEW.md",
        ".vibecode/architecture/STRUCTURE.md",
        ".vibecode/handoff/NOW.md",
        ".vibecode/handoff/NEXT.md",
        ".vibecode/handoff/BLOCKERS.md",
        ".vibecode/history/README.md",
        ".vibecode/index/README.md",
        ".vibecode/index/schema.json",
    ):
        assert (tmp_path / Path(rel)).is_file(), f"Expected {rel} to be created"
        assert rel in report.created_missing_manual_files


# ---------------------------------------------------------------------------
# Tests: missing manual files on a partial .vibecode
# ---------------------------------------------------------------------------


def test_refresh_creates_missing_manual_files_on_partial_vibecode(tmp_path):
    """When .vibecode exists but truth files are absent, refresh creates them."""
    _make_minimal_repo(tmp_path)
    (tmp_path / ".vibecode").mkdir()
    (tmp_path / ".vibecode" / "project.yaml").write_text(
        _minimal_project_yaml(), encoding="utf-8"
    )

    report = VibecodeRefreshService(tmp_path).refresh()

    assert (tmp_path / ".vibecode" / "architecture" / "INVARIANTS.md").is_file()
    assert (tmp_path / ".vibecode" / "handoff" / "NOW.md").is_file()
    assert ".vibecode/architecture/INVARIANTS.md" in report.created_missing_manual_files
    assert ".vibecode/handoff/NOW.md" in report.created_missing_manual_files


# ---------------------------------------------------------------------------
# Tests: preservation of existing human-maintained files
# ---------------------------------------------------------------------------


def test_refresh_preserves_customized_manual_files_byte_for_byte(tmp_path):
    """Refresh must never overwrite human-maintained files that have custom content."""
    _make_minimal_repo(tmp_path)
    svc = VibecodeRefreshService(tmp_path)
    svc.refresh()  # First run: creates defaults

    custom_invariants = "# My Custom Invariants\n\nNever overwrite me.\n"
    custom_now = "# Now\n\nWorking on the refresh service.\n"
    invariants_path = tmp_path / ".vibecode" / "architecture" / "INVARIANTS.md"
    now_path = tmp_path / ".vibecode" / "handoff" / "NOW.md"
    invariants_path.write_text(custom_invariants, encoding="utf-8")
    now_path.write_text(custom_now, encoding="utf-8")

    report2 = svc.refresh()

    assert invariants_path.read_text(encoding="utf-8") == custom_invariants
    assert now_path.read_text(encoding="utf-8") == custom_now
    assert ".vibecode/architecture/INVARIANTS.md" in report2.preserved_manual_files
    assert ".vibecode/handoff/NOW.md" in report2.preserved_manual_files


def test_refresh_preserves_all_human_maintained_files_on_second_run(tmp_path):
    """After first refresh, a second run must list all manual files as preserved."""
    _make_minimal_repo(tmp_path)
    svc = VibecodeRefreshService(tmp_path)
    svc.refresh()

    report2 = svc.refresh()

    for rel in (
        ".vibecode/project.yaml",
        ".vibecode/architecture/INVARIANTS.md",
        ".vibecode/handoff/NOW.md",
        ".vibecode/index/README.md",
        ".vibecode/index/schema.json",
    ):
        assert rel in report2.preserved_manual_files, f"{rel} should be preserved"
    assert report2.created_missing_manual_files == []


# ---------------------------------------------------------------------------
# Tests: disposable file cleanup
# ---------------------------------------------------------------------------


def test_refresh_removes_stale_current_files(tmp_path):
    """Refresh must delete stale files from .vibecode/current/."""
    _make_minimal_repo(tmp_path)
    svc = VibecodeRefreshService(tmp_path)
    svc.refresh()

    stale = tmp_path / ".vibecode" / "current" / "stale_context.md"
    stale.write_text("old content", encoding="utf-8")
    stale_rel = stale.relative_to(tmp_path).as_posix()

    report2 = svc.refresh()

    assert not stale.exists(), "Stale current file should have been removed"
    assert stale_rel in report2.disposable_removed


def test_refresh_removes_stale_generated_files(tmp_path):
    """Refresh must delete stale files from .vibecode/generated/."""
    _make_minimal_repo(tmp_path)
    svc = VibecodeRefreshService(tmp_path)
    svc.refresh()

    gen_dir = tmp_path / ".vibecode" / "generated"
    gen_dir.mkdir(exist_ok=True)
    stale = gen_dir / "old_export.md"
    stale.write_text("old export", encoding="utf-8")
    stale_rel = stale.relative_to(tmp_path).as_posix()

    report2 = svc.refresh()

    assert not stale.exists(), "Stale generated file should have been removed"
    assert stale_rel in report2.disposable_removed


def test_refresh_removes_disposable_index_files_before_regen(tmp_path):
    """Disposable index files planted before refresh must be cleaned then regenerated."""
    _make_minimal_repo(tmp_path)
    svc = VibecodeRefreshService(tmp_path)
    svc.refresh()  # First run creates and writes index

    # The inventory should now exist; record its content
    inventory = tmp_path / ".vibecode" / "index" / "file_inventory.json"
    assert inventory.exists()

    # Overwrite with stale data to verify refresh replaces it
    inventory.write_text('{"stale": true}', encoding="utf-8")

    svc.refresh()

    # After refresh, inventory is regenerated (valid JSON, not the stale stub)
    import json
    data = json.loads(inventory.read_text(encoding="utf-8"))
    assert "stale" not in data


# ---------------------------------------------------------------------------
# Tests: logs and runs are never deleted
# ---------------------------------------------------------------------------


def test_refresh_does_not_delete_logs(tmp_path):
    """Refresh must never touch .vibecode/logs/* files."""
    _make_minimal_repo(tmp_path)
    svc = VibecodeRefreshService(tmp_path)
    svc.refresh()

    log_dir = tmp_path / ".vibecode" / "logs" / "index_runs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "important.log"
    log_file.write_text("critical log entry\n", encoding="utf-8")

    svc.refresh()

    assert log_file.exists(), "Log file must not be deleted by refresh"


def test_refresh_does_not_delete_runs(tmp_path):
    """Refresh must never touch .vibecode/runs/* files."""
    _make_minimal_repo(tmp_path)
    svc = VibecodeRefreshService(tmp_path)
    svc.refresh()

    runs_dir = tmp_path / ".vibecode" / "runs"
    runs_dir.mkdir(exist_ok=True)
    run_file = runs_dir / "session_abc.json"
    run_file.write_text('{"session": "abc"}', encoding="utf-8")

    svc.refresh()

    assert run_file.exists(), "Run record must not be deleted by refresh"


# ---------------------------------------------------------------------------
# Tests: structured report
# ---------------------------------------------------------------------------


def test_refresh_returns_refresh_report_instance(tmp_path):
    """refresh() must return a RefreshReport dataclass instance."""
    _make_minimal_repo(tmp_path)
    report = VibecodeRefreshService(tmp_path).refresh()
    assert isinstance(report, RefreshReport)


def test_refresh_report_as_dict_has_required_keys(tmp_path):
    """RefreshReport.as_dict() must include all required fields."""
    _make_minimal_repo(tmp_path)
    d = VibecodeRefreshService(tmp_path).refresh().as_dict()

    required_keys = {
        "repo_path",
        "vibecode_existed",
        "preserved_manual_files",
        "created_missing_manual_files",
        "disposable_removed",
        "generated_artifacts",
        "validation_status",
        "validation_summary",
        "warnings",
        "errors",
        "next_recommended_action",
    }
    assert required_keys.issubset(d.keys())


def test_refresh_report_repo_path_is_posix(tmp_path):
    """repo_path in the report must be an absolute POSIX path."""
    _make_minimal_repo(tmp_path)
    report = VibecodeRefreshService(tmp_path).refresh()
    assert "/" in report.repo_path
    assert "\\" not in report.repo_path


def test_refresh_report_next_recommended_action_is_non_empty(tmp_path):
    """next_recommended_action must always be a non-empty string."""
    _make_minimal_repo(tmp_path)
    report = VibecodeRefreshService(tmp_path).refresh()
    assert isinstance(report.next_recommended_action, str)
    assert report.next_recommended_action.strip()


def test_refresh_report_list_fields_are_lists(tmp_path):
    """All list fields in the report must be actual list objects."""
    _make_minimal_repo(tmp_path)
    d = VibecodeRefreshService(tmp_path).refresh().as_dict()
    for key in (
        "preserved_manual_files",
        "created_missing_manual_files",
        "disposable_removed",
        "generated_artifacts",
        "warnings",
        "errors",
    ):
        assert isinstance(d[key], list), f"Expected list for '{key}'"


# ---------------------------------------------------------------------------
# Tests: index artifact regeneration
# ---------------------------------------------------------------------------


def test_refresh_regenerates_index_artifacts_or_records_failure(tmp_path):
    """After refresh, index artifacts should exist OR errors should explain why."""
    _make_minimal_repo(tmp_path)
    report = VibecodeRefreshService(tmp_path).refresh()

    inventory = tmp_path / ".vibecode" / "index" / "file_inventory.json"
    if inventory.exists():
        # Index ran: validation status must be something concrete
        assert report.validation_status in ("ok", "error")
    else:
        # Index did not run: errors must explain why
        assert report.errors, "Missing index artifacts must be explained by errors"


def test_refresh_validation_status_is_set(tmp_path):
    """validation_status must be one of the expected values after refresh."""
    _make_minimal_repo(tmp_path)
    report = VibecodeRefreshService(tmp_path).refresh()
    assert report.validation_status in ("ok", "error", "skipped")


# ---------------------------------------------------------------------------
# Tests: idempotency
# ---------------------------------------------------------------------------


def test_refresh_is_idempotent(tmp_path):
    """Running refresh twice should produce consistent results."""
    _make_minimal_repo(tmp_path)
    svc = VibecodeRefreshService(tmp_path)

    report1 = svc.refresh()
    report2 = svc.refresh()

    # After the first refresh .vibecode exists
    assert report2.vibecode_existed is True
    # On the second run all manual files should be preserved, none created
    assert report2.created_missing_manual_files == []
    # Validation status should be deterministic
    assert report2.validation_status == report1.validation_status


def test_refresh_vibecode_existed_false_on_first_call(tmp_path):
    """vibecode_existed must be False when .vibecode was absent before refresh."""
    _make_minimal_repo(tmp_path)
    report = VibecodeRefreshService(tmp_path).refresh()
    assert report.vibecode_existed is False


def test_refresh_vibecode_existed_true_on_second_call(tmp_path):
    """vibecode_existed must be True when .vibecode was present before refresh."""
    _make_minimal_repo(tmp_path)
    svc = VibecodeRefreshService(tmp_path)
    svc.refresh()
    report2 = svc.refresh()
    assert report2.vibecode_existed is True


# ---------------------------------------------------------------------------
# Tests: repo_path correctness
# ---------------------------------------------------------------------------


def test_refresh_report_repo_path_matches_root(tmp_path):
    """repo_path must match the resolved repo root."""
    _make_minimal_repo(tmp_path)
    report = VibecodeRefreshService(tmp_path).refresh()
    assert report.repo_path == tmp_path.resolve().as_posix()
