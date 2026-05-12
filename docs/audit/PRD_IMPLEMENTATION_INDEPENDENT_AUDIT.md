# Independent PRD Implementation Audit

## Scope and contamination controls

Existing audit, review, dogfood, and follow-up files were not read, opened, grepped, summarized, or used as evidence.

Excluded inputs:
- `docs/audit/**`
- any existing file whose name contains `AUDIT`, `DOGFOOD`, `REVIEW`, or `FOLLOWUP`
- `.vibecode/runs/**`
- `.vibecode/logs/**`
- `.pytest-tmp/**`

Allowed sources actually inspected:
- `PRD.json`
- source under `vibecode/**`, especially `events.py`, `session_log.py`, `run.py`, `process_runner.py`, `monitor_app.py`, `show_run.py`, `mcp_server.py`, `guard.py`, `cli.py`, `adapters/opencode.py`, `context/agents_export.py`, and `indexer/scanner.py`
- tests under `tests/**`, especially event/session/run/process/guard/MCP/monitor/show-run tests
- `README.md`, `docs/QUICKSTART.md`, `AGENTS.md`
- `pyproject.toml`, `.gitignore`
- CLI help and fresh validation commands run during this audit

Note: the required `git status --short` command later displayed `.pytest-tmp` path names after tests had run. I did not read or use `.pytest-tmp` file contents as implementation evidence.

## Executive verdict

Overall status: **FAIL**

The observable run monitor is substantially implemented, not merely described: there is a structured event spine, per-run artifact layer, run controller, streaming process runner, guard report generation, replay command, MCP tool-call logging, and a Textual monitor. However, the current working tree became dirty during validation and the current on-disk code now fails the run-controller fake OpenCode regression path. The most serious current regression is in `vibecode/adapters/opencode.py`: `_default_command()` returns `opencode run`, while `resolve_opencode_command()` checks `shutil.which()` against the whole string, so default command discovery fails and `vibecode run`/`monitor` abort unless `OPENCODE_COMMAND` is explicitly set.

Top 5 risks:
1. Current `vibecode run` default OpenCode discovery is broken; targeted run-controller/run tests fail on the current tree.
2. Earliest abort paths do not always create durable run artifacts/events, so "every run is replayable" is not fully true.
3. MCP observability is best-effort side-log only; session correlation is manual/environment-based and MCP events are not streamed into the monitor.
4. TUI monitor is real but under-dogfooded: formatting/import tests exist, but no real Textual fake-run validation was performed here.
5. Repo hygiene is unstable: validation changed the working tree and surfaced tracked `.pytest-tmp` deletions; current validation state is not clean.

## Command validation

| Command | Result | Notes |
|---|---:|---|
| `git status --short` | PASS | Initial status before validation was clean. |
| `python -m compileall vibecode -q` | PASS | Passed before pytest and passed again after the later dirty-tree changes. |
| `python -m pytest -p no:cacheprovider -q` | PASS | Full suite passed: `1754 passed, 35 warnings in 269.65s`. This was before the later observed dirty-tree regression. |
| `python -m vibecode.cli --help` | PASS | CLI exposes `run`, `monitor`, `runs`, `serve`, `dashboard`, guard/check/handoff, etc. |
| `python -m vibecode.cli run --help` | PASS | Documents `--guard-mode {advisory,strict}` and advisory default. |
| `python -m vibecode.cli monitor --help` | PASS | Documents split-pane monitor and streaming-not-PTY limitation. |
| `python -m vibecode.cli runs --help` | PASS | Documents `runs list` and `runs show`. |
| `python -m pytest -p no:cacheprovider -q tests/test_vibecode_opencode_adapter.py` | PASS | Current adapter unit tests pass: `14 passed`. They do not catch the default resolution bug. |
| `python -m pytest -p no:cacheprovider -q tests/test_vibecode_run_controller.py tests/test_vibecode_run.py::TestCmdRunEndToEnd tests/test_vibecode_run.py::TestCmdRunPreflight::test_safe_gitignore_allows_agent_launch` | FAIL | Current tree fails: `17 failed, 30 passed`. Failures abort with "OpenCode command not found" after fake `opencode` is placed on PATH. |
| `git status --short` | FAIL | Final status was dirty. Source/test/package files were modified and tracked `.pytest-tmp` deletions were reported. |

