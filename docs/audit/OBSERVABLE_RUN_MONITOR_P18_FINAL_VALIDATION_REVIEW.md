# Observable Run Monitor P18.1 Final Validation Review

Date: 2026-05-13
Scope: review `docs/PRD_OBSERVABLE_RUN_MONITOR_FOLLOWUP_VALIDATION.md`, current code/tests where needed, CLI help, and available run artifacts.

## Verdict

CONDITIONAL PASS.

The validation report is broadly credible for supervised dogfooding readiness, but I cannot independently reproduce the full targeted/full pytest evidence in the current workspace because pytest temp-root setup now fails with Windows `PermissionError`. The report's readiness claim should be treated as supported by its captured output plus current code/test structure, not by a clean fresh rerun from this review session.

No implementation files were modified.

## Key Findings

1. Targeted fake OpenCode regression coverage is real, not just parser registration.
   - `tests/test_vibecode_run_controller.py` contains `test_fake_opencode_orchestration_writes_artifacts_and_preserves_advisory_guard`, which creates `opencode.cmd`, captures argv/stdin, asserts `["run"]`, checks fake stdout/stderr logs, prompt/context snapshots, `summary.json`, and lifecycle event phases.
   - `tests/test_vibecode_run.py::TestCmdRunEndToEnd` also uses fake OpenCode and exercises CLI `run` outcomes.
   - Fresh full targeted rerun was blocked by environment, not by a Vibecode assertion:
     ```
     python -m pytest -p no:cacheprovider -q tests/test_vibecode_opencode_adapter.py tests/test_vibecode_run_controller.py "tests/test_vibecode_run.py::TestCmdRunEndToEnd" "tests/test_vibecode_run.py::TestCmdRunPreflight::test_safe_gitignore_allows_agent_launch"
     -> 26 passed, 69 errors
     -> repeated setup error: PermissionError: [WinError 5] Access denied: C:\Users\Martin\AppData\Local\Temp\pytest-of-Martin
     ```
   - A focused non-temp target passes:
     ```
     python -m pytest -p no:cacheprovider -q tests/test_vibecode_opencode_adapter.py
     26 passed in 0.06s
     ```

2. Successful run artifacts are replayable.
   - Available artifact sample: `.vibecode/runs/20260512T051751673320Z/`.
   - Replay command:
     ```
     python -m vibecode.cli runs show 20260512T051751673320Z --repo . --events
     ```
   - Evidence: output lists 11 artifacts, including `summary.json`, `metadata.json`, `events.jsonl`, guard/check/handoff JSON reports, agent stdout/stderr logs, `context_pack.md`, and `opencode_prompt.md`.
   - Replay loaded 22 events, including:
     ```
     Run started
     Git preflight started/completed
     Index check started/completed
     Context pack written
     Prompt written
     Agent started: opencode run
     VIBECODE_REAL_OPENCODE_SMOKE_OK
     Agent finished (exit_code=0)
     Guard completed
     Checks completed
     Handoff completed
     Run summary written
     Run finished: incomplete
     ```
   - Note: this is a real OpenCode smoke artifact, not the fake-run temp artifact described in the validation report. It still proves replayability for a completed agent launch.

3. Early-failure replay is evidenced by the validation report, but not independently reproduced here.
   - The report includes a no-index early abort with `events.jsonl`, `summary.json`, and `runs show <session_id> --events` replaying six events through `Run aborted: no index`.
   - Current code has early-abort tests in `TestEarlyAbortArtifacts` and `TestEarlyAbortShowCLI`, but a fresh run of `tests/test_vibecode_run_controller.py` is blocked by the same pytest temp-root permission failure.
   - Review status: accepted from report output plus test presence, not freshly reproduced.

4. Monitor smoke is more than parser registration.
   - Focused event-pump and MCP formatting smoke passed:
     ```
     python -m pytest -p no:cacheprovider -q tests/test_vibecode_monitor.py::TestMonitorEventPumpSmoke tests/test_vibecode_monitor.py::TestMcpEventFormatting
     27 passed in 0.25s
     ```
   - Full monitor suite did not complete in this environment:
     ```
     python -m pytest -p no:cacheprovider -q tests/test_vibecode_monitor.py
     78 passed, 10 errors
     ```
   - The 10 errors are all pytest `tmp_path` setup failures from `C:\Users\Martin\AppData\Local\Temp\pytest-of-Martin`, not monitor assertions.
   - Real TUI smoke remains honestly skipped; the validation report's reason is acceptable: it needs `[tui]` and an interactive terminal.

5. Advisory and strict guard behavior is freshly verified.
   ```
   python -m pytest -p no:cacheprovider -q tests/test_vibecode_run_post.py::TestAdvisoryGuardMode
   9 passed in 0.10s
   ```
   This covers advisory non-blocking behavior and strict-mode non-zero failures.

