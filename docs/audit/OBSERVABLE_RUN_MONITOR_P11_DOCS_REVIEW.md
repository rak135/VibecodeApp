# Observable Run Monitor P11 Docs Review

Generated: 2026-05-12

## Verdict

PASS WITH DOC FIXES REQUIRED. The updated README, Quickstart, control-layer audit, and AGENTS guidance mostly describe implemented behavior: advisory guard mode is clear, the monitor is documented as streaming text rather than a PTY, run-session artifact paths are mostly accurate, and MCP observability limitations are stated directly.

I found four documentation issues to fix before calling the docs fully aligned with implementation truth:

- `runs list` examples use a positional repo path, but the implemented CLI requires `--repo`.
- README says monitor `--task` is required, but the parser accepts an omitted task as an empty string.
- Quickstart claims guard checks review edits "before and after the run"; implemented guard evaluation is post-run only.
- The run artifact lists omit `metadata.json`, which is still written and recognized as a fallback artifact.

This review did not modify implementation or test files. The task scope allowed only this review document.

## Findings

### PASS: advisory guard semantics are clear

README describes `--guard-mode {advisory,strict}` and says advisory mode logs guard findings with full severity, sets `overall_status` to `needs_review`, and exits 0 (`README.md:347-352`). Quickstart repeats the same default and strict-mode behavior (`docs/QUICKSTART.md:17`, `docs/QUICKSTART.md:364`).

That matches `RunSummary.overall_status`: strict guard failures become `failure`, while advisory guard failures become `needs_review` after check and handoff status are considered (`vibecode/run.py:119-134`). `_exit_code_for_status()` returns 0 for `needs_review`, and the run summary prints an advisory note when guard findings are present (`vibecode/run.py:394`, `vibecode/run.py:1071-1073`).

### PASS: monitor limitations are honest

README and Quickstart both state that `vibecode monitor` is a streaming-output text monitor, not a PTY, and tell users to run OpenCode directly for full interactive terminal control (`README.md:333`, `docs/QUICKSTART.md:384`). CLI help uses the same limitation and avoids promising process lifecycle management when Q is pressed (`vibecode/cli.py:394-396`).

That matches the implementation: `MonitorApp` runs `RunController` in a daemon thread and routes structured events into Textual via `call_from_thread`; it does not provide PTY/ConPTY behavior or interactive stdin control (`vibecode/monitor_app.py:1-12`, `vibecode/monitor_app.py:182-192`).

### PASS WITH NOTE: run artifact paths are mostly accurate

The documented first-class session directory is correct: `.vibecode/runs/<session_id>/` with `summary.json`, `events.jsonl`, guard/check/handoff reports, prompt/context snapshots, and agent stdout/stderr logs (`README.md:356-370`, `docs/QUICKSTART.md:412-426`). Those paths match `RunSession` properties (`vibecode/session_log.py:55-122`) and the `RunController` persistence path (`vibecode/run.py:998-1055`).

Completeness note: `RunController` also writes `.vibecode/runs/<session_id>/metadata.json` (`vibecode/run.py:170-208`, `vibecode/run.py:1047-1048`). `runs show` recognizes that file as a fallback artifact (`vibecode/show_run.py:7-9`, `vibecode/show_run.py:69-71`, `vibecode/show_run.py:121-124`). The user-facing artifact lists should either include `metadata.json` as a compatibility artifact or explicitly say the listed files are the primary artifacts.

### FIX: `runs list` examples use the wrong repo syntax

README shows:

```powershell
vibecode runs list C:\path\to\repo
```

Quickstart shows the same positional path form in two places (`README.md:379`, `docs/QUICKSTART.md:433`, `docs/QUICKSTART.md:604`).

The implemented parser only accepts `--repo` for `runs list`; the positional form is not registered (`vibecode/cli.py:456-474`). The docs should use:

```powershell
vibecode runs list --repo C:\path\to\repo
python -m vibecode.cli runs list --repo C:\path\to\example-repo
```

The existing `runs show <session_id> --repo ...` examples are accurate (`vibecode/cli.py:480-489`).

### FIX: README says monitor `--task` is required, but the CLI does not enforce it

README's monitor flag table lists `--task` as `(required)` (`README.md:339`). The parser accepts the flag with `default=""` for both `run` and `monitor` (`vibecode/cli.py:172`, `vibecode/cli.py:406`).

Either the implementation should make `--task` required for monitor/run, or the docs should describe the actual behavior: task text is optional at the parser level but should normally be supplied so the generated context pack and prompt are meaningful.

### FIX: Quickstart overstates guard timing