## PRD implementation matrix

| Task | Status | Implementation evidence | Test evidence | Gaps | Severity | Recommended next action |
|---|---|---|---|---|---|---|
| P0.1 baseline audit task | NOT VERIFIED | Current code/docs contain the surfaces P0.1 wanted inspected, but the required artifact is under forbidden `docs/audit/**`. | Not used. | Cannot verify the baseline audit output without violating contamination rules. | Low | Leave historical audit uncredited in this report. |
| P1.1 structured event spine | PASS | `vibecode/events.py`: `VibecodeEvent`, `EventLevel`, event constants, `EventSink`, `InMemoryEventSink`, `JsonlEventSink`, `ConsoleEventSink`, `MultiEventSink`, `NullEventSink`, `create_event`. | `tests/test_vibecode_events.py`. | Event types are category strings plus `data["phase"]`, not distinct classes for each lifecycle name. Acceptable for P1. | Low | Keep schema stable; avoid coupling imports. |
| P2.1 per-run session paths/artifacts | PARTIAL | `vibecode/session_log.py`: `RunSession` paths and snapshot helpers; `RunController.execute()` creates JSONL sink after git preflight. | `tests/test_vibecode_session_log.py`, run snapshot tests in `tests/test_vibecode_run.py` and `tests/test_vibecode_run_controller.py`. | Early aborts before the JSONL sink is attached do not always produce durable `events.jsonl`/summary artifacts. | Medium | Create session artifacts at run start, including early failures. |
| P3.1 observable run controller | FAIL | `vibecode/run.py`: `RunController`, `RunSummary`, event emissions for preflight/index/context/prompt/agent/guard/check/handoff/summary/finish. | Full suite initially passed, but current targeted run-controller tests fail. | Current default OpenCode command resolution breaks fake/default agent launch; early failures are not fully replayable. | Critical | Fix command resolution and rerun full validation from a clean tree. |
| P4.1 streaming agent process output | PARTIAL | `vibecode/process_runner.py`: `run_streaming()` uses `subprocess.Popen`, reader threads, stdout/stderr events, log files, exit code preservation. `RunController.execute()` calls it with session log paths. | `tests/test_vibecode_process_runner.py`; run-controller tests previously covered integration. | Current default run path fails before agent launch unless explicit env command is used. | High | After P3 fix, rerun streaming integration tests and a fake monitor run. |
| P5.1 advisory guard by default | PARTIAL | `RunSummary.guard_mode="advisory"`, `overall_status` returns `needs_review`; CLI help exposes `--guard-mode advisory/strict`. | `tests/test_vibecode_run_post.py::TestAdvisoryGuardMode` and agent guard tests. | Logic is present, but current default run regression prevents normal CLI dogfooding. | High | Revalidate advisory behavior through `vibecode run` after P3 fix. |
| P6.1 human-readable guard reports | PASS | `vibecode/guard.py`: enriched `GuardFinding`, counts, `write_guard_report_md`; `RunController.execute()` writes session `guard_report.json` and `.md`, emits finding/completed events. | `tests/test_vibecode_guard_report.py`. | If guard is skipped before running, no report is produced; otherwise findings/no-findings are covered. | Medium | Consider explicit skipped report when guard cannot run. |
| P7.1 prompt/context snapshot events | PARTIAL | `RunController.execute()` snapshots `context_pack.md` and `opencode_prompt.md`; emits paths, snapshot paths, sizes, task summary, sections, platform/profile; avoids raw body. | `tests/test_vibecode_run_controller.py::TestContextAndPromptSnapshotEvents`. | Current default run path fails before agent launch; prompt stdin equality test fails in the dirty tree due command discovery. | High | Revalidate exact prompt-to-agent flow after P3 fix. |
| P8.1 MCP tool-call observability | PARTIAL | `vibecode/mcp_server.py`: `VibecodeServer` emits `EVENT_MCP` for calls/returns/failures; logs via `JsonlEventSink`; session id from parameter/env/default. | `tests/test_vibecode_mcp_server.py::TestMcpToolLogging`. | No automatic run-controller propagation of `VIBECODE_SESSION_ID`; MCP events are not per-run artifacts and not live in monitor. | Medium | Pass session id to the agent/MCP environment or document manual-only correlation more prominently. |
| P9.1 TUI two-pane monitor MVP | PARTIAL | `vibecode/monitor_app.py`: Textual `MonitorApp`, left/right panes, `TUIEventSink`, event routing, status bar; `cli.py` registers `monitor`. | `tests/test_vibecode_monitor.py`. | No real TUI/fake-run smoke was performed; monitor depends on P3 run path; MCP events are not shown. `pyproject.toml` now makes Textual optional without docs for installing monitor extra. | High | Add a non-interactive fake monitor run test and document/install optional TUI extra. |
| P10.1 run replay/show command | PASS | `vibecode/show_run.py`: `list_runs`, `load_run_summary`, `load_run_events`, `format_run_show`, `cmd_runs`; `cli.py` registers `runs list/show`. | `tests/test_vibecode_show_run.py`. | No top-level `show-run` alias, but `runs show` matches accepted PRD alternative. | Low | Keep replay output bounded and add more artifact corruption cases if needed. |
| P11.1 documentation and AGENTS guidance | PARTIAL | `README.md`, `docs/QUICKSTART.md`, `AGENTS.md`, `vibecode/context/agents_export.py`. | `tests/test_vibecode_quickstart.py`, AGENTS export tests indirectly. | Docs claim plain install then monitor/serve, but current `pyproject.toml` makes Textual/MCP optional. Docs list `handoff_report.md` as a run artifact, but run code only writes JSON handoff reports. | Medium | Align install docs and artifact list with current packaging/code. |
| P12.1 final validation/dogfood capability | FAIL | Validation code/tests exist; fake OpenCode tests exist; replay command exists. | Full pytest initially passed; current targeted run tests fail. | Current tree is dirty and default run regression blocks fake/real default validation. Existing dogfood reports are forbidden and were not used. | Critical | Restore clean validation: fix default command resolution, remove tracked temp-state churn, rerun full pytest. |

