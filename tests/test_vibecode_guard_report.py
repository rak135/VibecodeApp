"""Tests for guard report generation: guard_report.json, guard_report.md,
GuardFindingEmitted events, and GuardCompleted event data."""

from __future__ import annotations

import json
from pathlib import Path

from vibecode.events import (
    EVENT_GUARD,
    EVENT_GUARD_FINDING,
    EventLevel,
    InMemoryEventSink,
    create_event,
)
from vibecode.guard import (
    GuardFinding,
    GuardResult,
    write_guard_report_md,
    write_guard_result,
)
from vibecode.session_log import RunSession


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _finding(
    rule_id: str = "test-rule",
    path: str = "foo.py",
    severity: str = "error",
    message: str = "Something bad",
    title: str = "Something bad happened",
    category: str = "",
    why_it_matters: str = "Because it matters",
    evidence: str = "foo.py:42",
    recommended_fix: str = "Fix it",
    required_tests: tuple[str, ...] = (),
) -> GuardFinding:
    return GuardFinding(
        rule_id=rule_id,
        path=path,
        severity=severity,
        message=message,
        title=title,
        category=category,
        why_it_matters=why_it_matters,
        evidence=evidence,
        recommended_fix=recommended_fix,
        required_tests=required_tests,
    )


# ---------------------------------------------------------------------------
# A — GuardFinding enriched fields
# ---------------------------------------------------------------------------


class TestGuardFindingFields:
    def test_new_fields_present_in_as_dict(self):
        f = _finding(
            title="Manual edit of generated file",
            category="generated-files",
            why_it_matters="Will be overwritten",
            evidence=".vibecode/current/context_pack.md",
            recommended_fix="Run vibecode index",
        )
        d = f.as_dict()
        assert d["title"] == "Manual edit of generated file"
        assert d["category"] == "generated-files"
        assert d["why_it_matters"] == "Will be overwritten"
        assert d["evidence"] == ".vibecode/current/context_pack.md"
        assert d["recommended_fix"] == "Run vibecode index"

    def test_category_derived_from_rule_id_when_not_set(self):
        f = GuardFinding(
            rule_id="generated-runtime-files",
            path="x",
            severity="error",
            message="m",
        )
        assert f.resolved_category == "generated-files"
        assert f.as_dict()["category"] == "generated-files"

    def test_category_derived_for_testing_rule(self):
        f = GuardFinding(
            rule_id="source-test-change-balance",
            path="x",
            severity="warning",
            message="m",
        )
        assert f.resolved_category == "testing"

    def test_category_derived_for_architecture_rule(self):
        f = GuardFinding(
            rule_id="architecture-truth-record",
            path="x",
            severity="error",
            message="m",
        )
        assert f.resolved_category == "architecture"

    def test_category_derived_for_documentation_rule(self):
        f = GuardFinding(
            rule_id="readme-manual-only",
            path="x",
            severity="error",
            message="m",
        )
        assert f.resolved_category == "documentation"

    def test_category_defaults_to_general_for_unknown_rule(self):
        f = GuardFinding(
            rule_id="unknown-custom-rule",
            path="x",
            severity="error",
            message="m",
        )
        assert f.resolved_category == "general"

    def test_explicit_category_overrides_rule_derived_category(self):
        f = GuardFinding(
            rule_id="generated-runtime-files",
            path="x",
            severity="error",
            message="m",
            category="custom-override",
        )
        assert f.resolved_category == "custom-override"

    def test_title_falls_back_to_message_in_as_dict(self):
        f = GuardFinding(
            rule_id="r",
            path="x",
            severity="error",
            message="The message",
        )
        d = f.as_dict()
        assert d["title"] == "The message"

    def test_optional_fields_absent_when_empty(self):
        f = GuardFinding(
            rule_id="r",
            path="x",
            severity="error",
            message="m",
        )
        d = f.as_dict()
        assert "why_it_matters" not in d
        assert "evidence" not in d
        assert "rule" not in d
        assert "recommended_fix" not in d
        assert "required_tests" not in d


# ---------------------------------------------------------------------------
# B — GuardResult.counts_by_severity / counts_by_category
# ---------------------------------------------------------------------------


