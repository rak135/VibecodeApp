# Observable Run Monitor P10 Run Replay Review

Generated: 2026-05-12

## Verdict

PASS WITH FIXES REQUIRED. `vibecode runs list` and `vibecode runs show` are artifact readers, not run executors, and default output avoids dumping raw event payloads or stdout/stderr blobs. The command is useful for basic triage: it shows core metadata, guard/check/handoff status, optional event replay, and links to the per-run artifacts.

Two honesty/debuggability issues should be fixed before treating this as complete: corrupt summary files are reported as missing, and missing event logs are shown as `Events (0)` rather than "events artifact missing". The summary view also hides the most useful failure details already present in `summary.json`.

This review did not modify implementation or test files. The task scope allowed only this review document.

## Findings

### PASS: replay/show reads artifacts instead of re-executing anything

`vibecode/show_run.py` only reads from `.vibecode/runs/<session_id>/`: `list_runs()` iterates run directories, `load_run_summary()` reads `summary.json` or `metadata.json`, and `load_run_events()` reads `events.jsonl` (`vibecode/show_run.py:27-105`). The display helpers format loaded dictionaries/events and existing artifact paths (`vibecode/show_run.py:113-239`).

The CLI wiring registers `runs list` and `runs show` as inspection commands (`vibecode/cli.py:455-494`) and dispatches to `cmd_runs()` only for `args.command == "runs"` (`vibecode/cli.py:677-679`). I found no import or call path from `show_run.py` into `RunController`, `cmd_run`, `run_streaming`, `subprocess`, guard execution, check execution, or handoff validation.

### FIX: corrupt summary data is treated as absent

`load_run_summary()` returns `None` for both missing files and invalid JSON (`vibecode/show_run.py:62-75`). `_cmd_runs_show()` then prints `No summary.json found. Available artifacts:` whenever `summary is None` and artifacts exist (`vibecode/show_run.py:308-322`). If `summary.json` exists but is corrupt, that message is not honest: the summary was found but could not be parsed.

The same ambiguity affects `runs list`: a run directory with corrupt `summary.json` is listed without status/task fields, indistinguishable from a run that legitimately has no summary (`vibecode/show_run.py:42-56`).

Recommended fix: return a small load result with `data`, `path`, and `error`, or add a companion loader that distinguishes `missing`, `unreadable`, and `corrupt`. The CLI should say `summary.json is corrupt` or `summary.json could not be read` with the parse/read error, then still list other artifacts.

### FIX: missing events are not reported honestly when `--events` is requested

`load_run_events()` returns `([], [])` when `events.jsonl` does not exist (`vibecode/show_run.py:78-88`). With `--events`, `_cmd_runs_show()` passes that through to the formatter, which prints `Events (0):` (`vibecode/show_run.py:328-344`, `vibecode/show_run.py:224-236`). That output implies an existing empty event log, not a missing event artifact.

The test currently locks in graceful behavior only: `test_show_missing_events_jsonl_graceful` asserts `Events (0)` (`tests/test_vibecode_show_run.py:495-506`). The behavior should remain non-crashing, but the text should distinguish "missing events.jsonl" from "empty events.jsonl".

### PASS WITH GAP: corrupt event lines are handled without crashing

`load_run_events()` reads the JSONL file with replacement decoding, skips blank lines, parses each event independently, and records line-numbered errors for bad JSON or invalid event shape (`vibecode/show_run.py:90-105`). `format_run_show()` surfaces up to five parse errors when events are shown (`vibecode/show_run.py:224-236`), and `_cmd_runs_show()` emits a stderr warning when every event line failed (`vibecode/show_run.py:328-336`).

Tests cover valid events, missing event files, corrupt lines, blank lines, field preservation, and CLI corrupt-events behavior (`tests/test_vibecode_show_run.py:144-198`, `tests/test_vibecode_show_run.py:469-506`). Missing coverage: a CLI assertion that partial corruption is visibly reported, and a missing-events assertion with honest wording after the fix above.

### FIX RECOMMENDED: the summary view is too shallow for failed runs