## Detailed findings by task

### P0.1 Audit current run, guard, context, MCP, and TUI surfaces

Requirements extracted from PRD:
- Create a baseline audit artifact under `docs/audit/`.
- Cover CLI entry points, run/context/prompt generation, external invocation, stdout/stderr/exit capture, summary files, guard behavior, MCP instrumentation potential, TUI/dashboard structure, tests, risks.
- Run compile/tests and record results.

Evidence found:
- Allowed current code includes all relevant surfaces: `vibecode/cli.py`, `vibecode/run.py`, `vibecode/context/**`, `vibecode/guard.py`, `vibecode/mcp_server.py`, `vibecode/tui_app.py`, `vibecode/monitor_app.py`, and related tests.

Missing or weak parts:
- The actual P0.1 output is under forbidden `docs/audit/**`, so it was not verified.

Test coverage assessment:
- Not applicable to this clean-room audit; historical audit tests/commands were not used.

Runtime verification assessment:
- Not verified.

Final status: **NOT VERIFIED**.

### P1.1 Implement structured event spine

Requirements extracted from PRD:
- Serializable event model with stable fields.
- Event type constants for lifecycle, context, prompt, agent process, MCP, git delta, guard, checks, handoff, summary.
- Memory, JSONL, console, multi, and null sinks.
- Consistent event helper and deterministic serialization.
- Low coupling and tests.

