# P13-P18 Independent Completion Review

## Contamination controls

- Forbidden paths/patterns honored: `docs/audit/**`, `docs/*AUDIT*`, `docs/*DOGFOOD*`, `docs/*REVIEW*`, `docs/*FOLLOWUP*`, `docs/*VALIDATION*`, `docs/PRD_IMPLEMENTATION_INDEPENDENT_AUDIT.md`, `docs/PRD_FOLLOWUP_TASKS_ADDED.md`, `docs/PRD_P13_COMPLETION_AUDIT.md`, `.vibecode/runs/**`, `.vibecode/logs/**`, and `.pytest-tmp/**`.
- Inspected sources: `PRD.json`; source under `vibecode/**`; tests under `tests/**`; `pyproject.toml`; `.gitignore`; fresh CLI help output; for P17/P18 only, `README.md`, `docs/QUICKSTART.md`, `AGENTS.md`, and `vibecode/context/agents_export.py`.
- I did not read, open, grep, summarize, or rely on existing audit/review/dogfood/follow-up/status reports.

## Executive verdict

- Overall verdict: FAIL

The repository is close in many targeted areas, but it is not ready for a clean supervised dogfood baseline: full pytest fails, P14's early artifact creation dirties repos before the missing-`.gitignore` safety check can report the intended blocker, MCP truth is correlated to per-run side logs but not live-streamed into the monitor, and docs/CLI help still overstate some artifact behavior. Top risks: validation regression hidden outside targeted subsets, replay/artifact truth gaps for early failures, and operator confusion about MCP/monitor visibility.

## Command validation

| command | result | notes |
|---|---:|---|
| `git status --short` | PASS | Initial output empty. |
| `python -m compileall vibecode -q` | PASS | Exit 0. |
| `python -m pytest -p no:cacheprovider -q tests/test_vibecode_opencode_adapter.py` | PASS | `26 passed in 0.05s`. |
| `python -m pytest -p no:cacheprovider -q tests/test_vibecode_run_controller.py tests/test_vibecode_run.py::TestCmdRunEndToEnd tests/test_vibecode_run.py::TestCmdRunPreflight::test_safe_gitignore_allows_agent_launch` | PASS | `69 passed in 93.90s`. |
| `python -m pytest -p no:cacheprovider -q tests/test_vibecode_show_run.py tests/test_vibecode_session_log.py` | PASS | `98 passed in 0.49s`. |
| `python -m pytest -p no:cacheprovider -q tests/test_vibecode_mcp_server.py` | PASS | `79 passed in 1.41s`. |
| `python -m pytest -p no:cacheprovider -q tests/test_vibecode_monitor.py` | PASS | `88 passed in 0.36s`. |
| `python -m pytest -p no:cacheprovider -q tests/test_vibecode_quickstart.py tests/test_vibecode_agents_export.py` | PASS | `76 passed in 5.01s`. |
| `python -m pytest -p no:cacheprovider -q` | FAIL | `1 failed, 1849 passed, 35 warnings in 290.21s`; failing test: `tests/test_vibecode_run.py::TestCmdRunPreflight::test_missing_gitignore_blocks_agent_launch`. |
| `python -m vibecode.cli --help` | PASS | Exit 0; top-level command list rendered. |
| `python -m vibecode.cli run --help` | PASS | Exit 0; advisory/strict help rendered. |
| `python -m vibecode.cli monitor --help` | PASS | Exit 0; states streaming text, not PTY. Does not mention `[tui]` extra. |
| `python -m vibecode.cli runs --help` | PASS | Exit 0; overstates artifact presence by saying each run directory contains guard/check/handoff/log artifacts. |
| `python -m vibecode.cli serve --help` | PASS | Exit 0; describes MCP env correlation and propagation caveat. |
| `Get-Command opencode -ErrorAction SilentlyContinue` | PASS | Found `opencode.ps1` under npm roaming path. |
| `opencode --version` | PASS | Output: `1.14.48`. |
| `git status --short` | PASS | Output empty after validation, before writing this report. |

## Phase matrix

