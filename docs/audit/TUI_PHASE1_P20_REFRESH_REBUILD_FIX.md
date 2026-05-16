# TUI Phase 1 P20 Refresh/Rebuild Fix

Applied: 2026-05-16
Based on: `docs/audit/TUI_PHASE1_P20_REFRESH_REBUILD_REVIEW.md` (findings 1-3)

## Changes applied

### 1. Preservation allowlist: cross-check against canonical `HUMAN_MAINTAINED_PATHS`

**File**: `vibecode/refresh.py:161-174`

`_ensure_vibecode()` now imports `write_rules.HUMAN_MAINTAINED_PATHS` and cross-checks that every path declared as human-maintained is covered by either `_file_templates()` or `PROFILES`. If a path is added to `write_rules.py` but not to the template/profile machinery, refresh emits a warning so the gap is visible instead of silent.

This closes the drift risk between the canonical policy and the refresh creation logic.

### 2. Disposable cleanup: `risk_report.json` in schema.json `generated_outputs`

**File**: `vibecode/project.py:323`

Added `"risk_report.json"` to the `generated_outputs` list in `_file_templates()` (the template that produces `.vibecode/index/schema.json`). This aligns the human-maintained schema declaration with the refresh disposable-index allowlist and `cmd_index()` behavior — all three now agree that `risk_report.json` is a generated disposable artifact.

Note: The existing `.vibecode/index/schema.json` on disk is human-maintained and is not overwritten by init. The template fix ensures future initializations include the correct list.

### 3. Test coverage: malformed `project.yaml` edge case

**File**: `tests/test_vibecode_refresh.py:399-430`

Added three tests:
- `test_refresh_survives_malformed_project_yaml`: Refresh does not crash; reports the YAML error honestly.
- `test_refresh_preserves_malformed_project_yaml_byte_for_byte`: Refresh does not overwrite a malformed `project.yaml` with defaults.
- `test_refresh_checks_human_maintained_paths_coverage`: Verifies the cross-check from fix 1 emits (or does not emit) a warning based on whether all `HUMAN_MAINTAINED_PATHS` are covered.

## Verification

- `python -m compileall vibecode -q` — PASS
- `python -m ruff check vibecode\refresh.py tests\test_vibecode_refresh.py vibecode\project.py` — PASS
- `python -m pytest tests\test_vibecode_refresh.py -v` — 24/24 PASS
- Full pytest timed out but was progressing without failures

## Changed files

- `vibecode/refresh.py` — added `HUMAN_MAINTAINED_PATHS` cross-check warning (lines 161-174)
- `vibecode/project.py` — added `risk_report.json` to schema.json generated_outputs (line 323)
- `tests/test_vibecode_refresh.py` — added 3 tests (lines 399-459)
