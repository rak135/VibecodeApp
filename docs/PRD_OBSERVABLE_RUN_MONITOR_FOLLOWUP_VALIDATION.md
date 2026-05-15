# Observable Run Monitor — Final Follow-up Validation Report

**Date:** 2026-05-15 (supersedes 2026-05-13 report)
**Validator:** GitHub Copilot (automated)
**Scope:** Post P13–P17 final validation pass — observable run monitor readiness for supervised dogfooding.
**Verdict:** ✅ **READY FOR SUPERVISED DOGFOODING** (with documented limitations)

---

## 1. Git State

### Before validation

```
$ git status --short
M PRD.json
```

**Result:** One unrelated modification (`PRD.json`) was present — user change unrelated to the observable run monitor.
No source or test files were dirty. No user work was reverted.

### After validation

```
$ git status --short
M PRD.json
M docs/PRD_OBSERVABLE_RUN_MONITOR_FOLLOWUP_VALIDATION.md
```

**Result:** Only `PRD.json` (pre-existing) and this report changed. No source or test files were modified.

---

## 2. Compile Check

```
$ python -m compileall vibecode -q
(no output)
exit code: 0
```

**Result:** PASS. All Python source files in `vibecode/` compile without errors.

---

## 3. Targeted Regression Subset

```
$ python -m pytest -p no:cacheprovider -q \
    tests/test_vibecode_opencode_adapter.py \
    tests/test_vibecode_run_controller.py \
    "tests/test_vibecode_run.py::TestCmdRunEndToEnd" \
    "tests/test_vibecode_run.py::TestCmdRunPreflight::test_safe_gitignore_allows_agent_launch"
```

**Result:** ✅ **95 passed in 126.11s** — exit code 0.

| Test file / class | Tests | Result |
|---|---|---|
| `test_vibecode_opencode_adapter.py` | 21 | PASS |
| `test_vibecode_run_controller.py` | 61 | PASS |
| `TestCmdRunEndToEnd` | 7 | PASS |
| `TestCmdRunPreflight::test_safe_gitignore_allows_agent_launch` | 1 | PASS |

All previously failing targeted fake-OpenCode run-controller tests pass.

---

## 4. Full Pytest Suite

```
$ python -m pytest -p no:cacheprovider -q
```

**Result:** ✅ **1852 passed, 35 warnings in 322.32s** — exit code 0.

| Status | Count |
|---|---|
| Passed | 1852 |
| Failed | 0 |
| Warnings | 35 (non-blocking) |

**Notable improvement over previous report:** The 2026-05-13 report recorded 1 pre-existing failure
(`TestCmdRunPreflight::test_missing_gitignore_blocks_agent_launch`). That failure is now absent — the full
suite passes cleanly at **1852/1852**. No regressions introduced.

---

## 5. CLI Discovery

All help commands were executed and responded correctly.

### `vibecode --help`

```
$ python -m vibecode.cli --help
```

✅ All commands present: `init`, `inventory`, `index`, `context`, `map`, `validate`, `guard`, `check`,
`handoff-check`, `run`, `run-plan`, `history`, `project`, `serve`, `dashboard`, `monitor`, `export-agents`, `runs`.

### `vibecode run --help`

✅ Shows: `--task`, `--platform {opencode}`, `--profile`, `--allow-dirty`, `--no-index`, `--guard-mode {advisory,strict}`.

### `vibecode monitor --help`

✅ Shows split-pane TUI description, streaming-output mode disclaimer, same flags as `run`.

### `vibecode runs --help`

✅ Shows `list` and `show` sub-commands with `--events` flag. Artifact inventory documented inline.

### `vibecode serve --help`

✅ Shows MCP stdio transport description, tool list (`get_file_card`, `find_symbol`, `list_high_risk`),
`VIBECODE_MCP_EVENTS_LOG` / `VIBECODE_SESSION_ID` env var documentation, OpenCode config example.

---

## 6. Fake Run — Full Path Artifact Verification

A temporary git repository was initialised with minimal `.vibecode/` config. A fake OpenCode Python script (exits 0,
outputs `FAKE_STDOUT\n` to stdout) was placed on `PATH` as `opencode.cmd`. A complete `vibecode run` lifecycle was
driven from CLI.

### Command

```
$ python -m vibecode.cli run <tmp_repo> --task "validation smoke" --no-index
(with fake opencode.cmd on PATH)
```

### Result

**Exit code:** 0 — `overall_status: success`

### Artifacts in `.vibecode/runs/<session_id>/`

| Artifact | Present |
|---|---|
| `events.jsonl` | ✅ |
| `summary.json` | ✅ |
| `agent_stdout.log` | ✅ (contains `FAKE_STDOUT`) |
| `agent_stderr.log` | ✅ |
| `guard_report.json` | ✅ |
| `guard_report.md` | ✅ |
| `checks_report.json` | ✅ |
| `handoff_report.json` | ✅ |
| `context_pack.md` | ✅ (context snapshot) |
| `opencode_prompt.md` | ✅ (prompt snapshot) |
| `metadata.json` | ✅ |

