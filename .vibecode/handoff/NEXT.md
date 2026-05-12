# Next

- Conduct supervised dogfooding: run `vibecode run` against a real task on a real repository with real OpenCode; inspect run folder artifacts; use `vibecode runs show <session_id> --events` to replay the event timeline.
- Validate the monitor TUI (`vibecode monitor`) with the `[tui]` extra installed in an interactive terminal session.
- Fix pre-existing `test_missing_gitignore_blocks_agent_launch` failure (unrelated to observable monitor).
- Investigate and fix Windows stdin-close OSError in `process_runner.py` line 151.
- Investigate `runs show` checks count display inconsistency (shows 0/0 when summary.json reports 1/1).
