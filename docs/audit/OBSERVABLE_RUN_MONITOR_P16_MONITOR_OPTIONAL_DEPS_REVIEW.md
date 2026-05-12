# Observable Run Monitor P16 Monitor Optional Deps Review

Generated: 2026-05-12

## Verdict

PASS WITH VERIFICATION CAVEATS. The P16.1 implementation keeps Textual optional
in packaging, avoids importing Textual from the base CLI path, gives actionable
install guidance when `dashboard` or `monitor` are invoked without Textual, and
keeps the monitor wired to the structured `VibecodeEvent` event spine rather
than scraped stdout text.

I found no implementation-file blocker in the reviewed scope. Full-suite
verification is not green in this local environment because pytest cannot read
or create its temp/cache directories, and `ruff check .` reports pre-existing
lint issues outside the P16.1 implementation files.

This review only adds this document, per the task constraint.

## Findings

### PASS: dependency and extras contract is coherent

`pyproject.toml` keeps base dependencies minimal:

- `dependencies = ["pyyaml>=6.0"]`
- `tui = ["textual>=0.47"]`
- `mcp = ["mcp>=1.0"]`
- `all = ["textual>=0.47", "mcp>=1.0"]`

That matches the implementation: Textual-backed commands are optional TUI
features, not base CLI requirements.

Docs no longer assume Textual is always installed. `README.md` and
`docs/QUICKSTART.md` both mention the TUI extra, and command-level missing
dependency messages recommend `pip install 'vibecode[tui]'` or `pip install
textual`.

### PASS: CLI and TUI import boundaries are safe

`vibecode/cli.py` imports only stdlib modules at module import time. The
`dashboard` and `monitor` branches import `vibecode.tui_app.cmd_dashboard` and
`vibecode.monitor_app.cmd_monitor` only after the selected command is known.

`vibecode/monitor_app.py` and `vibecode/tui_app.py` wrap all Textual imports in
`try/except ImportError`, expose `_TEXTUAL_AVAILABLE`, and define stubs when
Textual is unavailable. `TUIEventSink`, `route_event`, `format_agent_line`, and
`format_vibecode_line` remain importable without Textual.

Direct import-blocking smoke:

```text
Command: block all textual/textual.* imports in a subprocess, then import vibecode.cli,
run main(["--help"]), import monitor_app/tui_app, and invoke cmd_monitor/cmd_dashboard.
Result: exit 0
top_help_rc=0
monitor_textual_available=False
dashboard_textual_available=False
monitor_rc=1; monitor_hint=True
dashboard_rc=1; dashboard_hint=True
```

### PASS: missing Textual behavior is clear and user-facing

Manual command probe with `_TEXTUAL_AVAILABLE = False`:

```text
Command: call cmd_monitor() and cmd_dashboard() with Textual marked unavailable.
Result: exit 0 for the probe script
monitor_rc=1
dashboard_rc=1
Error: the 'textual' package is required for 'vibecode monitor'.
Install it with:  pip install 'vibecode[tui]'
  or:            pip install textual
Error: the 'textual' package is required for 'vibecode dashboard'.
Install it with:  pip install 'vibecode[tui]'
  or:            pip install textual
```

This satisfies the optional-dependency contract if Textual remains optional.
It also avoids `sys.exit()` bypasses; both command functions return `1`.

### PASS: monitor uses the event spine, not scraped stdout text

The monitor consumes `VibecodeEvent` objects:

- `vibecode/monitor_app.py` imports `VibecodeEvent` and event type constants.
- `TUIEventSink.emit(event: VibecodeEvent)` forwards the event through
  Textual's `call_from_thread()`.
- `MonitorApp.on_mount()` constructs `RunController(..., sink=sink, ...)`.
- `MonitorApp.handle_vibecode_event(event: VibecodeEvent)` routes events to
  panes.
- `route_event()` sends only `EVENT_AGENT_PROCESS` to the agent pane.

The stdout/stderr stream itself is converted into structured events before the
monitor sees it: `vibecode/process_runner.py` documents and emits
`EVENT_AGENT_PROCESS` with `data["phase"] = "stdout"` or `"stderr"` for each
line. I found no monitor-side scraping of CLI stdout text.

Relevant tests are not limited to `MonitorApp.run()` mocks. Exact smoke tests
that exercise the event-sink pipeline include:

- `tests/test_vibecode_monitor.py::TestMonitorEventPumpSmoke::test_agent_stdout_lands_in_agent_log_not_event_log`
- `tests/test_vibecode_monitor.py::TestMonitorEventPumpSmoke::test_stderr_agent_event_lands_in_agent_log`
- `tests/test_vibecode_monitor.py::TestMonitorEventPumpSmoke::test_lifecycle_event_lands_in_event_log_not_agent_log`
- `tests/test_vibecode_monitor.py::TestMonitorEventPumpSmoke::test_guard_event_lands_in_event_log`
- `tests/test_vibecode_monitor.py::TestMonitorEventPumpSmoke::test_check_event_lands_in_event_log`
- `tests/test_vibecode_monitor.py::TestMonitorEventPumpSmoke::test_guard_finding_lands_in_event_log`
- `tests/test_vibecode_monitor.py::TestMonitorEventPumpSmoke::test_mcp_event_lands_in_event_log`
- `tests/test_vibecode_monitor.py::TestMonitorEventPumpSmoke::test_mixed_event_types_route_to_correct_panes`
- `tests/test_vibecode_monitor.py::TestMonitorEventPumpSmoke::test_events_preserved_in_emission_order`
- `tests/test_vibecode_monitor.py::TestMonitorEventPumpSmoke::test_event_log_includes_timestamp_from_event`
- `tests/test_vibecode_monitor.py::TestMonitorEventPumpSmoke::test_agent_log_strips_trailing_newline`

