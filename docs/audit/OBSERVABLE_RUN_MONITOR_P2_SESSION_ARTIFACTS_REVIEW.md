# Observable Run Monitor P2 Session Artifacts Review

Generated: 2026-05-11

## Verdict

FIX REQUIRED. The new `RunSession` primitive is small and mostly well-shaped, and its own path properties are under `.vibecode/runs/<session_id>/`. However, the implementation is not yet wired into the real `vibecode run` path. Current runs still write flat metadata at `.vibecode/runs/<session_id>.json`, post-check reports remain in `.vibecode/current/`, and the advertised prompt/context snapshots are only unit-tested helpers rather than normal run artifacts.

This review did not modify implementation or test files. The task scope allowed only this review document.

## Findings

### BLOCKER: `vibecode run` still writes flat run metadata outside the session directory

`_write_run_metadata()` still documents and writes `.vibecode/runs/<session_id>.json` (`vibecode/run.py:151`, `vibecode/run.py:180`). `cmd_run()` still calls that writer before writing the nested summary (`vibecode/run.py:653`, `vibecode/run.py:657`).

That violates the P2 requirement that paths live under `.vibecode/runs/<session_id>`, not scattered under `.vibecode/runs/`. Tests also preserve the old behavior by globbing for `.vibecode/runs/*.json` in run integration tests (`tests/test_vibecode_run.py:300`, `tests/test_vibecode_run.py:315`, `tests/test_vibecode_run.py:373`; `tests/test_vibecode_run_post.py:920`).

Recommended fix: route run metadata through the session directory, for example `.vibecode/runs/<session_id>/metadata.json`, and update tests to reject flat `.vibecode/runs/*.json` records.

### BLOCKER: The standard session artifact paths are not used by the run pipeline

`RunSession` defines paths for `events.jsonl`, `summary.json`, `opencode_prompt.md`, `context_pack.md`, guard reports, check reports, handoff reports, and agent stdout/stderr logs (`vibecode/session_log.py:72-118`). The real run path does not instantiate or use `RunSession`; `rg` finds `RunSession` only in `vibecode/session_log.py`, `.vibecode/handoff/NOW.md`, and `tests/test_vibecode_session_log.py`.

As a result:

- Guard results are still written through `write_guard_result(..., vibecode_dir, root)` to current/runtime output (`vibecode/run.py:322`).
- Check results are still written through `write_check_results(..., vibecode_dir)` (`vibecode/run.py:337`).
- Handoff validation is returned in memory but not written to `handoff_report.json` / `handoff_report.md`.
- Agent stdout/stderr are embedded in JSON summaries but are not written to `agent_stdout.log` / `agent_stderr.log`.
- `events.jsonl` is not created by normal runs.

Recommended fix: create a `RunSession(root, session_id)` at the start of `cmd_run()` and use its paths for all per-run artifacts while preserving existing `.vibecode/current/` outputs for backward compatibility.

### BLOCKER: Snapshot behavior is explicit at helper level, but not covered in normal run flow

The helper behavior is explicit: `snapshot_prompt()` copies `.vibecode/current/opencode_prompt.md` to `run_dir/opencode_prompt.md` (`vibecode/session_log.py:170-177`), and `snapshot_context_pack()` copies `.vibecode/current/context_pack.md` to `run_dir/context_pack.md` (`vibecode/session_log.py:179-187`).

The unit tests cover present and absent prompt/context files, including missing-source behavior and run-dir creation (`tests/test_vibecode_session_log.py:221-274`). They also cover missing destination parent directories through `test_snapshot_current_file_creates_dest_parents` (`tests/test_vibecode_session_log.py:202-211`).

What is missing is the normal snapshot flow: no run integration test proves that after `vibecode run`, `.vibecode/runs/<session_id>/context_pack.md` and `.vibecode/runs/<session_id>/opencode_prompt.md` exist and match the `.vibecode/current/` files produced for that run.

Recommended fix: add an end-to-end run test that asserts both current behavior and nested session snapshots are present after a fake OpenCode run.

### WARNING: Focused Ruff check fails on the new session-log test file

`python -m ruff check --no-cache vibecode\session_log.py tests\test_vibecode_session_log.py` fails:

- `tests/test_vibecode_session_log.py:10` imports `VibecodeEvent` but never uses it.