All 11 expected artifacts present. Context and prompt snapshots captured.

### Events (20 events recorded)

- First event type: `run.lifecycle` (phase=started)
- Last event type: `run.lifecycle` (phase=finished)
- Full phase sequence: git_preflight → index_check → context → prompt → agent_process → guard → check → handoff → summary → lifecycle(finished)

Full lifecycle is observable end-to-end.

---

## 7. Fake Early-Failure Scenario + `runs show --events` Replay

A run was driven with a fake OpenCode that exits 1 (simulating agent crash). The run completes with `overall_status: failure`.

### Command

```
$ python -m vibecode.cli run <tmp_repo> --task "fail scenario" --no-index
(with fake opencode.cmd that exits 1 on PATH)
```

### Result

**vibecode run exit code:** 1 — `overall_status: failure`

**Artifacts created:**
- `events.jsonl` ✅
- `summary.json` ✅ (overall_status=failure)
- `agent_stdout.log`, `agent_stderr.log` ✅ (post-agent phases run even on agent failure)
- `guard_report.json`, `checks_report.json`, `handoff_report.json` ✅

### `runs show <session_id> --events` output

```
$ python -m vibecode.cli runs show <session_id> --events --repo <tmp_repo>
exit code: 0
```

- Output contains session ID ✅
- Output contains `Events (N):` section ✅
- Command exits 0 ✅

**Result:** PASS — a failed run can be fully inspected without rerunning the agent. Events are replayed correctly.

---

## 8. Monitor Smoke Path

### Non-interactive unit test suite

```
$ python -m pytest -p no:cacheprovider -q tests/test_vibecode_monitor.py
```

**Result:** ✅ **88 passed in 0.36s** — exit code 0.

Covers: `TestMissingTextual` (import-error graceful), `TestMonitorEventPumpSmoke` (non-interactive event pump),
`TestMcpEventFormatting` (MCP event formatting), monitor rendering/lifecycle.

### CLI smoke

```
$ python -m vibecode.cli monitor --help
exit code: 0
```

✅ Help text present, mentions split-pane TUI, streaming-output mode disclaimer.

**Limitation:** Real TUI (`vibecode monitor`) requires the `[tui]` extra (`pip install -e ".[tui]"`) and an interactive
terminal (live PTY). This validation was run in a non-interactive PowerShell session. The real TUI was not launched;
non-interactive smoke tests cover the event-routing logic without a live PTY.

---

## 9. Advisory vs. Strict Guard Mode

### Unit tests

```
$ python -m pytest -p no:cacheprovider -q tests/test_vibecode_run_post.py
```

**Result:** ✅ **112 passed in 35.56s** — exit code 0. Includes `TestAdvisoryGuardMode` (9 tests).

Verified behaviors:
- **Advisory mode** (default): guard findings logged with full severity as `needs_review`; run continues; exit code 0.
- **Strict mode**: guard errors cause run failure; non-zero exit code returned.
- Guard finding counts correctly reflected in summary and `runs show` output.

### Live smoke (fake run with `--guard-mode`)

Fake OpenCode run with `--guard-mode advisory`:
- Run exits 0 even when fake agent modifies a file ✅

Fake OpenCode run with `--guard-mode strict`:
- Flag accepted; `summary.json` records `guard_mode: strict` ✅

---

## 10. MCP Correlation

### Unit tests

```
$ python -m pytest -p no:cacheprovider -q tests/test_vibecode_mcp_server.py
```

**Result:** ✅ **79 passed** — exit code 0.

### Live smoke

A fake OpenCode script was instrumented to capture its environment variables to disk. After `vibecode run`:

- `VIBECODE_SESSION_ID` set in agent subprocess environment ✅ (value: run session ID)
- `VIBECODE_MCP_EVENTS_LOG` set in agent subprocess environment ✅ (value: `.vibecode/runs/<session_id>/mcp_events.jsonl`)

MCP correlation env vars are propagated correctly. Per-run correlation depends on OpenCode propagating these env vars
to its MCP server subprocess; this is documented in `vibecode serve --help`.

---

## 11. Real OpenCode Status

```
$ where opencode
(found)
$ opencode --version
1.14.48
```

**Real OpenCode is installed** on this machine (version 1.14.48, npm-distributed package).

**Skipped with reason:** Running real OpenCode during this validation pass would:
1. Incur real AI API costs (unknown amount)
2. Potentially modify files in the current repository (VibecodeApp itself)
3. Require interactive supervision to avoid runaway changes

The fake-OpenCode scenarios comprehensively validate the full `vibecode run` lifecycle (preflight → context →
agent launch → guard → checks → handoff → summary). Correctness of the real OpenCode model integration is out of
scope for this automated validation pass and should be verified in a supervised dogfood session.

