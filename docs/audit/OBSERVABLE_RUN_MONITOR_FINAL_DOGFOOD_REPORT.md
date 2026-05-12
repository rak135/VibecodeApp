# Observable Run Monitor — Final Dogfood Report

**Date:** 2026-05-12  
**Repo:** `rak135/VibecodeApp` (`C:\DATA\PROJECTS\VibecodeApp`)  
**HEAD:** `6e317f3` (branch: main)  
**Environment:** Windows 11, Python 3.12, PowerShell 7

---

## 1. Product Goal

> VibecodeApp's observable run layer makes every agent session fully inspectable: structured events emitted to `events.jsonl`, artifacts captured under `.vibecode/runs/<session_id>/`, a live monitor TUI (`vibecode monitor`), and post-run replay via `vibecode runs show`.

This report validates that the observable run layer works end-to-end.

**Post-fix update (2026-05-12):** The pre-existing test failure and 7 ruff lint issues identified in this report have been fixed. See `docs/audit/OBSERVABLE_RUN_MONITOR_FINAL_FIX.md` for details.

---

## 2. Validation Commands Run

### 2.1 Compilation

```
python -m compileall vibecode -q
```

**Result: PASS** (exit code 0) — all Python source files compile without errors.

---

### 2.2 CLI Help Smoke

```
python -m vibecode.cli --help
python -m vibecode.cli monitor --help
python -m vibecode.cli runs --help
python -m vibecode.cli index --help
python -m vibecode.cli context --help
```

**Result: PASS** — all 18 registered commands appear in top-level `--help`.  
Commands confirmed: `init`, `inventory`, `index`, `context`, `map`, `validate`, `guard`, `check`, `handoff-check`, `run`, `run-plan`, `history`, `project`, `serve`, `dashboard`, `monitor`, `export-agents`, `runs`.

---

### 2.3 Full Pytest Suite

```
python -m pytest -p no:cacheprovider -q
```

**Result: 1754 PASSED** (250 s) — all tests green.

**Post-fix update:** The pre-existing `test_missing_gitignore_blocks_agent_launch` failure (documented below in the original report) has been fixed by deferring `events.jsonl` creation until after the git preflight check.

---

### 2.4 Ruff Linting

```
python -m ruff check vibecode/
```

**Result: PASS** (0 errors)

**Post-fix update:** All 7 previously-reported lint issues have been fixed (unused locals, unused imports, undefined name in ts_symbols.py).

---

### 2.5 `vibecode validate`

```
python -m vibecode.cli validate .
```

**Result: PASS** (with 1 warning)

All structure checks pass. One warning: `NOW.md contains placeholder text`. This is a cosmetic issue with the current handoff content.

---

### 2.6 `vibecode run-plan` (no agent launch)

```
python -m vibecode.cli run-plan . --task "dogfood smoke test"
```

**Result: PASS** — run plan assembled showing repo root, platform `opencode`, profile `safe.json`, git status CLEAN, index STALE/MISSING (index built for `c84bdc4`, HEAD now `6e317f3`), context pack and prompt paths.

---

### 2.7 Session Artifact Smoke (Python-layer, no real agent)

Verified using a temporary git repo + `vibecode init` + manual `RunSession` construction:

```python
from vibecode.session_log import RunSession
from vibecode.events import create_event, EventLevel, JsonlEventSink, EVENT_RUN_LIFECYCLE, EVENT_GUARD_FINDING, EVENT_INDEX_CHECK

session = RunSession(root=tmp, session_id='dogfood_b9b7e48c')
session.ensure_dir()
sink = session.create_event_sink()
# emit 4 events…
sink.emit(create_event(session_id, EVENT_RUN_LIFECYCLE, EventLevel.INFO, 'run started', data={'task': 'dogfood smoke'}))
sink.emit(create_event(session_id, EVENT_INDEX_CHECK, EventLevel.INFO, 'index ok', data={'status': 'ok'}))
sink.emit(create_event(session_id, EVENT_GUARD_FINDING, EventLevel.WARNING, 'guard finding', data={...}))
sink.emit(create_event(session_id, EVENT_RUN_LIFECYCLE, EventLevel.INFO, 'run complete', data={'exit_code': 0}))
session.snapshot_context_pack()   # copies .vibecode/current/context_pack.md
session.guard_report_json.write_text(…)
session.summary_json.write_text(…)
```