| phase | verdict | implementation evidence | test evidence | runtime evidence | gaps | severity | recommended action |
|---|---|---|---|---|---|---|---|
| P13 | PARTIAL | `vibecode/adapters/opencode.py` uses `shlex.split(default_cmd)[0]` before `shutil.which`; `run.py` passes `opencode run` to streaming runner. | Adapter tests and targeted run subset pass. | Compile/help pass; full suite exposes related preflight regression. | Full pytest failure shows clean validation baseline is not restored. | High | Fix missing-`.gitignore`/early-artifact ordering regression and rerun full suite. |
| P14 | PARTIAL | `RunController.execute()` creates `RunSession` and JSONL sink before prerequisites; `_write_abort_summary()` writes minimal summaries. | Early-abort tests cover missing config, invalid profile, dirty repo, missing index, inventory failure, replay. | `runs show` tests pass. | Abort summaries lack available artifact paths; early events can dirty a repo and mask missing-`.gitignore` diagnostics; not all requested failures are directly covered. | High | Reconcile early artifact durability with preflight safety/hygiene and enrich abort summaries. |
| P15 | PARTIAL | `run.py` injects `VIBECODE_SESSION_ID` and `VIBECODE_MCP_EVENTS_LOG`; `cmd_serve()` honors env log path/fallback; MCP events are compact. | MCP server, env propagation, and monitor formatting tests pass. | `serve --help` documents propagation caveat. | Live MCP streaming into monitor is not implemented; `runs show` does not list `mcp_events.jsonl`; limitation is not consistently present in Quickstart/AGENTS. | Medium | Add replay visibility for per-run MCP logs or document/test the limitation everywhere. |
| P16 | PASS | Textual is optional in `pyproject.toml`; `monitor_app.py` imports Textual lazily behind try/except and prints install guidance. | Monitor and CLI optional-dependency tests pass. | `monitor --help` passes and states not PTY. | Help text does not mention `[tui]`, but runtime missing-Textual path is tested. | Low | Add `[tui]` note to monitor/dashboard help for operator clarity. |
| P17 | PARTIAL | README/Quickstart mostly align with optional extras and monitor limitations; AGENTS/generated block agree on command extras. | Docs tests pass. | CLI help fresh output reviewed. | `runs --help` says each run directory contains optional artifacts; AGENTS/generated block does not explain MCP observability limitation; Quickstart does not carry the README's MCP limitation language. | Medium | Align CLI help, Quickstart, AGENTS, and generated AGENTS text with optional artifact and MCP limitation truth. |
| P18 | FAIL | Validation capability exists in tests and CLI commands, but current validation is red. | Full pytest fails. | Real OpenCode availability checked, but no real session was run. | Cannot claim dogfood readiness with failing full suite and unresolved P14/P15/P17 gaps. | High | Fix the full-suite failure first, then rerun final validation from clean status. |

## Detailed phase review

### P13

- Requirements extracted: split `opencode run` into executable lookup plus args, never `shutil.which("opencode run")`, preserve `OPENCODE_COMMAND` compound overrides, fake default launch, clear missing-command errors, safe availability check, stdout/stderr/log/prompt/advisory/strict behavior, clean validation.
- Code evidence: `vibecode/adapters/opencode.py` has `shutil.which(shlex.split(default_cmd)[0])` in `resolve_opencode_command()` and `shutil.which(binary)` in `check_opencode()`; `check_opencode()` uses `--version` rather than launching an agent; `vibecode/run.py` sends the prompt to `run_streaming()` and writes stdout/stderr logs.
- Test evidence: `tests/test_vibecode_opencode_adapter.py` covers env override, compound command, missing command, and default executable-only lookup; `tests/test_vibecode_run_controller.py::test_fake_opencode_stdin_matches_prompt_snapshot` covers prompt equality; `tests/test_vibecode_run_post.py` covers advisory/strict semantics.
- Command/runtime evidence: adapter suite passed; targeted run subset passed; `Get-Command opencode` found OpenCode and `opencode --version` returned `1.14.48`.
- Gaps: full pytest fails in `test_missing_gitignore_blocks_agent_launch`; validation baseline is not cleanly restored.
- Verdict: PARTIAL.

### P14

- Requirements extracted: create durable per-run directory/events/summary before early failures, cover missing config/profile/dirty repo/missing OpenCode/check/index/context/launch failures, replay early aborts, show optional artifacts honestly.
- Code evidence: `vibecode/run.py::RunController.execute()` creates `RunSession` and `JsonlEventSink` at lines 532-540 before prerequisite checks; `_write_abort_summary()` writes `summary.json`; `vibecode/show_run.py::format_run_show()` labels guard/check/handoff as skipped for abort summaries.
- Test evidence: `TestEarlyAbortArtifacts` covers missing project YAML, invalid profile, dirty repo, missing index, inventory health failure, and event roundtrip; `TestEarlyAbortShowCLI` covers `runs show --events`.
- Command/runtime evidence: run-controller/show/session targeted suites passed.
- Gaps: `_write_abort_summary()` omits available artifact paths and agent/exit fields; requested OpenCode check failure, context failure, and launch exception coverage is weaker than the listed acceptance criteria; early `events.jsonl` creation can make the repo dirty before missing `.gitignore` safety behavior runs.
- Verdict: PARTIAL.

