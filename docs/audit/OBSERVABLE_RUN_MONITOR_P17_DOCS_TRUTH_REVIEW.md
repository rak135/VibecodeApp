# P17.1 Documentation Truth Review

Status: FIX REQUIRED.

This review checked the P17.1 documentation against current source, CLI help, dependency metadata, and run artifact writers. It does not rely on prior audit reports.

## Findings

### 1. `vibecode runs --help` still claims `handoff_report.*`

`vibecode runs --help` says each run directory contains `handoff_report.*`. That is not true for artifacts written by the current run controller.

Evidence inspected:

- `vibecode/cli.py`, `runs` parser description, lines 458-470: lists `handoff_report.*`.
- Actual command output from `python -m vibecode.cli runs --help`: "Each run directory contains: summary.json, events.jsonl, guard_report.*, checks_report.json, handoff_report.*, agent_stdout.log, agent_stderr.log."
- `vibecode/run.py`, per-session report persistence, lines 1119-1139: writes `guard_report.json`, attempts `guard_report.md`, writes `checks_report.json`, and writes only `handoff_report.json`.
- `vibecode/session_log.py`, artifact path properties, lines 105-112: defines both `handoff_report_json` and `handoff_report_md`, but `rg "handoff_report_md|handoff_report\\.\\*"` shows no `run.py` writer for `handoff_report.md`.
- `vibecode/show_run.py`, lines 119-133: recognizes `handoff_report.md` only if it happens to exist.

README and Quickstart correctly avoid listing `handoff_report.md` as an expected run artifact, but the `runs` CLI help remains stale.

### 2. README and Quickstart artifact trees imply conditional files are always present

The prose says every `vibecode run` / `vibecode monitor` creates a session directory and then shows a tree with reports, prompt/context snapshots, and agent logs. In code, early aborts create durable `events.jsonl` and `summary.json`, but many listed files are written only after later phases succeed or start.

Evidence inspected:

- `README.md`, "Where run artifacts are written", lines 363-380: lists `metadata.json`, guard reports, checks report, handoff report, prompt/context snapshots, and agent logs under "Every `vibecode run` / `vibecode monitor` creates a session directory".
- `docs/QUICKSTART.md`, Step 9b, lines 417-432: same unconditional-looking artifact tree.
- `docs/QUICKSTART.md`, troubleshooting/session artifact summary, lines 609-625: says "The session directory contains" the same broad list.
- `vibecode/run.py`, lines 532-535: creates the per-run event sink immediately.
- `vibecode/run.py`, `_write_abort_summary`, lines 225-265: early abort path writes only minimal `summary.json`.
- `vibecode/run.py`, early returns at lines 549-559, 561-572, 662-678, 680-688, 730-738, 743-751, and 802-820 show aborts can happen before prompt snapshots, agent logs, guard/check/handoff reports, or final metadata exist.
- `vibecode/run.py`, lines 758-780: prompt/context snapshots happen only after context generation succeeds.
- `vibecode/run.py`, lines 903-917: agent stdout/stderr logs are attached only when launching the agent process.
- `vibecode/run.py`, lines 1116-1139: guard/check/handoff reports are conditional on those results existing.

The docs should distinguish always-written artifacts (`events.jsonl` and `summary.json` for observable attempts) from conditional artifacts.

### 3. `serve --help` overstates automatic per-run MCP correlation

README documents MCP correlation with the right caveat: OpenCode must propagate `VIBECODE_SESSION_ID` and `VIBECODE_MCP_EVENTS_LOG` to the MCP server subprocess. The actual `serve --help` text omits that caveat and says `vibecode run` and `vibecode monitor` set both variables automatically for per-run MCP correlation.

Evidence inspected:

- `README.md`, "MCP observability", lines 399-403: accurately says per-run logging depends on OpenCode propagating the environment variables, and live streaming from the agent side process is not implemented.
- `vibecode/cli.py`, `serve` help description, lines 342-348: says run/monitor set both variables automatically for per-run MCP correlation, without the propagation qualification.
- Actual command output from `python -m vibecode.cli serve --help`: repeats that unqualified claim.
- `vibecode/run.py`, lines 903-908: injects the variables into the OpenCode child process environment.
- `vibecode/mcp_server.py`, lines 373-379: `cmd_serve()` reads those variables only from its own process environment and otherwise falls back to `.vibecode/logs/mcp_events.jsonl`.

This is a docs/help-text truth issue, not an implementation defect.

## Truth Checks That Passed

- Optional dependency docs are accurate in README, Quickstart, AGENTS, and the generated AGENTS template:
  - `pyproject.toml`, lines 10-15: plain dependencies are only `pyyaml>=6.0`; `[tui]` adds `textual>=0.47`; `[mcp]` adds `mcp>=1.0`; `[all]` adds both.
  - `README.md`, install section, lines 68-74; dashboard and serve sections, lines 239-260; monitor section, lines 324-331.
  - `docs/QUICKSTART.md`, install section, lines 46-54; monitor section, lines 371-389; dashboard/serve sections, lines 486-513.
  - `AGENTS.md`, command list, lines 45-54.
  - `vibecode/context/agents_export.py`, rendered command list, lines 61-80.

