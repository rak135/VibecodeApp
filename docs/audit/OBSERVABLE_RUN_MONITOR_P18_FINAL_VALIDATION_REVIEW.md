# Observable Run Monitor P18.1 Final Validation Review

**Date:** 2026-05-15
**Scope:** Review `docs/PRD_OBSERVABLE_RUN_MONITOR_FOLLOWUP_VALIDATION.md`, current code/tests where needed, CLI help output, and preserved run artifacts.

## Verdict

**PASS WITH CORRECTIONS.**

The core readiness claim is supported by fresh evidence in the current workspace:

- targeted fake-OpenCode regression coverage passes,
- full pytest passes at **1852 passed, 35 warnings**,
- monitor and MCP suites pass,
- CLI help output matches the documented surface,
- preserved successful and failure run artifacts replay through `vibecode runs show --events`.

I found one material report mismatch: section 9 of the validation report says `tests/test_vibecode_run_post.py` produced **112 passed**. A fresh rerun in the current tree produced **52 passed in 41.66s**. That is a documentation/evidence error, not a product failure, but the report should not present `112 passed` as current proof.

I also found one operational gap outside the report text itself: `python -m vibecode.cli check .` currently fails because the required `python -m pytest` step times out after **300 seconds**, while the full suite now needs **334.88 seconds**. The product code under review still passes the explicit full-suite audit run; the failure is in the required-check wrapper budget.

No implementation files were modified in this review.

## Findings

### 1. Targeted fake OpenCode regression proof is real

Fresh command:

```text
python -m pytest -p no:cacheprovider -q tests/test_vibecode_opencode_adapter.py tests/test_vibecode_run_controller.py "tests/test_vibecode_run.py::TestCmdRunEndToEnd" "tests/test_vibecode_run.py::TestCmdRunPreflight::test_safe_gitignore_allows_agent_launch"
95 passed in 133.50s (0:02:13)
```

Current test code confirms this is not parser-only coverage:

- `tests/test_vibecode_run_controller.py:465-542` writes a fake `opencode.cmd`, captures argv/stdin, edits a file, and asserts `agent_stdout.log`, `agent_stderr.log`, `summary.json`, `context_pack.md`, `opencode_prompt.md`, and `events.jsonl`.
- The same test asserts `json.loads(argv_capture.read_text(...)) == ["run"]`, proving the fake command is actually launched as `opencode run`.
- `tests/test_vibecode_run_controller.py:1131-1151` also proves agent stdin exactly matches the prompt snapshot written to disk.

### 2. Replayability is proven for both success and failure paths

Preserved successful run sample:

```text
python -m vibecode.cli runs show 20260512T051751673320Z --repo . --events
```

Fresh replay output shows:

- **11 artifacts** listed, including `summary.json`, `metadata.json`, `events.jsonl`, `guard_report.json`, `guard_report.md`, `checks_report.json`, `handoff_report.json`, `agent_stdout.log`, `agent_stderr.log`, `context_pack.md`, and `opencode_prompt.md`
- **Events (22)**
- `Agent started: opencode run`
- `VIBECODE_REAL_OPENCODE_SMOKE_OK`
- `Agent finished (exit_code=0)`

Preserved failure run sample:

```text
python -m vibecode.cli runs show 20260512T052734396950Z --repo . --events
```

Fresh replay output shows:

- **11 artifacts** listed again
- **Events (260)**
- `Agent status : failure`
- `Overall      : failure`
- replay still works through the full stored event log

The exact fake early-failure artifact sample from the validation report is not preserved by session ID in the repo, so I could not replay that exact sample folder. Current regression coverage still proves the early-abort/failure replay path:

```text
python -m pytest -p no:cacheprovider -q tests/test_vibecode_run_controller.py::TestEarlyAbortArtifacts tests/test_vibecode_show_run.py::TestEarlyAbortShowCLI
18 passed in 8.44s
```

Supporting code evidence:

- `tests/test_vibecode_run_controller.py:1159-1188` verifies early-abort runs still write durable `events.jsonl`.
- `tests/test_vibecode_show_run.py:824-873` verifies `runs show --events` succeeds for abort summaries and prints replayed abort events.

### 3. Monitor smoke coverage is deeper than parser registration

Fresh command:

```text
python -m pytest -p no:cacheprovider -q tests/test_vibecode_monitor.py
88 passed in 0.37s
```

Code evidence:

- `tests/test_vibecode_monitor.py:876-930` (`TestMonitorEventPumpSmoke`) routes `run.agent_process` events into the agent pane and `run.lifecycle` / `run.guard` events into the event pane through `TUIEventSink`, `route_event`, `format_agent_line`, and `format_vibecode_line`.

This directly checks the event-routing spine. It is not limited to CLI parser registration.

**Live monitor smoke:** not rerun in this review. The skip reason remains valid: this session is a non-interactive PowerShell environment, while `vibecode monitor` is a split-pane TUI intended for a live terminal session.

### 4. Advisory/strict guard behavior is tested, but the report's count is stale

Fresh command:

```text
python -m pytest -p no:cacheprovider -q tests/test_vibecode_run_post.py
52 passed in 41.66s
```

This materially supports the guard-mode claim, and `tests/test_vibecode_run_post.py:1345-1435` still contains `TestAdvisoryGuardMode` coverage for:

- advisory default,
- advisory `needs_review`,
- strict failure behavior,
- exit code mapping,
- preserved guard findings.

**Finding:** the validation report's `112 passed` figure for this suite is not accurate for the current codebase. The behavioral claim is supported; the numeric evidence is not.

### 5. MCP/session correlation claims are backed by code and passing tests

