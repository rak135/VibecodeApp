# Observable Run Monitor P4 Streaming Agent Review

Generated: 2026-05-11

## Verdict

PASS WITH NOTES. The streaming process implementation replaces batch `subprocess.run(..., capture_output=True)` agent execution with `subprocess.Popen` plus separate stdout/stderr reader threads. That design addresses the Windows pipe-deadlock risk, preserves the child process exit code for normal completion, emits per-line output events, and writes accumulated stdout/stderr to per-run log artifacts.

This review did not modify implementation or test files. The task scope allowed only this review document.

## Findings

### PASS: stdout/stderr deadlock risk is addressed

`run_streaming()` starts one reader thread for stdout and one reader thread for stderr immediately after process launch (`vibecode/process_runner.py:128-144`). Each thread drains its pipe independently through `_read_stream()` (`vibecode/process_runner.py:32-59`) while the main thread waits on the process (`vibecode/process_runner.py:146-155`).

That avoids the classic deadlock shape where one pipe fills while the parent waits for process completion or drains only the other stream.

### PASS: Windows compatibility was considered

The runner keeps `shell=True` because the configured OpenCode command may be a Windows `.cmd`/`.bat` wrapper or a local compound command (`vibecode/run.py:726-734`). Paths are passed through `pathlib.Path` and `cwd=str(cwd)` (`vibecode/process_runner.py:105-115`), and the tests create Windows-style fake `opencode.cmd` wrappers rather than requiring a POSIX executable (`tests/test_vibecode_run_controller.py:136-162`).

This is stream capture, not terminal emulation, so using pipes is appropriate for the current scope.

### PASS: exit code truth is preserved

For normal process completion, `run_streaming()` returns `proc.returncode` directly in `ProcessResult.exit_code` (`vibecode/process_runner.py:167-176`). `RunController.execute()` assigns that value to the run's `exit_code` and emits it in the finished agent event (`vibecode/run.py:734-758`).

Timeouts are explicitly represented as `exit_code=-1` (`vibecode/process_runner.py:164-167`), which is a synthetic controller result rather than a hidden success.

### PASS: output is emitted as events and saved as logs

Each stdout/stderr line is appended to the accumulated stream and emitted as `run.agent_process` with `data["phase"]` set to `"stdout"` or `"stderr"` (`vibecode/process_runner.py:46-56`). After process completion, the full accumulated streams are written to `stdout_log` and `stderr_log` when paths are provided (`vibecode/process_runner.py:169-174`).

`RunController` passes the session's `agent_stdout.log` and `agent_stderr.log` paths into `run_streaming()` (`vibecode/run.py:734-742`). It also creates an `events.jsonl` sink for every run and wraps any injected sink with it, so normal CLI runs persist events while tests can still inspect an in-memory sink (`vibecode/run.py:452-459`).

### PASS: tests do not depend on real OpenCode

The process-runner tests execute temporary Python scripts through `sys.executable` (`tests/test_vibecode_process_runner.py:26-33`). The run-controller tests install a fake `opencode.cmd` on `PATH` and use that wrapper for agent execution (`tests/test_vibecode_run_controller.py:136-194`).

I did not find test coverage that requires a real OpenCode installation.

### PASS: implementation does not claim full interactive terminal support

`vibecode/process_runner.py` explicitly describes the feature as a streaming-output MVP that reads line-by-line in text mode, with PTY/ConPTY support out of scope (`vibecode/process_runner.py:1-10`). The run-site comment also describes the behavior as pipe draining and live event emission, not an interactive terminal (`vibecode/run.py:731-733`).

### NOTE: focused lint currently fails in the streaming test file

`python -m ruff check --no-cache vibecode\process_runner.py vibecode\run.py tests\test_vibecode_process_runner.py tests\test_vibecode_run_controller.py` reports one issue: `tests/test_vibecode_process_runner.py:15` imports `pytest` but does not use it.

That is not a streaming behavior defect, but it prevents the reviewed files from being lint-clean.

### NOTE: test execution is blocked by local temp-directory permissions

Focused pytest runs failed during setup/cleanup with Windows `PermissionError` on pytest base temp directories, before meaningful product assertions could run. The one test that does not need `tmp_path` passed before fixture setup errors began.

The failure appears environmental, but it means I could not independently confirm the full focused test suite in this session.

## Checks Run

- `python -m vibecode.cli context . --task "Review the streaming process implementation"`
  - Result: passed; wrote the task context pack to `.vibecode/current/context_pack.md`.
- `python -m pytest tests/test_vibecode_process_runner.py tests/test_vibecode_run_controller.py -p no:cacheprovider --basetemp .\codex_pytest_p4_streaming_tmp`
  - Result: failed during pytest temp-directory cleanup with `PermissionError` on `C:\DATA\PROJECTS\VibecodeApp\codex_pytest_p4_streaming_tmp`.
- `python -m pytest tests/test_vibecode_process_runner.py -p no:cacheprovider --basetemp C:\tmp\pytest-vibecode-p4-streaming-process --tb=short`
  - Result: failed at `tmp_path` fixture setup with `PermissionError` creating `C:\tmp\pytest-vibecode-p4-streaming-process`; 1 test passed, 21 errored.
- `python -m ruff check --no-cache vibecode\process_runner.py vibecode\run.py tests\test_vibecode_process_runner.py tests\test_vibecode_run_controller.py`
  - Result: failed with one lint issue: unused `pytest` import in `tests/test_vibecode_process_runner.py:15`.
- `python -m vibecode.cli --help`
  - Result: passed.
- `python -m vibecode.cli index --help`
  - Result: passed.
- `python -m vibecode.cli context --help`
  - Result: passed.
- `python -m vibecode.cli check .`
  - Result: failed because the required `python -m pytest` check exited 1; CLI help, index help, and context help checks passed.
- `python -m vibecode.cli guard .`
  - Result: passed; no guard violations found.
- `python -m vibecode.cli handoff-check .`
  - Result: failed on an existing `.vibecode/handoff/NOW.md` placeholder-text issue.
