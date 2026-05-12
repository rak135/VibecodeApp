# P13 Command Baseline Fix Summary

## Fix Applied

### 1. Quoted compound command parsing (Medium)

**File:** `vibecode/adapters/opencode.py:80`

Replaced `str.split()` with `shlex.split(resolved, posix=(os.name != "nt"))` so that quoted Windows paths (e.g. `"C:\Program Files\OpenCode\opencode.cmd" run`) are parsed safely without the binary token being truncated at the first space inside quotes.

- On Windows, `posix=False` prevents backslashes from being treated as escape characters.
- On POSIX, `posix=True` (default) preserves standard shell semantics.
- `ValueError` on malformed quoting returns an `OpenCodeStatus` with `available=False` and a descriptive parse-failure message.

### 2. Missing wrapper script detection (Low)

**File:** `vibecode/adapters/opencode.py:150-161`

For compound commands where the first extra arg looks like a local path (contains `/`, `\`, or starts with `.`), an `os.path.exists()` check verifies the script exists. Missing scripts now fail early during the availability check rather than during agent execution.

- Non-path-like args (e.g. module names for `python -m`) skip the existence check.

### 3. `.gitignore` hygiene (Low)

**File:** `.gitignore:9`

Added `.codex_pytest_mcp_review/` to the ignored pytest temp directories.

## Tests Added

**File:** `tests/test_vibecode_opencode_adapter.py`

New test class `TestCompoundCommandParsing` with 5 tests:
- `test_quoted_windows_path_parsed_correctly` — quoted path with spaces preserves binary token
- `test_missing_local_script_detected` — `./missing_opencode.py` fails availability
- `test_non_pathlike_arg_skips_existence_check` — `python some_module` skips path check
- `test_missing_absolute_script_detected` — absolute missing path fails
- `test_malformed_quoting_returns_unavailable` — unterminated quote produces safe error

## Verification

```
python -m compileall vibecode -q                  # PASS
python -m pytest -q tests/test_vibecode_opencode_adapter.py                     # 26 passed
python -m pytest -q tests/test_vibecode_opencode_adapter.py tests/test_vibecode_run_controller.py tests/test_vibecode_run.py::TestCmdRunEndToEnd tests/test_vibecode_run.py::TestCmdRunPreflight::test_safe_gitignore_allows_agent_launch  # 74 passed
python -m pytest -q                                                             # 1769 passed, 0 failures
git ls-files .pytest-tmp .pytest-local-check .check-tmp .vibecode/tmp .vibecode/runs .vibecode/current .vibecode/logs .vibecode/cache tmp .codex_pytest_mcp_review  # no tracked files
```

## Changed Files

- `vibecode/adapters/opencode.py` — shlex.split + script existence check
- `tests/test_vibecode_opencode_adapter.py` — 5 new tests
- `.gitignore` — added `.codex_pytest_mcp_review/`
