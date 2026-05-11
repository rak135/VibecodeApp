# Observable Run Monitor P8 MCP Observability – Fix Log

Generated: 2026-05-12
Review: `docs/audit/OBSERVABLE_RUN_MONITOR_P8_MCP_OBSERVABILITY_REVIEW.md`

## Fixes Applied

### 1. E741 ambiguous variable name lint failures (REQUIRED FIX)

`tests/test_vibecode_mcp_server.py` lines 884, 901, 902: renamed `l` to `line` in JSONL
comprehensions.

### 2. Compact payload hardening (RECOMMENDED)

Added `test_find_symbol_result_summary_contains_no_raw_result` and
`test_list_high_risk_result_summary_contains_no_raw_result` to
`TestMcpToolLogging`. These assert that symbol kinds, line numbers, file headings,
and heuristic kinds are **not** present in MCP event data — confirming the
compact-summary behaviour already implemented for `get_file_card` also holds for
`find_symbol` and `list_high_risk`.

### 3. Session correlation documentation (RECOMMENDED)

Added a paragraph to `vibecode serve --help` describing MCP event correlation via
`VIBECODE_SESSION_ID` and the `"mcp-server"` fallback.

### 4. Optional-dependency simulation tests (RECOMMENDED)

Added two import-hook tests using `sys.meta_path` to block `mcp` package imports:

- `test_cli_help_works_when_mcp_imports_blocked` — proves `create_parser()` and
  `print_help()` succeed and list `serve` and `guard` commands.
- `test_non_mcp_command_works_when_mcp_imports_blocked` — proves the `validate`
  subcommand can be parsed without the `mcp` package.

Both tests confirm that non-MCP CLI paths are not blocked by a missing MCP runtime.

### 5. cmd_serve forwards correct args to build_mcp_server (RECOMMENDED)

Added `test_cmd_serve_forwards_log_path_and_session_id` to `TestCmdServe`. It
asserts that `cmd_serve()` calls `build_mcp_server()` with the expected
`log_path` (`<repo>/.vibecode/logs/mcp_events.jsonl`) and `session_id` read
from `VIBECODE_SESSION_ID`.

## Checks Run

- `python -m ruff check --no-cache vibecode\mcp_server.py vibecode\cli.py tests\test_vibecode_mcp_server.py` — **All checks passed**
- `python -c "import vibecode.mcp_server; import vibecode.cli"` — **passed**
- `python -m pytest tests/test_vibecode_mcp_server.py -x -p no:cacheprovider --basetemp .pytest-tmp` — **75 passed**
- `python -m pytest tests/test_integration.py -x -p no:cacheprovider --basetemp .pytest-tmp` — **12 passed**

## Changed Files

- `vibecode/cli.py` — session correlation docs in serve parser description
- `tests/test_vibecode_mcp_server.py` — E741 fix, compact-payload tests, import-blocker tests, cmd_serve arg-forwarding test
