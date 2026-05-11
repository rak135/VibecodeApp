# Observable Run Monitor P1 Event Spine Review

Generated: 2026-05-11

## Verdict

FIX REQUIRED. The event spine is correctly isolated from high-level runtime modules and the core schema/sinks are small, replayable, and test-covered. However, the new files are not lint-clean: `vibecode/events.py` has unused dataclass imports, and `tests/test_vibecode_events.py` has an unused `PureWindowsPath` import. Those should be fixed before this task is accepted.

This review did not modify implementation or test files. The task scope allowed only this review document.

## Findings

### BLOCKER: Focused Ruff check fails on unused imports

`python -m ruff check --no-cache vibecode\events.py tests\test_vibecode_events.py` fails with three `F401` findings:

- `vibecode/events.py:15` imports `asdict` but never uses it.
- `vibecode/events.py:15` imports `field` but never uses it.
- `tests/test_vibecode_events.py:323` imports `PureWindowsPath` but never uses it.

This is a cleanup-only fix and does not require product behavior changes.

### PASS: `events.py` is not coupled to high-level runtime modules

`vibecode/events.py` imports only stdlib modules: `json`, `os`, `uuid`, `dataclasses`, `datetime`, `enum`, `pathlib`, and `typing` (`vibecode/events.py:12-19`). It does not import `run`, `guard`, `check`, `handoff`, `context`, dashboard, MCP, or CLI modules.

Reference search found `vibecode.events` imported only by `tests/test_vibecode_events.py`; no production module depends on it yet. That means this P1 spine did not accidentally alter existing product flows.

### PASS: Event schema is adequate for replay and future GUI/TUI rendering

`VibecodeEvent` includes the minimum stable fields needed to reconstruct and render an event stream: `event_id`, `session_id`, `timestamp`, `type`, `level`, `message`, and optional `data` (`vibecode/events.py:63-69`). Serialization emits both level name and numeric value (`vibecode/events.py:74-82`), which is useful for sorting/filtering in a future UI while remaining human-readable.

Replay is viable because JSONL file order plus `timestamp`, `session_id`, and `event_id` preserve event identity and session grouping. A future integration may still want an explicit monotonic sequence number or schema version, but that is not required for this first isolated spine.

### PASS: JSONL sink appends and creates parent directories

`JsonlEventSink.__init__` creates parent directories with `mkdir(parents=True, exist_ok=True)` (`vibecode/events.py:149-151`). `emit()` opens the target in append mode and writes exactly one serialized JSON object plus newline (`vibecode/events.py:157-160`).

This satisfies the P1 append-safe requirement for a single-process local CLI event stream. It does not attempt cross-process locking or fsync durability, which is appropriate for the current scope.

### PASS: Tests prove serialization and sink behavior

The event tests directly cover:

- Dictionary/JSON structure and round trips (`tests/test_vibecode_events.py:80-125`).
- Event level ordering and event type constants (`tests/test_vibecode_events.py:131-148`).
- Event factory behavior (`tests/test_vibecode_events.py:154-178`).
- In-memory sink filtering and clearing (`tests/test_vibecode_events.py:184-217`).
- JSONL append order, parent directory creation, and valid JSON lines (`tests/test_vibecode_events.py:223-250`).
- Console, multi-sink, null-sink, and protocol compatibility behavior (`tests/test_vibecode_events.py:256-387`).
- Serialization fallback and non-serializable data failure behavior (`tests/test_vibecode_events.py:317-369`).

One test hygiene issue remains: `test_all_sinks_satisfy_protocol` writes `test.jsonl` relative to the current working directory (`tests/test_vibecode_events.py:379`) and then deletes it (`tests/test_vibecode_events.py:387`). That can leave or touch repo-root files when tests run from the repository root. It should use `tmp_path` like the focused JSONL tests.

### PASS: No direct product behavior changed accidentally

The event spine is not wired into production command paths yet. Existing commands still flow through their prior return values, stdout/stderr output, and file writes. The implementation added an isolated primitive, not a behavior change to `run`, `guard`, `check`, `handoff`, `context`, MCP, or dashboard flows.

### PASS: No broad refactors were introduced

The reviewed implementation is limited to `vibecode/events.py` and `tests/test_vibecode_events.py`. It does not restructure existing modules, move responsibilities, or alter architecture docs or generated/runtime artifacts.

## Checks Run

- `python -m vibecode.cli validate .`
  - Result: passed; existing warning that `.vibecode/handoff/NOW.md` contains placeholder text.
- `python -m pytest tests\test_vibecode_events.py`
  - Result: failed in this sandbox before a clean signal because pytest could not access the default Windows temp directory and the repo-root `test.jsonl` cleanup hit `PermissionError`.
- `python -m pytest C:\DATA\PROJECTS\VibecodeApp\tests\test_vibecode_events.py --basetemp C:\Users\Martin\.codex\memories\pytest-vibecode-events\basetemp -o cache_dir=C:\Users\Martin\.codex\memories\pytest-vibecode-events\cache`
  - Result: still non-zero due sandbox directory access during pytest temp cleanup; progress output showed most non-`tmp_path` event tests executed, but the run did not complete cleanly.
- `python -m ruff check --no-cache vibecode\events.py tests\test_vibecode_events.py`
  - Result: failed with the `F401` findings listed above.
- `python -m vibecode.cli check .`
  - Result: failed because the required `unit tests` command exited 1; required CLI help checks passed.
- `python -m vibecode.cli guard . --task "Review the event spine implementation"`
  - Result: passed.

## Recommendation

Apply the lint-only cleanup and move the protocol test JSONL path to `tmp_path`. After that, rerun the focused event tests, Ruff, and the repository required checks. No runtime integration changes are needed for this review round.
