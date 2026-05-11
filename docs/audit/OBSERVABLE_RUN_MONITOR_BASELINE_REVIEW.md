# Observable Run Monitor Baseline Review

Generated: 2026-05-11

## Verdict

BLOCKER. The baseline audit is mostly grounded in the current code and correctly identifies the real `vibecode run` path, but it misses stale/contradictory documentation that is present in the repository. That omission matters because this baseline is intended to anchor observable run monitor work against current truth rather than outdated status notes.

## Findings

### BLOCKER: Stale docs are present but not identified by the baseline audit

The task explicitly asks the audit to identify stale or contradictory docs if present. `docs/audit/OBSERVABLE_RUN_MONITOR_BASELINE.md` does not include a stale-docs section or finding.

Exact files to inspect:

- `docs/CONTROL_LAYER_FINAL_AUDIT.md:29` says the CLI control layer has "No GUI, MCP implementation, swarm, or server".
- `docs/CONTROL_LAYER_FINAL_AUDIT.md:79` repeats that there is "no GUI, MCP implementation, swarm, or server".
- Current code contradicts that status: `vibecode/cli.py:533` dispatches `serve`, `vibecode/mcp_server.py:201` implements `cmd_serve`, `vibecode/cli.py:539` dispatches `dashboard`, and `vibecode/tui_app.py:147` implements `VibecodeTUI`.

Related doc tension to call out, not necessarily to fix in this baseline:

- `docs/audit/PRD_STRUCTURE_AND_ROUTING_REVIEW.md:33` lists a future task to "Make guard behavior advisory by default".
- `docs/audit/PRD_STRUCTURE_AND_ROUTING_REVIEW.md:64` says guards are advisory by default as product semantics.
- Current implementation is blocking for guard errors: `vibecode/run.py:95` through `vibecode/run.py:107` makes failed guard results an overall failure, and `vibecode/run.py:694` through `vibecode/run.py:700` returns exit code 1 for that failure. Standalone guard also exits non-zero for errors in `vibecode/guard.py:711` through `vibecode/guard.py:716`.

Recommended baseline-audit fix:

- Add a "Stale or contradictory docs" section that names these files and distinguishes current implementation truth from future PRD intent.
- Do not change runtime behavior as part of the audit fix.

### PASS: The audit identifies the real run path, not just README claims

The run-path description matches current code:

- CLI dispatch: `vibecode/cli.py:516` calls `cmd_run`.
- Run entry point: `vibecode/run.py:355` implements `cmd_run`.
- Context and OpenCode prompt generation: `vibecode/run.py:482` through `vibecode/run.py:498` calls `cmd_context`, which writes the context pack via `vibecode/context/__init__.py:12` and `vibecode/context/renderer.py:36`.
- OpenCode command resolution and availability checks are through `vibecode/run.py:509`, `vibecode/adapters/opencode.py:38`, and `vibecode/adapters/opencode.py:55`.
- The actual agent invocation is `subprocess.run(..., capture_output=True, shell=True)` at `vibecode/run.py:569`.
- Post-run evaluation uses the post-agent delta via `vibecode/run.py:614` and `_run_post_checks` at `vibecode/run.py:304`.
- Summary status is centralized in `RunSummary.overall_status` at `vibecode/run.py:95`.

### PASS: The audit accurately describes current guard blocking behavior

The baseline audit is correct for current code: guard findings with severity `error` block successful `vibecode run` completion, while guard warnings do not.

Exact code paths:

- `vibecode/guard.py:85` defines `GuardResult.passed` as false only when an error-severity finding exists.
- `vibecode/run.py:95` through `vibecode/run.py:107` maps a failed guard result to overall `"failure"`.
- `vibecode/run.py:694` through `vibecode/run.py:700` maps `"failure"` to process exit code 1.
- `vibecode/guard.py:711` through `vibecode/guard.py:716` makes standalone `vibecode guard` exit 1 for errors and only treat warnings as failures under `--strict`.

Relevant tests support this:

- `tests/test_vibecode_run_post.py:272`
- `tests/test_vibecode_run_post.py:303`
- `tests/test_vibecode_run_post.py:934`
- `tests/test_vibecode_run_post.py:955`
- `tests/test_vibecode_run_post.py:989`

### WARNING: File-change list is mostly realistic but should be tightened

The "Known Risk Areas and Likely Files to Touch" section is broadly useful, but `vibecode/permissions.py` is not a likely monitor implementation file unless the monitor changes profile UX or policy reporting. The more realistic implementation set is:

- `vibecode/run.py` for run orchestration, event points, process output, summaries, and post-check sequencing.
- `vibecode/cli.py` for new commands or flags.
- `vibecode/guard.py`, `vibecode/check.py`, and `vibecode/handoff.py` for reported result shape and status semantics.
- `vibecode/diff_summary.py` for change summaries.
- `vibecode/context/__init__.py`, `vibecode/context/renderer.py`, and `vibecode/context/platform_export.py` for prompt/context snapshot events.
- `vibecode/mcp_server.py` for MCP tool-call observability.
- `vibecode/tui_app.py`, `vibecode/tui_theme.tcss`, and possibly `vibecode/data_loader.py` for monitor UI and data loading.
- Tests under `tests/test_vibecode_run.py`, `tests/test_vibecode_run_post.py`, `tests/test_vibecode_guard.py`, `tests/test_vibecode_mcp_server.py`, `tests/test_vibecode_dashboard.py`, and integration tests.

### PASS: The audit does not secretly implement product changes

`docs/audit/OBSERVABLE_RUN_MONITOR_BASELINE.md` is an audit document. It does not modify source code or introduce runtime behavior. Its implementation recommendations are framed as future integration points, not as changes already made.

## Final Recommendation

Do not use the baseline audit as the sole implementation handoff until the stale-doc finding is added. The most important correction is documentation truthfulness, not code behavior: amend the baseline audit to name stale docs and to distinguish current blocking guard behavior from future advisory-guard PRD intent.