| Artifact | Status | Size |
|----------|--------|------|
| `events.jsonl` | ✅ OK | 1051 bytes (4 events) |
| `summary.json` | ✅ OK | 135 bytes |
| `context_pack.md` (snapshot) | ✅ OK | 30 bytes |
| `guard_report.json` | ✅ OK | 35 bytes |
| `opencode_prompt.md` | ⚠ Not present | No agent run |
| `agent_stdout.log` | ⚠ Not present | No agent run |
| `agent_stderr.log` | ⚠ Not present | No agent run |
| `handoff_report.json` | ⚠ Not present | No agent run |

All 4 events round-trip correctly through JSONL serialisation. The absent artifacts (`opencode_prompt.md`, `agent_*.log`, `handoff_report.*`) are expected when no real OpenCode process runs.

---

### 2.8 `vibecode runs list` and `vibecode runs show`

```
python -m vibecode.cli runs list --repo <tmp>
python -m vibecode.cli runs show dogfood_b9b7e48c --repo <tmp>
```

**Result: PASS**

`runs list` output:
```
Run sessions (most recent first):
  dogfood_b9b7e48c  [ok]  opencode  task='dogfood'
```

`runs show` output correctly renders: task, platform, exit code, overall status, and artifact paths (summary, events, guard report, context pack).

`vibecode runs show <id> --events` (tested via unit test suite, 40 tests in `test_vibecode_show_run.py`) replays all events in chronological order.

---

### 2.9 Monitor Smoke (formatting helpers, no PTY)

```python
from vibecode.monitor_app import MonitorApp, TUIEventSink, route_event, format_agent_line, format_vibecode_line
```

All helpers import and execute correctly:

| Call | Result |
|------|--------|
| `format_vibecode_line(run.lifecycle)` | `'[00:27:20] INFO    run.lifecycle: run started'` |
| `format_vibecode_line(run.guard_finding)` | `'[00:27:20] WARNING run.guard_finding: WARNING \| app.py \| …'` |
| `format_agent_line(run.agent_process stdout)` | `'agent says hello'` |
| `format_agent_line(run.agent_process started)` | `'[STARTED] agent started'` |
| `route_event(run.agent_process)` | `'agent'` (agent pane) |
| `route_event(run.lifecycle)` | `'event'` (event pane) |

**Result: PASS** — A full Textual TUI launch was not attempted (requires an interactive terminal; `vibecode monitor` is a streaming-text TUI, not a PTY). The 45 tests in `tests/test_vibecode_monitor.py` cover the full monitor path including `cmd_monitor` dispatch.

---

### 2.10 Real OpenCode Smoke Run

**Result: EXECUTED.** The previous "skipped" claim was wrong for this
environment. `opencode` is installed and responds:

```text
Get-Command opencode -ErrorAction SilentlyContinue
Path: C:\Users\Martin\AppData\Roaming\npm\opencode.ps1

opencode --version
1.14.48
```

Successful real smoke command:

```powershell
$env:OPENCODE_COMMAND='opencode run'
python -m vibecode.cli run . --platform opencode --guard-mode advisory --allow-dirty --task "REAL OPENCODE SMOKE TEST ONLY. Do not modify any files. Inspect the VibecodeApp observable run prompt/context and print a concise confirmation that the agent process executed. Include the marker VIBECODE_REAL_OPENCODE_SMOKE_OK in your final output."
```

Session: `20260512T051751673320Z`

The OpenCode process executed, exited 0, and wrote
`VIBECODE_REAL_OPENCODE_SMOKE_OK` to `agent_stdout.log`. Vibecode wrote
`events.jsonl`, `summary.json`, `opencode_prompt.md`, `context_pack.md`,
`agent_stdout.log`, `agent_stderr.log`, `guard_report.json`,
`guard_report.md`, and `handoff_report.json`.

The overall status was `incomplete`, not `success`, because handoff validation
flagged a pre-existing false-positive placeholder issue in
`.vibecode/handoff/NOW.md`. That validator was fixed after the smoke.

After fixing default command construction, a second no-env smoke used the same
`python -m vibecode.cli run ...` command and launched `opencode run` directly
(session `20260512T052734396950Z`). That run failed honestly with
`exit_code=-1` because OpenCode exceeded Vibecode's 300 second agent timeout
after doing extra inspection/test commands. Artifacts were still written and
`vibecode runs show --events` can replay the session.

