"""Tests for internal guard rule evaluation."""

from __future__ import annotations

from vibecode.config import ProtectedPathRule
from vibecode.git_state import GitState
from vibecode.guard import (
    ARCHITECTURE_TRUTH_RECORD_MESSAGE,
    GENERATED_RUNTIME_MESSAGE,
    README_MANUAL_ONLY_MESSAGE,
    check_architecture_truth_recorded,
    check_generated_runtime_changes,
    check_protected_path_changes,
    check_readme_changes,
    check_source_test_change_balance,
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
        changed_paths=("docs/app.md", ".vibecode/index/repo_tree.generated.md"),
        untracked_paths=(),
    )

    result = evaluate_guard(state, task="update app")

    assert result.passed is False
    assert tuple(finding.path for finding in result.findings) == (
        ".vibecode/index/repo_tree.generated.md",
    )


def test_source_only_change_warns_with_suggested_tests():
    test_map = {
        "rules": [
            {
                "path_pattern": "vibecode/guard.py",
                "required_checks": ["tests/test_vibecode_guard.py"],
            }
        ]
    }

    result = check_source_test_change_balance(
        ("vibecode/guard.py",),
        test_map=test_map,
    )

    finding = result.findings[0]
    assert result.passed is True
    assert finding.rule_id == "source-test-change-balance"
    assert finding.severity == "warning"
    assert "Source changed without corresponding test changes" in finding.message
    assert "tests/test_vibecode_guard.py" in finding.recommended_fix
    assert finding.required_tests == ("tests/test_vibecode_guard.py",)


def test_test_only_change_warns_unless_task_is_explicitly_test_only():
    result = check_source_test_change_balance(
        ("tests/test_vibecode_guard.py",),
        task="update guard behavior",
    )

    finding = result.findings[0]
    assert result.passed is True
    assert finding.severity == "warning"
    assert "Tests changed without source changes" in finding.message
    assert "test-only" in finding.message

    explicit = check_source_test_change_balance(
        ("tests/test_vibecode_guard.py",),
        task="test-only cleanup for guard coverage",
    )
    assert explicit.findings == ()


def test_paired_source_and_test_change_does_not_warn():
    test_map = {
        "rules": [
            {
                "path_pattern": "vibecode/guard.py",
                "required_checks": ["tests/test_vibecode_guard.py"],
            }
        ]
    }

    result = check_source_test_change_balance(
        ("vibecode/guard.py", "tests/test_vibecode_guard.py"),
        test_map=test_map,
    )

    assert result.passed is True
    assert result.findings == ()


def test_docs_only_change_does_not_require_tests():
    result = check_source_test_change_balance(("docs/QUICKSTART.md", "README.md"))

    assert result.passed is True
    assert result.findings == ()


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


def test_architecture_doc_change_requires_handoff_or_history_record():
    result = check_architecture_truth_recorded(
        (".vibecode/architecture/INVARIANTS.md",)
    )

    finding = result.findings[0]
    assert result.passed is False
    assert finding.rule_id == "architecture-truth-record"
    assert finding.path == ".vibecode/architecture/INVARIANTS.md"
    assert finding.severity == "error"
    assert ARCHITECTURE_TRUTH_RECORD_MESSAGE in finding.message
    assert "handoff" in finding.recommended_fix
    assert "history" in finding.recommended_fix


def test_architecture_doc_change_passes_with_handoff_now_record():
    result = check_architecture_truth_recorded(
        (
            ".vibecode/architecture/INVARIANTS.md",
            ".vibecode/handoff/NOW.md",
        )
    )

    assert result.passed is True
    assert result.findings == ()


def test_architecture_doc_change_passes_with_history_summary():
    result = check_architecture_truth_recorded(
        (
            ".vibecode/architecture/INVARIANTS.md",
            ".vibecode/history/architecture-summary.md",
        )
    )

    assert result.passed is True
    assert result.findings == ()


def test_architecture_doc_change_allows_future_explicit_override():
    result = check_architecture_truth_recorded(
        (".vibecode/architecture/INVARIANTS.md",),
        override=True,
    )

    assert result.passed is True
    assert result.findings == ()


def test_evaluate_guard_fails_architecture_change_without_record():
    state = GitState(
        is_git_repo=True,
        changed_paths=(".vibecode/architecture/INVARIANTS.md",),
        untracked_paths=(),
    )

    result = evaluate_guard(state, task="update architecture truth")

    assert result.passed is False
    assert "architecture-truth-record" in {
        finding.rule_id for finding in result.findings
    }


def test_evaluate_guard_keeps_architecture_record_message_when_unscoped():
    state = GitState(
        is_git_repo=True,
        changed_paths=(".vibecode/architecture/INVARIANTS.md",),
        untracked_paths=(),
    )

    result = evaluate_guard(state, task="update app logic")

    messages = "\n".join(finding.message for finding in result.findings)
    assert result.passed is False
    assert "Protected path changed without explicit task scope" in messages
    assert ARCHITECTURE_TRUTH_RECORD_MESSAGE in messages


def test_evaluate_guard_passes_architecture_change_with_record():
    state = GitState(
        is_git_repo=True,
        changed_paths=(
            ".vibecode/architecture/INVARIANTS.md",
            ".vibecode/handoff/NOW.md",
        ),
        untracked_paths=(),
    )

    result = evaluate_guard(state, task="update architecture handoff truth")

    assert result.passed is True
    assert "architecture-truth-record" not in {
        finding.rule_id for finding in result.findings
    }


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
