# Observable Run Monitor P6 Guard Report Review

Generated: 2026-05-11

## Verdict

FIX REQUIRED. The guard report improvements make individual guard findings much easier for a human to read and keep severity/rule identity intact across JSON, Markdown, and monitor events. However, per-session guard reports are not written when guard evaluation itself raises, so the monitor path can still lose the guard report artifact in a partial-failure case. The reviewed files are also not lint-clean.

This review did not modify implementation or test files. The task scope allowed only this review document.

## Findings

### FIX: partial guard failures do not produce per-session guard reports

`RunController.execute()` captures guard evaluation exceptions into `guard_error` and emits a `run.guard` error event (`vibecode/run.py:801-824`), but the session report writers only run under `if guard_result:` (`vibecode/run.py:938-950`). If `evaluate_project_guard()` or report serialization fails before a `GuardResult` exists, `.vibecode/runs/<session>/guard_report.json` and `guard_report.md` are not created.

That does not satisfy the review requirement that report generation works even when guard partially fails. The monitor would have an event, but not the expected guard report artifacts. A robust fix would synthesize a guard error result, for example with a stable rule id such as `guard-evaluation-error`, severity `error`, category `guard`, and the exception message as bounded evidence, then write both JSON and Markdown reports from that result.

I did not find a test covering this path. Searches for partial/failed guard report behavior only found normal report generation tests and no simulated `evaluate_project_guard()` exception coverage.

### FIX: reviewed files are not lint-clean

Focused Ruff reports three unused imports:

- `tests/test_vibecode_guard_report.py:9` imports `pytest` but does not use it.
- `vibecode/guard.py:16` imports `is_documentation_path` but does not use it.
- `vibecode/guard.py:21` imports `strip_to_posix` but does not use it.

These are mechanical cleanup items, but they block a clean lint result for the reviewed change set.

### PASS: findings are understandable to a human

`GuardFinding` now carries `category`, `title`, `why_it_matters`, `evidence`, `recommended_fix`, and `required_tests` in addition to the original rule fields (`vibecode/guard.py:62-115`). The concrete findings for generated/runtime files, README changes, architecture truth, protected paths, and source/test balance all populate titles, impact text, and remediation guidance (`vibecode/guard.py:371-689`).

The Markdown writer groups findings by severity and category, then renders rule id, path, severity, category, what happened, why it matters, suggested fix, evidence, rule text, and related tests (`vibecode/guard.py:254-333`). That is a clear operator-facing shape.

### PASS: JSON and Markdown are generated from the same finding model

JSON serialization is driven by `GuardResult.as_dict()` and `GuardFinding.as_dict()` (`vibecode/guard.py:97-155`). Markdown rendering reads the same `GuardResult.findings` objects and includes the same core identity fields: `rule_id`, `severity`, `category`, path, title/message, evidence, fix, and required tests (`vibecode/guard.py:318-331`).

The tests cover JSON enrichment and no-findings output (`tests/test_vibecode_guard_report.py:321-365`) and Markdown findings/no-findings output (`tests/test_vibecode_guard_report.py:214-260`). One test gap remains: there is no direct parity test that creates one `GuardResult`, writes both formats, and asserts the same finding count, rule ids, severities, and categories appear in both.

### PASS: severity and rule identity are preserved

The enriched finding serializer always includes `rule_id`, `path`, `severity`, `category`, `title`, and `message` (`vibecode/guard.py:97-115`). The Markdown writer displays `rule_id`, severity, and category for each finding (`vibecode/guard.py:321-324`). The monitor event emitted per finding also includes `rule_id`, `severity`, `category`, path, title, message, evidence, fix, and required tests (`vibecode/run.py:833-848`).

Existing tests assert severity/category counts and per-finding event payloads (`tests/test_vibecode_guard_report.py:166-205`, `tests/test_vibecode_guard_report.py:423-535`).

### PASS WITH NOTE: guard-specific monitor payloads avoid huge raw blobs

Guard finding evidence is path-oriented. Multi-path source/test evidence is summarized to three paths plus a remaining count (`vibecode/guard.py:795-798`), and the monitor finding event carries structured strings/lists rather than raw diffs, stdout, stderr, or file contents (`vibecode/run.py:833-848`).

Note: the broader run summary and metadata still serialize full agent `stdout` and `stderr` (`vibecode/run.py:154-155`, `vibecode/run.py:196-197`). That appears to predate this guard-report change, but it is still a monitor-path size risk if large agent output is common.

### PASS: tests cover findings and no-findings report cases

The added guard-report tests cover Markdown with findings, Markdown with no findings, parent directory creation, grouping, session/root metadata, related tests, JSON with findings, JSON with no findings, per-finding monitor events, no-findings event behavior, and session report paths (`tests/test_vibecode_guard_report.py:214-599`).

The coverage is good for normal returned `GuardResult` cases. The missing case is an exception during guard evaluation/report construction, as noted above.

## Checks Run

- `python -m vibecode.cli context . --task "Review the guard report improvements"`
  - Result: passed; wrote `.vibecode/current/context_pack.md`.
- `python -m pytest tests/test_vibecode_guard_report.py -p no:cacheprovider --basetemp C:\tmp\vibecode-p6-guard-report`
  - Result: failed due environment temp-directory permissions. Pytest collected 36 tests; 23 passed, then 13 `tmp_path`-based tests errored with `PermissionError: C:\tmp\vibecode-p6-guard-report`.
- `python -m ruff check --no-cache vibecode\guard.py vibecode\run.py tests\test_vibecode_guard_report.py`
  - Result: failed with the three unused imports listed above.
- `python -m vibecode.cli guard .`
  - Result: passed; no guard violations found.
- `python -m vibecode.cli handoff-check .`
  - Result: failed on an existing `.vibecode/handoff/NOW.md` placeholder-text issue.
- `python -m vibecode.cli --help`
  - Result: passed.
- `python -m vibecode.cli check .`
  - Result: failed because the required `unit tests` step exited 1 after 158.937s; required CLI help, index help, and context help checks passed.

## Changed Files

- `docs/audit/OBSERVABLE_RUN_MONITOR_P6_GUARD_REPORT_REVIEW.md`