Detailed evidence is in
`docs/audit/OBSERVABLE_RUN_MONITOR_REAL_OPENCODE_SMOKE.md`.

---

### 2.11 `vibecode check` (required checks runner)

```
python -m vibecode.cli check .
```

**Result: PASS** (exit code 0)

| Check | Status | Duration |
|-------|--------|----------|
| unit tests (`python -m pytest`) | **PASS** | 254.4 s |
| cli help | PASS | 0.063 s |
| index command help | PASS | 0.078 s |
| context command help | PASS | 0.062 s |

**Post-fix update:** All four checks now pass after the preflight buffering fix and ruff lint fixes.

---

## 3. Known Limitations

1. ~~**Pre-existing test failure**~~ — **FIXED.** `test_missing_gitignore_blocks_agent_launch` now passes after deferring `events.jsonl` creation until after git preflight check.

2. ~~**Pre-existing ruff issues**~~ — **FIXED.** All 7 ruff issues (unused locals/imports, undefined `posix`) are resolved. `ruff check vibecode` is clean.

3. ~~**No real OpenCode run possible**~~ — **CORRECTED.** OpenCode is available (`opencode --version` -> `1.14.48`) and real smoke sessions were executed. The first real smoke proved successful agent execution; the second proved the default command path now launches `opencode run` but can still time out if the agent keeps working past Vibecode's 300 second timeout.

4. **Monitor TUI non-interactive** — `vibecode monitor` requires an interactive terminal with full Textual rendering; it cannot be smoke-tested in a non-PTY CI/scripted environment. Validated via unit tests and helper-function smoke only.

5. **Index stale** — The `.vibecode/index/` was built for commit `c84bdc4` but HEAD is `6e317f3`. `vibecode run-plan` correctly reports this as a warning. A fresh `vibecode index` would resolve it.

6. **`NOW.md` placeholder warning** — `vibecode validate` warns that `NOW.md` contains placeholder text. This is cosmetic.

---

## 4. Is the Product Goal Met?

**Yes, with the caveats above.**

The observable run layer is complete and correct:

- ✅ `RunSession` dataclass with stable per-run artifact paths  
- ✅ `events.jsonl` written via `JsonlEventSink` with full `VibecodeEvent` round-trip  
- ✅ `summary.json` written at run end with guard mode, overall status, exit code  
- ✅ Context pack snapshot (`context_pack.md`) taken before run  
- ✅ Guard report JSON + Markdown written after guard phase  
- ✅ `RunController` emits structured events at every phase (git preflight, index check, context, prompt, agent process, guard findings, checks, handoff, summary)  
- ✅ `vibecode runs list / show [--events]` replay command works  
- ✅ Monitor TUI helpers (`route_event`, `format_agent_line`, `format_vibecode_line`) work correctly  
- ✅ Advisory/strict guard mode wired through `RunController → RunSummary → summary.json`  
- ✅ MCP tool call instrumentation (`McpToolCalled`, `McpToolReturned`, `McpToolFailed`) implemented  
- ✅ All 1754 tests pass (the 1 pre-existing failure has been fixed)
- ✅ All 7 ruff lint errors have been fixed
- ⚠ Real end-to-end agent run not testable in this environment  

---

## 5. Next Recommended Work

1. ~~**Fix `test_missing_gitignore_blocks_agent_launch`**~~ — **DONE.** Events are now buffered in memory until git preflight passes.

2. ~~**Fix ruff errors**~~ — **DONE.** All 7 ruff issues resolved.

3. **Refresh stale index** — run `vibecode index` so `run-plan` no longer warns about stale index.

4. ~~**Real OpenCode integration test**~~ — **DONE as a fake CI regression.** A fake `opencode` path now verifies launch, stdout/stderr logs, prompt/context snapshots, summary, agent events, and advisory guard behavior without requiring a paid model/API. Real OpenCode smoke remains a manual/local validation because credentials and model behavior are environment-specific.

5. **Monitor PTY test** — consider a headless Textual test using `textual.testing.Pilot` for basic TUI startup.

6. **Clean `NOW.md` placeholder text** — update handoff to remove the placeholder warning from `vibecode validate`.
