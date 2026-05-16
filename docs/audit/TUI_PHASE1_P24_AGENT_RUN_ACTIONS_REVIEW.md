# TUI Phase 1 P24 Agent Run Actions Review

Generated: 2026-05-16

## Verdict

PASS WITH FOLLOW-UP. P24.1 wires `[A]` and `[S]` into the existing
`RunController` flow, prompts for a task when needed, regenerates context before
launch, uses fake OpenCode in automated coverage instead of requiring a real
OpenCode install, preserves inspectable run artifacts under
`.vibecode/runs/<session_id>/`, keeps `run` / `monitor` / `runs show`
compatible, and does not make Vibecode call an LLM directly.

I found one medium implementation issue and one low follow-up:

1. `AgentRunService` flattens failure results inaccurately, so the main TUI can
   show the wrapper exit code instead of the real agent exit code and can reduce
   specific early-abort reasons to a generic "see run directory" message.
2. The right-panel artifact list is useful, but it omits several artifacts that
   the run layer actually writes and that `runs show` can already inspect.

This review only adds this document, per task scope.

## Findings

### PASS: `[A]` and `[S]` correctly route through the existing run controller and preserve advisory profile semantics

The TUI action wiring is appropriately thin:

- `action_cmd_audit()` and `action_cmd_safe()` both delegate to `_start_run()`
  with `"audit"` and `"safe"` respectively (`vibecode/main_app.py:1115-1121`).
- When there is no current task, `_start_run()` stores the pending profile and
  reuses the existing task-input screen instead of inventing a second task flow
  (`vibecode/main_app.py:1285-1293`).
- `AgentRunService.run()` instantiates `RunController` and passes
  `profile_name=profile` without hardcoding one profile path
  (`vibecode/main_app.py:683-693`).

That matches the repository's existing run/monitor contract. In
`vibecode/run.py`, profiles are explicitly documented as Vibecode-side advisory
metadata: validated, recorded, and surfaced in run/session metadata, but not
translated into OpenCode flags by Vibecode itself (`vibecode/run.py:13-24`).
`MonitorApp` uses the same `RunController` contract and forwards the selected
profile in the same way (`vibecode/monitor_app.py:265-275`).

The tests cover the user-visible wiring directly:

- missing-task prompt flow for `[A]` / `[S]`:
  `tests/test_vibecode_run_action_tui.py:488-502`
- thread launch when a task already exists:
  `tests/test_vibecode_run_action_tui.py:515-547`
- profile propagation into the controller factory:
  `tests/test_vibecode_run_action_tui.py:213-223`
- monitor profile forwarding compatibility:
  `tests/test_vibecode_monitor.py:505-586`

### PASS: task/context prerequisites are handled before launch through existing run orchestration

P24.1 did not duplicate context or preflight logic in the TUI layer. The
existing run flow still owns the prerequisites:

- project/profile/git/index preflight:
  `vibecode/run.py:571-735`
- context-pack generation and prompt export:
  `vibecode/run.py:739-807`
- prompt/context snapshots into the per-run artifact directory before launch:
  `vibecode/run.py:781-807`, `vibecode/session_log.py:174-192`

That means `[A]` and `[S]` can start from either an existing task or the same
prompt flow as `[C]`, but the actual run still regenerates the context pack and
prompt before invoking the external agent command.

Manual fake-OpenCode smoke in
`C:\DATA\PROJECTS\VibecodeApp\tmp\p24_review_repo` confirmed that behavior for
both a successful safe run and a failing audit run:

- `run.context` and `run.prompt` events were emitted before `run.agent_process`
  started;
- the fake runner launch markers existed for both sessions:
  - `.vibecode\tmp\launch_review-safe-001.txt`
  - `.vibecode\tmp\launch_review-audit-001.txt`
- those marker files contained the prompt payload, proving the fake command
  consumed real stdin rather than only exercising parser/preflight paths.

### PASS: center/right output stays Phase-1 honest and keeps agent output separate from Vibecode events

The center panel remains honest about Phase 1 scope:

- the default placeholder explicitly says a fully embedded interactive terminal
  is **not** implemented and points users at `vibecode monitor`
  (`vibecode/main_app.py:52-60`);
- the monitor path is also documented as streaming text mode, not a PTY
  (`vibecode/monitor_app.py:8-13`).

During runs, the split remains clean:

- `handle_run_event()` routes `EVENT_AGENT_PROCESS` to the center output pane
  and everything else to the right event pane
  (`vibecode/main_app.py:1340-1357`);
- `monitor_app.route_event()`, `format_agent_line()`, and
  `format_vibecode_line()` keep stdout/stderr/process lifecycle separate from
  context/prompt/guard/check/handoff events
  (`vibecode/monitor_app.py:49-154`).

Smoke excerpts from the reviewed fake runs:

```text
Center pane:
[STARTED] Agent started: ...\opencode_safe.cmd
[stderr] SAFE_STDERR\n
SAFE_STDOUT\nstep ok\n
[FINISHED] Agent finished (exit_code=0)
```

