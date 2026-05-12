# P17 Documentation Truth Fix

Status: APPLIED.

## Changes Made

### 1. `vibecode/cli.py` — runs help: `handoff_report.*` → `handoff_report.json`

The `runs` parser description listed `handoff_report.*` as an expected run artifact, but the current run controller only writes `handoff_report.json`. Changed the help text to list `handoff_report.json` explicitly.

### 2. `vibecode/cli.py` — serve help: MCP correlation propagation caveat

The `serve` parser description stated that `vibecode run` and `vibecode monitor` set environment variables "automatically for per-run MCP correlation." Added the qualification that per-run correlation depends on OpenCode propagating the variables to the MCP server subprocess, matching the README's accurate caveat.

### 3. `README.md` — artifact tree: distinguish always vs conditional

The artifact tree under "Where run artifacts are written" listed all files unconditionally under "Every vibecode run / vibecode monitor creates a session directory." Added a note that `events.jsonl` and `summary.json` are always written, while other artifacts appear as their phases complete. Added a blockquote noting that an early abort only leaves those two files.

### 4. `docs/QUICKSTART.md` — artifact tree: same distinction

Applied the same always-vs-conditional clarification to the identical artifact tree in the Quickstart.

## Verification

- `python -m compileall vibecode -q` — PASS
- `python -m pytest -p no:cacheprovider -q tests/test_vibecode_quickstart.py tests/test_vibecode_agents_export.py` — 76 passed
- `python -m vibecode.cli runs --help` — now lists `handoff_report.json` (not `handoff_report.*`)
- `python -m vibecode.cli serve --help` — now includes propagation caveat
- `python -m vibecode.cli monitor --help` — unchanged (already correct)
- `python -m vibecode.cli run --help` — unchanged (already correct)
- AGENTS.md / agents_export.py — no mismatch (confirmed in review)

## No Changes Required

- AGENTS.md / agents_export.py: already matched (truth check passed in review)
- Optional dependency install guidance: already accurate (truth check passed in review)
- Advisory guard documentation: already accurate (truth check passed in review)
- Monitor docs: already accurate about streaming-text mode, not PTY (truth check passed in review)