Fresh command:

```text
python -m pytest -p no:cacheprovider -q tests/test_vibecode_mcp_server.py
79 passed in 1.16s
```

Fresh code review confirms:

- `vibecode/run.py:925-931` injects `VIBECODE_SESSION_ID` and `VIBECODE_MCP_EVENTS_LOG` into the child environment before launching the agent.
- `tests/test_vibecode_run_controller.py:1660-1761` captures those env vars from fake OpenCode and asserts the session id and per-run `mcp_events.jsonl` path.
- `tests/test_vibecode_mcp_server.py:485-547` verifies `cmd_serve()` consumes `VIBECODE_MCP_EVENTS_LOG` and `VIBECODE_SESSION_ID` correctly.
- `python -m vibecode.cli serve --help` still documents both env vars and the OpenCode MCP snippet.

### 6. CLI discovery claims are current

Fresh help output confirms:

- `python -m vibecode.cli --help` lists `init`, `inventory`, `index`, `context`, `map`, `validate`, `guard`, `check`, `handoff-check`, `run`, `run-plan`, `history`, `project`, `serve`, `dashboard`, `monitor`, `export-agents`, `runs`
- `python -m vibecode.cli run --help` shows `--guard-mode {advisory,strict}`
- `python -m vibecode.cli monitor --help` describes the split-pane streaming monitor and explicitly says it is **not a PTY**
- `python -m vibecode.cli runs --help` shows `list` / `show` and `--events`
- `python -m vibecode.cli serve --help` documents `VIBECODE_MCP_EVENTS_LOG` and `VIBECODE_SESSION_ID`
- `python -m vibecode.cli index --help` and `python -m vibecode.cli context --help` both return cleanly

### 7. Full-suite readiness evidence is fresh

Fresh command:

```text
python -m pytest -p no:cacheprovider -q
1852 passed, 35 warnings in 334.88s (0:05:34)
```

This matches the validation report's headline full-suite claim.

### 8. Real OpenCode smoke was not rerun, but preserved evidence remains replayable

I did **not** launch a new real OpenCode run in this review session.

Honest skip reason:

1. it would invoke an external model/tool outside the scope of this doc-only audit,
2. it can incur real cost,
3. it can still modify the repository if the agent misbehaves.

What is still evidenced in-repo:

- `docs/audit/OBSERVABLE_RUN_MONITOR_REAL_OPENCODE_SMOKE.md` documents one successful real smoke and one timed-out failure smoke,
- both corresponding run directories still replay today through `vibecode runs show --events`.

That is enough to support the validation report's **skip with reason** posture, but not enough to treat a fresh real-OpenCode smoke as re-executed today.

### 9. Required checks are not currently green via `vibecode check`

Fresh command:

```text
python -m vibecode.cli check .
FAIL: unit tests (exit code 1, 328.515s)
PASS: cli help (exit code 0, 0.078s)
PASS: index command help (exit code 0, 0.079s)
PASS: context command help (exit code 0, 0.078s)
```

`.vibecode/current/check_results.json` records the unit-test failure as:

```text
Command timed out after 300 seconds
```

This does **not** contradict the explicit audit rerun:

```text
python -m pytest -p no:cacheprovider -q
1852 passed, 35 warnings in 334.88s (0:05:34)
```

It does mean the repository's required-check wrapper is currently stricter than the observed suite runtime.

## Overall Assessment of the Validation Report

The report is **substantially credible** and its dogfood-readiness conclusion is still supported by current code/tests and preserved artifacts. The main correction needed is narrower:

- keep the readiness verdict,
- correct the `tests/test_vibecode_run_post.py` evidence from `112 passed` to the current passing result,
- avoid implying that the exact fake early-failure artifact sample is still available for direct replay unless a session ID or artifact folder is preserved,
- note that `vibecode check .` is not currently green because the unit-test timeout is below the observed full-suite runtime.

## Commands Run

```text
python -m vibecode.cli validate
python -m vibecode.cli context . --task "Review P18.1 validation report and produce final validation review"
git --no-pager status --short
python -m vibecode.cli --help
python -m vibecode.cli run --help
python -m vibecode.cli monitor --help
python -m vibecode.cli runs --help
python -m vibecode.cli serve --help
python -m vibecode.cli index --help
python -m vibecode.cli context --help
python -m vibecode.cli runs show 20260512T051751673320Z --repo . --events
python -m vibecode.cli runs show 20260512T052734396950Z --repo . --events
python -m pytest -p no:cacheprovider -q tests/test_vibecode_opencode_adapter.py tests/test_vibecode_run_controller.py "tests/test_vibecode_run.py::TestCmdRunEndToEnd" "tests/test_vibecode_run.py::TestCmdRunPreflight::test_safe_gitignore_allows_agent_launch"
python -m pytest -p no:cacheprovider -q tests/test_vibecode_run_controller.py::TestEarlyAbortArtifacts tests/test_vibecode_show_run.py::TestEarlyAbortShowCLI
python -m pytest -p no:cacheprovider -q tests/test_vibecode_monitor.py
python -m pytest -p no:cacheprovider -q tests/test_vibecode_run_post.py
python -m pytest -p no:cacheprovider -q tests/test_vibecode_mcp_server.py
python -m pytest -p no:cacheprovider -q
python -m vibecode.cli check .
```

## Final Git Status

Before review commands: clean working tree (`git --no-pager status --short` produced no file entries).

After writing this review and running the audit commands:

```text
M docs/audit/OBSERVABLE_RUN_MONITOR_P18_FINAL_VALIDATION_REVIEW.md
```

Remaining dirt is expected and task-related only.