```text
Right pane:
[11:41:02] INFO    run.context: Context pack written  (...\review-safe-001\context_pack.md)
[11:41:02] INFO    run.prompt: Prompt written  (...\review-safe-001\opencode_prompt.md)  opencode  safe
[11:41:03] INFO    run.guard: Guard completed
[11:41:03] INFO    run.check: Checks completed
[11:41:03] INFO    run.handoff: Handoff completed
```

That is the right Phase 1 shape: useful streaming output without pretending to
be a fully embedded Windows Terminal.

### PASS: successful and failing fake runs leave durable artifacts, and existing `run` / `monitor` / `runs show` behavior remains compatible

The run artifact layer is real and reusable, not TUI-only glue:

- `RunSession` defines stable per-run paths for `events.jsonl`, `summary.json`,
  `metadata.json`, context/prompt snapshots, guard/check/handoff reports, and
  agent stdout/stderr logs (`vibecode/session_log.py:54-127`);
- `RunController.execute()` writes those artifacts and emits replayable events
  (`vibecode/run.py:553-563`, `vibecode/run.py:1139-1205`);
- `runs show` and `runs list` load the same artifact set and already understand
  early-abort summaries and event replay (`vibecode/show_run.py:27-111`,
  `vibecode/show_run.py:119-260`).

Manual smoke artifacts:

| Session | Result | Example artifact paths |
| --- | --- | --- |
| `review-safe-001` | success | `...\runs\review-safe-001\summary.json`, `...\events.jsonl`, `...\guard_report.json`, `...\checks_report.json`, `...\handoff_report.json`, `...\agent_stdout.log`, `...\agent_stderr.log`, `...\context_pack.md`, `...\opencode_prompt.md` |
| `review-audit-001` | failure | `...\runs\review-audit-001\summary.json`, `...\events.jsonl`, `...\guard_report.json`, `...\checks_report.json`, `...\handoff_report.json`, `...\agent_stdout.log`, `...\agent_stderr.log`, `...\context_pack.md`, `...\opencode_prompt.md` |
| `review-abort-001` | early abort | `...\runs\review-abort-001\summary.json`, `...\events.jsonl`, `...\metadata.json`, `...\context_pack.md`, `...\opencode_prompt.md` |

Compatibility evidence is good:

- `tests/test_vibecode_run.py` passed, including fake-run artifact, preflight,
  and durable-abort coverage;
- `tests/test_vibecode_monitor.py` passed, including `cmd_monitor` argument
  forwarding and CLI dispatch smoke coverage;
- `tests/test_vibecode_show_run.py` passed, including replay and early-abort
  display coverage;
- live `python -m vibecode.cli runs list --repo ...` and
  `python -m vibecode.cli runs show ... --events` both succeeded on the fake
  smoke artifacts.

### PASS: no direct Vibecode LLM call and no OpenCode startup on TUI boot

I found no evidence that the main TUI launches OpenCode on startup or that
Vibecode calls an LLM directly:

- `VibecodeMainApp.on_mount()` only logs `[ready]` and the repo path
  (`vibecode/main_app.py:1070-1072`);
- `AgentRunService` is instantiated lazily and used only from `[A]` / `[S]`
  (`vibecode/main_app.py:1045-1048`, `vibecode/main_app.py:1115-1121`);
- the external agent launch still happens only through `run_streaming()` inside
  `RunController.execute()` (`vibecode/run.py:901-942`).

That satisfies both the startup-safety check and the "external LLM use only
through explicitly started external OpenCode flow" requirement.

### MEDIUM: `AgentRunService` drops important failure detail, so the main TUI can misreport failures

This is the clearest P24.1 issue I found.

`RunController.execute()` returns two different exit-code concepts:

1. `summary.exit_code`: the raw external agent exit code;
2. the function return code: Vibecode's overall status mapping
   (`vibecode/run.py:519-527`, `vibecode/run.py:1255`).

`AgentRunService.run()` stores the **function** return code directly in
`result["exit_code"]` (`vibecode/main_app.py:713-716`) and uses a generic
fallback error whenever `summary is None` (`vibecode/main_app.py:738-740`).

That creates two honesty gaps in the TUI summary path:

1. for ordinary agent failures, the right-panel summary can show the wrapper
   exit code instead of the real agent exit code;
2. for early aborts, the right-panel summary can collapse a specific reason into
   `"Run aborted — see run directory for details."`

I reproduced both during this review:

```text
Audit fake run:
- external fake agent exit: 7
- summary.json / runs show: Exit code    : 7
- AgentRunService result / right panel: Exit code: 1
```

```text
Early abort fake run:
- controller stderr: OpenCode command 'definitely-not-a-real-opencode' not found on PATH...
- right-panel summary: ERROR: Run aborted — see run directory for details.
```

