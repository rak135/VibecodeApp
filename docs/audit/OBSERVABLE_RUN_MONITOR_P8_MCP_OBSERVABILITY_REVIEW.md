# Observable Run Monitor P8 MCP Observability Review

Generated: 2026-05-12

## Verdict

PASS WITH FIXES RECOMMENDED. MCP tool observability is implemented in the normal `vibecode serve` path: calls, returns, and failures emit `run.mcp` events, and `cmd_serve()` writes those events to `.vibecode/logs/mcp_events.jsonl`. Result payloads are compact and do not include full tool responses.

Two follow-ups should be handled before treating this as fully polished: MCP session correlation is best-effort and is only documented in code docstrings, not the user-facing CLI/docs path; and the focused MCP test file is not Ruff-clean.

This review did not modify implementation or test files. The task scope allowed only this review document.

## Findings

### PASS: tool calls, returns, and failures are visible

`VibecodeServer._emit()` creates `run.mcp` events with the configured `session_id`, INFO level for normal events, and ERROR level for failures (`vibecode/mcp_server.py:77`). Each public tool method emits a `McpToolCalled` event before execution and a `McpToolReturned` event after success (`vibecode/mcp_server.py:207`, `vibecode/mcp_server.py:233`, `vibecode/mcp_server.py:255`).

Failure logging is present for all three tools. Exceptions from `_get_file_card`, `_find_symbol`, and `_list_high_risk` emit `McpToolFailed` with `error` and `error_type`, then re-raise the original exception (`vibecode/mcp_server.py:217`, `vibecode/mcp_server.py:244`, `vibecode/mcp_server.py:268`).

`cmd_serve()` passes `.vibecode/logs/mcp_events.jsonl` into `build_mcp_server()`, so normal MCP server usage has a durable JSONL event stream (`vibecode/mcp_server.py:368`).

### PASS: result payloads are compact

Return events record counts and sizes rather than full markdown responses:

- `get_file_card`: `found` and `result_chars` (`vibecode/mcp_server.py:223`).
- `find_symbol`: `match_count` and `result_chars` (`vibecode/mcp_server.py:250`).
- `list_high_risk`: `risk_count` and `result_chars` (`vibecode/mcp_server.py:274`).

This avoids dumping large file cards, snippets, facts, heuristics, symbol listings, or high-risk reports into the monitor event stream. The current payloads still include the caller-supplied `path` or `symbol`, which is useful context and much smaller than the result body.

Recommended hardening: add explicit no-raw-result assertions for `find_symbol` and `list_high_risk`, matching the existing `get_file_card` regression test.

### PASS WITH NOTE: session correlation is honest but best-effort

`VibecodeServer` accepts an explicit `session_id`, falls back to `VIBECODE_SESSION_ID`, then falls back to `"mcp-server"` (`vibecode/mcp_server.py:42`). `cmd_serve()` reads `VIBECODE_SESSION_ID` and forwards it into the MCP server builder (`vibecode/mcp_server.py:369`).

That is honest best-effort correlation. It does not automatically attach MCP events to `.vibecode/runs/<session_id>/events.jsonl`; MCP events are written to `.vibecode/logs/mcp_events.jsonl` with a matching `session_id` when the environment is set. A monitor can join those streams by `session_id`, but the implementation does not guarantee that an MCP server belongs to a specific `vibecode run` unless the launcher sets the environment correctly.

The best-effort model is documented in the `cmd_serve()` docstring (`vibecode/mcp_server.py:333`), but not in `vibecode serve --help`, `README.md`, or `docs/QUICKSTART.md`. Recommended fix: add one user-facing sentence saying MCP event correlation uses `VIBECODE_SESSION_ID` and otherwise falls back to the standalone `"mcp-server"` session.

### PASS: non-MCP CLI usage is not blocked by missing MCP runtime

The CLI imports `cmd_serve` only when `args.command == "serve"` (`vibecode/cli.py:545`, `vibecode/cli.py:548`). `vibecode/mcp_server.py` also defers `from mcp.server.fastmcp import FastMCP` until `build_mcp_server()` is called (`vibecode/mcp_server.py:298`). The base package dependencies do not include `mcp` (`pyproject.toml:10`), so this lazy import pattern is important.

