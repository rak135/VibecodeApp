# TUI Phase 1 P23 Safety Actions Fix

Generated: 2026-05-16

## Source

`docs/audit/TUI_PHASE1_P23_SAFETY_ACTIONS_REVIEW.md`

## Fixes applied

### MEDIUM: `[I]` stale-index freshness bypass (line 211-214)

`InspectMapService.run()` previously only checked whether `.vibecode/current/last_index.json` existed. It did not call `check_index_freshness()` from `vibecode.indexer`, so stale-by-age, stale-by-commit-drift, and stale-by-file-set-change were all missed.

**Change:** Added `_is_static()` static method to `InspectMapService` that calls `check_index_freshness()` and falls back to the simple existence check on import error. The `run()` method now delegates to `_is_static()`.

File: `vibecode/main_app.py:211-224`

### LOW: Missing direct action-wiring regression tests

The existing test suite covered services, renderers, and callbacks individually but never called the bound action methods (`action_inspect_map()`, `action_cmd_guard()`, `action_cmd_tests()`, `action_cmd_handoff()`) and verified the full service→callback wire.

**Change:** Added `TestActionWiringRegression` class with 8 tests:
- 4 "calls_service" tests — inject a fake service, call the action, verify `svc.run(repo_root)` was called and the correct `_on_*_done` callback was routed.
- 4 "routes_error" tests — inject a fake service that raises, verify the correct `_on_*_error` callback receives the error string.

Threading is patched synchronous via `monkeypatch.setattr` so tests are deterministic and fast.

File: `tests/test_vibecode_main_tui.py:1785-1933`

### Stale-index tests (age-based)

Added two tests to `TestInspectMapService`:
- `test_stale_when_index_too_old` — last_index.json with `started_at` 600s in the past → stale.
- `test_not_stale_when_index_is_recent` — last_index.json with current timestamp → not stale.

File: `tests/test_vibecode_main_tui.py:795-824`

## Verification

```
python -m compileall vibecode -q          → PASS
python -m pytest -p no:cacheprovider -q
  tests\test_vibecode_main_tui.py
  tests\test_vibecode_guard_cli.py
  tests\test_vibecode_check.py
  tests\test_vibecode_handoff_cli.py
  tests\test_vibecode_validation.py       → 231 passed
```

All ruff warnings are pre-existing (E741, F401 in test file — flagged in original review).

## Changed files

- `vibecode/main_app.py`
- `tests/test_vibecode_main_tui.py`
- `docs/audit/TUI_PHASE1_P23_SAFETY_ACTIONS_FIX.md` (this file)
