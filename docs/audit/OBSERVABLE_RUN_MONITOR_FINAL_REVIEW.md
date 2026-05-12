# Observable Run Monitor Final Review

Generated: 2026-05-12

## Verdict

PARTIAL PASS. The observable run monitor is substantially implemented: normal
`vibecode run` execution writes structured events, durable run artifacts,
prompt/context snapshots, guard/check/handoff reports, and replayable
`runs show` output. The monitor is an MVP streaming Textual view, not a PTY,
and the docs/dogfood report state that limitation clearly.

I would not mark the product goal as fully closed yet. One real correctness
issue remains: `RunController.execute()` creates `.vibecode/runs/<session_id>/events.jsonl`
before git preflight, so the run artifact can change the working tree state
that preflight is supposed to inspect. The dogfood report treats the resulting
`test_missing_gitignore_blocks_agent_launch` failure as stale-test fragility,
but the behavior itself is brittle and should be fixed. Current verification
is also not green: required tests fail in this environment because pytest
cannot access its temp base, and `ruff check vibecode` still reports 7 issues.

This review only adds this document. It does not modify implementation files or
tests, per the task's "Only write the final review" constraint.

## Findings

### FIX REQUIRED: run artifacts affect git preflight

`RunController.execute()` constructs a `RunSession`, creates the JSONL event
sink, and emits `Run started` before running `_run_git_check()` (`vibecode/run.py:474-520`).
That creates `.vibecode/runs/<session_id>/events.jsonl` before the dirty-tree
preflight. In repos where `.vibecode/runs/` is not already ignored, the run's
own observability artifact becomes a changed file and can mask the intended
preflight error.

The dogfood report documents this exact symptom for
`test_missing_gitignore_blocks_agent_launch`: the observed failure is a dirty
tree caused by `.vibecode/runs/<session_id>/events.jsonl`, not the expected
gitignore-missing message. That is not just a stale assertion; it is a
preflight purity bug.

Recommended fix: keep early events in memory until after gitignore/dirty-tree
preflight has completed, or ensure run artifacts are created only in a location
that is known to be ignored before the dirty-tree check runs.

### PASS: event spine is wired through run and monitor

The event model is dependency-light and serializable (`vibecode/events.py`).
Normal `RunController` execution fans out to a per-run `JsonlEventSink`, and
also to an injected sink when the monitor supplies one (`vibecode/run.py:486-490`).
The controller emits lifecycle, git preflight, index, context, prompt, agent,
guard, check, handoff, and summary events.

The monitor uses that same controller with `TUIEventSink`, routes agent process
events to the left pane, and routes all other Vibecode events to the right pane
(`vibecode/monitor_app.py:122-246`). This is the right MVP shape.

### PASS WITH LIMITATION: MCP uses the event model, but not the per-run spine

MCP tool calls emit `run.mcp` events with compact call/return/failure payloads
(`vibecode/mcp_server.py:81-88`, `vibecode/mcp_server.py:212-276`). `cmd_serve`
writes those events to `.vibecode/logs/mcp_events.jsonl` and can correlate via
`VIBECODE_SESSION_ID` (`vibecode/mcp_server.py:327-370`).

That is observable, but it is a separate serve-process log, not the same
`.vibecode/runs/<session_id>/events.jsonl` stream and not shown in the monitor.
The current docs report that limitation, so this is acceptable as long as the
claim stays scoped to correlation rather than unified per-run capture.

### PASS: guard is advisory by default

`RunSummary.guard_mode` defaults to `advisory`, the CLI `run` and `monitor`
parsers default `--guard-mode` to `advisory`, and `_exit_code_for_status()`
returns 0 for `needs_review` (`vibecode/run.py:115-134`,
`vibecode/run.py:394-399`, `vibecode/cli.py:193-204`, `vibecode/cli.py:428-435`).
Strict mode is still available and turns guard failures into run failure.

### PASS: artifacts are durable and replayable

`RunSession` defines stable per-session paths for `events.jsonl`,
`summary.json`, prompt/context snapshots, guard/check/handoff reports, and
agent stdout/stderr logs (`vibecode/session_log.py:55-122`). Successful normal
runs persist summary, metadata, reports, snapshots, and logs under
`.vibecode/runs/<session_id>/` (`vibecode/run.py:998-1055`).

`vibecode runs list/show` reads artifacts only; it does not re-execute agents,
guards, checks, or handoff validation (`vibecode/show_run.py:27-105`,
`vibecode/show_run.py:285-382`). Prior replay review issues around corrupt
summaries and missing event files appear fixed: the loader distinguishes
missing/corrupt/unreadable summaries and `--events` reports missing
`events.jsonl`.

### PASS: prompt/context truth is preserved per run

Context and prompt snapshots are copied into the run directory before the
corresponding events are emitted (`vibecode/run.py:661-689`). The events carry
snapshot path, size, task summary, platform/profile, and context sections
without embedding the full prompt/context bodies. The targeted tests include a
fake OpenCode stdin assertion that the prompt sent to the agent matches the
snapshot on disk (`tests/test_vibecode_run_controller.py:1012-1032`).

