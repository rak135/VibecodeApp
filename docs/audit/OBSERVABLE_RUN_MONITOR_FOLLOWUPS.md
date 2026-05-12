# Observable Run Monitor — Follow-up Work

Generated: 2026-05-12

The final review identified several items that are larger than concrete/safe fixes.
These are documented here for future work.

## 1. Real OpenCode smoke durability

OpenCode is available in this environment (`opencode --version` -> `1.14.48`),
and real `vibecode run` smokes were executed. The first smoke completed the
agent process and captured the marker; the second launched through the fixed
default `opencode run` command but timed out after the agent did extra work.

**Recommendation**: Keep a manual/local real-OpenCode smoke checklist for
release validation, and consider adding configurable agent timeouts or a
shorter smoke prompt/profile for predictable non-interactive validation.

## 2. Fake OpenCode CI regression

A fake `opencode` regression test now verifies launch, stdout/stderr capture,
agent logs, prompt/context snapshots, summary writing, agent start/finish
events, and advisory guard behavior without requiring a paid model/API.

**Recommendation**: Keep this as the CI guard for orchestration. It is not a
replacement for the manual real-OpenCode smoke.

## 3. Monitor PTY test

`vibecode monitor` requires an interactive terminal with full Textual rendering;
it cannot be smoke-tested in a non-PTY CI/scripted environment. Validated via
unit tests and helper-function smoke only.

**Recommendation**: Consider a headless Textual test using `textual.testing.Pilot`
for basic TUI startup and event routing verification.

## 4. MCP uses separate event log, not the per-run spine

MCP tool call events are written to `.vibecode/logs/mcp_events.jsonl` via `cmd_serve`,
not the same `.vibecode/runs/<session_id>/events.jsonl` stream. They are not shown
in the monitor. Correlation is possible via `VIBECODE_SESSION_ID` but there is no
unified per-run capture.

**Recommendation**: Either accept this as a documented limitation or integrate MCP
events into the per-run JSONL stream via the existing `MultiEventSink` pattern.

## 5. Handoff placeholder semantics

The false-positive `TODO/FIXME` placeholder warning in `.vibecode/handoff/NOW.md`
has been fixed. Actual unfinished lines such as `TODO: ...`, `TBD`, HTML
comments, and the word `placeholder` still fail handoff validation.

**Recommendation**: Keep the placeholder detector strict for real unfinished
handoff content, but avoid flagging historical prose that describes marker
formats.

## 6. Stale index

The index was refreshed during the real smoke. It may become stale again as this
validation cleanup lands additional source and docs changes.

**Recommendation**: Run `vibecode index` before final handoff or release tagging.
