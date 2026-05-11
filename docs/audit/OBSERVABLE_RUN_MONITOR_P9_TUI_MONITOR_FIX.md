# Observable Run Monitor P9 TUI Monitor Fix

Generated: 2026-05-12

## Changes Applied

### Fix 1: prompt/context artifact paths shown in TUI

`format_vibecode_line()` in `vibecode/monitor_app.py:60-109` now special-cases `EVENT_CONTEXT` and `EVENT_PROMPT`:

- For context events: includes `snapshot_path` (falling back to `path`) in the visible line.
- For prompt events: includes `snapshot_path` (or `path`), `platform`, and `profile`.

Tests added in `tests/test_vibecode_monitor.py`:
- `test_context_event_shows_snapshot_path`
- `test_context_event_falls_back_to_path_when_no_snapshot`
- `test_context_event_no_path_no_crash`
- `test_prompt_event_shows_snapshot_path_platform_profile`
- `test_prompt_event_falls_back_to_path_when_no_snapshot`

### Fix 2: guard finding details displayed clearly

`format_vibecode_line()` now special-cases `EVENT_GUARD_FINDING`. The formatted line includes severity, category, path, title, recommended fix (first 80 chars), and required tests (first 3).

Tests added:
- `test_guard_finding_warning_shows_details`
- `test_guard_finding_error_shows_severity`
- `test_guard_finding_no_tests_no_fix_no_crash`

### Fix 3: guard status bar shows error/warning counts

`MonitorApp` in `vibecode/monitor_app.py` now tracks `_guard_errors` and `_guard_warnings` counts from incoming `EVENT_GUARD_FINDING` events and displays them in the status bar (e.g., "✗ 1 errors, 3 warnings") when the `EVENT_GUARD` completed event arrives.

### Fix 4: quit behavior help text corrected

`vibecode/cli.py:396` — changed from "Press Q to quit (the agent run continues until it exits naturally)" to "Press Q to close the monitor (running agent process behavior is not managed)".

### Lint fix

Removed unused `from pathlib import Path` import in `tests/test_vibecode_monitor.py:15`.

## Changed Files

- `vibecode/monitor_app.py` — formatter improvements, guard count tracking
- `vibecode/cli.py` — help text correction
- `tests/test_vibecode_monitor.py` — new tests, removed unused import

## Checks Run

- `python -m ruff check --no-cache vibecode\monitor_app.py vibecode\cli.py tests\test_vibecode_monitor.py` — passed
- `python -m pytest tests/test_vibecode_monitor.py -x -v -p no:cacheprovider` — 53 passed
- `python -m pytest --collect-only -p no:cacheprovider -q` — 1703 tests collected
