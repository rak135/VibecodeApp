# Observable Run Monitor P6 Guard Report Fix

Generated: 2026-05-12

## Changes Applied

### 1. Removed unused imports (lint fixes)

- `vibecode/guard.py` — removed `is_documentation_path` and `strip_to_posix` from `vibecode.paths` import
- `tests/test_vibecode_guard_report.py` — removed unused `import pytest`

### 2. Synthetic guard result on evaluation error

Problem: When `evaluate_project_guard()` raises an exception, no per-session guard reports (`guard_report.json`, `guard_report.md`) were written. The `session` report block only ran under `if guard_result:`.

Fix: In `vibecode/run.py` (lines 820-832), when `guard_result is None and guard_error` is set, the error handler now:

1. Emits the existing `run.guard` error event
2. Synthesizes a `GuardResult` containing a single `GuardFinding` with:
   - `rule_id`: `"guard-evaluation-error"`
   - `severity`: `"error"`
   - `category`: `"guard"`
   - Exception message as `evidence`
3. Calls `write_guard_result()` to write `.vibecode/current/guard_result.json`
4. Falls through to the existing per-finding event emission and session report writers

The `if/elif/else` was restructured to `if/else` so the synthesized result flows into the same per-finding event loop and `run.guard` completed event that normal results use.

### 3. Tests added

5 new tests in `tests/test_vibecode_guard_report.py` (`TestGuardEvaluationErrorResult`):
- `test_json_report_written_for_evaluation_error` — JSON report contains correct error finding
- `test_md_report_written_for_evaluation_error` — MD report contains error details
- `test_synthetic_result_finding_fields` — all finding fields populated
- `test_synthetic_result_is_not_passed` — `result.passed` is False
- `test_synthetic_result_counts` — severity/category counts are correct

## Verification

- Ruff lint: passed (0 issues) on `vibecode/guard.py`, `vibecode/run.py`, `tests/test_vibecode_guard_report.py`
- Guard report tests: 41 passed (36 existing + 5 new)
- Full test suite: 1227 passed, 1 pre-existing failure unrelated to this change
- `vibecode guard .`: passed (1 advisory warning on source/test balance — expected for source-only changes)
- CLI help checks: passed
