# Next

- Conduct supervised dogfooding: run `vibecode run` against a real task on a real repository with real OpenCode 1.14.48; inspect run folder artifacts; use `vibecode runs show <session_id> --events` to replay the event timeline.
- Validate the monitor TUI (`vibecode monitor`) with the `[tui]` extra installed in an interactive terminal session.
- Verify OpenCode MCP server subprocess inherits `VIBECODE_SESSION_ID` / `VIBECODE_MCP_EVENTS_LOG` from `vibecode run` environment (requires real OpenCode integration test).