class TestGuardResultCounts:
    def test_counts_by_severity_empty(self):
        r = GuardResult()
        assert r.counts_by_severity() == {}

    def test_counts_by_severity_mixed(self):
        r = GuardResult(
            findings=(
                _finding(severity="error"),
                _finding(severity="error"),
                _finding(severity="warning"),
            )
        )
        assert r.counts_by_severity() == {"error": 2, "warning": 1}

    def test_counts_by_category_empty(self):
        r = GuardResult()
        assert r.counts_by_category() == {}

    def test_counts_by_category_groups(self):
        r = GuardResult(
            findings=(
                _finding(category="testing"),
                _finding(category="testing"),
                _finding(rule_id="readme-manual-only", category=""),
            )
        )
        counts = r.counts_by_category()
        assert counts["testing"] == 2
        assert counts["documentation"] == 1

    def test_as_dict_includes_counts_by_severity_and_category(self):
        r = GuardResult(
            findings=(
                _finding(severity="error", category="testing"),
                _finding(severity="warning", category="architecture"),
            )
        )
        d = r.as_dict()
        assert d["counts_by_severity"] == {"error": 1, "warning": 1}
        assert d["counts_by_category"] == {"testing": 1, "architecture": 1}


# ---------------------------------------------------------------------------
# C — write_guard_report_md
# ---------------------------------------------------------------------------


class TestWriteGuardReportMd:
    def test_report_written_when_findings_exist(self, tmp_path: Path):
        result = GuardResult(
            findings=(
                _finding(
                    rule_id="generated-runtime-files",
                    severity="error",
                    title="Generated file edited",
                    category="generated-files",
                    why_it_matters="Will be overwritten on regeneration",
                    evidence=".vibecode/current/x.md",
                    recommended_fix="Regenerate with vibecode index",
                ),
                _finding(
                    rule_id="source-test-change-balance",
                    severity="warning",
                    title="No tests for source change",
                    category="testing",
                ),
            )
        )
        dest = tmp_path / "guard_report.md"
        write_guard_report_md(result, dest, session_id="sess-123")

        assert dest.exists()
        text = dest.read_text(encoding="utf-8")
        assert "# Guard Report" in text
        assert "sess-123" in text
        assert "FAILED" in text
        assert "Errors (1)" in text
        assert "Warnings (1)" in text
        assert "generated-file" in text.lower() or "generated-files" in text
        assert "Generated file edited" in text
        assert "Will be overwritten on regeneration" in text
        assert "Regenerate with vibecode index" in text
        assert ".vibecode/current/x.md" in text
        assert "No tests for source change" in text

    def test_report_written_when_no_findings(self, tmp_path: Path):
        result = GuardResult()
        dest = tmp_path / "guard_report.md"
        write_guard_report_md(result, dest, session_id="clean-session")

        assert dest.exists()
        text = dest.read_text(encoding="utf-8")
        assert "# Guard Report" in text
        assert "PASSED" in text
        assert "No findings" in text

    def test_report_not_written_when_path_parent_missing_is_created(self, tmp_path: Path):
        result = GuardResult()
        dest = tmp_path / "nested" / "deep" / "guard_report.md"
        write_guard_report_md(result, dest)
        assert dest.exists()

    def test_report_groups_by_severity_and_category(self, tmp_path: Path):
        result = GuardResult(
            findings=(
                _finding(severity="error", category="architecture", title="Arch error"),
                _finding(severity="error", category="testing", title="Test error"),
                _finding(severity="warning", category="testing", title="Test warning"),
            )
        )
        dest = tmp_path / "guard_report.md"
        write_guard_report_md(result, dest)
        text = dest.read_text(encoding="utf-8")

        # Both error categories present under Errors section
        assert "Errors (2)" in text
        assert "Warnings (1)" in text
        # Categories appear
        assert "architecture" in text
        # Findings within groups
        assert "Arch error" in text
        assert "Test error" in text
        assert "Test warning" in text

    def test_report_includes_session_id_and_root(self, tmp_path: Path):
        result = GuardResult()
        dest = tmp_path / "report.md"
        write_guard_report_md(result, dest, session_id="my-session", root=tmp_path)
        text = dest.read_text(encoding="utf-8")
        assert "my-session" in text
        assert tmp_path.as_posix() in text

    def test_report_related_tests_listed(self, tmp_path: Path):
        result = GuardResult(
            findings=(
                _finding(
                    severity="warning",
                    title="Missing test",
                    required_tests=("tests/test_foo.py", "tests/test_bar.py"),
                ),
            )
        )
        dest = tmp_path / "report.md"
        write_guard_report_md(result, dest)
        text = dest.read_text(encoding="utf-8")
        assert "tests/test_foo.py" in text
        assert "tests/test_bar.py" in text


# ---------------------------------------------------------------------------
# D — guard_report.json enrichment
# ---------------------------------------------------------------------------


