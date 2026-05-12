# Observable Run Monitor P15 MCP Correlation Review

Status: PASS WITH FOLLOW-UPS

P15.1 mostly closes the MCP/run correlation gap. `RunController` now injects
`VIBECODE_SESSION_ID` and `VIBECODE_MCP_EVENTS_LOG` into the child agent
environment, `cmd_serve()` consumes both variables, MCP tool events stay compact,
and the monitor has compact formatting/routing for injected `run.mcp` events.

## Findings

### MEDIUM: non-MCP optional-dependency proof does not execute a command

The optional MCP dependency boundary is correct in implementation, but one
required evidence item is weak. `test_non_mcp_command_works_when_mcp_imports_blocked`
blocks MCP imports and parses `validate`, but it does not dispatch or execute a
non-MCP command (`tests/test_vibecode_mcp_server.py:1104-1121`). That proves parser
construction is safe, not that non-MCP commands do not fail without MCP installed.

Implementation evidence is still favorable: `vibecode/cli.py` imports
`cmd_serve` only inside the `serve` dispatch branch (`vibecode/cli.py:645-649`),
and `build_mcp_server()` imports `FastMCP` lazily only when building the MCP
server (`vibecode/mcp_server.py:280-306`). Add a small execution test such as
`main(["validate", <minimal initialized repo>])` or another cheap non-MCP command
while MCP imports are blocked.

### LOW: user-facing docs still describe the pre-P15 side-log limitation

The implementation now routes MCP events to a per-run path when the agent process
inherits `VIBECODE_MCP_EVENTS_LOG` (`vibecode/run.py:906-919`,
`vibecode/session_log.py:124-127`, `vibecode/mcp_server.py:373-379`). However,
README still says MCP events are appended to a single log file and are not written
into the per-run session directory (`README.md:396-398`). `vibecode serve --help`
also mentions only `.vibecode/logs/mcp_events.jsonl` and `VIBECODE_SESSION_ID`,
not the per-run `VIBECODE_MCP_EVENTS_LOG` override (`vibecode/cli.py:342-345`).

The monitor limitation remains accurate: live cross-process MCP streaming into
the monitor is not implemented; monitor formatting only renders `run.mcp` events
that are delivered to its sink (`vibecode/monitor_app.py:110-144`). The docs should
separate these two facts: per-run MCP JSONL exists for agent-inherited MCP servers,
but live monitor ingestion of that side log remains best-effort/not implemented.

## Evidence Reviewed

### Environment propagation

`RunController.execute()` copies the parent environment, injects
`VIBECODE_SESSION_ID` and `VIBECODE_MCP_EVENTS_LOG`, and passes the resulting env
to `run_streaming()` (`vibecode/run.py:906-919`). `run_streaming()` accepts `env`
and passes it directly to `subprocess.Popen` (`vibecode/process_runner.py:80-91`,
`vibecode/process_runner.py:129-140`).

Tests use a fake `opencode.cmd` that writes its received environment to JSON.
They assert the child sees the configured session id and that the MCP log path is
inside `.vibecode/runs/<session_id>/mcp_events.jsonl`
(`tests/test_vibecode_run_controller.py:1660-1761`). This is stronger than a
direct unit-only assertion because it exercises the actual process launch path.

### MCP server correlation and fallback

`cmd_serve()` reads `VIBECODE_MCP_EVENTS_LOG` first and falls back to
`<repo>/.vibecode/logs/mcp_events.jsonl`; it passes `VIBECODE_SESSION_ID` through
to `build_mcp_server()` (`vibecode/mcp_server.py:373-379`). `VibecodeServer` then
falls back from explicit session id to `VIBECODE_SESSION_ID` to `"mcp-server"`
(`vibecode/mcp_server.py:31-42`).

Tests cover the per-run log env var, default log fallback, env session id, missing
session id, constructor session id, env session id, and `"mcp-server"` fallback
(`tests/test_vibecode_mcp_server.py:465-565`, `tests/test_vibecode_mcp_server.py:958-996`).

### Compact MCP event payloads

The tool wrappers emit `McpToolCalled`, `McpToolReturned`, and `McpToolFailed`
without changing the underlying functional responses (`vibecode/mcp_server.py:207-277`).
Returned-event payloads contain compact fields only: `found`, `match_count`,
`risk_count`, and `result_chars`.

Tests assert JSONL events are written and parse as `run.mcp`
(`tests/test_vibecode_mcp_server.py:1000-1032`). They also assert full file-card
snippets, fact text, raw symbol result text, and raw high-risk report content do
not appear in event data (`tests/test_vibecode_mcp_server.py:894-941`).

### Monitor rendering and limitation

`format_vibecode_line()` renders MCP events compactly as called, returned, or
failed; `route_event()` sends MCP events to the event pane, not the agent pane
(`vibecode/monitor_app.py:110-149`). Tests cover call/return/failure formatting,
argument truncation behavior, no-data safety, and routing
(`tests/test_vibecode_monitor.py:620-766`).

This is render support, not live side-log ingestion. The source comment is
explicit that live cross-process MCP streaming into the monitor is not implemented
(`vibecode/monitor_app.py:111-114`).

### Optional MCP dependency boundary

Base dependencies keep MCP optional (`pyproject.toml:10-15`). `vibecode.mcp_server`
does not import `mcp` at module import time; only `build_mcp_server()` imports
`FastMCP` (`vibecode/mcp_server.py:280-306`). `VibecodeServer` and its tool methods
can run without the MCP package because they use only local Python code
(`tests/test_vibecode_mcp_server.py:1051-1066`).

The remaining weakness is the non-MCP CLI execution test noted above.

## Checks Run

- `python -m vibecode.cli context . --task "Review the P15.1 implementation"`
- `python -m vibecode.cli --help` - PASS
- `python -m vibecode.cli index --help` - PASS
- `python -m vibecode.cli context --help` - PASS
- `python -m vibecode.cli guard . --task "Review the P15.1 implementation"` - PASS
- `python -m pytest tests/test_vibecode_run_controller.py::TestMcpEnvPropagation tests/test_vibecode_mcp_server.py::TestMcpToolLogging tests/test_vibecode_monitor.py::TestMcpEventFormatting -q` - BLOCKED by local pytest temp/cache permission errors before relevant test assertions ran (`PermissionError` reading `C:\Users\Martin\AppData\Local\Temp\pytest-of-Martin`).
- `python -m pytest tests/test_vibecode_run_controller.py::TestMcpEnvPropagation tests/test_vibecode_mcp_server.py::TestMcpToolLogging tests/test_vibecode_monitor.py::TestMcpEventFormatting -q -p no:cacheprovider --basetemp C:\tmp\pytest-vibecode-p15-focused` - BLOCKED by `PermissionError` creating `C:\tmp\pytest-vibecode-p15-focused`.
- `python -m pytest tests/test_vibecode_run_controller.py::TestMcpEnvPropagation tests/test_vibecode_mcp_server.py::TestMcpToolLogging tests/test_vibecode_monitor.py::TestMcpEventFormatting -q -p no:cacheprovider --basetemp .\pytest-tmp-p15-focused` - BLOCKED by `PermissionError` reading the workspace basetemp directory after pytest created it.
- `python -m pytest -q` - BLOCKED by the same local pytest temp permission issue; many tests requiring `tmp_path` errored before assertions.
- `python -m ruff check .` - FAILS with 45 existing lint findings across `scripts/` and `tests/`, plus Ruff cache write permission warnings. The new review markdown file is not implicated.