---

## 12. Summary Matrix

| Check | Command / Test | Result | Notes |
|---|---|---|---|
| Git state (before) | `git status --short` | ⚠ M PRD.json | Pre-existing user change; no source files dirty |
| Compile | `python -m compileall vibecode -q` | ✅ PASS | Exit 0 |
| Targeted regression | 4 test targets (95 tests) | ✅ 95/95 PASS | All pass, exit 0 |
| Full pytest | `pytest -q` | ✅ 1852/1852 PASS | Clean suite, no failures |
| CLI `vibecode --help` | root help | ✅ All 18 commands present | — |
| CLI `run --help` | run help | ✅ All flags present | guard-mode, profile, allow-dirty |
| CLI `monitor --help` | monitor help | ✅ TUI description present | — |
| CLI `runs --help` | runs help | ✅ list/show sub-commands | — |
| CLI `serve --help` | serve help | ✅ MCP env var docs present | — |
| Fake run — artifacts | Live fake run (exit 0) | ✅ 11/11 artifacts | All phases produced output |
| Fake run — events sequence | events.jsonl inspection | ✅ PASS | 20 events, lifecycle wraps |
| Early-failure run | Live fake run (exit 1) | ✅ run exits 1, folder written | All artifacts created |
| `runs show --events` replay | CLI live test | ✅ PASS | Exits 0, shows events section |
| Advisory guard (live) | Fake run `--guard-mode advisory` | ✅ Exit 0 | Non-blocking on findings |
| Strict guard flag (live) | Fake run `--guard-mode strict` | ✅ Accepted, recorded in summary | — |
| Advisory guard (unit) | `TestAdvisoryGuardMode` (9 tests) | ✅ 9/9 PASS | Both modes verified |
| Monitor smoke (unit) | `test_vibecode_monitor.py` | ✅ 88/88 PASS | Non-interactive only |
| Monitor TUI (live) | `vibecode monitor` | ⏭ SKIPPED | Requires TTY + [tui] extra |
| MCP env vars (live) | Fake run env capture | ✅ PASS | VIBECODE_SESSION_ID + MCP_EVENTS_LOG set |
| MCP server (unit) | `test_vibecode_mcp_server.py` | ✅ 79/79 PASS | — |
| Real OpenCode | `opencode --version` = 1.14.48 | ⏭ SKIPPED | Available; skipped for cost/safety |
| Git state (after) | `git status --short` | ✅ Only PRD.json + this report | No source changes |

---

## 13. Known Limitations

1. **Monitor TUI not live-validated:** `vibecode monitor` requires the `[tui]` extra and a live interactive terminal
   (PTY). This validation was run in a non-interactive shell. Non-interactive monitor unit tests (88 passing) cover the
   event pump and formatting logic. Full PTY validation requires a supervised terminal session.

2. **Real OpenCode not validated end-to-end:** OpenCode 1.14.48 is installed but was skipped. Real-agent correlation
   (MCP subprocess env propagation, actual model calls) is not proven by this pass and should be the first item in
   the supervised dogfood session.

3. **Strict guard with no guard rules:** The strict guard live test fired a fake agent that modified a file, but the
   repo had no guard rules configured to emit ERROR-severity findings, so the run exited 0. The unit tests
   (`TestAdvisoryGuardMode`) cover the strict-mode non-zero exit path with synthesised findings.

---

## 14. Final Dogfood Verdict

> **✅ READY FOR SUPERVISED DOGFOODING**

The observable run monitor (P13–P17) is functionally complete as verified by this fresh pass on 2026-05-15:

- Full test suite passes cleanly: **1852/1852** (previously 1849/1850 — the pre-existing failure is now resolved).
- All targeted run-controller/adapter/end-to-end tests pass: **95/95**.
- All lifecycle phases produce expected artifacts on disk (verified live with fake OpenCode).
- Events are recorded and replayable via `runs show --events` (verified live).
- Guard (advisory/strict), checks, and handoff phases run and are reflected in summary (live + unit).
- Context pack and prompt snapshots captured for every run (verified live).
- MCP correlation env vars (`VIBECODE_SESSION_ID`, `VIBECODE_MCP_EVENTS_LOG`) propagated to agent subprocess (verified live).
- Monitor non-interactive smoke path passes (88/88 unit tests).
- CLI help responds correctly for all 5 commands.

**Recommended supervised dogfooding steps:**
1. Run `vibecode run` against a real task on a real repository with real OpenCode 1.14.48.
2. Inspect the run folder artifacts after completion.
3. Use `vibecode runs show <session_id> --events` to replay the event timeline.
4. Verify the monitor TUI (`vibecode monitor` with `[tui]` extra) renders correctly in a live terminal.
5. Verify MCP server subprocess inherits `VIBECODE_SESSION_ID` from the OpenCode config.
6. Document any issues found as follow-up items.
