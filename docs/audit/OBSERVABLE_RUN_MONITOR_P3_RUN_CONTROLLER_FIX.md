# Observable Run Monitor P3 Run Controller Fix

Applied: 2026-05-11
Based on: docs/audit/OBSERVABLE_RUN_MONITOR_P3_RUN_CONTROLLER_REVIEW.md

## Changes Applied

### Fix 1 (BLOCKER): Wire events.jsonl for normal CLI runs

`RunController.execute()` now creates a `JsonlEventSink` via `RunSession.create_event_sink()` and wraps it together with any injected sink in a `MultiEventSink`. This ensures that all normal `vibecode run` executions write structured events to `.vibecode/runs/<session_id>/events.jsonl`.

- `vibecode/run.py:58` — added `MultiEventSink` import
- `vibecode/run.py:453-459` — after creating `RunSession`, construct `MultiEventSink([jsonl_sink, ...])` and assign to `self.sink`

### Fix 2 (BLOCKER): Post-check exceptions emit proper error events

Guard, required-checks, and handoff exception paths now emit `EventLevel.ERROR` events with `passed=False`, `status="error"`, and the exception message. Previously these paths emitted misleading success-shaped events (`passed=True`, `findings=0`) when the result object was `None` due to an exception.

- `vibecode/run.py:780` — guard: added `guard_error: str | None` tracking variable
- `vibecode/run.py:795` — guard: capture exception string in `guard_error`
- `vibecode/run.py:798-809` — guard: emit ERROR event when exception occurred, emit skipped event when not a git repo, emit normal event otherwise
- `vibecode/run.py:813` — checks: added `check_error: str | None` tracking variable
- `vibecode/run.py:819` — checks: capture exception string in `check_error`
- `vibecode/run.py:821-837` — checks: emit ERROR event when exception occurred, defensive INFO for None case, normal event otherwise
- `vibecode/run.py:842` — handoff: added `handoff_error: str | None` tracking variable
- `vibecode/run.py:851` — handoff: capture exception string in `handoff_error`
- `vibecode/run.py:853-869` — handoff: emit ERROR event when exception occurred, emit skipped event when not a git repo, emit normal event otherwise

### Fix 3 (WARNING): Agent preflight failure phase changed to 'preflight_failed'

Agent-availability failure events (command-not-found, check-failed) now use `phase: "preflight_failed"` and include `status: "error"` in their data payload. Previously they used `phase: "started"`, which was misleading since no agent process was ever started.

- `vibecode/run.py:664-665` — "Agent command not found" event
- `vibecode/run.py:681-682` — "Agent check failed" event

### Lint fixes (tests)

Removed unused `import stat` and unused local variable `types` in `tests/test_vibecode_run_controller.py`.

### Tests added

- `tests/test_vibecode_run_controller.py:365-369` — `test_summary_json_exists_after_successful_run` now verifies `events.jsonl` exists and is non-empty when running without an injected sink
- `tests/test_vibecode_run_controller.py:586-590` — `test_cli_run_writes_summary_json` now verifies `events.jsonl` exists and is non-empty in the CLI path

## Verification

- `ruff check vibecode/run.py tests/test_vibecode_run_controller.py` — passed (0 errors)
- `pytest tests/test_vibecode_run_controller.py` — 21 passed

## Not Addressed

The WARNING about a large orchestration object (`RunController.execute()`) is a refactoring suggestion, not an actionable bug fix. The method size predates this refactor and was not made worse by it.

The WARNING about post-check code duplication between `execute()` and `_run_post_checks()` is also a refactoring concern. Both copies now share the same fixed event-emission logic.
