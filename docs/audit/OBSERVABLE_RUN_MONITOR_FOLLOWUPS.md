# Observable Run Monitor — Follow-up Work

Generated: 2026-05-12

The final review identified several items that are larger than concrete/safe fixes.
These are documented here for future work.

## 1. Real OpenCode integration test

No `opencode` binary is available in the environment. Agent logs (`agent_stdout.log`,
`agent_stderr.log`), prompt snapshots (`opencode_prompt.md`), and `handoff_report.*`
can only be verified end-to-end in an environment with OpenCode installed.

**Recommendation**: Add an integration smoke in CI that uses a stub/mock `opencode`
binary (like the existing `fake_bin_ign` pattern) to verify `agent_stdout.log`,
prompt snapshot, and `handoff_report.*` are written.

## 2. Monitor PTY test

`vibecode monitor` requires an interactive terminal with full Textual rendering;
it cannot be smoke-tested in a non-PTY CI/scripted environment. Validated via
unit tests and helper-function smoke only.

**Recommendation**: Consider a headless Textual test using `textual.testing.Pilot`
for basic TUI startup and event routing verification.

## 3. MCP uses separate event log, not the per-run spine

MCP tool call events are written to `.vibecode/logs/mcp_events.jsonl` via `cmd_serve`,
not the same `.vibecode/runs/<session_id>/events.jsonl` stream. They are not shown
in the monitor. Correlation is possible via `VIBECODE_SESSION_ID` but there is no
unified per-run capture.

**Recommendation**: Either accept this as a documented limitation or integrate MCP
events into the per-run JSONL stream via the existing `MultiEventSink` pattern.

## 4. NOW.md placeholder warning

`vibecode validate` warns that `.vibecode/handoff/NOW.md` contains placeholder text.

**Recommendation**: Update the handoff to remove the placeholder content.

## 5. Stale index

The `.vibecode/index/` was built for a previous commit. `vibecode run-plan` reports
this as a warning.

**Recommendation**: Run `vibecode index` to refresh.