The underlying artifacts are good, and the center/event stream still contains
useful information, but the completed TUI summary is less truthful than the run
artifacts and `runs show`. That is directly relevant to the review brief's
"hide early failures" watch item and to the requested center/right-panel status
output.

### LOW: the right-panel artifact list omits artifacts that the run layer already writes and `runs show` can display

`render_right_run_result()` only shows paths supplied in
`result["artifact_paths"]` (`vibecode/main_app.py:784-834`). But
`AgentRunService.run()` currently collects only:

- `events.jsonl`
- `summary.json`
- `guard_report.json`
- `guard_report.md`
- `checks_report.json`
- `agent_stdout.log`

(`vibecode/main_app.py:742-752`)

That is narrower than the real session artifact surface:

- `RunSession` defines `handoff_report_json`, `agent_stderr_log`, and
  `metadata.json` in the run directory (`vibecode/session_log.py:75-122`);
- the smoke run directories contained those files;
- `runs show` listed them correctly, but the TUI right-panel summary did not.

This is not a functional blocker because the artifacts still exist on disk and
`runs show` remains compatible. It is still a real inspectability gap relative
to the P24.1 brief's request for visible artifact paths and post-run results.

## Verification

### Commands run

```text
python -m vibecode.cli validate
python -m vibecode.cli context . --task "Review P24.1 [A]/[S] task/context prerequisites run orchestration fake OpenCode tests panel output session artifacts"
git --no-pager status --short
python -m compileall vibecode -q
python -m pytest -p no:cacheprovider -q tests\test_vibecode_run.py tests\test_vibecode_run_action_tui.py tests\test_vibecode_monitor.py tests\test_vibecode_show_run.py tests\test_vibecode_tui_entrypoint.py
python -m vibecode.cli --help
python -m vibecode.cli index --help
python -m vibecode.cli context --help
python -m vibecode.cli check .
python -m vibecode.cli runs list --repo C:\DATA\PROJECTS\VibecodeApp\tmp\p24_review_repo
python -m vibecode.cli runs show review-safe-001 --repo C:\DATA\PROJECTS\VibecodeApp\tmp\p24_review_repo --events
python -m vibecode.cli runs show review-audit-001 --repo C:\DATA\PROJECTS\VibecodeApp\tmp\p24_review_repo --events
python - <manual fake-OpenCode smoke for safe success, audit failure, and early abort>
```

### Results

- `python -m compileall vibecode -q` -> **PASS**
- focused P24.1 review suite -> **PASS**, `271 passed in 56.91s`
- `python -m vibecode.cli --help` -> **PASS**
- `python -m vibecode.cli index --help` -> **PASS**
- `python -m vibecode.cli context --help` -> **PASS**
- `python -m vibecode.cli check .` -> **PASS**
  - `unit tests` -> `PASS` (`328.375s`)
  - `cli help` -> `PASS`
  - `index command help` -> `PASS`
  - `context command help` -> `PASS`
- no repository lint command is declared in `pyproject.toml` or
  `.vibecode/checks/required_checks.yaml`, so no additional lint run existed for
  this review

Manual fake-OpenCode smoke results:

- `review-safe-001`
  - launch marker existed
  - overall status `success`
  - run directory contained 11 inspectable artifacts
  - `runs show --events` replayed 20 events successfully
- `review-audit-001`
  - launch marker existed
  - overall status `failure`
  - raw agent exit code in `summary.json` / `runs show`: `7`
  - TUI result/right-panel exit code: `1`
- `review-abort-001`
  - run directory still contained durable artifacts:
    `context_pack.md`, `events.jsonl`, `metadata.json`,
    `opencode_prompt.md`, `summary.json`
  - the right-panel summary fell back to a generic error string even though the
    underlying failure reason was more specific

### Existing command compatibility

The reviewed P24.1 work did not break the existing observable-run surface:

- `run` compatibility is covered by the passing `tests/test_vibecode_run.py`
  suite and by the manual fake-run smoke above;
- `monitor` compatibility is covered by the passing
  `tests/test_vibecode_monitor.py` suite, which still verifies argument
  forwarding into `MonitorApp` and CLI dispatch through `main(["monitor", ...])`;
- `runs show` compatibility is covered by the passing
  `tests/test_vibecode_show_run.py` suite and by the live replay of
  `review-safe-001` and `review-audit-001`.

## Final recommendation

Accept P24.1 as functionally correct for Phase 1, but queue one concrete fix:
make `AgentRunService` preserve the controller's real failure detail in the TUI
result layer — use the raw agent exit code from `RunSummary` when available, and
surface specific early-abort reasons instead of the generic fallback message.

Also widen the right-panel artifact list to include the already-written
`metadata.json`, `handoff_report.json`, and `agent_stderr.log` paths so the TUI
summary matches the artifact surface that `runs show` already exposes.

## Changed files

- `docs/audit/TUI_PHASE1_P24_AGENT_RUN_ACTIONS_REVIEW.md`