Evidence found:
- `vibecode/events.py::VibecodeEvent` has `event_id`, `session_id`, `timestamp`, `type`, `level`, `message`, and `data`.
- `vibecode/events.py::JsonlEventSink.emit()` appends one JSON object per line and creates parents.
- `vibecode/events.py` imports only low-level standard library modules and does not import run/guard/context.
- `tests/test_vibecode_events.py` covers roundtrip, JSONL append, sink fan-out, memory sink capture, fallback serialization, and non-serializable failure.

Missing or weak parts:
- Non-JSON data is rejected at serialization time, not at event construction.
- Event names are broad category constants; exact lifecycle names are usually represented in `message`/`data["phase"]`.

Test coverage assessment:
- Strong focused unit coverage.

Runtime verification assessment:
- Verified by compile and tests.

Final status: **PASS**.

### P2.1 Implement per-run session paths and durable run artifacts

Requirements extracted from PRD:
- Stable `.vibecode/runs/<session_id>/` directory.
- Define events, summary, prompt, context, guard, checks, handoff, stdout, stderr paths.
- Snapshot prompt/context.
- Preserve `.vibecode/current`.
- Create JSONL sink and parent dirs.
- Windows-safe paths and tests.

Evidence found:
- `vibecode/session_log.py::RunSession` defines `run_dir`, `events_jsonl`, `summary_json`, `opencode_prompt_md`, `context_pack_md`, `guard_report_json`, `guard_report_md`, `checks_report_json`, `handoff_report_json`, `handoff_report_md`, `agent_stdout_log`, `agent_stderr_log`.
- `RunSession.snapshot_prompt()` and `snapshot_context_pack()` copy from `.vibecode/current`.
- `RunSession.snapshot_current_file(..., missing_ok=True)` safely returns `False` for optional missing files.
- `tests/test_vibecode_session_log.py` covers paths, directory creation, snapshot behavior, missing optional files, and Path usage.

Missing or weak parts:
- `RunController.execute()` attaches the session JSONL sink only after successful project/profile/git preflight. Missing `.vibecode/project.yaml` and invalid profile failures emit to memory only and are not durable replay artifacts.

Test coverage assessment:
- Good unit coverage for the artifact layer; weaker integration coverage for earliest abort persistence.

Runtime verification assessment:
- Successful run artifacts were tested, but not every failure path is durable.

Final status: **PARTIAL**.

### P3.1 Refactor run command around observable run controller

Requirements extracted from PRD:
- Run orchestration extracted into controller/equivalent.
- Orchestrate git/preflight, index, context, prompt, external agent, guard/check/handoff, summary.
- Emit required structured events.
- Preserve CLI behavior.
- Observable failures.
- Test without real OpenCode.

Evidence found:
- `vibecode/run.py::RunController.execute()` implements orchestration and emits events for run lifecycle, git preflight, index, context, prompt, agent, guard, checks, handoff, summary.
- `vibecode/run.py::cmd_run()` routes CLI to the controller.
- `tests/test_vibecode_run_controller.py` has fake OpenCode tests for ordering, summaries, failures, CLI compatibility, and prompt/context events.

Missing or weak parts:
- Current code in `vibecode/adapters/opencode.py::_default_command()` returns `opencode run`, but `resolve_opencode_command()` calls `shutil.which(default_cmd)` on that whole string. This fails when only `opencode` is on PATH.
- Current targeted run-controller/run validation failed with `OpenCode command not found` in fake OpenCode tests.
- Earliest abort paths do not write complete session events/summary.
- Required event names are not individual enum constants such as `RunStarted`; they are category events plus phase/message.

Test coverage assessment:
- The intended fake OpenCode coverage exists, but currently fails on the dirty tree.

Runtime verification assessment:
- Default runtime path is currently broken unless `OPENCODE_COMMAND` is explicitly set.

Final status: **FAIL**.

### P4.1 Add streaming agent process output

