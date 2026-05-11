# Observable Run Monitor P7 Prompt Context Review

Generated: 2026-05-12

## Verdict

PASS WITH TEST HARDENING RECOMMENDED. The prompt/context snapshot behavior is wired into the observable run path and preserves per-run artifacts under `.vibecode/runs/<session_id>/` while leaving existing `.vibecode/current/` context generation intact. Events point to those per-run snapshot files and carry bounded metadata instead of raw prompt/context bodies.

This review did not modify implementation or test files. The task scope allowed only this review document.

## Findings

### PASS: per-run prompt and context snapshots are preserved

`RunSession` defines stable per-run artifact paths for `opencode_prompt.md` and `context_pack.md` under `.vibecode/runs/<session_id>/` (`vibecode/session_log.py:80-87`). Its snapshot helpers copy the current prompt/context files into those run-specific paths without moving or deleting `.vibecode/current/` (`vibecode/session_log.py:135-187`).

`RunController.execute()` calls `session.snapshot_context_pack()` and `session.snapshot_prompt()` immediately after successful context generation and before emitting the written events (`vibecode/run.py:661-678`). The prompt passed to OpenCode is then read from the generated prompt path, falling back to the context pack only when no platform prompt exists, and is sent on stdin through `run_streaming()` (`vibecode/run.py:739-786`).

Note: for maximum exactness under hypothetical concurrent runs, the controller could read agent stdin from the just-written snapshot path after snapshotting. The current implementation is exact for the normal serial run path because there is no intervening write between snapshot and prompt read.

### PASS: events point to snapshot files, not only current files

The `run.context` written event includes both `path` and `snapshot_path`, with `snapshot_path` set to the run directory copy when snapshotting succeeds (`vibecode/run.py:666-675`). The `run.prompt` written event does the same for the platform prompt (`vibecode/run.py:678-686`).

The tests assert that context and prompt snapshot paths are present, include the session id, live under `.vibecode/runs/<session_id>/`, and are session-specific across two runs (`tests/test_vibecode_run_controller.py:711-764`, `tests/test_vibecode_run_controller.py:843-946`).

### PASS: event payloads avoid giant prompt/context bodies

The context event carries bounded metadata: `snapshot_path`, `size_bytes`, a 200-character `task_summary`, and the list of `##` section headings (`vibecode/run.py:666-675`). The prompt event carries `snapshot_path`, `size_bytes`, `platform`, and `profile` (`vibecode/run.py:678-686`). Neither event embeds the prompt body or full context pack content.

The existing tests cover the bounded fields, including task-summary truncation and section extraction (`tests/test_vibecode_run_controller.py:766-841`). Recommended hardening: add an explicit regression test that serializes `run.context` and `run.prompt` event data and asserts raw prompt/context body text is absent.

### PASS: existing context generation behavior is preserved

`cmd_context()` still writes the context pack through `write_context_pack()` to `.vibecode/current/context_pack.md`, and platform export still writes `.vibecode/current/opencode_prompt.md` from that generated pack (`vibecode/context/__init__.py:12-68`, `vibecode/context/platform_export.py:27-48`). The session layer is additive: it snapshots from current files into the run directory and does not replace the existing current-file workflow.

The end-to-end run test explicitly asserts the current files still exist and that the run snapshots match them after a successful run (`tests/test_vibecode_run.py:381-407`).

### PASS WITH NOTE: tests prove per-run snapshot behavior

Coverage exists at three levels:

- `RunSession` unit tests prove prompt/context snapshot helpers copy from `.vibecode/current/` and create the run directory (`tests/test_vibecode_session_log.py:220-274`).
- `RunController` tests prove context and prompt events include session-specific snapshot paths and metadata (`tests/test_vibecode_run_controller.py:711-946`).
- CLI run coverage proves a real `vibecode run` leaves both current files and per-run snapshot files, with matching content (`tests/test_vibecode_run.py:381-407`).

Recommended hardening: add one fake-OpenCode test that records stdin and asserts it exactly equals the prompt snapshot content. Current code inspection supports that behavior for serial runs, but a direct test would make the "exact prompt used" guarantee stronger.

## Checks Run

- `python -m vibecode.cli context . --task "Review prompt/context snapshot behavior"`
  - Result: passed; wrote `.vibecode/current/context_pack.md`.
- `python -m pytest tests/test_vibecode_session_log.py tests/test_vibecode_run_controller.py::TestContextAndPromptSnapshotEvents tests/test_vibecode_run.py::TestCmdRunHappyPath::test_run_snapshots_prompt_and_context_pack -p no:cacheprovider --basetemp C:\tmp\vibecode-p7-prompt-context`
  - Result: failed during collection because the selected `TestCmdRunHappyPath` class does not exist.
- `python -m pytest tests/test_vibecode_session_log.py tests/test_vibecode_run_controller.py::TestContextAndPromptSnapshotEvents -p no:cacheprovider --basetemp C:\tmp\vibecode-p7-prompt-context`
  - Result: failed before test bodies with `PermissionError: C:\tmp\vibecode-p7-prompt-context`.
- `python -m pytest tests/test_vibecode_session_log.py tests/test_vibecode_run_controller.py::TestContextAndPromptSnapshotEvents tests/test_vibecode_run.py::TestCmdRunEndToEnd::test_run_snapshots_prompt_and_context_pack -p no:cacheprovider --basetemp .\codex_pytest_p7_prompt_context`
  - Result: failed before test bodies with `PermissionError: C:\DATA\PROJECTS\VibecodeApp\codex_pytest_p7_prompt_context`.
- `python -m pytest tests/test_vibecode_session_log.py::test_run_dir_path -q`
  - Result: failed before the test body with `PermissionError: C:\Users\Martin\AppData\Local\Temp\pytest-of-Martin`.
- `python -m pytest tests/test_vibecode_session_log.py::test_run_dir_path -q -p no:cacheprovider --basetemp C:\Users\Martin\.codex\memories\vibecode-p7-pytest`
  - Result: failed during pytest session cleanup with `PermissionError: C:\Users\Martin\.codex\memories\vibecode-p7-pytest`.
- `python -m ruff check --no-cache vibecode\run.py vibecode\session_log.py tests\test_vibecode_run_controller.py tests\test_vibecode_run.py tests\test_vibecode_session_log.py`
  - Result: failed due existing unused imports in `tests/test_vibecode_run.py` (`stat`, `cmd_run`, `RunSummary`, `_write_run_summary`).
- `python -m vibecode.cli --help`
  - Result: passed.
- `python -m vibecode.cli validate .`
  - Result: passed with warning: `.vibecode/handoff/NOW.md` contains placeholder text.
- `python -m vibecode.cli guard .`
  - Result: passed; no violations found.
- `python -m vibecode.cli handoff-check .`
  - Result: failed on existing `.vibecode/handoff/NOW.md` placeholder-text issue.
- `python -m vibecode.cli index --help`
  - Result: passed.
- `python -m vibecode.cli context --help`
  - Result: passed.
- `python -m vibecode.cli check .`
  - Result: failed because required `unit tests` exited 1 after 161.453s; required CLI help, index help, and context help checks passed.

## Changed Files

- `docs/audit/OBSERVABLE_RUN_MONITOR_P7_PROMPT_CONTEXT_REVIEW.md`
