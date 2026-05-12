# Observable Run Monitor P14 Durable Failures Review

## Verdict

**FIX REQUIRED / EVIDENCE INCOMPLETE.**

The core `RunController.execute()` setup order is correct: it constructs `RunSession`, attaches the per-session JSONL sink, replaces `self.sink` with a `MultiEventSink`, and only then emits `run.started` (`vibecode/run.py:534-543`). That addresses the main durability risk of events being emitted before `events.jsonl` exists.

The implementation also writes abort summaries for the visible early-return paths I checked: missing project config, invalid profile, dirty preflight, index generation failure, missing index, inventory health failure, context generation failure, missing context pack, missing OpenCode, OpenCode check failure, and run-plan preflight errors (`vibecode/run.py:551-875`). The abort summary shape is intentionally minimal and marks `overall_status` as `"error"` with an `error` field (`vibecode/run.py:225-260`).

I do not accept the P14.1 implementation as fully proven because the required test evidence is incomplete for several requested failure classes, and local pytest execution is blocked before product assertions by Windows temp-directory ACL errors.

## Findings

### Medium: required early-abort matrix is not covered by tests

`TestEarlyAbortArtifacts` covers missing `project.yaml`, invalid profile, and dirty preflight only (`tests/test_vibecode_run_controller.py:1118-1349`). I found no targeted tests proving durable `events.jsonl` and `summary.json` for index generation failure, missing index, inventory health failure, context generation failure, missing context pack, missing OpenCode, OpenCode check failure, run-plan preflight errors, or agent launch `OSError`.

Those paths do call `_write_abort_summary()` in implementation (`vibecode/run.py:666-875`), and agent launch `OSError` is converted into an agent failure summary later (`vibecode/run.py:914-1162`). But the task explicitly required evidence for index/context failures, missing OpenCode, OpenCode check failure, and launch exceptions. That evidence is not present in the test suite.

### Medium: persisted early-abort JSONL is not parsed back as `VibecodeEvent`

The new early-abort tests read persisted `events.jsonl` with `json.loads()` (`tests/test_vibecode_run_controller.py:1140`, `tests/test_vibecode_run_controller.py:1197`, `tests/test_vibecode_run_controller.py:1255`, `tests/test_vibecode_run_controller.py:1306`). `load_run_events()` correctly parses JSONL lines through `VibecodeEvent.from_json()` (`vibecode/show_run.py:107`), and `TestLoadRunEvents` covers that parser with synthetic events (`tests/test_vibecode_show_run.py:147-205`).

What is missing is the required proof that actual `RunController` abort artifacts round-trip through the event model. Add at least one early-abort integration assertion that reads `.vibecode/runs/<session_id>/events.jsonl` from a real controller abort and parses every line as `VibecodeEvent`.

### Low: duplicate-event fan-out is not regression-tested

The code avoids duplication in the default path by appending the caller sink only when `self.sink` is not a `NullEventSink` (`vibecode/run.py:537-540`). I did not see an implementation bug in the CLI/default path.

However, there is no regression test comparing the durable JSONL stream to the external in-memory sink for a run with an injected sink. A simple test could assert matching event IDs with no duplicates in each sink. That would directly cover the watch item for sink fan-out mistakes.

## Pass Evidence

