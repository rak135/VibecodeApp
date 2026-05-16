# TUI Phase 2 P27 Event Artifact Surfacing Review

Generated: 2026-05-16

## Verdict

PASS. The debug cockpit is genuinely split from agent output, run-artifact paths match the session layout, missing artifacts are reported honestly, and log summaries are bounded instead of reading whole files into memory. I found no evidence that the watcher introduces any LLM/OpenCode call path.

## Findings

### PASS: right-panel Vibecode debug is distinct from agent output

`vibecode/main_app.py` renders a dedicated right-panel debug cockpit (`#right-debug-cockpit`) plus a separate event stream (`#main-event-log`). Agent process events go to the center pane via `handle_run_event()` when `route_event()` returns `"agent"`, while all other Vibecode events are formatted with `format_vibecode_line()` and routed into the right-side log.

The monitor TUI follows the same split: `vibecode/monitor_app.py` routes `EVENT_AGENT_PROCESS` to the agent pane and all other event types to the Vibecode event pane.

### PASS: artifact paths stay aligned with the run directory layout

`RunSession` defines the canonical run-artifact paths (`events.jsonl`, `summary.json`, `metadata.json`, `guard_report.json/md`, `checks_report.json`, `handoff_report.json/md`, `agent_stdout.log`, `agent_stderr.log`, `context_pack.md`, `opencode_prompt.md`). `SessionArtifactWatcher.snapshot()` and `vibecode/show_run.py` both consume those paths directly, so the review surface stays compatible with existing `runs list/show` behavior.

### PASS: missing artifacts are handled honestly

`SessionArtifactWatcher.snapshot()` marks each artifact with `exists`, emits a `Missing artifacts: ...` warning, and uses `(no active run session)` when nothing is selected. `load_run_events()` returns a missing-file flag instead of pretending an empty file exists, and `runs show` prints `events.jsonl not found.` when the event artifact is absent.

`_summarize_text_file()` also reports `(missing)` and `(unreadable: ...)` explicitly, so the right panel does not hide failure states under a generic success message.

### PASS: large logs are bounded and clearly truncated

`_summarize_text_file()` caps bytes and lines, and `render_right_debug_cockpit()` appends `[truncated]` markers when the summary was clipped. That keeps context/events/stderr previews readable without loading giant logs into memory.

### PASS: the watcher does not introduce OpenCode/LLM calls

`SessionArtifactWatcher` only computes paths, checks file existence, and summarizes local files through `RunSession`. It does not import or invoke provider, subprocess, or OpenCode logic.

## Evidence

### Test output

- `python -m pytest tests\test_vibecode_debug_cockpit.py tests\test_vibecode_monitor.py tests\test_vibecode_show_run.py -q`
  - `156 passed in 0.75s`
- `python -m vibecode.cli check C:\DATA\PROJECTS\VibecodeApp`
  - `PASS: unit tests (exit code 0, 378.578s)`
  - `PASS: cli help (exit code 0, 0.063s)`
  - `PASS: index command help (exit code 0, 0.093s)`
  - `PASS: context command help (exit code 0, 0.079s)`

### Example right-panel / debug model output

```text
Session: sess-ev
Run dir: C:\DATA\PROJECTS\VibecodeApp\tmp\review-evidence\.vibecode\runs\sess-ev
Artifacts:
  [ok     ] context pack: ...
  [ok     ] opencode prompt: ...
  [ok     ] events.jsonl: ...
  [ok     ] summary.json: ...
  [missing] agent stdout.log: ...
  [ok     ] agent stderr.log: ...
  [missing] guard report: ...
  [missing] checks report: ...
  [missing] handoff report: ...
Context preview:
  Review event artifact surfacing
  ...
  [truncated]
Event/log excerpts:
  events: ...
  [truncated]
  stderr: ERR
  [truncated]
Warnings / errors:
  WARN: Missing artifacts: agent stdout.log, guard report, checks report, handoff report
```

### Example missing-artifact handling

`snapshot["warnings"][0]` was:

```text
Missing artifacts: agent stdout.log, guard report, checks report, handoff report
```

### Example truncation behavior

The same snapshot reported:

```text
TRUNCATION FLAGS: True True True
```

## Changed Files

- `docs/audit/TUI_PHASE2_P27_EVENT_ARTIFACT_SURFACING_REVIEW.md`