That means ordinary commands such as `vibecode --help`, `index`, `context`, `guard`, and `check` can still import and dispatch without the MCP package. The current test `test_vibecode_server_does_not_require_mcp` covers `VibecodeServer` tool logic without preloaded MCP modules (`tests/test_vibecode_mcp_server.py:923`), but it does not install an import blocker. Recommended hardening: add a subprocess or import-hook test that proves `python -m vibecode.cli --help` and a representative non-MCP command still work when `mcp` imports fail.

### PASS WITH GAP: tests cover success and failure logging

Focused MCP logging tests cover:

- Called/returned events for all three tools (`tests/test_vibecode_mcp_server.py:628`, `tests/test_vibecode_mcp_server.py:663`, `tests/test_vibecode_mcp_server.py:698`).
- Failure event emission and exception re-raise for all three tools (`tests/test_vibecode_mcp_server.py:733`, `tests/test_vibecode_mcp_server.py:754`, `tests/test_vibecode_mcp_server.py:772`).
- Compact payload behavior for `get_file_card` (`tests/test_vibecode_mcp_server.py:792`).
- No-sink behavior, proving instrumentation remains optional (`tests/test_vibecode_mcp_server.py:817`).
- Explicit, environment, and fallback session ids (`tests/test_vibecode_mcp_server.py:830`, `tests/test_vibecode_mcp_server.py:840`, `tests/test_vibecode_mcp_server.py:855`).
- JSONL event file creation and called/returned persistence (`tests/test_vibecode_mcp_server.py:872`, `tests/test_vibecode_mcp_server.py:892`).

The main test gap is user-facing correlation documentation and stronger optional-dependency simulation. There is also no assertion that `cmd_serve()` passes the exact fallback `.vibecode/logs/mcp_events.jsonl` path and environment session id into `build_mcp_server()`; that would be a useful small integration test.

### FIX: focused Ruff check fails in MCP tests

Focused linting reports three `E741` failures in `tests/test_vibecode_mcp_server.py` where the variable name `l` is used in JSONL line comprehensions (`tests/test_vibecode_mcp_server.py:884`, `tests/test_vibecode_mcp_server.py:901`, `tests/test_vibecode_mcp_server.py:902`).

This is not an MCP observability behavior bug, but it blocks a clean lint result for the reviewed test file.

## Checks Run

- `python -m vibecode.cli context . --task "Review MCP observability"`
  - Result: passed; wrote `.vibecode/current/context_pack.md`.
- `python -m pytest tests/test_vibecode_mcp_server.py -p no:cacheprovider --basetemp .codex_pytest_mcp_review`
  - Result: failed due environment temp-directory permissions. Pytest collected 70 tests, some non-`tmp_path` tests ran, then pytest exited with `PermissionError: C:\DATA\PROJECTS\VibecodeApp\.codex_pytest_mcp_review` during session cleanup.
- `python -m ruff check --no-cache vibecode\mcp_server.py vibecode\events.py tests\test_vibecode_mcp_server.py`
  - Result: failed with three `E741` ambiguous variable name findings in `tests/test_vibecode_mcp_server.py`.
- `python -m vibecode.cli --help`
  - Result: passed.
- `python -m vibecode.cli serve --help`
  - Result: passed.
- `python -m vibecode.cli guard .`
  - Result: passed; no violations found.
- `python -m vibecode.cli validate .`
  - Result: passed with warning: `.vibecode/handoff/NOW.md` contains placeholder text.
- `python -m vibecode.cli handoff-check .`
  - Result: failed on existing `.vibecode/handoff/NOW.md` placeholder-text issue.
- `python -m vibecode.cli check .`
  - Result: failed because required `unit tests` exited 1 after 164.516s; required CLI help, index help, and context help checks passed.

## Changed Files

- `docs/audit/OBSERVABLE_RUN_MONITOR_P8_MCP_OBSERVABILITY_REVIEW.md`