### PASS WITH LIMITATION: two-pane monitor is MVP-level

The monitor provides the claimed two-pane split, status fields, and event
routing helpers. It is explicitly a streaming text monitor, not PTY/ConPTY,
and the CLI help states that closing the monitor does not manage the running
agent process (`vibecode/monitor_app.py:1-12`, `vibecode/cli.py:386-396`).

The remaining gap is validation depth: the dogfood run did not launch a real
OpenCode binary or an interactive Textual session. Unit coverage and helper
smoke tests are useful, but the final report should continue to call this an
MVP until a fake or real end-to-end monitor run verifies live agent output,
artifact writing, and process exit behavior together.

### PASS WITH GAPS: tests are broad but current checks are not green

The observable layer has credible focused coverage across session paths,
events, controller sequencing, advisory guard mode, prompt/context snapshots,
MCP logging, monitor formatting/dispatch, and run replay. The tests are not
just superficial parser checks.

The current repository state still does not satisfy the requested quality bar:
`vibecode check .` fails because `python -m pytest` cannot access
`C:\Users\Martin\AppData\Local\Temp\pytest-of-Martin`, and `ruff check vibecode`
reports 7 lint issues. The dogfood report's earlier "1753 passed, 1 failed"
result is useful historical evidence, but my current verification cannot
reproduce a green test run in this environment.

## Architecture Review

I did not find evidence of an agent runtime being implemented beyond the
explicit external OpenCode orchestration already in scope. The event module
stays dependency-light, session artifacts remain under ignored runtime paths,
and MCP observability does not store large response blobs in event payloads.

The main architecture violation risk is the preflight side effect described
above: runtime artifacts should not influence guard/preflight truth. Fixing
that would make the observable layer align cleanly with the repository's
generated/runtime separation rules.

## Checks Run

- `python -m vibecode.cli context . --task "Perform final independent review of the observable monitor implementation and dogfood report"`
  - Result: passed; wrote `.vibecode/current/context_pack.md`.
- `python -m compileall vibecode -q`
  - Result: passed.
- `python -m vibecode.cli --help`
  - Result: passed.
- `python -m vibecode.cli monitor --help`
  - Result: passed.
- `python -m vibecode.cli runs --help`
  - Result: passed.
- `python -m vibecode.cli index --help`
  - Result: passed.
- `python -m vibecode.cli context --help`
  - Result: passed.
- `python -m pytest tests/test_vibecode_monitor.py::TestRouteEvent tests/test_vibecode_monitor.py::TestFormatAgentLine tests/test_vibecode_monitor.py::TestFormatVibecodeeLine tests/test_vibecode_monitor.py::TestTUIEventSink tests/test_vibecode_monitor.py::TestMonitorModuleImport tests/test_vibecode_monitor.py::TestMonitorCLIParser -p no:cacheprovider`
  - Result: passed, 47 tests.
- `python -m pytest tests/test_vibecode_session_log.py tests/test_vibecode_run_controller.py tests/test_vibecode_run_post.py tests/test_vibecode_mcp_server.py tests/test_vibecode_monitor.py tests/test_vibecode_show_run.py -p no:cacheprovider --basetemp C:\tmp\vibecode-final-review-pytest`
  - Result: failed at setup; pytest could not create the basetemp directory due `PermissionError: [WinError 5]`.
- `python -m pytest tests/test_vibecode_session_log.py tests/test_vibecode_run_controller.py tests/test_vibecode_run_post.py tests/test_vibecode_mcp_server.py tests/test_vibecode_monitor.py tests/test_vibecode_show_run.py -p no:cacheprovider --basetemp tmp/vibecode-final-review-pytest-2`
  - Result: failed; many `tmp_path` tests errored and pytest later hit `PermissionError` reading the basetemp directory.
- `python -m vibecode.cli check .`
  - Result: failed. Required unit tests failed after 176.375s because pytest could not scan `C:\Users\Martin\AppData\Local\Temp\pytest-of-Martin`. Required CLI help, index help, and context help checks passed.
- `python -m ruff check vibecode`
  - Result: failed with 7 existing issues: unused locals/imports in indexer files, undefined `posix` in `vibecode/indexer/ts_symbols.py`, and unused `to_posix_str` in `vibecode/registry.py`.
- `python -m ruff check vibecode tests docs`
  - Result: failed with broader existing lint issues in tests plus the 7 `vibecode` issues above.
- `python -m vibecode.cli guard .`
  - Result: passed with 1 warning from pre-existing deleted `.pytest-tmp/...` fixture paths (`source-test-change-balance`).
- `python -m vibecode.cli validate .`
  - Result: passed with 1 warning: `.vibecode/handoff/NOW.md` contains placeholder text.
- `python -m vibecode.cli handoff-check .`
  - Result: failed on the existing `.vibecode/handoff/NOW.md` placeholder-text issue.

## Changed Files

- `docs/audit/OBSERVABLE_RUN_MONITOR_FINAL_REVIEW.md`