6. MCP/session correlation is plausible in code/tests, but full fresh test proof is blocked here.
   - Code check: `RunController.execute()` sets `VIBECODE_SESSION_ID` and `VIBECODE_MCP_EVENTS_LOG` in the child environment; `cmd_serve()` reads `VIBECODE_MCP_EVENTS_LOG` first and falls back to `.vibecode/logs/mcp_events.jsonl`.
   - Test check: `TestMcpEnvPropagation` fake OpenCode captures both env vars; `tests/test_vibecode_mcp_server.py` covers log path/session id behavior.
   - Fresh command blocked:
     ```
     python -m pytest -p no:cacheprovider -q tests/test_vibecode_mcp_server.py -k "env"
     5 errors, all pytest tmp_path setup PermissionError
     ```

7. CLI discovery claims are current.
   - `python -m vibecode.cli --help` lists `init`, `inventory`, `index`, `context`, `map`, `validate`, `guard`, `check`, `handoff-check`, `run`, `run-plan`, `history`, `project`, `serve`, `dashboard`, `monitor`, `export-agents`, `runs`.
   - `python -m vibecode.cli run --help` shows `--guard-mode {advisory,strict}`.
   - `python -m vibecode.cli monitor --help` states split-pane TUI and streaming-output, not PTY.
   - `python -m vibecode.cli runs show --help` shows `--events`.
   - `python -m vibecode.cli serve --help` documents `VIBECODE_MCP_EVENTS_LOG`, `VIBECODE_SESSION_ID`, and the OpenCode MCP snippet.

8. Required checks did not pass during this review because pytest temp setup is broken.
   ```
   python -m vibecode.cli check
   FAIL: unit tests (exit code 1, 191.359s)
   PASS: cli help
   PASS: index command help
   PASS: context command help
   ```
   `.vibecode/current/check_results.json` shows 1850 collected tests and widespread setup errors rooted in:
   ```
   PermissionError: [WinError 5] Access denied: C:\Users\Martin\AppData\Local\Temp\pytest-of-Martin
   ```
   Collection itself works:
   ```
   python -m pytest --collect-only -q
   1850 tests collected in 0.63s
   ```

9. Compile and lint evidence.
   ```
   python -m compileall vibecode -q
   exit code 0, no output
   ```
   ```
   python -m ruff check vibecode
   All checks passed!
   warning: Failed to write cache file ... .ruff_cache ... Access denied
   ```
   Full `ruff check vibecode tests` fails with 43 pre-existing test lint findings, so source lint is clean but repository-wide lint is not currently clean.

10. Real OpenCode smoke status is mixed.
   - The validation report says real OpenCode was installed but skipped for cost/safety. That is an honest skip reason.
   - Available run artifacts also show a prior real OpenCode smoke run with `VIBECODE_REAL_OPENCODE_SMOKE_OK` and replayable events. This strengthens replayability evidence, but it is separate from the validation report's stated skip.

## Git Status Evidence

Final status is not clean.

Command:
```
git status --short
```

Output visible in this environment:
```
?? docs/audit/OBSERVABLE_RUN_MONITOR_P18_FINAL_VALIDATION_REVIEW.md
warning: could not open directory '.pytest-tmp-p16-review/target-cli/': Permission denied
warning: could not open directory '.pytest-tmp-p16-review/target-dashboard/': Permission denied
warning: could not open directory '.pytest-tmp-p16-review/target-monitor/': Permission denied
warning: could not open directory '.pytest-tmp-p17-docs-review-fresh-001/': Permission denied
warning: could not open directory '.pytest-vibecode-p181-targeted-local/': Permission denied
warning: could not open directory 'pytest-tmp-p15-focused/': Permission denied
warning: could not open directory 'pytest_tmp_p17_docs_review_fresh_002/': Permission denied
warning: could not open directory 'pytest_tmp_p17_docs_review_fresh_003/': Permission denied
warning: could not open directory 'pytest_tmp_p17_docs_review_fresh_004/': Permission denied
```

Remaining dirt:
- Expected from this task: `docs/audit/OBSERVABLE_RUN_MONITOR_P18_FINAL_VALIDATION_REVIEW.md` is untracked.
- `docs/PRD_OBSERVABLE_RUN_MONITOR_FOLLOWUP_VALIDATION.md` exists and is tracked.
- Unexpected review-attempt artifact: `.pytest-vibecode-p181-targeted-local/` was created by a failed pytest `--basetemp` attempt and is inaccessible to this process. Removal was attempted but blocked by the command policy/permissions.
- Other inaccessible pytest temp directories appear pre-existing and unrelated to this review.

## Recommendation

Keep the P18.1 readiness verdict as "ready for supervised dogfooding with limitations", but do not present the current workspace as clean or freshly fully verified. Before final handoff, clear or fix the inaccessible pytest temp/cache directories and rerun:

```
python -m pytest -p no:cacheprovider -q tests/test_vibecode_opencode_adapter.py tests/test_vibecode_run_controller.py "tests/test_vibecode_run.py::TestCmdRunEndToEnd" "tests/test_vibecode_run.py::TestCmdRunPreflight::test_safe_gitignore_allows_agent_launch"
python -m pytest -p no:cacheprovider -q tests/test_vibecode_monitor.py
python -m pytest -p no:cacheprovider -q tests/test_vibecode_mcp_server.py
python -m vibecode.cli check
git status --short
```