- `RunSession` and JSONL sink are created before the first lifecycle event (`vibecode/run.py:534-543`).
- `RunSession.create_event_sink()` ensures `.vibecode/runs/<session_id>/` exists before JSONL writes (`vibecode/session_log.py:126-133`).
- `_write_abort_summary()` writes `.vibecode/runs/<session_id>/summary.json` with `$schema`, `session_id`, timestamps, `overall_status: "error"`, and `error` (`vibecode/run.py:225-260`).
- Missing config and invalid profile abort before git/index work but still emit `run.started`, `run.finished`, and summary (`vibecode/run.py:551-570`).
- Dirty preflight emits git-preflight events, `run.finished`, and summary (`vibecode/run.py:577-598`).
- Index/context/OpenCode abort paths call `_write_abort_summary()` (`vibecode/run.py:666-875`).
- Agent launch `OSError` is captured into stderr/log files and a normal failure summary is written after post-run checks (`vibecode/run.py:914-1162`).
- `runs show` marks missing guard/check/handoff data on early aborts as `(skipped - run aborted)`, not success (`vibecode/show_run.py:196-247`).
- `runs show --events` uses `load_run_events()` and parses JSONL lines as `VibecodeEvent` objects (`vibecode/show_run.py:82-111`, `vibecode/show_run.py:376-389`).
- Optional artifact display lists only existing paths and does not infer guard/check/handoff success from artifact presence (`vibecode/show_run.py:119-132`, `vibecode/show_run.py:195-247`).
- `load_run_summary()` preserves backward compatibility by falling back from `summary.json` to `metadata.json` (`vibecode/show_run.py:57-70`).

## Test Evidence Review

- Exact artifact paths are asserted for several cases, for example `.vibecode/runs/abort-no-yaml-001/events.jsonl`, `.vibecode/runs/abort-no-yaml-002/summary.json`, `.vibecode/runs/abort-dirty-001/events.jsonl`, and `.vibecode/runs/abort-profile-002/summary.json` (`tests/test_vibecode_run_controller.py:1135-1282`).
- Summary status/error fields are asserted for missing config, dirty preflight, and invalid profile (`tests/test_vibecode_run_controller.py:1169-1176`, `tests/test_vibecode_run_controller.py:1226-1229`, `tests/test_vibecode_run_controller.py:1286-1290`).
- CLI replay/formatter output for aborted runs is covered by `TestEarlyAbortShowCLI`, including `runs show --events` output (`tests/test_vibecode_show_run.py:824-889`).
- Missing optional `events.jsonl` is handled gracefully for `runs show --events` (`tests/test_vibecode_show_run.py:861-873`).
- Missing evidence: real controller abort JSONL parsed as `VibecodeEvent`; durable artifacts for index/context/OpenCode check failures; durable summary for agent launch exception.

## Validation Commands

- `python -m vibecode.cli context . --task "Review the P14.1 implementation for durable failure run monitor behavior"`
  - **PASS**. Wrote `.vibecode/current/context_pack.md`.
- `python -m pytest tests/test_vibecode_run_controller.py::TestEarlyAbortArtifacts tests/test_vibecode_show_run.py::TestLoadRunEvents tests/test_vibecode_show_run.py::TestEarlyAbortDisplay tests/test_vibecode_show_run.py::TestEarlyAbortShowCLI -p no:cacheprovider`
  - **FAIL / ENVIRONMENT**. All 25 selected tests errored during `tmp_path` fixture setup because pytest could not scan `C:\Users\Martin\AppData\Local\Temp\pytest-of-Martin` (`PermissionError: [WinError 5]`).
- Same targeted pytest command with `--basetemp C:\tmp\codex-p14-review-pytest`
  - **FAIL / ENVIRONMENT**. All 25 selected tests errored during base temp creation (`PermissionError: [WinError 5]` creating `C:\tmp\codex-p14-review-pytest` with mode `0o700`).
- `python -m vibecode.cli --help`
  - **PASS**.
- `python -m vibecode.cli index --help`
  - **PASS**.
- `python -m vibecode.cli context --help`
  - **PASS**.
- `python -m ruff check vibecode tests docs`
  - **FAIL**. 43 existing lint findings, including new P14.1 ambiguous variable-name findings in `tests/test_vibecode_run_controller.py:1197`, `tests/test_vibecode_run_controller.py:1255`, and `tests/test_vibecode_show_run.py:787-801`; Ruff cache writes also failed with access denied.
- `python -m vibecode.cli check .`
  - **TIMEOUT / FAILING UNIT TESTS** after 190s. The command reported `FAIL: unit tests`, then `PASS` for the three CLI help checks before the shell timeout.

## Scope Notes

- No implementation files were modified for this review.
- I did not update `.vibecode/handoff/NOW.md` because the task explicitly constrained output to this review document only.
