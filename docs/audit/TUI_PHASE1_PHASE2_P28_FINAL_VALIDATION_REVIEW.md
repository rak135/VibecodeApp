# TUI Phase 1+2 P28 Final Validation Review

**Date:** 2026-05-16  
**Scope reviewed:** `docs/PRD_TUI_PHASE1_PHASE2_VALIDATION.md` plus current code/tests/artifacts referenced by that report.

## Verdict

**PASS WITH CORRECTIONS.**

The P28.1 validation report is materially credible: the central readiness posture (**partially ready with one blocker**) is still accurate in the current tree. Fresh evidence confirms broad test health, targeted TUI coverage, refresh preservation behavior, fake OpenCode coverage, and external-terminal mocking safety.  
The blocker remains handoff hygiene (`NOW.md` placeholder text), exactly as the report states.

## Required evidence checks

| Requirement | Status | Evidence |
|---|---:|---|
| Exact/summarized command outputs included | PASS | This review records fresh command outputs below (pytest slices, full pytest, guard/check/handoff/validate, compile, git status). |
| Full or broadest practical pytest ran | PASS | `python -m pytest -p no:cacheprovider -q` → `2396 passed, 35 warnings in 377.57s (0:06:17)`. |
| Targeted TUI tests pass | PASS | `python -m pytest -p no:cacheprovider -q tests/test_vibecode_main_tui.py tests/test_vibecode_run_action_tui.py tests/test_vibecode_context_tui.py tests/test_vibecode_debug_cockpit.py` → `313 passed in 59.74s`. |
| Refresh preserves manual truth files | PASS | `tests/test_vibecode_refresh.py` includes direct byte-for-byte assertions (`test_refresh_preserves_customized_manual_files_byte_for_byte`, lines 118-137). Fresh run: `24 passed in 8.52s`; focused run: `3 passed, 21 deselected in 1.71s`. |
| Refresh does not delete logs/runs | PASS | `tests/test_vibecode_refresh.py` (`test_refresh_does_not_delete_logs`, `test_refresh_does_not_delete_runs`, lines 223-252) assert files remain after refresh. Verified in focused run above. |
| Context generation works from TUI/service path | PASS | `tests/test_vibecode_context_tui.py` (`test_run_calls_write_context_pack`, lines 238-281) and `tests/test_vibecode_external_terminal.py` (`test_adapter_receives_prompt_path`, lines 667-688; context generation wiring at lines 635-679). Fresh focused run: `3 passed, 168 deselected in 0.32s`. |
| Fake OpenCode audit/safe run works | PASS | `tests/test_vibecode_run.py` (`test_run_succeeds_with_fake_opencode`, `test_safe_gitignore_allows_agent_launch`, lines 292-307 and 546-577) + `tests/test_vibecode_run_controller.py` (`test_fake_opencode_orchestration_writes_artifacts_and_preserves_advisory_guard`, lines 465-542). Fresh focused run: `3 passed, 93 deselected in 6.95s`. |
| External terminal adapter tested without real terminals in CI | PASS | Test module docstring explicitly states mocking/no real terminal launch (`tests/test_vibecode_external_terminal.py`, lines 19-20). Behavioral guard test `test_adapter_launch_does_not_call_opencode` (lines 852-873) passed. Focused run: `2 passed, 98 deselected in 0.25s`; full file also passed (`100 passed in 8.67s`). |
| Honest status of real Windows Terminal/OpenCode smoke | PASS (as skipped) | No new live smoke was executed in this non-interactive session. The P28.1 report marks both live TUI and real OpenCode smoke as skipped with rationale; that remains accurate. |
| Final `git status --short` clean/unrelated dirt documented | PASS | Before writing this review, `git --no-pager status --short` returned no entries (clean). After writing, expected dirt is this review file only. |

## Additional validation findings

1. **Hidden failures check:**  
   - `python -m vibecode.cli guard .` → `Guard check passed. No violations found.`  
   - `python -m vibecode.cli handoff-check .` → fails on `.vibecode/handoff/NOW.md` placeholder text (`handoff_exit=1`).  
   - `python -m vibecode.cli validate .` → warning for same placeholder text (`validate_exit=0`).  
   - `python -m vibecode.cli check .` → all required checks pass, including `unit tests` (`check_exit=0`, unit tests duration `379.109s`).
2. **Referenced artifacts exist and are current:**  
   - `.vibecode/current/check_results.json` present and records `2396` collected/passing tests and required-check PASS states.  
   - `.vibecode/current/validation.json` present with `status: "ok"` and one warning on `NOW.md`.  
   - `.vibecode/index/file_inventory.json`, `symbol_map.json`, `dependency_map.json`, `test_map.json` all present.
3. **Report metadata drift:**  
   - P28.1 report records `HEAD: d70f746`.  
   - Current HEAD during this review is `bdedd65` (`master`).  
   This does not invalidate the report’s main conclusion, but it should be treated as commit-pinned evidence rather than current-HEAD evidence.

## Commands run (fresh)

```text
python -m pytest -p no:cacheprovider -q tests/test_vibecode_main_tui.py tests/test_vibecode_run_action_tui.py tests/test_vibecode_context_tui.py tests/test_vibecode_debug_cockpit.py
python -m pytest -p no:cacheprovider -q tests/test_vibecode_refresh.py
python -m pytest -p no:cacheprovider -q tests/test_vibecode_external_terminal.py
python -m pytest -p no:cacheprovider -q tests/test_vibecode_context_pack.py tests/test_vibecode_mcp_server.py
python -m pytest -p no:cacheprovider -q
python -m pytest -p no:cacheprovider -q tests/test_vibecode_context_tui.py tests/test_vibecode_external_terminal.py -k "run_calls_write_context_pack or adapter_receives_prompt_path or error_when_context_generation_fails"
python -m pytest -p no:cacheprovider -q tests/test_vibecode_external_terminal.py -k "adapter_launch_does_not_call_opencode or windows_terminal_detected_first"
python -m pytest -p no:cacheprovider -q tests/test_vibecode_refresh.py -k "preserves_customized_manual_files_byte_for_byte or does_not_delete_logs or does_not_delete_runs"
python -m pytest -p no:cacheprovider -q tests/test_vibecode_run.py tests/test_vibecode_run_controller.py -k "run_succeeds_with_fake_opencode or safe_gitignore_allows_agent_launch or fake_opencode_orchestration_writes_artifacts_and_preserves_advisory_guard"
python -m vibecode.cli guard .
python -m vibecode.cli handoff-check .
python -m vibecode.cli validate .
python -m vibecode.cli check .
python -m compileall vibecode -q
git --no-pager rev-parse --short HEAD
git --no-pager branch --show-current
git --no-pager status --short
```

## Final assessment

The P28.1 report’s **readiness framing is correct**: core Phase 1+2 surfaces are validated, and the **single blocker remains handoff placeholder cleanup**. The only correction needed in the report itself is explicit awareness that its recorded HEAD (`d70f746`) is not the current HEAD (`bdedd65`) at review time.
