# Observable Run Monitor P16 Monitor Optional Deps Fix

Generated: 2026-05-12

## Verdict

No fixes needed. The review (`OBSERVABLE_RUN_MONITOR_P16_MONITOR_OPTIONAL_DEPS_REVIEW.md`)
found no implementation-file blockers in the reviewed scope. All implementation
findings were PASS.

## No-Fix Rationale

- **Optional dependency import boundaries**: `vibecode/cli.py` imports only stdlib
  at module level. `vibecode/monitor_app.py` and `vibecode/tui_app.py` wrap all
  Textual imports in `try/except ImportError`. No changes needed.
- **Monitor runtime behavior**: monitor consumes `VibecodeEvent` objects via
  `TUIEventSink` → `call_from_thread` → `route_event` → `format_*`. No scraped
  stdout text. No changes needed.
- **Fake monitor smoke coverage**: `TestMonitorEventPumpSmoke` exercises 11 tests
  routing real `VibecodeEvent` instances through `TUIEventSink` without Textual or
  OpenCode. No gaps identified. No changes needed.
- **CLI help/error behavior**: `--help` for base CLI and `monitor` work correctly.
  Missing-Textual detection returns exit code 1 with actionable install guidance
  (`pip install 'vibecode[tui]'`). No changes needed.

## Verification (post-review, local)

- `python -m compileall vibecode -q` — PASS
- `python -m pytest -p no:cacheprovider -q tests/test_vibecode_monitor.py tests/test_vibecode_cli.py` — 113 passed
- `python -m vibecode.cli --help` — PASS (lists all commands including dashboard, monitor)
- `python -m vibecode.cli monitor --help` — PASS (includes split-pane description and not-a-PTY limitation)

## Review Caveats (not addressed — out of scope)

- Pre-existing lint issues (45 ruff findings outside P16.1 implementation files).
- Local pytest temp/cache directory permission errors during full-suite runs.
  These are environment issues, not implementation regressions.
