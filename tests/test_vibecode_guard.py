"""Tests for internal guard rule evaluation."""

from __future__ import annotations

from vibecode.config import ProtectedPathRule
from vibecode.git_state import GitState
from vibecode.guard import (
    GENERATED_RUNTIME_MESSAGE,
    README_MANUAL_ONLY_MESSAGE,
    check_generated_runtime_changes,
    check_protected_path_changes,
    check_readme_changes,
    evaluate_guard,
)


def test_generated_runtime_change_fails_for_current_file():
    result = check_generated_runtime_changes((".vibecode/current/context_pack.md",))

    assert result.passed is False
    assert len(result.findings) == 1
    assert result.findings[0].severity == "error"
    assert result.findings[0].path == ".vibecode/current/context_pack.md"
    assert GENERATED_RUNTIME_MESSAGE in result.findings[0].message


def test_generated_runtime_change_fails_for_generated_directory():
    result = check_generated_runtime_changes((".vibecode/generated/AGENTS.md",))

    assert result.passed is False
    assert GENERATED_RUNTIME_MESSAGE in result.findings[0].message


def test_generated_runtime_change_fails_for_generated_index_file():
    result = check_generated_runtime_changes((".vibecode/index/repo_tree.generated.md",))

    assert result.passed is False
    assert result.findings[0].path == ".vibecode/index/repo_tree.generated.md"


def test_generated_runtime_change_fails_for_runtime_directories():
    paths = (
        ".vibecode/logs/run.log",
        ".vibecode/runs/20260101.json",
        ".vibecode/tmp/scratch.txt",
        ".vibecode/cache/context.json",
    )

    result = check_generated_runtime_changes(paths)

    assert result.passed is False
    assert tuple(finding.path for finding in result.findings) == paths


def test_human_maintained_architecture_doc_is_allowed():
    result = check_generated_runtime_changes((".vibecode/architecture/INVARIANTS.md",))

    assert result.passed is True
    assert result.findings == ()


def test_non_generated_index_file_is_allowed():
    result = check_generated_runtime_changes((".vibecode/index/schema.json",))

    assert result.passed is True


def test_generator_behavior_task_allows_untracked_generated_file():
    result = check_generated_runtime_changes(
        (".vibecode/current/context_pack.md",),
        task="testing generator behavior for context-pack output",
        untracked_paths=(".vibecode/current/context_pack.md",),
    )

    assert result.passed is True


def test_generator_behavior_task_still_fails_for_tracked_generated_file():
    result = check_generated_runtime_changes(
        (".vibecode/current/context_pack.md",),
        task="testing generator behavior for context-pack output",
        untracked_paths=(),
    )

    assert result.passed is False


def test_evaluate_guard_consumes_git_state_changed_paths():
    state = GitState(
        is_git_repo=True,
        changed_paths=("src/app.py", ".vibecode/index/repo_tree.generated.md"),
        untracked_paths=(),
    )

    result = evaluate_guard(state, task="update app")

    assert result.passed is False
    assert tuple(finding.path for finding in result.findings) == (
        ".vibecode/index/repo_tree.generated.md",
    )


def test_readme_change_is_allowed_during_docs_task():
    result = check_readme_changes(("README.md",), task="update docs")

    assert result.passed is True
    assert result.findings == ()


def test_readme_change_fails_for_non_docs_task():
    result = check_readme_changes(("README.md",), task="update app logic")

    finding = result.findings[0]

    assert result.passed is False
    assert finding.rule_id == "readme-manual-only"
    assert finding.path == "README.md"
    assert finding.severity == "error"
    assert README_MANUAL_ONLY_MESSAGE in finding.message
    assert "README/docs task" in finding.message


def test_docs_quickstart_change_does_not_trigger_readme_guard():
    result = check_readme_changes(("docs/QUICKSTART.md",), task="update app logic")

    assert result.passed is True
    assert result.findings == ()


def test_evaluate_guard_applies_readme_policy():
    state = GitState(
        is_git_repo=True,
        changed_paths=("README.md",),
        untracked_paths=(),
    )

    result = evaluate_guard(state, task="update app logic")

    assert result.passed is False
    assert tuple(finding.rule_id for finding in result.findings) == (
        "readme-manual-only",
    )


def test_protected_architecture_change_requires_explicit_task_scope():
    rule = ProtectedPathRule(
        path=".vibecode/architecture/",
        rule="Architecture truth requires explicit task scope.",
    )

    result = check_protected_path_changes(
        (".vibecode/architecture/INVARIANTS.md",),
        (rule,),
        task="update docs",
    )

    finding = result.findings[0]
    assert result.passed is False
    assert finding.path == ".vibecode/architecture/INVARIANTS.md"
    assert finding.rule == "Architecture truth requires explicit task scope."
    assert finding.severity == "error"
    assert "Add explicit task scope" in finding.recommended_fix


def test_protected_core_change_reports_required_tests_when_scoped():
    rule = ProtectedPathRule(
        path="vibecode/context/scoring.py",
        rule="Context scoring changes require ranking tests.",
        required_tests=("python -m pytest tests/test_vibecode_relevant_files.py",),
    )

    result = check_protected_path_changes(
        ("vibecode/context/scoring.py",),
        (rule,),
        task="update context scoring behavior",
    )

    finding = result.findings[0]
    assert result.passed is True
    assert finding.path == "vibecode/context/scoring.py"
    assert finding.rule == "Context scoring changes require ranking tests."
    assert finding.severity == "warning"
    assert finding.required_tests == (
        "python -m pytest tests/test_vibecode_relevant_files.py",
    )
    assert "Run required tests" in finding.recommended_fix


def test_protected_generated_policy_change_is_hard_failure():
    rule = ProtectedPathRule(
        path=".vibecode/index/*.generated.*",
        rule="Regenerate through index commands instead of manual edits.",
    )

    result = check_protected_path_changes(
        (".vibecode/index/repo_tree.generated.md",),
        (rule,),
        task="update generated index",
    )

    finding = result.findings[0]
    assert result.passed is False
    assert finding.severity == "error"
    assert finding.rule == "Regenerate through index commands instead of manual edits."
    assert "Regenerate this artifact" in finding.recommended_fix


def test_handoff_change_requires_explanation_when_scoped():
    rule = ProtectedPathRule(
        path=".vibecode/handoff/",
        rule="Handoff state requires careful updates.",
    )

    result = check_protected_path_changes(
        (".vibecode/handoff/NOW.md",),
        (rule,),
        task="update handoff state",
    )

    finding = result.findings[0]
    assert result.passed is True
    assert finding.severity == "warning"
    assert finding.path == ".vibecode/handoff/NOW.md"
    assert "Explain the protected truth-doc change" in finding.recommended_fix