The current summary output shows task, platform/profile, timestamps, exit code, agent status, guard mode, overall status, guard severity counts, aggregate check counts, handoff pass/fail, and existing artifact paths (`vibecode/show_run.py:171-222`). That is enough to orient an operator.

For debugging a failed or `needs_review` run, it omits the highest-value details already available in `summary.json`: guard finding titles/paths/recommended fixes, failed check names/commands, handoff issues, diff summary, and the top-level `error` field. `RunSummary.as_dict()` persists those nested objects, plus `diff` and `error` when present (`vibecode/run.py:137-167`), but `format_run_show()` only displays aggregate counts.

Recommended fix: keep the default compact, but add a short "Findings" section for guard finding titles/paths, a "Failed checks" section with names and exit codes, a handoff issues section, and the top-level error when present. Continue pointing to artifact files for full logs.

### PASS: raw huge payloads are not exposed by default

Default `runs show` does not print event data, `stdout`, `stderr`, report JSON bodies, prompt contents, context pack contents, or agent logs. It lists artifact paths instead (`vibecode/show_run.py:216-222`). `--events` is opt-in, and even then the formatter prints timestamp, level, type, and message only, not `event.data` (`vibecode/show_run.py:224-236`).

One hardening test is missing: create a summary with large `stdout`/`stderr` values and an event with large `data`, then assert default `format_run_show()` does not include those raw payloads. This would protect the current good behavior.

### PASS WITH TEST GAPS: tests cover normal and some missing/corrupt cases

The focused test file has 40 tests. It covers summary loading, metadata fallback, no summary file, corrupt summary loader return, event parsing, corrupt event lines, missing events, run listing, artifact listing, event replay, missing guard data, missing run IDs, missing summaries with artifacts, and empty run directories (`tests/test_vibecode_show_run.py:92-537`).

Important gaps:

- No CLI test proves corrupt `summary.json` is reported as corrupt rather than missing.
- No test distinguishes missing `events.jsonl` from an empty event log.
- No test asserts default output suppresses large `stdout`, `stderr`, and event `data`.
- No test asserts failed check names, guard finding paths, handoff issues, or run errors are visible.
- No test proves the "chronological order" help text if events are stored out of timestamp order; current replay preserves file order.

## Checks Run

- `python -m vibecode.cli context . --task "Review the run replay/show implementation"`
  - Result: passed; wrote `.vibecode/current/context_pack.md`.
- `python -m pytest tests\test_vibecode_show_run.py -p no:cacheprovider --basetemp C:\tmp\vibecode-showrun-pytest`
  - Result: failed. Pytest collected 40 tests; 4 non-`tmp_path` tests passed, and 36 tests errored because pytest could not create `C:\tmp\vibecode-showrun-pytest` (`PermissionError: [WinError 5]`).
- `python -m pytest tests\test_vibecode_show_run.py -p no:cacheprovider --basetemp .pytest-local-check`
  - Result: failed. Pytest collected 40 tests; 4 non-`tmp_path` tests passed, and 36 tests errored because pytest could not remove/recreate `.pytest-local-check` (`PermissionError: [WinError 5]`).
- `python -m ruff check --no-cache vibecode\show_run.py vibecode\cli.py tests\test_vibecode_show_run.py`
  - Result: failed on existing test lint: `tests\test_vibecode_show_run.py:9` imports `pytest` but does not use it.
- `python -m vibecode.cli runs --help`
  - Result: passed.
- `python -m vibecode.cli --help`
  - Result: passed.
- `python -m vibecode.cli index --help`
  - Result: passed.
- `python -m vibecode.cli context --help`
  - Result: passed.
- `python -m vibecode.cli check .`
  - Result: failed. Required `unit tests` exited 1 after 171.687s; required CLI help, index help, and context help checks passed.
- `python -m vibecode.cli guard .`
  - Result: passed with 1 warning from pre-existing `.pytest-tmp/...` deleted/dirty fixture paths: `source-test-change-balance`.

## Changed Files

- `docs/audit/OBSERVABLE_RUN_MONITOR_P10_RUN_REPLAY_REVIEW.md`
