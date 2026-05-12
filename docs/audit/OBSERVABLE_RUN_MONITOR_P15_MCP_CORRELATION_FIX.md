# Observable Run Monitor P15 MCP Correlation Fix

Status: FIXES APPLIED

## Changes Applied

### MEDIUM: non-MCP optional-dependency proof strengthened

**Before:** `test_non_mcp_command_works_when_mcp_imports_blocked` only parsed
`validate` arguments. It proved parser construction is safe with MCP blocked,
but did not prove non-MCP commands execute without MCP installed.

**After:** The test now has two phases:
1. (preserved) Parse `validate` args while blocking `mcp` imports.
2. (new) Execute `main(["validate", str(tmp_path)])` while blocking both `mcp`
   and `vibecode.mcp_server` imports. Asserts no `ImportError` is raised.
   `validate` on an uninitialised temp dir returns exit code 0 or 1 (errors for
   missing project files), but must not crash on missing MCP.

Helped by `_BlockMCP_DirectImport` that also blocks `vibecode.mcp_server`.
Cleanup helpers `_clear_mcp_modules()` and `_remove_blocker()` extracted to
avoid duplication.

File: `tests/test_vibecode_mcp_server.py:1104-1149`

### LOW: user-facing docs updated for per-run MCP JSONL

**README.md** — MCP observability section rewritten:
- Describes per-run `VIBECODE_MCP_EVENTS_LOG` routing (set automatically by
  `vibecode run` and `vibecode monitor`).
- Separates the two facts: per-run JSONL exists, live monitor ingestion of the
  side log remains not implemented.

File: `README.md:394-401`

**CLI serve help text** — now mentions `VIBECODE_MCP_EVENTS_LOG` as the
primary log path, with the `.vibecode/logs/mcp_events.jsonl` fallback.
Notes that `vibecode run` and `vibecode monitor` set both env vars
automatically.

File: `vibecode/cli.py:342-348`

## Verification

- `python -m compileall vibecode -q` — PASS (clean)
- `python -m pytest -p no:cacheprovider -q tests/test_vibecode_mcp_server.py tests/test_vibecode_run_controller.py tests/test_vibecode_monitor.py` — PASS (210 passed)
- No replay/docs test paths changed; existing assertions unaffected.