Broader Ruff on the run/session test set also reports pre-existing unused imports and unused local variables in `tests/test_vibecode_run.py` and `tests/test_vibecode_run_post.py`. The new session artifact test file should at least be lint-clean before this task is accepted.

### PASS: Existing `.vibecode/current/` behavior is preserved

The implementation is additive. `snapshot_prompt()` and `snapshot_context_pack()` copy from `.vibecode/current/` and do not delete or move those files (`vibecode/session_log.py:170-187`). Existing context and prompt generation still writes `.vibecode/current/context_pack.md` and `.vibecode/current/opencode_prompt.md` through the established context path (`vibecode/run.py:482-494`).

This satisfies backward compatibility, but it should coexist with nested per-run snapshots once the integration is completed.

### PASS: No brittle absolute paths in the session primitive

`RunSession` computes paths from `root / ".vibecode" / "runs" / session_id` and returns `pathlib.Path` objects (`vibecode/session_log.py:57`, `vibecode/session_log.py:72-118`). The tests assert `Path` return values and separate directories for different session IDs (`tests/test_vibecode_session_log.py:279-314`).

The implementation does not hard-code OS-specific absolute paths. A future hardening pass could validate `session_id` to prevent path traversal, but the current `cmd_run()` timestamp session IDs are safe.

### PASS: No accidental deletion of current/generated/runtime artifacts found

`vibecode/session_log.py` uses `mkdir()` and `shutil.copy2()` only; it does not call `unlink`, `remove`, `rmtree`, or cleanup routines. The run path also preserves the established current/generated writes. No deletion behavior was introduced by the session artifact primitive.

## Checks Run

- `python -m vibecode.cli context . --task "Review the session artifact implementation"`
  - Result: passed; wrote the task context pack to `.vibecode/current/context_pack.md`.
- `python -m vibecode.cli validate .`
  - Result: passed with the existing warning that `.vibecode/handoff/NOW.md` contains placeholder text.
- `python -m pytest tests/test_vibecode_session_log.py tests/test_vibecode_run.py tests/test_vibecode_run_post.py -p no:cacheprovider --basetemp C:\tmp\pytest-vibecode-session-artifacts`
  - Result: failed before a useful product signal because pytest could not create/access the sandbox temp directory (`PermissionError: C:\tmp\pytest-vibecode-session-artifacts`).
- `python -m pytest tests/test_vibecode_session_log.py tests/test_vibecode_run.py tests/test_vibecode_run_post.py -p no:cacheprovider --basetemp C:\Users\Martin\.codex\memories\pytest-vibecode-session-artifacts\basetemp`
  - Result: failed with sandbox temp-directory access errors during pytest setup/cleanup.
- `python -m pytest tests/test_vibecode_session_log.py -p no:cacheprovider --basetemp .\codex_pytest_tmp_session\basetemp`
  - Result: failed with sandbox temp-directory access errors during pytest setup/cleanup.
- `python -m ruff check --no-cache vibecode\session_log.py tests\test_vibecode_session_log.py`
  - Result: failed with the unused `VibecodeEvent` import listed above.
- `python -m ruff check --no-cache vibecode\session_log.py tests\test_vibecode_session_log.py vibecode\run.py tests\test_vibecode_run.py tests\test_vibecode_run_post.py`
  - Result: failed with unused imports / unused local variables in reviewed test files.
- `python -m vibecode.cli --help`
  - Result: passed.
- `python -m vibecode.cli index --help`
  - Result: passed.
- `python -m vibecode.cli context --help`
  - Result: passed.
- `python -m vibecode.cli check .`
  - Result: failed because the required `unit tests` command exited 1; CLI help, index help, and context help checks passed. The recorded pytest failure is the same environment issue: `PermissionError` under `C:\Users\Martin\AppData\Local\Temp\pytest-of-Martin`.
- `python -m vibecode.cli guard . --task "Review the session artifact implementation"`
  - Result: passed.

## Recommendation

Do not accept P2 session artifacts as complete yet. Keep the additive `RunSession` primitive, but wire it into `cmd_run()` so all per-run artifacts are created under `.vibecode/runs/<session_id>/`, leave `.vibecode/current/` compatibility outputs intact, add end-to-end snapshot assertions, and clean the focused Ruff failure.