Requirements extracted from PRD:
- Streaming runner with incremental stdout/stderr reads.
- Emit stdout/stderr events.
- Write full logs.
- Preserve exit code.
- Avoid stdout/stderr deadlock.
- Do not claim PTY/ConPTY.
- Tests with fake processes.

Evidence found:
- `vibecode/process_runner.py::run_streaming()` uses `subprocess.Popen`, reader threads for stdout/stderr, writes `stdout_log`/`stderr_log`, and returns `ProcessResult(exit_code, stdout, stderr)`.
- `_read_stream()` emits `EVENT_AGENT_PROCESS` with `data["phase"]` set to `stdout` or `stderr`.
- `RunController.execute()` invokes `run_streaming()` with `RunSession.agent_stdout_log` and `agent_stderr_log`.
- Module and docs explicitly say it is streaming output, not PTY/ConPTY.
- `tests/test_vibecode_process_runner.py` covers stdout, stderr, mixed streams, logs, events, exit codes, stdin, and parent directory creation.

Missing or weak parts:
- Current default command regression can prevent the runner from being reached through normal `vibecode run`.
- Events are generic `EVENT_AGENT_PROCESS` with phase fields, not distinct `AgentStdout`/`AgentStderr` event constants.

Test coverage assessment:
- Strong for the runner; currently weak for full run integration due P3 regression.

Runtime verification assessment:
- Fake process runner verified; real OpenCode not run.

Final status: **PARTIAL**.

### P5.1 Make guard behavior advisory by default

Requirements extracted from PRD:
- Advisory default.
- Preserve findings/severity.
- Do not hard-block solely because guard found issues.
- Strict/blocking explicit if present.
- Tests updated for new semantics.

Evidence found:
- `vibecode/run.py::RunSummary.guard_mode` defaults to `advisory`.
- `RunSummary.overall_status` returns `needs_review` for guard errors in advisory mode and `failure` in strict mode.
- `_exit_code_for_status("needs_review")` returns `0`.
- `vibecode/cli.py` exposes `--guard-mode {advisory,strict}` for `run` and `monitor`.
- `tests/test_vibecode_run_post.py::TestAdvisoryGuardMode` covers default, strict, preserved severity, exit code, and check failures still blocking.

Missing or weak parts:
- Current default run regression prevents normal end-to-end CLI validation in the dirty tree.

Test coverage assessment:
- Good unit/fixture coverage for summary semantics and previous full run tests.

Runtime verification assessment:
- Logic verified; current runtime path blocked by P3.

Final status: **PARTIAL**.

### P6.1 Improve guard findings into human-readable drift reports

Requirements extracted from PRD:
- Enriched findings: severity, rule id, category, path, title/message, why, suggested fix, evidence, related tests.
- `guard_report.json` and `guard_report.md` in run session.
- Per-finding events and completed counts by severity/category.
- Grouped human-readable report.
- No-findings and findings cases handled.

Evidence found:
- `vibecode/guard.py::GuardFinding` includes enriched fields and `as_dict()`.
- `vibecode/guard.py::GuardResult` provides `counts_by_severity()` and `counts_by_category()`.
- `vibecode/guard.py::write_guard_report_md()` groups by severity/category and writes a no-findings report.
- `RunController.execute()` emits `EVENT_GUARD_FINDING`, emits guard counts, and writes session `guard_report.json` and `guard_report.md`.
- `tests/test_vibecode_guard_report.py` covers JSON, Markdown, no-findings, grouped counts, finding events, and synthetic guard evaluation errors.

Missing or weak parts:
- Guard skip cases are evented but do not necessarily create a report artifact.

Test coverage assessment:
- Strong.

Runtime verification assessment:
- Guard reporting code verified; live run path currently depends on P3.

Final status: **PASS**.

### P7.1 Add prompt and context snapshot events

Requirements extracted from PRD:
- Copy exact context/prompt into run session.
- Emit events with current path, snapshot path, size, task summary, included sections, platform/model/profile.
- Avoid dumping huge prompt/context into event stream.
- Tests present.

