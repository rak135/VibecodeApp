# TUI Phase 2 P25 External Terminal Fixes

Date: 2026-05-16

## Source review

`docs/audit/TUI_PHASE2_P25_EXTERNAL_TERMINAL_REVIEW.md` — PASS WITH CORRECTIONS.

## Fixes applied

### MEDIUM: Implement missing cmd.exe launch branch

**Problem**: The adapter documentation and `detect_terminal()` both claimed a `cmd.exe` fallback
(`terminal_kind="cmd"`), but `launch()` had no `cmd` branch and unconditionally constructed a
PowerShell launch for everything that was not `"windows-terminal"`.

**Fix** (`vibecode/adapters/external_terminal.py`):

- Added `build_opencode_cmd_command()` — builds a cmd.exe command string using `&` separators,
  `set` for env vars, `cd /d` for directory change, and `echo` for the startup banner.
- Added `_quote_cmd()` helper for minimal cmd quoting (doubles embedded `"` as `""`).
- Added `elif terminal == "cmd":` branch in `launch()` that uses `["cmd.exe", "/K", cmd_string]`
  instead of calling `_find_ps()`.
- Restructured `shell_cmd` construction to happen inside each branch to avoid building
  PowerShell syntax for the cmd path.

**Tests** (`tests/test_vibecode_external_terminal.py`):

- Added `TestWindowsTerminalAdapterCmdFallback` (10 tests) covering:
  - `terminal_kind` is `"cmd"`
  - `launched=True` on success
  - Popen args start with `cmd.exe` (not PowerShell)
  - `/K` flag present
  - `cd /d` in command
  - Prompt path and profile passed through
  - PID returned
  - `command` display field populated

- Added `TestBuildOpencodeCmdCommand` (10 tests) covering:
  - Contains opencode command, prompt path, `cd /d`, `&` separator
  - No PowerShell syntax (`$env`, `Set-Location`)
  - Profile/session env vars
  - Banner lines
  - Paths with spaces

### LOW: Add [E] action/callback path tests

**Problem**: `action_cmd_external()`, `_start_external()`, `_on_external_task_received()`,
`_on_external_done()`, and `_on_external_error()` had no direct test coverage.

**Fix** (`tests/test_vibecode_external_terminal.py`):

- Added `TestExternalActionCallbacks` (15 tests) covering:
  - DI: external service default/None, injection, idempotent getter
  - `action_cmd_external()`: pushes input screen when no task, skips when task set
  - Thread start with `tui-external` name when task is set
  - Task received: sets current task, starts thread, cancel clears pending profile
  - `_on_external_done()`: success and failure log paths
  - `_on_external_error()`: logs error, does not raise

## Verification

```
python -m compileall vibecode -q            — PASS
python -m pytest -q tests/test_vibecode_external_terminal.py
                                            — 100 passed in 0.52s
python -m pytest -q tests/test_vibecode_external_terminal.py tests/test_vibecode_main_tui.py tests/test_vibecode_run_action_tui.py
                                            — 336 passed in 16.97s
python -m pytest -p no:cacheprovider -q      — 2339 passed, 35 warnings
git status --short                          — only test and adapter file changed
```

## Changed files

- `vibecode/adapters/external_terminal.py` — added `build_opencode_cmd_command()`,
  `_quote_cmd()`, cmd launch branch
- `tests/test_vibecode_external_terminal.py` — added cmd fallback tests,
  cmd command builder tests, `[E]` action/callback tests