### P15

- Requirements extracted: pass scoped session data to agent env, support per-run MCP event log env, safe fallback when no run exists, compact JSONL events, success/failure tests, monitor rendering or explicit tested limitation, no hard MCP dependency for normal CLI.
- Code evidence: `vibecode/run.py` injects `VIBECODE_SESSION_ID` and `VIBECODE_MCP_EVENTS_LOG`; `vibecode/mcp_server.py::cmd_serve()` reads those env vars and falls back to `.vibecode/logs/mcp_events.jsonl`; tool event payloads contain tool/path/symbol/count/chars/error summaries, not full bodies.
- Test evidence: `TestMcpEnvPropagation`, `TestMCPToolLogging`, JSONL log-path tests, and missing-MCP CLI tests pass; monitor MCP formatting tests pass.
- Command/runtime evidence: MCP server targeted suite passed; `serve --help` states per-run correlation depends on OpenCode propagating env vars.
- Gaps: live MCP-in-monitor streaming is explicitly not implemented in `monitor_app.py`; the monitor can format injected `run.mcp` events but does not bridge the agent-side MCP side log live; `runs show` does not include `mcp_events.jsonl`.
- Verdict: PARTIAL.

### P16

- Requirements extracted: clear Textual packaging contract, lazy imports if optional, graceful missing-Textual monitor behavior, fake monitor smoke/event pump, event spine not scraped stdout, separate panes, streaming text not PTY, dashboard not broken.
- Code evidence: `pyproject.toml` keeps `textual` under `[project.optional-dependencies].tui`; `vibecode/monitor_app.py` catches `ImportError`, exposes `_missing_textual_message()`, routes `EVENT_AGENT_PROCESS` separately from lifecycle/guard/check/handoff/MCP events, and states not PTY.
- Test evidence: `tests/test_vibecode_monitor.py` covers routing, formatting, missing Textual, dashboard missing Textual, and event-pump smoke; `tests/test_vibecode_cli.py` covers base CLI help when Textual is unavailable.
- Command/runtime evidence: monitor tests passed; `python -m vibecode.cli monitor --help` passed.
- Gaps: monitor help omits `[tui]` install guidance even though docs and runtime error include it.
- Verdict: PASS with a low-severity docs/help caveat.

### P17

- Requirements extracted: docs must match code, mention optional extras, list artifacts truthfully, avoid `handoff_report.md` always-present claims, describe MCP correlation honestly, guard semantics, strict mode, not-PTY monitor, and AGENTS/generated consistency.
- Code/docs evidence: `README.md` states `[tui]`/`[mcp]`, advisory/strict semantics, optional artifacts, and MCP live-monitor limitation; `docs/QUICKSTART.md` states optional extras and omits `handoff_report.md`; `AGENTS.md` and `agents_export.py` agree on command list and extras.
- Test evidence: quickstart/agents export tests passed and assert no `handoff_report.md` always-present claim.
- Command/runtime evidence: CLI help reviewed; `runs --help` claims each run directory contains optional artifacts.
- Gaps: Quickstart and AGENTS/generated guidance do not carry the README's MCP limitation/correlation caveat; CLI `runs --help` contradicts optional artifact truth; monitor help omits `[tui]`.
- Verdict: PARTIAL.

### P18

- Requirements extracted: fresh validation, targeted and full tests, CLI help, fake run/replay/monitor credibility, real OpenCode honestly skipped or performed, clean final tree, readiness verdict grounded in actual commands.
- Code/test evidence: targeted P13-P17 suites pass; full test suite is available and was run.
- Command/runtime evidence: full pytest failed; CLI helps passed; OpenCode exists and version check passed; no real OpenCode session was run because the task did not require launching a real modifying agent session and it would not be safe for this audit.
- Gaps: full suite red; real OpenCode runtime validation NOT VERIFIED; fake monitor is non-interactive test smoke rather than a live TUI dogfood; P14/P15/P17 gaps remain.
- Verdict: FAIL.

## Subtask review

