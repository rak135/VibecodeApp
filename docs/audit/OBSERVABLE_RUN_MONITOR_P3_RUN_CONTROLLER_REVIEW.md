# Observable Run Monitor P3 Run Controller Review

Generated: 2026-05-11

## Verdict

FIX REQUIRED. The refactor mostly preserves the existing `vibecode run` launch semantics and adds a useful injectable event surface, but the observable run monitor is not yet wired end-to-end for normal CLI runs. The most important gap is that `RunController` defaults to `NullEventSink` and `cmd_run()` does not connect the controller to the `RunSession` JSONL event artifact, so normal runs still do not produce `.vibecode/runs/<session_id>/events.jsonl`.

This review did not modify implementation or test files. The task scope allowed only this review document.

## Findings

### BLOCKER: Normal CLI runs do not write the session event artifact

`RunSession` defines `events_jsonl` and `create_event_sink()` for `.vibecode/runs/<session_id>/events.jsonl` (`vibecode/session_log.py:70-133`), but `RunController` defaults to `NullEventSink` when no sink is injected (`vibecode/run.py:420`) and `cmd_run()` constructs the controller without a sink (`vibecode/run.py:959-966`).

That means all events emitted by the default `vibecode run` path are discarded. The new events are only observable in tests or custom callers that explicitly pass a sink. This breaks the intended connection between session artifacts and events.

Recommended fix: have `cmd_run()` or `RunController.execute()` create a `RunSession(root, session_id).create_event_sink()` for normal runs, optionally using a `MultiEventSink` when an external sink is injected.

### BLOCKER: Post-check execution errors emit misleading success-shaped events

Guard, required-check, and handoff exceptions are printed to stderr, but their structured completion events still report passed/clean results when the result object is missing:

- Guard exceptions leave `guard_result` as `None`, then emit `passed=True` and `findings=0` (`vibecode/run.py:776-798`).
- Required-check exceptions leave `check_result` as `None`, then emit `passed=True`, `total=0`, and `failed=0` (`vibecode/run.py:803-817`).
- Handoff exceptions leave `handoff_result` as `None`, then emit `passed=True` and `issues=0` (`vibecode/run.py:822-838`).

The pre-existing run summary semantics tolerate missing post-check results, so this is not necessarily a behavior-preservation regression. It is an observability bug: failure paths do not emit useful events, and downstream monitors would read a check-execution failure as a clean completion.

Recommended fix: emit a `WARNING` or `ERROR` event with `passed=False`, `status="error"`, and the exception message when a post-check runner fails or is skipped unexpectedly.

### WARNING: Agent availability failures use the `started` phase even when no agent starts

When no command is resolved or `check_opencode()` fails, the controller emits `EVENT_AGENT_PROCESS` with `data={"phase": "started", ...}` (`vibecode/run.py:654-672`) and then aborts the run. No matching agent `finished` event is emitted because the process was never launched.

The error message itself is useful, but the phase value is misleading and makes event consumers treat a pre-launch failure as a started process.

Recommended fix: use a distinct phase such as `failed` or `preflight_failed`, or emit an agent-process completion event with `status="error"` and no `exit_code`.

### WARNING: The controller extraction still leaves a large orchestration object

`RunController.execute()` owns project validation, git preflight, index freshness checks, context generation, command resolution, process execution, post-run guard/check/handoff, artifact writes, summary printing, and exit-code mapping in one long method (`vibecode/run.py:442-941`). It also duplicates the post-check orchestration that still exists in `_run_post_checks()` (`vibecode/run.py:311-363`, `vibecode/run.py:773-838`).

This is not worse than the original `cmd_run()` in behavior, but it is close to a renamed god function with event calls inserted. The refactor would be easier to maintain if phase-sized private methods owned one concern each and reused `_run_post_checks()` or replaced it cleanly.

### PASS: Existing launch semantics appear preserved

The CLI still validates `.vibecode/project.yaml`, validates advisory permission profiles, refuses dirty trees unless `--allow-dirty`, refreshes missing/stale indexes unless `--no-index`, generates context/prompt through `cmd_context()`, checks OpenCode availability before launch, runs the configured command through `subprocess.run(..., shell=True)`, captures stdout/stderr, runs post-checks, writes metadata/summary, and maps overall statuses to the same exit codes (`vibecode/run.py:461-941`).

I did not find hidden hard enforcement newly added by the controller extraction. Permission profiles remain advisory metadata in `vibecode/permissions.py`, and the launch still does not pass profile settings into OpenCode permissions.

### PASS: Event volume is meaningful, not spammy

The controller emits phase-level events for lifecycle, git preflight, index check, context, prompt, agent process, guard, checks, handoff, and summary. That is a reasonable event granularity for an observable run monitor. It does not emit per-line stdout/stderr or high-cardinality file events.

### PASS: Tests avoid real OpenCode

The new controller tests create temporary git repositories and fake OpenCode commands rather than requiring a real OpenCode installation (`tests/test_vibecode_run_controller.py:32-195`). They exercise both direct `RunController` use and the legacy CLI path (`tests/test_vibecode_run_controller.py:203-674`).

Coverage gaps remain for durable `events.jsonl` creation in the real CLI path and for post-check exception events.

## Checks Run

- `python -m vibecode.cli context . --task "Review the run controller refactor"`
  - Result: passed; wrote the task context pack to `.vibecode/current/context_pack.md`.
- Static source review of `b78bf42` against `0079eb9`.
  - Result: completed; reviewed `vibecode/run.py`, `vibecode/events.py`, `vibecode/session_log.py`, and `tests/test_vibecode_run_controller.py`.
- `python -m pytest tests/test_vibecode_run_controller.py`
  - Result: failed before product assertions; pytest could not access `C:\Users\Martin\AppData\Local\Temp\pytest-of-Martin` (`PermissionError`).
- `python -m pytest tests/test_vibecode_run_controller.py -p no:cacheprovider --basetemp C:\tmp\pytest-vibecode-run-controller`
  - Result: failed before product assertions; pytest could not create `C:\tmp\pytest-vibecode-run-controller` (`PermissionError`).
- `python -m pytest tests/test_vibecode_run_controller.py -p no:cacheprovider --basetemp .\codex_pytest_run_controller_tmp`
  - Result: failed during pytest temp-directory cleanup with `PermissionError` on the workspace-local base temp directory.
- `python -m vibecode.cli --help`
  - Result: passed.
- `python -m vibecode.cli index --help`
  - Result: passed.
- `python -m vibecode.cli context --help`
  - Result: passed.
- `python -m vibecode.cli check .`
  - Result: failed because the required `python -m pytest` check hit the same pytest temp-root `PermissionError`; the three required CLI help checks passed.
- `python -m ruff check --no-cache vibecode tests`
  - Result: failed with 62 lint issues across existing source/tests. The new run-controller test file contributes `tests/test_vibecode_run_controller.py:11` (`stat` unused) and `tests/test_vibecode_run_controller.py:272` (unused local `types`).
- `python -m ruff check --no-cache docs\audit\OBSERVABLE_RUN_MONITOR_P3_RUN_CONTROLLER_REVIEW.md`
  - Result: passed with Ruff's warning that no Python files exist under that path.
- `python -m vibecode.cli guard .`
  - Result: passed; no guard violations found.
- `python -m vibecode.cli handoff-check .`
  - Result: failed on existing `.vibecode/handoff/NOW.md` placeholder-text issue.