Evidence found:
- `RunController.execute()` calls `session.snapshot_context_pack()` and `session.snapshot_prompt()` after context generation.
- Context event data includes `path`, `snapshot_path`, `size_bytes`, `task_summary`, and `sections`.
- Prompt event data includes `path`, `snapshot_path`, `size_bytes`, `platform`, and `profile`.
- `tests/test_vibecode_run_controller.py::TestContextAndPromptSnapshotEvents` covers snapshot paths, file existence, session specificity, no raw body text, and fake OpenCode stdin matching prompt snapshot.

Missing or weak parts:
- No model field is included in prompt event data; profile/platform are included.
- Current dirty-tree command regression makes the prompt-to-agent stdin test fail because fake OpenCode is never launched.

Test coverage assessment:
- Strong in intended state; currently failing for the exact agent stdin assertion.

Runtime verification assessment:
- Snapshot generation is real; default run launch currently broken.

Final status: **PARTIAL**.

### P8.1 Add MCP tool-call observability

Requirements extracted from PRD:
- Log/emit tool calls and returns/failures.
- Capture tool name, sanitized args, result summary, errors, timestamp, optional session id.
- Fallback log path if out-of-process.
- Avoid huge payloads.
- Non-MCP CLI works without optional dependency.

Evidence found:
- `vibecode/mcp_server.py::VibecodeServer.get_file_card()`, `find_symbol()`, and `list_high_risk()` emit called/returned/failed `EVENT_MCP` events.
- Result data contains compact fields such as `tool`, `path`, `symbol`, `found`, `match_count`, `risk_count`, `result_chars`, `error`, and `error_type`.
- `cmd_serve()` writes to `.vibecode/logs/mcp_events.jsonl` through `JsonlEventSink`.
- `VibecodeServer` session id comes from explicit parameter, `VIBECODE_SESSION_ID`, or `"mcp-server"`.
- `tests/test_vibecode_mcp_server.py::TestMcpToolLogging` covers success/failure logging, compact summaries, JSONL, session ids, and no-sink behavior.
- `build_mcp_server()` imports `mcp` lazily; normal parser/validate paths are tested without MCP import.

Missing or weak parts:
- `RunController` does not set `VIBECODE_SESSION_ID` for the agent/MCP environment, so correlation is manual/best-effort.
- MCP events are not written into `.vibecode/runs/<session_id>/` and are not consumed by the monitor.

Test coverage assessment:
- Good for direct tools and logs; weak for real OpenCode MCP session correlation.

Runtime verification assessment:
- Direct server/tool behavior verified; live MCP with OpenCode not verified.

Final status: **PARTIAL**.

### P9.1 Implement TUI two-pane monitor MVP

Requirements extracted from PRD:
- Monitor command runs task and shows two panes.
- Consume event spine, not scraped printed text.
- Separate agent output from Vibecode events.
- Show status/artifact path.
- Document streaming-only vs true interactive terminal.
- Import/format/smoke tests.

Evidence found:
- `vibecode/monitor_app.py::MonitorApp.compose()` builds header, task label, agent pane, event pane, and status bar.
- `TUIEventSink.emit()` bridges event spine into Textual.
- `route_event()` sends `EVENT_AGENT_PROCESS` to the agent pane and other events to the event pane.
- `_on_run_finished()` sets the run artifact path from `RunSession`.
- `vibecode/cli.py` registers `monitor` and help states it is not a PTY.
- `README.md` and `docs/QUICKSTART.md` document the streaming-not-PTY limitation.
- `tests/test_vibecode_monitor.py` covers formatting, routing, command registration, and mocked `cmd_monitor`.

Missing or weak parts:
- No real TUI run with fake `RunController` was executed here.
- Current default run regression means monitor cannot launch the normal fake/default agent path.
- MCP events are not shown in the monitor despite the product goal mentioning what the agent asked via MCP.
- Current `pyproject.toml` makes Textual optional, but docs do not tell users to install a TUI extra.

