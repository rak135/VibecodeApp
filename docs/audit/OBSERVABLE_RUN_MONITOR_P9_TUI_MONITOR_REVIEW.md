# Observable Run Monitor P9 TUI Monitor Review

Generated: 2026-05-12

## Verdict

PASS WITH FIXES REQUIRED. The monitor is correctly built on the structured event spine and keeps agent output separate from Vibecode events. It also avoids claiming PTY/full interactive terminal support.

Two operator-facing requirements are not fully met in the current TUI formatting: prompt/context artifact paths are present in event payloads but are not displayed, and guard finding details are emitted but mostly hidden by the generic event formatter. There is also one smaller documentation/behavior mismatch around quitting the monitor while a daemon worker thread is running.

This review did not modify implementation or test files. The task scope allowed only this review document.

## Findings

### PASS: monitor uses the event spine, not scraped CLI output

`MonitorApp.on_mount()` constructs a `RunController` with a `TUIEventSink` and runs the controller in a worker thread (`vibecode/monitor_app.py:162-192`). `TUIEventSink.emit()` forwards each `VibecodeEvent` through Textual's `call_from_thread()` bridge (`vibecode/monitor_app.py:76-87`).

The controller always creates the run-session JSONL sink and fans out to the monitor sink through `MultiEventSink` (`vibecode/run.py:483-490`). Agent stdout/stderr is also emitted as structured `run.agent_process` events by `run_streaming()` while the process is running (`vibecode/process_runner.py:32-59`, `vibecode/process_runner.py:120-144`). I found no monitor-side scraping of printed CLI output.

### PASS: agent output and Vibecode events are separated

The routing helper sends only `EVENT_AGENT_PROCESS` to the agent pane and all other events to the Vibecode event pane (`vibecode/monitor_app.py:66-68`). `handle_vibecode_event()` then writes routed agent lines to `#agent-log` and non-agent events to `#event-log` (`vibecode/monitor_app.py:198-206`).

The visible labels reinforce that separation: `Agent (stdout / stderr)` on the left and `Vibecode Events` on the right (`vibecode/monitor_app.py:148-154`). Tests cover the routing behavior for agent, guard, check, lifecycle, summary, and handoff events (`tests/test_vibecode_monitor.py:65-83`).

### PASS WITH NOTE: no full interactive terminal support is claimed

The monitor module explicitly says it is "a streaming-output monitor (text mode), not a PTY" and directs users to run OpenCode directly for full interactive terminal control (`vibecode/monitor_app.py:11-12`). The CLI help repeats the same limitation (`vibecode/cli.py:389-396`). `run_streaming()` also documents that full PTY/ConPTY support is out of scope (`vibecode/process_runner.py:8-9`).

The note is accurate for the implementation: the agent process receives the prompt on stdin and stdout/stderr are read line by line through pipes (`vibecode/process_runner.py:105-115`, `vibecode/process_runner.py:120-144`).

### FIX: prompt/context artifact paths are not shown in the TUI

The event spine has the required data. `RunController.execute()` emits `run.context` with `path`, `snapshot_path`, `size_bytes`, `task_summary`, and section headings (`vibecode/run.py:660-675`). It emits `run.prompt` with `path`, `snapshot_path`, `size_bytes`, `platform`, and `profile` (`vibecode/run.py:677-686`).

The monitor drops those payload fields. `format_vibecode_line()` renders only timestamp, severity, event type, and message (`vibecode/monitor_app.py:57-63`), and `handle_vibecode_event()` writes that generic string to the event pane (`vibecode/monitor_app.py:204-206`). In practice, the operator sees `run.context: Context pack written` and `run.prompt: Prompt written`, but not the prompt or context artifact paths.

Recommended fix: special-case `EVENT_CONTEXT` and `EVENT_PROMPT` in the formatter or event handler so the visible line includes at least `snapshot_path`, falling back to `path` when no snapshot exists. Add focused tests that format representative context and prompt events and assert the visible text contains `context_pack.md`, `opencode_prompt.md`, and the session run directory.

### FIX: guard warnings are visible, but not clear enough

Guard findings are emitted with rich data: rule id, severity, category, path, title, message, why-it-matters text, evidence, recommended fix, and required tests (`vibecode/run.py:886-904`). The guard completion event also includes counts by severity and category (`vibecode/run.py:906-920`).

The monitor currently displays only the event severity, event type, and event message (`vibecode/monitor_app.py:57-63`). The status bar reduces all non-passing guard results to `Guard: x findings` (`vibecode/monitor_app.py:214-219`, `vibecode/monitor_app.py:227-230`). That makes warnings technically visible but not operationally clear: the path, rule id/category, evidence, and recommended fix are hidden even though they are already present in the event payload.

Recommended fix: special-case `EVENT_GUARD_FINDING` so warning/error lines include severity, category/rule id, path, title, and a compact fix or required-test hint. Also include error/warning counts in the guard status after the `EVENT_GUARD` completed event. Add tests for warning and error guard-finding formatting.