| task | status | why | evidence | caveat |
|---|---|---|---|---|
| P13.1 | PARTIAL | Core command resolution works, but clean validation baseline fails. | Adapter code/tests pass; full pytest failure in missing `.gitignore` preflight. | No real OpenCode run performed. |
| P13.2 | PARTIAL | Review intent is partly covered by current tests and this fresh validation. | Targeted command results and source search prove executable-only lookup. | Old review doc not read; strict behavior evidence comes from full suite, which failed overall. |
| P13.3 | PARTIAL | Fixes appear applied for command parsing, not for full-suite hygiene. | `shutil.which()` not called with compound string; full pytest still fails. | Cannot credit the old fix doc. |
| P14.1 | PARTIAL | Durable early artifacts exist for several aborts, but implementation creates a preflight dirtiness regression and summaries are minimal. | `RunController.execute()` early sink; early-abort tests. | Coverage is not complete for all listed failure classes. |
| P14.2 | PARTIAL | Current tests verify much of review intent. | `TestEarlyAbortArtifacts`, `TestEarlyAbortShowCLI`. | Missing `.gitignore` regression shows review intent was not fully satisfied. |
| P14.3 | FAIL | Required correction did not leave P14 truly complete. | Full pytest failure is caused by early `.vibecode/runs/.../events.jsonl` changing preflight behavior. | Old correction doc not read. |
| P15.1 | PARTIAL | Env correlation and compact logs exist; live monitor truth is only injected-event formatting. | `run.py`, `mcp_server.py`, monitor formatting tests. | Cross-process live MCP streaming NOT VERIFIED/NOT IMPLEMENTED. |
| P15.2 | PARTIAL | Tests cover env and compact payloads. | `tests/test_vibecode_mcp_server.py`, `tests/test_vibecode_run_controller.py`. | Limitation is not fully represented in all docs or replay. |
| P15.3 | PARTIAL | Some fixes appear present, but promised monitor-visible truth remains limited. | `monitor_app.py` comment says live streaming is not implemented. | Old fix doc not read. |
| P16.1 | PASS | Optional dependency behavior is implemented and tested. | `pyproject.toml`, `monitor_app.py`, monitor/CLI tests. | Help text can be clearer about `[tui]`. |
| P16.2 | PASS | Review intent is independently covered by tests and source inspection. | Missing Textual and event-pump tests pass. | No interactive monitor session was run. |
| P16.3 | PASS | Corrections are reflected in current code/tests. | Lazy import and install guidance present. | Dashboard only verified by tests/help, not interactive use. |
| P17.1 | PARTIAL | Major docs truth updates are present, but gaps remain. | README/Quickstart/AGENTS/agents_export inspected. | CLI help is part of user-facing truth and still overstates artifacts. |
| P17.2 | PARTIAL | This review independently checked docs against code/help. | Docs tests pass; CLI help reviewed. | Old P17 review doc not read. |
| P17.3 | PARTIAL | Current docs are improved but not fully aligned. | AGENTS/generated agree on extras; README has MCP limitation. | Quickstart/AGENTS lack MCP limitation detail. |
| P18.1 | FAIL | Fresh validation was run and failed. | Full pytest: `1 failed, 1849 passed`. | Real OpenCode runtime NOT VERIFIED. |
| P18.2 | FAIL | Review intent cannot pass while final validation is red. | Failing test and unresolved gaps. | Old validation/review reports not read. |
| P18.3 | FAIL | Final validation fixes are not complete in current repository. | Full suite failure remains. | No source fixes were attempted in this audit. |

## Repo hygiene

- Initial git status: clean (`git status --short` output empty).
- Final validation git status before writing this report: clean (`git status --short` output empty).
- Any validation-created files: none left in the repository working tree by the validation commands.
- Temp artifact tracking status: `git ls-files -- .pytest-tmp .vibecode/tmp tmp` returned no tracked files; `.gitignore` contains `.pytest-tmp/`, `.vibecode/runs/`, `.vibecode/logs/`, `.vibecode/tmp/`, and `tmp/`.
- Final git status after writing this report: `?? P13_P18_INDEPENDENT_COMPLETION_REVIEW.md`; no other dirty files were present.

## Dogfooding readiness

- Is it ready for supervised dogfooding? No.
- Is P14 truly complete? No. It creates durable early artifacts, but those artifacts can pollute preflight state and mask the missing-`.gitignore` safety diagnostic.
- Is MCP truth actually visible where promised? Partially. It is correlated into per-run MCP JSONL when env propagation works, and monitor formatting can render injected MCP events, but live side-process MCP streaming into the monitor is not implemented.
- Is monitor runtime actually dogfoodable? Mostly for streaming stdout/stderr and event-spine visibility, assuming `[tui]` is installed; not for interactive PTY/ConPTY behavior or live MCP side-process events.
- Is documentation truthful enough? Partially. README is mostly honest, but CLI `runs --help`, Quickstart, and AGENTS/generated guidance need tighter artifact and MCP limitation language.
- Next single highest-leverage fix: fix the P14/P13 preflight ordering bug so early run artifact creation does not dirty repositories before the missing-`.gitignore` safety check, then rerun full pytest from a clean tree.