### PASS: monitor still states it is not a PTY

The limitation is present in all relevant user-facing surfaces:

- `vibecode/monitor_app.py` module docstring: streaming-output monitor, text
  mode, not a PTY.
- `python -m vibecode.cli monitor --help`: "streaming-output monitor (text
  mode), not a PTY."
- `README.md`: monitor is a streaming-output monitor, not a PTY.
- `docs/QUICKSTART.md`: same limitation, with guidance to run OpenCode
  directly for full interactive terminal control.

### PASS: dashboard import behavior is preserved

`vibecode/tui_app.py` uses the same guarded Textual import pattern as the
monitor. `load_dashboard_data()` remains dependency-light and delegates to
`vibecode.data_loader.load_project_data`, so data loading can be imported and
tested without Textual.

Dashboard command behavior with Textual unavailable returns `1` with the same
install guidance. The CLI still performs the missing-index hint before launching
the TUI command, and that path does not require Textual until the dashboard
command is actually selected.

## Verification

Targeted tests and probes:

- `python -m pytest tests/test_vibecode_monitor.py::TestMonitorEventPumpSmoke`
  with `PYTEST_DEBUG_TEMPROOT=.pytest-local-check` and `-p no:cacheprovider`:
  PASS, `11 passed in 0.24s`.
- `python -m pytest tests/test_vibecode_monitor.py::TestMissingTextual::test_missing_textual_message_mentions_install_extra tests/test_vibecode_monitor.py::TestMissingTextual::test_monitor_app_module_importable_without_textual tests/test_vibecode_monitor.py::TestMissingTextual::test_monitor_app_flag_is_bool tests/test_vibecode_cli.py::test_base_cli_help_works_when_textual_unavailable tests/test_vibecode_cli.py::test_non_monitor_command_works_when_textual_unavailable`
  with `PYTEST_DEBUG_TEMPROOT=.pytest-local-check` and `-p no:cacheprovider`:
  PASS, `5 passed in 0.25s`.
- `python -m pytest tests/test_vibecode_monitor.py::TestMissingTextual tests/test_vibecode_monitor.py::TestMonitorEventPumpSmoke tests/test_vibecode_cli.py::test_base_cli_help_works_when_textual_unavailable tests/test_vibecode_cli.py::test_non_monitor_command_works_when_textual_unavailable`:
  BLOCKED by local pytest temp/cache permissions; 16 selected tests passed,
  4 `tmp_path` setup errors from `PermissionError` reading
  `C:\Users\Martin\AppData\Local\Temp\pytest-of-Martin`.
- Same targeted command with `--basetemp=C:\tmp\...`: BLOCKED by
  `PermissionError` creating `C:\tmp\pytest-vibecode-p16-target`.
- Same targeted command with `--basetemp=.pytest-tmp-p16-review\...`:
  BLOCKED by `PermissionError` reading the workspace basetemp directory during
  pytest session cleanup.

CLI/help checks:

- `python -m vibecode.cli --help`: PASS, lists `dashboard`, `monitor`, and
  existing base commands.
- `python -m vibecode.cli monitor --help`: PASS, includes split-pane monitor
  description and not-a-PTY limitation.
- `python -m vibecode.cli dashboard --help`: PASS.
- `python -m vibecode.cli index --help`: PASS.
- `python -m vibecode.cli context --help`: PASS.

Required checks:

- `vibecode check C:\DATA\PROJECTS\VibecodeApp`: TIMED OUT after about 183s.
  It reported `FAIL: unit tests`, then `PASS: cli help`, `PASS: index command
  help`, and `PASS: context command help`.
- `python -m pytest -p no:cacheprovider`: TIMED OUT after about 185s. Pytest
  collected 1844 items, but many `tmp_path`-using tests errored with
  `PermissionError` reading
  `C:\Users\Martin\AppData\Local\Temp\pytest-of-Martin`.
- `python -m compileall vibecode tests`: FAIL due `PermissionError` replacing
  existing files under `tests\__pycache__`.
- `python -m ruff check .`: FAIL with 45 reported lint errors, apparently
  pre-existing and outside the P16.1 implementation surface; examples include
  unused imports in `scripts/write_tests.py`, `tests/test_vibecode_classifier.py`,
  and `tests/test_vibecode_diff_summary.py`, plus `F821 Undefined name Path` in
  `tests/test_vibecode_project_cli.py`.

## Review Notes

The most important prior risks are addressed:

- Base CLI is not broken by early Textual imports.
- Monitor tests are not only `MonitorApp.run()` mocks; event-pump tests route
  real `VibecodeEvent` instances through `TUIEventSink`.
- Packaging marks Textual optional, and docs plus runtime errors now give TUI
  extra install guidance.
- Dashboard uses the same optional dependency boundary and remains importable
  for data-loading behavior.

No implementation files were modified by this review.