class TestGuardReportJson:
    def test_json_report_includes_enriched_finding_fields(self, tmp_path: Path):
        vibecode_dir = tmp_path / ".vibecode"
        result = GuardResult(
            findings=(
                _finding(
                    rule_id="architecture-truth-record",
                    severity="error",
                    title="Arch truth not recorded",
                    category="architecture",
                    why_it_matters="Team unaware of structural decisions",
                    evidence=".vibecode/architecture/STRUCTURE.md",
                    recommended_fix="Update handoff/NOW.md",
                ),
            )
        )
        path = write_guard_result(result, vibecode_dir, tmp_path)
        data = json.loads(path.read_text(encoding="utf-8"))

        assert data["errors"] == 1
        assert data["warnings"] == 0
        assert "counts_by_severity" in data
        assert "counts_by_category" in data
        assert data["counts_by_severity"]["error"] == 1
        assert data["counts_by_category"]["architecture"] == 1

        finding = data["findings"][0]
        assert finding["rule_id"] == "architecture-truth-record"
        assert finding["severity"] == "error"
        assert finding["category"] == "architecture"
        assert finding["title"] == "Arch truth not recorded"
        assert finding["why_it_matters"] == "Team unaware of structural decisions"
        assert finding["evidence"] == ".vibecode/architecture/STRUCTURE.md"
        assert finding["recommended_fix"] == "Update handoff/NOW.md"

    def test_json_report_no_findings(self, tmp_path: Path):
        vibecode_dir = tmp_path / ".vibecode"
        result = GuardResult()
        path = write_guard_result(result, vibecode_dir, tmp_path)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["passed"] is True
        assert data["errors"] == 0
        assert data["warnings"] == 0
        assert data["counts_by_severity"] == {}
        assert data["counts_by_category"] == {}
        assert data["findings"] == []


# ---------------------------------------------------------------------------
# E — GuardFindingEmitted events and GuardCompleted event
# ---------------------------------------------------------------------------


