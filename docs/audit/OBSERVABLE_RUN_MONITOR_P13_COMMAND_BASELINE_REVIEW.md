# Observable Run Monitor P13 Command Baseline Review

## Verdict

**FIX REQUIRED / VALIDATION BLOCKED.**

The main P13.1 regression is fixed in code: default discovery now checks `shutil.which("opencode")`, not `shutil.which("opencode run")` (`vibecode/adapters/opencode.py:50`). Adapter tests also cover this directly (`tests/test_vibecode_opencode_adapter.py:211`).

I did not accept the implementation as fully validated because the requested independent-audit targeted subset could not be proven green in this environment. All tests using pytest `tmp_path` are blocked by local Windows temp/ACL behavior, and a patched pytest-temp run then failed in `git init` setup before product assertions.

## Findings

### Medium: quoted compound commands are not parsed safely

`check_opencode()` uses `resolved.split()` (`vibecode/adapters/opencode.py:73`). That works for `opencode run` and simple `python script.py`, but it breaks quoted Windows paths or quoted arguments, for example:

```text
OPENCODE_COMMAND="C:\Program Files\OpenCode\opencode.cmd" run
```

The binary becomes `"C:\Program`, so availability fails even though the configured command is valid for the shell runner. This is in scope for explicit `OPENCODE_COMMAND` and compound command parsing. Use a shell-aware parser or a small command-resolution object that preserves executable and arguments without ad hoc whitespace splitting.

### Low: compound-command availability can false-positive missing scripts

For a compound command such as `python missing_opencode.py`, `check_opencode()` verifies only that `python` exists, then returns available without checking the script path (`vibecode/adapters/opencode.py:73-130`). This avoids launching an agent session, which is correct, but it means missing wrapper/script errors move from preflight into agent execution. If explicit wrapper commands are a supported path, add a narrow existence check when the second token is a local script path.

## Pass Evidence

- Default command is still `opencode run` (`tests/test_vibecode_opencode_adapter.py:25`).
- Default resolution checks only the executable token (`vibecode/adapters/opencode.py:50`).
- The regression test asserts `shutil.which()` is never called with a string containing a space (`tests/test_vibecode_opencode_adapter.py:211-228`).
- Explicit `OPENCODE_COMMAND` wins before PATH lookup (`vibecode/adapters/opencode.py:46-48`; test at `tests/test_vibecode_opencode_adapter.py:230`).
- Availability checks use `--version`, not `opencode run`, for direct/default OpenCode checks (`vibecode/adapters/opencode.py:95-102`), so the check should not launch an agent session.
- Streaming stdout/stderr uses concurrent reader threads and preserves the process exit code (`vibecode/process_runner.py:80-198`).
- Run passes prompt content to stdin through `run_streaming(..., stdin_content=prompt_content, ...)` (`vibecode/run.py:790-800`).
- Prompt snapshot stdin equality is covered by `tests/test_vibecode_run_controller.py:1090-1110`, though it could not be executed to completion here due environment setup failures.
- Advisory/strict guard semantics are implemented in `RunSummary.overall_status` (`vibecode/run.py:120-135`) and covered by tests such as `tests/test_vibecode_run_post.py:1400-1412`.
- `.gitignore` ignores pytest temp/cache, root `tmp/`, and generated/runtime `.vibecode` paths (`.gitignore:5-9`, `.gitignore:42-59`).
- `git ls-files .pytest-tmp .pytest-local-check .check-tmp .vibecode/tmp .vibecode/runs .vibecode/current .vibecode/logs .vibecode/cache tmp` returned no tracked files.

## Validation Commands

- `python -m vibecode.cli context . --task "Review the P13.1 implementation"`
  - **PASS**. Wrote `.vibecode/current/context_pack.md`.
- `git status --short -uno`
  - **PASS** before validation: no tracked changes.
- `git ls-files .pytest-tmp .pytest-local-check .check-tmp .vibecode/tmp .vibecode/runs .vibecode/current .vibecode/logs .vibecode/cache`
  - **PASS**: no tracked temp/runtime files.
- `python -m pytest tests/test_vibecode_opencode_adapter.py -p no:cacheprovider`
  - **PASS**: `21 passed in 0.05s`.
- `python -m pytest tests/test_vibecode_opencode_adapter.py tests/test_vibecode_run_controller.py tests/test_vibecode_run.py::TestCmdRunEndToEnd tests/test_vibecode_run.py::TestCmdRunPreflight::test_safe_gitignore_allows_agent_launch -p no:cacheprovider --basetemp tmp\codex-p13-targeted`
  - **FAIL / ENVIRONMENT**: 21 adapter tests passed, 48 tests errored before product assertions; pytest could not access its base temp directory after creating it.
- In-process pytest run with `os.mkdir(..., 0o700)` patched to `0o777`, same targeted subset
  - **FAIL / ENVIRONMENT**: 23 tests passed, 45 setup errors and 1 failure. Failures occurred during temporary repo setup: `git init` failed with `could not lock config file .../.git/config: File exists`, before run-command assertions.
- `python -m compileall vibecode -q`
  - **PASS**.
- `python -m vibecode.cli --help`
  - **PASS**.
- `python -m vibecode.cli index --help`
  - **PASS**.
- `python -m vibecode.cli context --help`
  - **PASS**.
- `python -m vibecode.cli check .`
  - **FAIL**: required `unit tests` failed due pytest temp setup errors; CLI help checks passed.
- `python -m ruff check vibecode tests`
  - **FAIL**: 38 existing lint findings in tests, plus Ruff cache write warning.
- `git status --short -uno`
  - **PASS** after validation: no tracked changes.
- `git ls-files .pytest-tmp .pytest-local-check .check-tmp .vibecode/tmp .vibecode/runs .vibecode/current .vibecode/logs .vibecode/cache tmp`
  - **PASS** after validation: no tracked temp/runtime files.

## Independent-Audit Targeted Subset

The independent audit previously identified this targeted subset:

```text
python -m pytest tests/test_vibecode_opencode_adapter.py tests/test_vibecode_run_controller.py tests/test_vibecode_run.py::TestCmdRunEndToEnd tests/test_vibecode_run.py::TestCmdRunPreflight::test_safe_gitignore_allows_agent_launch -p no:cacheprovider
```

I cannot truthfully report that this subset now passes. The adapter portion passes, including the executable-vs-argument discovery regression, but the run-controller and fake-run cases are blocked by the local pytest temp/git setup failures above.

## Git Status And Temp Hygiene

Before validation, `git status --short -uno` was empty. After all validation attempts, `git status --short -uno` was still empty. That proves validation did not create tracked temp churn.

Full untracked status is not reliable in this workspace because Git warns that it cannot open `.codex_pytest_mcp_review/` due permission denial. The targeted tracked-file check is clean: no `.pytest-*`, root `tmp/`, or `.vibecode/current|runs|tmp|cache|logs` files are tracked.

## Review Scope Notes

- No implementation files were modified for this review.
- I did not update handoff files because the task explicitly constrained output to the review document.
- The implementation should not be accepted as fully proven until the targeted subset and `vibecode check` can run green in a clean temp environment.