Test coverage assessment:
- Good pure helper tests; insufficient live TUI/dogfood coverage.

Runtime verification assessment:
- CLI help verified; live TUI not safely run in this audit.

Final status: **PARTIAL**.

### P10.1 Add run replay/show command

Requirements extracted from PRD:
- List previous run ids.
- Show summary without rerunning agent.
- Read events/summary artifacts.
- Handle missing/corrupt data.
- Tests present.

Evidence found:
- `vibecode/show_run.py::list_runs()` lists run directories.
- `load_run_summary()` reads `summary.json` or falls back to `metadata.json`.
- `load_run_events()` parses JSONL and skips corrupt lines with collected errors.
- `format_run_show()` displays task, platform/profile, times, exit code, agent status, guard counts/findings, checks, handoff, artifact paths, and optional events.
- `cmd_runs()` dispatches `runs list` and `runs show`.
- `tests/test_vibecode_show_run.py` covers parsing, listing, missing run, corrupt summary/events, missing events, and CLI integration.

Missing or weak parts:
- No `show-run` alias, but `runs show` is an accepted PRD shape.

Test coverage assessment:
- Strong.

Runtime verification assessment:
- CLI help verified; unit/CLI tests passed in full suite.

Final status: **PASS**.

### P11.1 Update documentation and AGENTS guidance

Requirements extracted from PRD:
- Docs explain observable monitor, advisory guard, strict mode if implemented, TUI command, run artifacts, prompt/context snapshots, run replay, MCP observability and limitations.
- Docs must not oversell.
- Remove stale future-only claims.

Evidence found:
- `README.md` has an "Observable run monitor" section covering monitor, advisory/strict guard mode, run artifacts, replay commands, and MCP observability limitations.
- `docs/QUICKSTART.md` covers `run`, `monitor`, `runs list/show`, artifact paths, advisory guard mode, and not-a-PTY limitation.
- `AGENTS.md` lists run/monitor/runs commands and generated/runtime paths not to edit.
- `vibecode/context/agents_export.py::render_agents_block()` generates updated AGENTS guidance.

Missing or weak parts:
- Current `pyproject.toml` makes Textual and MCP optional, but installation docs still say plain `python -m pip install -e .` before monitor/serve workflows.
- README/Quickstart list `handoff_report.md` as a run artifact, but `RunController.execute()` only writes `handoff_report.json`; Markdown handoff path is defined but not written.
- AGENTS guidance is brief and does not mention MCP observability limitations.

Test coverage assessment:
- Some documentation consistency tests exist, but stale optional-dependency/artifact claims are not caught.

Runtime verification assessment:
- Documentation inspected directly.

Final status: **PARTIAL**.

### P12.1 Final validation and dogfood report

Requirements extracted from PRD:
- Run compile and full pytest/broad subset.
- Fake/safe monitor run if possible.
- Real OpenCode smoke only if available and safe.
- Show-run smoke if implemented.
- Verify run folder artifacts.
- Write dogfood report under forbidden `docs/audit/**`.

Evidence found:
- Full `python -m pytest -p no:cacheprovider -q` initially passed.
- Fake OpenCode regression tests exist in `tests/test_vibecode_run.py`, `tests/test_vibecode_run_controller.py`, and `tests/test_vibecode_run_post.py`.
- Replay/show command tests exist in `tests/test_vibecode_show_run.py`.
- `tests/test_vibecode_monitor.py` mocks `MonitorApp.run()` but does not perform a real fake monitor run.

Missing or weak parts:
- Existing dogfood report is forbidden and was not used.
- Current targeted fake run tests fail on the dirty tree.
- Real OpenCode was not run.
- No safe live monitor dogfood was run in this audit.

Test coverage assessment:
- Validation coverage exists but is currently not green for the run path.

Runtime verification assessment:
- Compile passes; full pytest passed before dirty regression; current run subset fails.

Final status: **FAIL**.

## Cross-cutting issues