class TestGuardEvents:
    """Test event emission using RunController's _emit flow directly."""

    def _make_sink_and_emit_guard(
        self,
        result: GuardResult,
    ) -> InMemoryEventSink:
        """Simulate the guard event emission logic from RunController."""
        sink = InMemoryEventSink()
        session_id = "test-session"

        def emit(type_, level, message, data=None):
            ev = create_event(session_id, type_, level, message, data=data)
            sink.emit(ev)

        for finding in result.findings:
            emit(
                EVENT_GUARD_FINDING,
                EventLevel.ERROR if finding.severity == "error" else EventLevel.WARNING,
                finding.title or finding.message,
                data={
                    "rule_id": finding.rule_id,
                    "severity": finding.severity,
                    "category": finding.resolved_category,
                    "path": finding.path,
                    "title": finding.title or finding.message,
                    "message": finding.message,
                    "why_it_matters": finding.why_it_matters,
                    "recommended_fix": finding.recommended_fix,
                    "evidence": finding.evidence,
                    "required_tests": list(finding.required_tests),
                },
            )

        emit(
            EVENT_GUARD,
            EventLevel.INFO if result.passed else EventLevel.WARNING,
            "Guard completed",
            data={
                "phase": "completed",
                "passed": result.passed,
                "findings": len(result.findings),
                "errors": sum(1 for f in result.findings if f.severity == "error"),
                "warnings": sum(1 for f in result.findings if f.severity == "warning"),
                "counts_by_severity": result.counts_by_severity(),
                "counts_by_category": result.counts_by_category(),
            },
        )
        return sink

    def test_no_findings_emits_only_guard_completed(self):
        result = GuardResult()
        sink = self._make_sink_and_emit_guard(result)

        finding_events = sink.events_by_type(EVENT_GUARD_FINDING)
        guard_events = sink.events_by_type(EVENT_GUARD)
        assert len(finding_events) == 0
        assert len(guard_events) == 1
        assert guard_events[0].data["passed"] is True
        assert guard_events[0].data["findings"] == 0

    def test_one_finding_emits_one_guard_finding_event(self):
        result = GuardResult(
            findings=(
                _finding(
                    rule_id="generated-runtime-files",
                    severity="error",
                    title="Generated file edited",
                    category="generated-files",
                    why_it_matters="Will be overwritten",
                    evidence=".vibecode/current/x.md",
                    recommended_fix="Regenerate",
                ),
            )
        )
        sink = self._make_sink_and_emit_guard(result)

        finding_events = sink.events_by_type(EVENT_GUARD_FINDING)
        assert len(finding_events) == 1
        ev = finding_events[0]
        assert ev.level == EventLevel.ERROR
        assert ev.data["rule_id"] == "generated-runtime-files"
        assert ev.data["severity"] == "error"
        assert ev.data["category"] == "generated-files"
        assert ev.data["title"] == "Generated file edited"
        assert ev.data["why_it_matters"] == "Will be overwritten"
        assert ev.data["recommended_fix"] == "Regenerate"
        assert ev.data["evidence"] == ".vibecode/current/x.md"

    def test_multiple_findings_emit_per_finding_events(self):
        result = GuardResult(
            findings=(
                _finding(severity="error", rule_id="r1"),
                _finding(severity="warning", rule_id="r2"),
                _finding(severity="error", rule_id="r3"),
            )
        )
        sink = self._make_sink_and_emit_guard(result)
        finding_events = sink.events_by_type(EVENT_GUARD_FINDING)
        assert len(finding_events) == 3
        rule_ids = [e.data["rule_id"] for e in finding_events]
        assert "r1" in rule_ids
        assert "r2" in rule_ids
        assert "r3" in rule_ids

    def test_guard_completed_event_has_counts_by_severity(self):
        result = GuardResult(
            findings=(
                _finding(severity="error"),
                _finding(severity="error"),
                _finding(severity="warning"),
            )
        )
        sink = self._make_sink_and_emit_guard(result)
        guard_ev = sink.events_by_type(EVENT_GUARD)[0]
        assert guard_ev.data["counts_by_severity"] == {"error": 2, "warning": 1}
        assert guard_ev.data["errors"] == 2
        assert guard_ev.data["warnings"] == 1

    def test_guard_completed_event_has_counts_by_category(self):
        result = GuardResult(
            findings=(
                _finding(severity="error", category="architecture"),
                _finding(severity="warning", category="testing"),
                _finding(severity="error", category="testing"),
            )
        )
        sink = self._make_sink_and_emit_guard(result)
        guard_ev = sink.events_by_type(EVENT_GUARD)[0]
        counts = guard_ev.data["counts_by_category"]
        assert counts["architecture"] == 1
        assert counts["testing"] == 2

    def test_guard_completed_passed_when_no_errors(self):
        result = GuardResult(
            findings=(_finding(severity="warning"),)
        )
        sink = self._make_sink_and_emit_guard(result)
        guard_ev = sink.events_by_type(EVENT_GUARD)[0]
        assert guard_ev.data["passed"] is True

    def test_guard_completed_failed_when_errors_present(self):
        result = GuardResult(
            findings=(_finding(severity="error"),)
        )
        sink = self._make_sink_and_emit_guard(result)
        guard_ev = sink.events_by_type(EVENT_GUARD)[0]
        assert guard_ev.data["passed"] is False

    def test_warning_finding_emits_warning_level_event(self):
        result = GuardResult(
            findings=(_finding(severity="warning", rule_id="source-test-change-balance"),)
        )
        sink = self._make_sink_and_emit_guard(result)
        ev = sink.events_by_type(EVENT_GUARD_FINDING)[0]
        assert ev.level == EventLevel.WARNING

    def test_error_finding_emits_error_level_event(self):
        result = GuardResult(
            findings=(_finding(severity="error", rule_id="readme-manual-only"),)
        )
        sink = self._make_sink_and_emit_guard(result)
        ev = sink.events_by_type(EVENT_GUARD_FINDING)[0]
        assert ev.level == EventLevel.ERROR


# ---------------------------------------------------------------------------
# F — SESSION integration: guard_report.json and guard_report.md via RunSession
# ---------------------------------------------------------------------------


