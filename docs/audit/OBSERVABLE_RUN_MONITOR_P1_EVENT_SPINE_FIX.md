# Observable Run Monitor P1 Event Spine Fix

Applied: 2026-05-11

## Summary

Three lint-only fixes applied as directed by `OBSERVABLE_RUN_MONITOR_P1_EVENT_SPINE_REVIEW.md`. No product behaviour was changed.

## Changes

### `vibecode/events.py` — remove unused dataclass imports

`asdict` and `field` were imported from `dataclasses` but never used.
Changed line 15 from:

```python
from dataclasses import asdict, dataclass, field
```

to:

```python
from dataclasses import dataclass
```

### `tests/test_vibecode_events.py` — remove unused `PureWindowsPath` import

`PureWindowsPath` was imported in `test_json_fallback_path` but only `PurePosixPath` was used.
Changed line 323 from:

```python
from pathlib import PurePosixPath, PureWindowsPath
```

to:

```python
from pathlib import PurePosixPath
```

### `tests/test_vibecode_events.py` — use `tmp_path` in protocol test

`test_all_sinks_satisfy_protocol` previously created `test.jsonl` relative to the
current working directory and then deleted it. The manual cleanup was fragile and
left a stale file when the test ran from the repository root. Replaced with the
pytest `tmp_path` fixture so the file is isolated and automatically cleaned up.

## Checks Run

- `python -m compileall vibecode` — exit 0
- `python -m ruff check --no-cache vibecode\events.py tests\test_vibecode_events.py` — All checks passed
- `python -m pytest tests\test_vibecode_events.py -p no:cacheprovider -q` — 37 passed