- AGENTS and generated AGENTS template agree:
  - `AGENTS.md`, managed block, lines 1-55.
  - `vibecode/context/agents_export.py`, `render_agents_block()` command text, lines 49-80.
  - Direct check: the content inside the AGENTS managed markers matches `render_agents_block()` exactly.

- Advisory guard documentation preserves severity truth:
  - `README.md`, lines 354-361: advisory mode logs full severity and writes guard reports while returning `needs_review` with exit code 0.
  - `docs/QUICKSTART.md`, lines 362-368: advisory logs findings but does not block; strict causes failure/exit code 1.
  - `vibecode/run.py`, lines 112-134 and 1150-1171: `guard_mode` is recorded and advisory guard failures become `needs_review`, while strict guard failures become `failure`.
  - `tests/test_vibecode_run_post.py`, lines 1424-1431: asserts advisory findings and severity are preserved.

- Monitor docs match actual help for the important operational limitation:
  - `README.md`, lines 328-342 and `docs/QUICKSTART.md`, lines 375-389: two-pane streaming-output monitor, not a PTY.
  - Actual `python -m vibecode.cli monitor --help`: says it is streaming-output text mode, not a PTY.

## Sections And Commands Inspected

Source/docs:

- `README.md`: install extras, Daily use with OpenCode, Observable run monitor, Advisory vs strict guard mode, run artifact paths, MCP observability.
- `docs/QUICKSTART.md`: install extras, command list, Step 8 run, Step 8b monitor, Step 9b runs inspection, Daily use with OpenCode, troubleshooting/session artifacts, `.vibecode/` structure reference.
- `AGENTS.md`: managed block, Do not manually edit, Available commands.
- `vibecode/context/agents_export.py`: `render_agents_block()` generated command list.
- `pyproject.toml`: `[project] dependencies`, `[project.optional-dependencies]`, `[project.scripts]`.
- `vibecode/cli.py`: parser descriptions for `serve`, `monitor`, and `runs`.
- `vibecode/session_log.py`: `RunSession` artifact path properties.
- `vibecode/run.py`: abort summary writer, run artifact creation, prompt/context snapshots, MCP env injection, report persistence, run summary status logic.
- `vibecode/show_run.py`: recognized artifact paths for `runs show`.
- `vibecode/mcp_server.py`: `cmd_serve()` environment and log-path handling.

CLI help executed:

- `python -m vibecode.cli --help` - pass.
- `python -m vibecode.cli run --help` - pass.
- `python -m vibecode.cli monitor --help` - pass.
- `python -m vibecode.cli runs --help` - pass, but stale `handoff_report.*` claim found.
- `python -m vibecode.cli runs list --help` - pass.
- `python -m vibecode.cli runs show --help` - pass.
- `python -m vibecode.cli serve --help` - pass, but MCP correlation wording is too absolute.
- `python -m vibecode.cli index --help` - pass.
- `python -m vibecode.cli context --help` - pass.

## Tests And Lint

- `python -m pytest`
  - FAIL: pytest cannot access `C:\Users\Martin\AppData\Local\Temp\pytest-of-Martin` (`PermissionError: [WinError 5]`).

- `python -m pytest --basetemp C:\tmp\pytest-vibecode-p17-docs-review`
  - FAIL: sandbox denies creation under `C:\tmp`.

- `python -m pytest --basetemp .pytest-tmp-p17-docs-review`
  - FAIL: pytest cannot remove/read the workspace temp directory after creation (`PermissionError: [WinError 5]`).

- `python -m pytest tests/test_vibecode_agents_export.py tests/test_vibecode_quickstart.py tests/test_vibecode_cli.py --basetemp pytest_tmp_p17_docs_review_fresh_002`
  - FAIL: same pytest temp-directory permission failure; tests that do not require `tmp_path` did run before the crash.

- `python -m ruff check vibecode`
  - PASS: all source checks passed. Ruff cache write emitted an access-denied warning for `.ruff_cache`.

- `python -m ruff check vibecode tests`
  - FAIL: 43 existing test lint findings, including unused imports, ambiguous variable names, and `tests/test_vibecode_project_cli.py:243` undefined `Path`. No reviewed docs or implementation files were modified.

- `python -m vibecode.cli validate .`
  - PASS.

- `python -m vibecode.cli guard .`
  - PASS: guard check found no violations.

- `python -m vibecode.cli check .`
  - FAIL: `unit tests` failed with exit code 1 after 228.734s; `cli help`, `index command help`, and `context command help` passed.

No new tests were added because this task explicitly constrained changes to the review document only.
