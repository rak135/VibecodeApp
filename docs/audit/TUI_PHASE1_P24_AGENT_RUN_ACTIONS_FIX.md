# TUI Phase 1 P24 Agent Run Actions Fix Report

Generated: 2026-05-16

## Review source

`docs/audit/TUI_PHASE1_P24_AGENT_RUN_ACTIONS_REVIEW.md`

## Fixes applied

### MEDIUM: AgentRunService failure detail accuracy

**Problem**: `AgentRunService.run()` stored the wrapper exit code (0/1/2 from `_exit_code_for_status`) instead of the raw agent exit code from `RunSummary.exit_code`. For early aborts, it always used a generic fallback error message regardless of the specific reason written to the abort summary.

**Fix** (`vibecode/main_app.py:729-756`):
- Renamed `exit_code` to `wrapper_exit_code` on the controller return.
- When `summary is not None`, `result["exit_code"]` now uses `summary.exit_code` (raw agent exit code).
- When `summary is None` (early abort), added `_load_abort_error()` helper that reads the specific error from the on-disk `summary.json` written by `_write_abort_summary()`. Falls back to the generic message only when no summary exists or is unreadable.

### LOW: Right-panel artifact list completeness

**Problem**: `AgentRunService.run()` only collected 6 artifact paths, omitting `handoff_report.json`, `agent_stderr.log`, and `metadata.json` — all of which `RunSession` defines and the run layer writes.

**Fix**:
- `vibecode/session_log.py:104-107`: Added `RunSession.metadata_json` property.
- `vibecode/main_app.py:758-768`: Expanded `artifact_paths` loop to include `handoff_report_json`, `metadata_json`, and `agent_stderr_log`.

## Tests added

8 new tests in `tests/test_vibecode_run_action_tui.py`:

- `test_raw_agent_exit_code_used_not_wrapper` — verifies agent exit code 7 is used, not the wrapper code
- `test_raw_agent_exit_code_zero` — verifies agent exit code 0 is used
- `test_abort_surfaces_specific_error_from_disk` — verifies specific abort reason loaded from `summary.json`
- `test_abort_fallback_when_no_summary_on_disk` — verifies generic fallback when no disk summary
- `test_artifact_paths_includes_handoff_report_json` — verifies `handoff_report.json` in artifacts
- `test_artifact_paths_includes_agent_stderr_log` — verifies `agent_stderr.log` in artifacts
- `test_artifact_paths_includes_metadata_json` — verifies `metadata.json` in artifacts
- `test_shows_nonzero_exit_code` — verifies non-zero exit code in right-panel rendering

## Verification

```
python -m compileall vibecode -q   -> PASS
python -m pytest -p no:cacheprovider -q   -> 2239 passed
git status --short -> 3 files changed (no untracked)
```

## Changed files

- `vibecode/main_app.py` — `AgentRunService.run()` fix + `_load_abort_error()` helper
- `vibecode/session_log.py` — `RunSession.metadata_json` property
- `tests/test_vibecode_run_action_tui.py` — 8 new tests + `_make_summary_factory` helper
- `docs/audit/TUI_PHASE1_P24_AGENT_RUN_ACTIONS_FIX.md` — this report
