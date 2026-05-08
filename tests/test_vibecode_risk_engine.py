"""Tests for the risk engine."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from vibecode.indexer.classifier import FileRecord, classify
from vibecode.indexer.risk_engine import (
    RiskResult,
    _find_keyword,
    _is_sensitive_dir,
    _matches_glob,
    build_risk_index,
    evaluate_risk,
)
from vibecode.indexer.risky_files import render_risky_files, write_risky_files


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rec(path: str, base_risk: str = "low") -> FileRecord:
    """Return a minimal FileRecord with the given path and risk level."""
    rec = classify(path, 100)
    # Override risk_level for tests that need a specific base level
    from dataclasses import replace
    return replace(rec, risk_level=base_risk)


def _evaluate(path: str, base: str = "low", protected=None, rules=None) -> RiskResult:
    return evaluate_risk(path, base, protected or [], rules or [])


# ---------------------------------------------------------------------------
# _matches_glob
# ---------------------------------------------------------------------------


class TestMatchesGlob:
    def test_exact_match(self):
        assert _matches_glob("foo/bar.py", "foo/bar.py")

    def test_wildcard(self):
        assert _matches_glob("foo/bar.py", "foo/*.py")

    def test_double_star_prefix(self):
        assert _matches_glob(".vibecode/architecture/INVARIANTS.md", ".vibecode/architecture/**")

    def test_double_star_deep(self):
        assert _matches_glob(".vibecode/handoff/sub/file.md", ".vibecode/handoff/**")

    def test_double_star_dir_itself(self):
        # The dir itself matches dir/**
        assert _matches_glob(".vibecode/history", ".vibecode/history/**")

    def test_no_match(self):
        assert not _matches_glob("other/file.py", ".vibecode/architecture/**")

    def test_fnmatch_star(self):
        assert _matches_glob("src/auth.py", "src/*.py")


# ---------------------------------------------------------------------------
# _find_keyword
# ---------------------------------------------------------------------------


class TestFindKeyword:
    def test_matching_stem(self):
        assert _find_keyword("engine/matching.py") == "matching"

    def test_policy_stem(self):
        assert _find_keyword("rules/policy.py") == "policy"

    def test_auth_stem(self):
        assert _find_keyword("services/auth.py") == "auth"

    def test_payments_stem(self):
        assert _find_keyword("billing/payments.py") == "payments"

    def test_compound_name(self):
        # "payment_matching.py" → "matching" or "payments" (both valid)
        kw = _find_keyword("payment_matching.py")
        assert kw in ("matching", "payments")

    def test_no_match(self):
        assert _find_keyword("utils/helpers.py") is None

    def test_case_insensitive_stem(self):
        # stem is lowercased before matching
        assert _find_keyword("AUTH_SERVICE.py") == "auth"

    def test_migration_stem(self):
        assert _find_keyword("db/migration.py") == "migration"

    def test_security_stem(self):
        assert _find_keyword("core/security.py") == "security"

    def test_permissions_stem(self):
        assert _find_keyword("api/permissions.py") == "permissions"

    def test_fx_stem(self):
        assert _find_keyword("finance/fx.py") == "fx"

    def test_tax_stem(self):
        assert _find_keyword("reports/tax.py") == "tax"

    def test_state_stem(self):
        assert _find_keyword("workflow/state.py") == "state"


# ---------------------------------------------------------------------------
# _is_sensitive_dir
# ---------------------------------------------------------------------------


class TestIsSensitiveDir:
    def test_docs_dir(self):
        assert _is_sensitive_dir("docs/guide.md")

    def test_audit_dir(self):
        assert _is_sensitive_dir("audit/report.md")

    def test_architecture_dir(self):
        assert _is_sensitive_dir("architecture/overview.md")

    def test_nested_docs(self):
        assert _is_sensitive_dir("project/docs/api.md")

    def test_root_file(self):
        assert not _is_sensitive_dir("README.md")

    def test_src_file(self):
        assert not _is_sensitive_dir("src/main.py")


# ---------------------------------------------------------------------------
# evaluate_risk – explicit protected paths
# ---------------------------------------------------------------------------


class TestEvaluateRiskProtectedPaths:
    def test_protected_path_always_high(self):
        result = _evaluate(
            ".vibecode/architecture/INVARIANTS.md",
            base="low",
            protected=[".vibecode/architecture/**"],
        )
        assert result.risk_level == "high"

    def test_protected_reason_included(self):
        result = _evaluate(
            ".vibecode/handoff/NOW.md",
            base="low",
            protected=[".vibecode/handoff/**"],
        )
        assert any("explicitly protected" in r for r in result.reasons)

    def test_protected_overrides_medium_base(self):
        result = _evaluate(
            ".vibecode/history/README.md",
            base="medium",
            protected=[".vibecode/history/**"],
        )
        assert result.risk_level == "high"

    def test_non_protected_path_unchanged(self):
        result = _evaluate(
            "tests/test_utils.py",
            base="low",
            protected=[".vibecode/architecture/**"],
        )
        assert result.risk_level == "low"

    def test_multiple_protected_patterns_first_match_wins(self):
        result = _evaluate(
            ".vibecode/history/log.md",
            base="low",
            protected=[".vibecode/architecture/**", ".vibecode/history/**"],
        )
        assert result.risk_level == "high"


# ---------------------------------------------------------------------------
# evaluate_risk – filename heuristics
# ---------------------------------------------------------------------------


class TestEvaluateRiskHeuristics:
    def test_matching_py_is_high(self):
        result = _evaluate("engine/matching.py", base="low")
        assert result.risk_level == "high"

    def test_policy_py_is_high(self):
        result = _evaluate("rules/policy.py", base="low")
        assert result.risk_level == "high"

    def test_auth_py_is_high(self):
        result = _evaluate("services/auth.py", base="low")
        assert result.risk_level == "high"

    def test_payments_py_is_high(self):
        result = _evaluate("billing/payments.py", base="low")
        assert result.risk_level == "high"

    def test_heuristic_does_not_lower_existing_high(self):
        result = _evaluate("engine/auth.py", base="high")
        assert result.risk_level == "high"

    def test_keyword_reason_included(self):
        result = _evaluate("security.py", base="low")
        assert any("sensitive keyword" in r for r in result.reasons)

    def test_no_keyword_plain_file(self):
        result = _evaluate("utils/helpers.py", base="low")
        assert result.risk_level == "low"
        assert any("base role" in r for r in result.reasons)


# ---------------------------------------------------------------------------
# evaluate_risk – sensitive directory floor
# ---------------------------------------------------------------------------


class TestEvaluateRiskSensitiveDir:
    def test_docs_file_at_least_medium(self):
        result = _evaluate("docs/guide.md", base="low")
        assert result.risk_level == "medium"

    def test_audit_file_at_least_medium(self):
        result = _evaluate("audit/report.md", base="low")
        assert result.risk_level == "medium"

    def test_architecture_dir_file_at_least_medium(self):
        result = _evaluate("architecture/overview.md", base="low")
        assert result.risk_level == "medium"

    def test_docs_existing_high_stays_high(self):
        result = _evaluate("docs/security.md", base="high")
        assert result.risk_level == "high"

    def test_docs_existing_medium_stays_medium(self):
        result = _evaluate("docs/guide.md", base="medium")
        assert result.risk_level == "medium"

    def test_docs_sensitive_keyword_is_high(self):
        # auth.md in docs/ → medium from dir + high from keyword → high
        result = _evaluate("docs/auth.md", base="low")
        assert result.risk_level == "high"


# ---------------------------------------------------------------------------
# evaluate_risk – risk_rules
# ---------------------------------------------------------------------------


class TestEvaluateRiskRules:
    def test_rule_pattern_match_raises_severity(self):
        rules = [{"pattern": "**/*.env", "severity": "high", "reason": "env files"}]
        result = _evaluate("config/secrets.env", base="low", rules=rules)
        assert result.risk_level == "high"

    def test_rule_reason_included(self):
        rules = [{"pattern": "src/auth.py", "severity": "high", "reason": "custom auth rule"}]
        result = _evaluate("src/auth.py", base="low", rules=rules)
        assert any("custom auth rule" in r for r in result.reasons)

    def test_rule_medium_severity(self):
        rules = [{"pattern": "scripts/*.sh", "severity": "medium"}]
        result = _evaluate("scripts/deploy.sh", base="low", rules=rules)
        assert result.risk_level == "medium"

    def test_rule_does_not_lower_higher_risk(self):
        rules = [{"pattern": "src/*.py", "severity": "medium"}]
        result = _evaluate("src/auth.py", base="high", rules=rules)
        assert result.risk_level == "high"

    def test_invalid_severity_defaults_to_high(self):
        rules = [{"pattern": "src/*.py", "severity": "critical"}]
        result = _evaluate("src/payments.py", base="low", rules=rules)
        assert result.risk_level == "high"

    def test_no_matching_rule_no_change(self):
        rules = [{"pattern": "secrets/**", "severity": "high"}]
        result = _evaluate("utils/helpers.py", base="low", rules=rules)
        assert result.risk_level == "low"


# ---------------------------------------------------------------------------
# build_risk_index – empty protected_paths warning
# ---------------------------------------------------------------------------


class TestBuildRiskIndexWarning:
    def test_empty_protected_paths_emits_warning(self):
        records = [classify("vibecode/cli.py", 100)]
        with pytest.warns(UserWarning, match="protected_paths is empty"):
            build_risk_index(records, protected_paths=[], risk_rules=[])

    def test_empty_protected_paths_logs_to_run_log(self):
        records = [classify("main.py", 50)]
        run_log: list[str] = []
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            build_risk_index(records, protected_paths=[], risk_rules=[], run_log=run_log)
        assert any("protected_paths" in entry for entry in run_log)

    def test_non_empty_protected_paths_no_warning(self):
        records = [classify("main.py", 50)]
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            # Should not raise
            build_risk_index(records, protected_paths=[".vibecode/**"], risk_rules=[])

    def test_returns_risk_index_for_all_files(self):
        records = [classify("main.py", 50), classify("tests/test_main.py", 80)]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            index = build_risk_index(records, protected_paths=[], risk_rules=[])
        assert "main.py" in index
        assert "tests/test_main.py" in index

    def test_explicit_protected_path_is_high(self):
        records = [classify(".vibecode/architecture/INVARIANTS.md", 200)]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            index = build_risk_index(
                records,
                protected_paths=[".vibecode/architecture/**"],
                risk_rules=[],
            )
        assert index[".vibecode/architecture/INVARIANTS.md"].risk_level == "high"

    def test_heuristic_file_in_index_is_high(self):
        records = [classify("engine/matching.py", 300)]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            index = build_risk_index(records, protected_paths=[], risk_rules=[])
        assert index["engine/matching.py"].risk_level == "high"


# ---------------------------------------------------------------------------
# render_risky_files
# ---------------------------------------------------------------------------


class TestRenderRiskyFiles:
    def test_no_elevated_risk(self):
        idx: dict = {
            "utils.py": RiskResult("utils.py", "low", ["base role classification (low)"]),
        }
        md = render_risky_files(idx)
        assert "No files with elevated risk" in md

    def test_high_risk_section_present(self):
        idx = {
            "auth.py": RiskResult("auth.py", "high", ["filename contains sensitive keyword 'auth'"]),
        }
        md = render_risky_files(idx)
        assert "## High Risk" in md
        assert "`auth.py`" in md
        assert "sensitive keyword" in md

    def test_medium_risk_section_present(self):
        idx = {
            "docs/guide.md": RiskResult(
                "docs/guide.md", "medium", ["file is in a docs/audit/architecture directory"]
            ),
        }
        md = render_risky_files(idx)
        assert "## Medium Risk" in md
        assert "`docs/guide.md`" in md

    def test_reason_indented_under_file(self):
        idx = {
            "payments.py": RiskResult(
                "payments.py", "high", ["filename contains sensitive keyword 'payments'"]
            ),
        }
        md = render_risky_files(idx)
        lines = md.splitlines()
        file_line = next(i for i, l in enumerate(lines) if "`payments.py`" in l)
        assert lines[file_line + 1].startswith("  -")

    def test_files_sorted_alphabetically(self):
        idx = {
            "z_payments.py": RiskResult("z_payments.py", "high", ["r"]),
            "a_auth.py": RiskResult("a_auth.py", "high", ["r"]),
        }
        md = render_risky_files(idx)
        pos_a = md.index("a_auth.py")
        pos_z = md.index("z_payments.py")
        assert pos_a < pos_z


# ---------------------------------------------------------------------------
# write_risky_files
# ---------------------------------------------------------------------------


class TestWriteRiskyFiles:
    def test_creates_file(self, tmp_path):
        idx = {
            "auth.py": RiskResult("auth.py", "high", ["sensitive"]),
        }
        out = tmp_path / ".vibecode" / "index" / "risky_files.md"
        write_risky_files(idx, out)
        assert out.exists()

    def test_creates_parent_dirs(self, tmp_path):
        out = tmp_path / "deep" / "nested" / "risky_files.md"
        write_risky_files({}, out)
        assert out.exists()

    def test_content_written(self, tmp_path):
        idx = {
            "auth.py": RiskResult("auth.py", "high", ["reason"]),
        }
        out = tmp_path / "risky_files.md"
        write_risky_files(idx, out)
        content = out.read_text(encoding="utf-8")
        assert "auth.py" in content

    def test_repeated_write_overwrites(self, tmp_path):
        out = tmp_path / "risky_files.md"
        write_risky_files({"a.py": RiskResult("a.py", "high", ["r"])}, out)
        write_risky_files({}, out)
        assert "No files with elevated risk" in out.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Integration: build_risk_index + inventory risk_level update
# ---------------------------------------------------------------------------


class TestInventoryRiskLevelUpdate:
    def test_inventory_uses_engine_risk_level(self, tmp_path):
        """risk_level in file_inventory.json must reflect the risk engine result."""
        from vibecode.indexer.inventory import build_inventory
        from vibecode.indexer.scanner import FileStatus, IndexedFile

        files = [IndexedFile(path="engine/matching.py", status=FileStatus.UNKNOWN, size=200)]
        records = [classify(f.path, f.size) for f in files]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            risk_index = build_risk_index(records, protected_paths=[], risk_rules=[])
        inv = build_inventory("proj", tmp_path, files, risk_index=risk_index)
        rec = inv["files"][0]
        assert rec["risk_level"] == "high"

    def test_protected_path_updates_inventory_risk(self, tmp_path):
        from vibecode.indexer.inventory import build_inventory
        from vibecode.indexer.scanner import FileStatus, IndexedFile

        files = [
            IndexedFile(
                path=".vibecode/architecture/INVARIANTS.md",
                status=FileStatus.UNKNOWN,
                size=100,
            )
        ]
        records = [classify(f.path, f.size) for f in files]
        risk_index = build_risk_index(
            records,
            protected_paths=[".vibecode/architecture/**"],
            risk_rules=[],
        )
        inv = build_inventory("proj", tmp_path, files, risk_index=risk_index)
        assert inv["files"][0]["risk_level"] == "high"

    def test_no_risk_index_uses_classifier_baseline(self, tmp_path):
        from vibecode.indexer.inventory import build_inventory
        from vibecode.indexer.scanner import FileStatus, IndexedFile

        files = [IndexedFile(path="README.md", status=FileStatus.UNKNOWN, size=50)]
        inv = build_inventory("proj", tmp_path, files)
        assert inv["files"][0]["risk_level"] == "low"