### PASS: existing dashboard and run commands are not obviously broken

The new monitor is registered as a separate CLI branch (`vibecode/cli.py:384-437`, `vibecode/cli.py:624-628`). Dashboard dispatch still imports and runs `VibecodeTUI` through its existing branch (`vibecode/cli.py:610-622`). The normal `run` command still resolves the repository and delegates to `cmd_run()` (`vibecode/cli.py:587-591`), and `cmd_run()` constructs `RunController` without a TUI sink (`vibecode/run.py:1109-1135`).

Monitor tests cover parser registration, command dispatch, and the mocked `cmd_monitor()` path (`tests/test_vibecode_monitor.py:296-345`, `tests/test_vibecode_monitor.py:353-460`). Dashboard tests remain in their existing file and import path (`tests/test_vibecode_dashboard.py`).

### FIX RECOMMENDED: quit behavior claim is not backed by lifecycle management

The monitor help says, "Press Q to quit (the agent run continues until it exits naturally)" (`vibecode/cli.py:396`). The implementation binds `q` to `app.exit` (`vibecode/monitor_app.py:103-107`) and runs `RunController.execute()` in a daemon thread (`vibecode/monitor_app.py:189-192`).

There is no explicit subprocess handoff, cancellation, detach, or join behavior when the Textual app exits. Once `cmd_monitor()` returns, Python process shutdown can stop the daemon thread, and the child process behavior is platform-dependent. This is not a PTY claim, but it is still an operator-facing overclaim.

Recommended fix: either remove that sentence or implement explicit lifecycle semantics for quit. For example, "Press Q to close the monitor; running agent process behavior is not managed" would be more honest unless the process is deliberately detached or gracefully stopped.

### PASS WITH TEST GAPS: import and formatting coverage prevents immediate rot

The monitor test file covers module import, required symbols, basic routing, agent-line formatting, generic Vibecode-line formatting, `TUIEventSink`, parser registration, `cmd_monitor()`, and CLI dispatch (`tests/test_vibecode_monitor.py:65-460`). That is enough to catch immediate import/registration/formatter breakage.

The tests do not yet cover the two missing operator-facing requirements above. There are no assertions that formatted context/prompt events display artifact paths, and no assertions that guard-finding formatting displays path/rule/fix details. Adding those tests would turn the current review findings into stable regressions.

## Checks Run

- `python -m vibecode.cli context . --task "Review the TUI monitor implementation"`
  - Result: passed; wrote `.vibecode/current/context_pack.md`.
- `python -m pytest tests/test_vibecode_monitor.py -p no:cacheprovider --basetemp C:\Users\Martin\.codex\memories\vibecode-p9-monitor-pytest`
  - Result: failed. Pytest collected 45 tests; the non-`tmp_path` formatter/import/parser tests ran through, then the `tmp_path`-using smoke tests errored and pytest crashed during session cleanup with `PermissionError: C:\Users\Martin\.codex\memories\vibecode-p9-monitor-pytest`.
- `python -m pytest tests/test_vibecode_monitor.py::TestCmdMonitor::test_cmd_monitor_calls_run_and_returns_zero -vv --tb=short -p no:cacheprovider --basetemp C:\Users\Martin\.codex\memories\vibecode-p9-one-pytest`
  - Result: failed before useful test output with the same pytest temp-directory `PermissionError`.
- `python -m pytest -p no:cacheprovider --basetemp C:\Users\Martin\.codex\memories\vibecode-p9-full-pytest`
  - Result: failed. Pytest collected 1695 tests, but many tests using temp fixtures errored and pytest crashed during session cleanup with `PermissionError: C:\Users\Martin\.codex\memories\vibecode-p9-full-pytest`.
- `python -m ruff check --no-cache vibecode\monitor_app.py vibecode\cli.py tests\test_vibecode_monitor.py`
  - Result: failed due an unused import in the existing monitor test file: `tests/test_vibecode_monitor.py:15` imports `pathlib.Path` but does not use it.
- `python -m vibecode.cli --help`
  - Result: passed.
- `python -m vibecode.cli index --help`
  - Result: passed.
- `python -m vibecode.cli context --help`
  - Result: passed.
- `python -m vibecode.cli monitor --help`
  - Result: passed.
- `python -m vibecode.cli guard .`
  - Result: exit code 0 with one warning from pre-existing `.pytest-tmp/...` deleted/dirty fixture files: `source-test-change-balance`.
- `python -m vibecode.cli validate .`
  - Result: passed with warning: `.vibecode/handoff/NOW.md` contains placeholder text.
- `python -m vibecode.cli handoff-check .`
  - Result: failed on existing `.vibecode/handoff/NOW.md` placeholder-text issue.
- `python -m vibecode.cli check .`
  - Result: failed because required `unit tests` exited 1 after 170.203s; required CLI help, index help, and context help checks passed.

## Changed Files

- `docs/audit/OBSERVABLE_RUN_MONITOR_P9_TUI_MONITOR_REVIEW.md`
