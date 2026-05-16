# Next

- Conduct supervised dogfooding: run `vibecode run` against a real task on a real repository with real OpenCode 1.14.48; inspect run folder artifacts; use `vibecode runs show <session_id> --events` to replay the event timeline.
- Validate the monitor TUI (`vibecode monitor`) with the `[tui]` extra installed in an interactive terminal session.
- Verify OpenCode MCP server subprocess inherits `VIBECODE_SESSION_ID` / `VIBECODE_MCP_EVENTS_LOG` from `vibecode run` environment (requires real OpenCode integration test).
- Dogfood the Phase 1 main TUI shell: run `vibecode` (no args) in a real terminal with `[tui]` extra installed; verify three-column layout renders, R refresh wires correctly, I loads repo map into center panel; verify `[E]` launches OpenCode in an external Windows Terminal window.
- Phase 2 TUI actions: wire C (context pack), G (guard report), T (task input), H (handoff view) keys to real functionality replacing the "not implemented yet" stubs in `vibecode/main_app.py`. (`[A]`/`[S]` and `[E]` are already wired.)