class TestRunSessionGuardReports:
    def test_session_guard_report_json_path(self, tmp_path: Path):
        session = RunSession(root=tmp_path, session_id="sid-01")
        assert session.guard_report_json == (
            tmp_path / ".vibecode" / "runs" / "sid-01" / "guard_report.json"
        )

    def test_session_guard_report_md_path(self, tmp_path: Path):
        session = RunSession(root=tmp_path, session_id="sid-01")
        assert session.guard_report_md == (
            tmp_path / ".vibecode" / "runs" / "sid-01" / "guard_report.md"
        )

    def test_guard_report_json_written_to_run_dir(self, tmp_path: Path):
        session = RunSession(root=tmp_path, session_id="sid-02")
        result = GuardResult(
            findings=(
                _finding(severity="error", title="Test error"),
            )
        )
        session.ensure_dir()
        session.guard_report_json.write_text(
            json.dumps(result.as_dict(root=tmp_path), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        assert session.guard_report_json.exists()
        data = json.loads(session.guard_report_json.read_text(encoding="utf-8"))
        assert data["errors"] == 1
        assert data["counts_by_severity"]["error"] == 1

    def test_guard_report_md_written_to_run_dir(self, tmp_path: Path):
        session = RunSession(root=tmp_path, session_id="sid-03")
        result = GuardResult(
            findings=(
                _finding(severity="error", title="Arch breach"),
            )
        )
        session.ensure_dir()
        write_guard_report_md(
            result,
            session.guard_report_md,
            session_id="sid-03",
            root=tmp_path,
        )
        assert session.guard_report_md.exists()
        text = session.guard_report_md.read_text(encoding="utf-8")
        assert "Arch breach" in text
        assert "sid-03" in text

    def test_guard_report_md_written_for_clean_run(self, tmp_path: Path):
        session = RunSession(root=tmp_path, session_id="sid-04")
        result = GuardResult()
        session.ensure_dir()
        write_guard_report_md(result, session.guard_report_md, session_id="sid-04")
        assert session.guard_report_md.exists()
        text = session.guard_report_md.read_text(encoding="utf-8")
        assert "PASSED" in text


# ---------------------------------------------------------------------------
# G — Guard evaluation error synthetic result
# ---------------------------------------------------------------------------


class TestGuardEvaluationErrorResult:
    """When evaluate_project_guard raises, a synthetic error result is created
    so session guard reports are still written."""

    @staticmethod
    def _synthetic_result(error_message: str) -> GuardResult:
        return GuardResult(findings=(
            GuardFinding(
                rule_id="guard-evaluation-error",
                path=".",
                severity="error",
                message=f"Guard evaluation failed: {error_message}",
                category="guard",
                title="Guard evaluation error",
                why_it_matters=(
                    "The guard check could not complete. "
                    "Repository changes may not have been validated."
                ),
                evidence=error_message,
                recommended_fix=(
                    "Check the error message, fix the underlying issue, "
                    "and re-run guard."
                ),
            ),
        ))

    def test_json_report_written_for_evaluation_error(self, tmp_path: Path):
        error_msg = "division by zero"
        result = self._synthetic_result(error_msg)
        vibecode_dir = tmp_path / ".vibecode"

        path = write_guard_result(result, vibecode_dir, tmp_path)
        data = json.loads(path.read_text(encoding="utf-8"))

        assert data["passed"] is False
        assert data["errors"] == 1
        assert data["warnings"] == 0
        assert data["counts_by_severity"]["error"] == 1
        assert data["counts_by_category"]["guard"] == 1

        finding = data["findings"][0]
        assert finding["rule_id"] == "guard-evaluation-error"
        assert finding["severity"] == "error"
        assert finding["category"] == "guard"
        assert finding["title"] == "Guard evaluation error"
        assert "division by zero" in finding["message"]
        assert finding["evidence"] == "division by zero"

    def test_md_report_written_for_evaluation_error(self, tmp_path: Path):
        error_msg = "division by zero"
        result = self._synthetic_result(error_msg)
        dest = tmp_path / "guard_report.md"

        write_guard_report_md(result, dest, session_id="sess-err-1", root=tmp_path)

        assert dest.exists()
        text = dest.read_text(encoding="utf-8")
        assert "# Guard Report" in text
        assert "sess-err-1" in text
        assert "FAILED" in text
        assert "guard-evaluation-error" in text
        assert "Guard evaluation error" in text
        assert "division by zero" in text
        assert "guard" in text

    def test_synthetic_result_finding_fields(self):
        error_msg = "mock error"
        result = self._synthetic_result(error_msg)

        finding = result.findings[0]
        assert finding.rule_id == "guard-evaluation-error"
        assert finding.path == "."
        assert finding.severity == "error"
        assert finding.category == "guard"
        assert finding.resolved_category == "guard"
        assert finding.title == "Guard evaluation error"
        assert error_msg in finding.message
        assert finding.evidence == error_msg
        assert finding.recommended_fix
        assert "re-run guard" in finding.recommended_fix

    def test_synthetic_result_is_not_passed(self):
        result = self._synthetic_result("error")
        assert not result.passed

    def test_synthetic_result_counts(self):
        result = self._synthetic_result("error")
        assert result.counts_by_severity() == {"error": 1}
        assert result.counts_by_category() == {"guard": 1}