### Packaging/dependencies

Current `pyproject.toml` declares only `pyyaml` as a base dependency and makes Textual/MCP optional. `vibecode monitor` imports Textual in `vibecode/monitor_app.py`; `vibecode serve` imports MCP lazily in `build_mcp_server()`. Optional extras are reasonable, but README/Quickstart do not tell users to install `.[tui]`, `.[mcp]`, or `.[all]` before using monitor/serve.

### Repo hygiene

The initial `git status --short` was clean. After validation, the working tree became dirty, including source/test/package files and tracked temporary pytest-state deletions. This makes the validation story unstable and directly affected this audit: full pytest passed first, but a later targeted run subset failed against the current tree.

### Stale docs

Docs mostly match current features, but they overstate `handoff_report.md` generation and under-document optional extras for monitor/MCP.

### Optional dependencies

Non-MCP CLI code is protected by lazy imports and tests. Monitor is less graceful: invoking `vibecode monitor` without Textual installed will fail at import time.

### Windows concerns

`RunSession` uses `pathlib`; tests cover Windows-style path assumptions. `process_runner.run_streaming()` uses `shell=True` with documented trust assumptions and reader threads, which is pragmatic for Windows `.cmd` wrappers. The current `opencode run` default command regression is especially relevant on Windows because tests rely on a fake `opencode.cmd`.

### Fake vs real OpenCode validation

Fake OpenCode validation exists and was previously passing. Current fake validation fails because default command discovery cannot find `opencode` after `_default_command()` became `opencode run`. Real OpenCode was not run in this audit.

### MCP correlation limits

MCP session id is accepted through constructor/env, but the run controller does not set `VIBECODE_SESSION_ID` for the agent process. Correlation is therefore manual or best-effort, not automatic.

### TUI limitations

The TUI is an event-spine view, not random stdout scraping. It is also honestly documented as streaming text, not a PTY. It does not manage a running agent process after quitting, does not show MCP events, and lacks live fake-run validation here.

### Guard advisory semantics

The advisory/strict semantics are implemented cleanly in `RunSummary` and documented in CLI help/docs. Advisory mode preserves severity and returns `needs_review` with exit code 0 for guard-only errors. Required check failures still block.

## Recommended fix queue

### 1. Must fix now

1. Fix default OpenCode command resolution in `vibecode/adapters/opencode.py`. Either keep `_default_command()` as a resolvable binary plus add run args elsewhere, or split the command before `shutil.which()`.
2. Restore a clean working tree and stop validation from mutating tracked files or tracked `.pytest-tmp` state.
3. Rerun `python -m compileall vibecode -q` and full `python -m pytest -p no:cacheprovider -q` from the clean current tree.
4. Ensure `RunController` creates per-run artifacts/events for earliest aborts, not only after git preflight.

### 2. Should fix soon

1. Propagate `VIBECODE_SESSION_ID` into the agent/MCP environment where safe.
2. Add a real fake-run monitor smoke path that exercises `MonitorApp` event consumption without requiring real OpenCode.
3. Align README/Quickstart with optional extras and actual handoff report generation.
4. Add tests that catch default compound-command discovery.

### 3. Later/product polish

1. Stream MCP events into the monitor when they can be correlated.
2. Add a top-level `show-run` alias if desired.
3. Generate a clear skipped-guard report artifact when guard cannot run.
4. Improve monitor lifecycle behavior when the user quits during an active agent run.

## Final answer

The observable run monitor is **real, not mostly cosmetic**. It has a real event spine, durable artifacts for successful/late-stage runs, a streaming runner, a TUI view, MCP logging hooks, and replay commands.

It is **not ready for supervised dogfooding in the current tree**. The current default OpenCode command discovery regression blocks normal fake/default runs, and the repository became dirty during validation.

The next single highest-leverage task is: **fix OpenCode command resolution and restore a clean green validation baseline**, then rerun full pytest and a fake monitor/run smoke from a clean tree.