Quickstart says there is "No auto-commit or auto-approve" and that every agent edit is reviewed through guard checks "before and after the run" (`docs/QUICKSTART.md:34`). The implemented run pipeline performs git/profile/index/context/platform preflight before invoking the agent, then starts guard evaluation under "Post-run quality checks" after the agent process exits (`vibecode/run.py:513-533`, `vibecode/run.py:744-758`, `vibecode/run.py:818-833`).

The accurate wording is that Vibecode runs preflight checks before the agent and guard/check/handoff validation after the agent. Standalone `vibecode guard` can be run independently before a run, but `vibecode run` does not currently run a full pre-agent guard pass.

### PASS WITH NOTE: AGENTS.md is safe but terse on run artifacts

AGENTS.md tells future agents not to manually edit `.vibecode/runs/*` and lists `vibecode monitor`, `vibecode runs list`, and `vibecode runs show <session_id> [--events]` (`AGENTS.md:15-21`, `AGENTS.md:45-48`). That is enough to steer agents toward safe inspection instead of editing run metadata.

A small future improvement would be to add `--repo` syntax to the `runs` command descriptions for parity with CLI help, but the current guidance is not unsafe.

### PASS: MCP observability limitations are explicit

README says MCP tool events go to `.vibecode/logs/mcp_events.jsonl`, can be correlated with `VIBECODE_SESSION_ID`, are not written into per-run directories, and are not streamed into the monitor TUI (`README.md:390-394`). This matches the serve help and implementation model where MCP events are a separate log stream rather than part of `.vibecode/runs/<session_id>/events.jsonl`.

### NOTE: docs/VISION.md remains future-facing marketing material

`docs/VISION.md` still describes GUI, swarm, Kanban, automatic updates, and multi-agent orchestration as a product vision rather than current behavior (`docs/VISION.md:13`, `docs/VISION.md:77-107`, `docs/VISION.md:149-156`). Because the filename is explicit, this is not a direct contradiction in README/Quickstart/AGENTS, but it should not be used as current implementation guidance. If it remains in the docs set, add a short top note saying it is aspirational and not the current CLI truth.

## Checks Run

- `python -m vibecode.cli context . --task "Review updated documentation and AGENTS guidance"`
  - Result: passed; wrote `.vibecode/current/context_pack.md`.
- `python -m vibecode.cli check .`
  - Result: failed because required `unit tests` exited 1 after 173.875s. The three required help checks passed.
  - Failure cause from `.vibecode/current/check_results.json`: pytest collected 1754 tests, then many `tmp_path` setup failures occurred because pytest could not scan `C:\Users\Martin\AppData\Local\Temp\pytest-of-Martin` (`PermissionError: [WinError 5] Přístup byl odepřen`).
- `python -m pytest -x --tb=short -p no:cacheprovider`
  - Result: failed on the first test setup with the same `PermissionError` for `C:\Users\Martin\AppData\Local\Temp\pytest-of-Martin`.
- `python -m ruff check --no-cache .`
  - Result: failed on existing lint findings outside this review file, including unused imports in `scripts/write_tests.py`, `tests/test_vibecode_architecture_templates.py`, `tests/test_vibecode_diff_summary.py`, `tests/test_vibecode_run.py`, undefined names in `tests/test_vibecode_project_cli.py` and `vibecode/indexer/ts_symbols.py`, and several `E741` ambiguous-name findings. Ruff also printed existing permission warnings for local temp/cache directories.
- `python -m vibecode.cli --help`
  - Result: passed.
- `python -m vibecode.cli index --help`
  - Result: passed.
- `python -m vibecode.cli context --help`
  - Result: passed.
- `python -m vibecode.cli monitor --help`
  - Result: passed.
- `python -m vibecode.cli runs --help`
  - Result: passed.
- `python -m vibecode.cli runs list C:\path\to\repo`
  - Result: failed as expected for the documented-but-unsupported positional repo syntax: `unrecognized arguments: C:\path\to\repo`.
- `python -m vibecode.cli runs list --repo .`
  - Result: passed; printed that no runs were found under this repo's `.vibecode/runs`.
- `python -m vibecode.cli guard .`
  - Result: exit code 0 with one warning from pre-existing deleted `.pytest-tmp/...` fixture files: `source-test-change-balance`.
- `python -m vibecode.cli validate .`
  - Result: passed with warning: `.vibecode/handoff/NOW.md` contains placeholder text.
- `python -m vibecode.cli handoff-check .`
  - Result: failed on the existing `.vibecode/handoff/NOW.md` placeholder-text issue.

## Changed Files

- `docs/audit/OBSERVABLE_RUN_MONITOR_P11_DOCS_REVIEW.md`
