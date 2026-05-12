# Observable Run Monitor P14 Durable Failures Fix

## Verdict

**NO IMPLEMENTATION BUGS FOUND. TEST COVERAGE ADDED.**

The review confirmed that `RunController.execute()` correctly:
- Constructs `RunSession` and JSONL sink before emitting any lifecycle events
- Calls `_write_abort_summary()` on every early-return path
- Handles agent launch `OSError` with a full failure summary

All three findings identified gaps in test coverage, not implementation defects.

## Fixes Applied

### 1. Added early-abort tests for missing index and inventory health failure

**File**: `tests/test_vibecode_run_controller.py`
**Class**: `TestEarlyAbortArtifacts`

Added 6 new tests proving durable `events.jsonl` and `summary.json` for:
- **Missing index** (`no_index=True`, no `last_index.json`): verifies run started/finished events and error summary with "no index" message.
- **Inventory health failure** (corrupt `file_inventory.json`): verifies run started/finished events and error summary with "inventory" message.

These augment the existing coverage for missing project.yaml, invalid profile, and dirty preflight.

### 2. Added round-trip test: real abort JSONL parsed as VibecodeEvent

**File**: `tests/test_vibecode_run_controller.py`
**Class**: `TestEarlyAbortArtifacts`
**Method**: `test_abort_events_roundtrip_as_vibecode_event`

Real `RunController` abort (missing project.yaml) produces `events.jsonl`, which is loaded via `load_run_events()` — the same parser used by `runs show --events`. Every parsed line is asserted as a `VibecodeEvent` instance with correct `session_id`, types, phases, and level.

### 3. Added sink fan-out regression tests

**File**: `tests/test_vibecode_run_controller.py`
**Class**: `TestUserSinkFanOut` (new)

4 tests verify that when a non-`NullEventSink` is injected:
- The durable JSONL and in-memory sink have the same event count
- No duplicate event IDs exist in the durable JSONL
- No duplicate event IDs exist in the in-memory sink
- Event order (by ID) is identical between both sinks

## Validation

```
python -m compileall vibecode -q                        # PASS
python -m pytest -p no:cacheprovider -q \
  tests/test_vibecode_run_controller.py \
  tests/test_vibecode_show_run.py                       # 120 passed
python -m pytest -p no:cacheprovider -q \
  tests/test_vibecode_session_log.py \
  tests/test_vibecode_guard.py \
  tests/test_vibecode_guard_report.py \
  tests/test_vibecode_guard_cli.py                      # 140 passed
```

## Changed Files

- `tests/test_vibecode_run_controller.py` — added `_minimal_vibecode_no_index` helper, `load_run_events`/`VibecodeEvent` imports, 10 new test methods across `TestEarlyAbortArtifacts` and `TestUserSinkFanOut`
