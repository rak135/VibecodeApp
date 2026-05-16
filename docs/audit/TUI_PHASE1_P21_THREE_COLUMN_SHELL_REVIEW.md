# TUI Phase 1 P21 Three-Column Shell Review

Generated: 2026-05-16

## Verdict

PASS WITH FOLLOW-UP. P21.1 delivers the requested no-argument `vibecode`
startup, preserves explicit subcommands and `--help`, renders a real
three-column Textual shell, shows the resolved repo path and required left-panel
status fields, wires `[R]` to the refresh service, and keeps startup free of
OpenCode/LLM calls.

I found one medium follow-up and one low follow-up:

1. the right-hand event panel is useful, but it still does not surface the exact
   artifact paths and context-summary detail promised by the P21.1 brief;
2. the tests cover rendering and startup well, but they do not directly exercise
   the `r` binding / `action_refresh_repo()` path, so the refresh keyboard wiring
   is proven mainly by manual smoke rather than by an automated regression test.

This review only adds this document, per task scope.

## Findings

### PASS: `vibecode` is now the primary TUI command and existing CLI behavior remains usable

`vibecode/cli.py:568-576` routes to `vibecode.main_app.cmd_tui()` only when
`args.command is None`, so plain `vibecode` opens the main shell while explicit
commands still flow through `_dispatch()` (`vibecode/cli.py:607-721`). The
explicit alias is also present: `tui` is registered with an optional `repo`
argument and dispatched to the same bootstrap path
(`vibecode/cli.py:447-467`, `vibecode/cli.py:717-719`).

That keeps the command surface stable:

- top-level `--help` is still argparse-managed;
- named commands like `index`, `context`, `guard`, `run`, and `monitor` still
  parse and dispatch normally;
- `vibecode tui [repo]` remains a diagnostic/explicit alias instead of a second
  code path.

Evidence:

- `tests/test_vibecode_tui_entrypoint.py:22-113`
- `tests/test_vibecode_main_tui.py:510-544`
- `tests/test_vibecode_cli.py:10-137`
- manual help smoke below

### PASS: the shell renders the requested three-column structure and shows the resolved repo path

`VibecodeMainApp.compose()` builds the shell as one `Horizontal` container with
three `Vertical` columns: left status/actions, center agent console, and right
event log (`vibecode/main_app.py:188-202`). The left panel text is assembled by
`render_left_panel()` and includes:

- `Active repo`
- `.vibecode exists`
- `manual files`
- `generated index`
- `current context`
- `checks`
- `git state`
- the full Phase 1 action list

The resolved path comes from `RepoResolutionService.resolve()` with the required
priority order of explicit path -> registry active project -> cwd
(`vibecode/repo_resolution.py:16-42`), then `cmd_tui()` computes status once and
passes both values into the TUI bootstrap (`vibecode/main_app.py:319-345`).

The no-arg smoke render in this environment showed the real resolved repo path
and the requested columns:

```text
VibecodeApp - Control Shell
Status / Actions | Agent Console | Vibecode Events
Active repo:
  C:\DATA\PROJECTS\VibecodeApp
Status:
  .vibecode exists: yes
  manual files: ok
  generated index: stale
  current context: ready
  checks: pass
  git state: clean
```

Evidence:

- `vibecode/main_app.py:85-135`
- `vibecode/main_app.py:188-206`
- `tests/test_vibecode_main_tui.py:46-202`
- `tests/test_vibecode_tui_entrypoint.py:22-100`

### PASS: the center panel is an honest Phase 1 console placeholder, not a fake PTY

The center panel content is explicit about its limits. `_CENTER_PLACEHOLDER`
states `Provider: OpenCode`, `Current task: none`, `No command running`, and
most importantly:

- `Phase 1 placeholder`
- `A fully embedded interactive terminal is not implemented in Phase 1`
- `Use 'vibecode monitor' to run an agent session with live output`

That text is rendered as a `Static`, with a separate `RichLog` underneath for
future/output display (`vibecode/main_app.py:50-58`, `vibecode/main_app.py:195-198`).
I found no subprocess-backed pseudo-terminal behavior in this shell. The design
is honest about being a placeholder/output area, which is the correct Phase 1
shape.

This also satisfies the review requirement to confirm that Phase 1 intentionally
does **not** embed an interactive PTY.

Evidence:

- `vibecode/main_app.py:50-58`
- `vibecode/main_app.py:195-198`
- `tests/test_vibecode_main_tui.py:240-260`

### PASS: startup and rendering stay decoupled from mutation/orchestration logic

The reviewed code keeps concerns separated in a way that is appropriate for
Phase 1:

- `RepoResolutionService` resolves the repo path (`vibecode/repo_resolution.py`)
- `RepoStatusService` computes repo health without Textual
  (`vibecode/repo_status.py:76-122`)
- `render_status_lines()` and `render_left_panel()` are exported pure-ish
  rendering helpers (`vibecode/main_app.py:66-135`)
- `VibecodeRefreshService` owns the actual refresh/rebuild filesystem work
  (`vibecode/refresh.py:82-267`)
- `VibecodeMainApp` only orchestrates UI events and calls the services

That means the TUI is not tightly coupled to filesystem mutation logic, which
was one of the main architectural checks in the review brief.

### PASS: `[R]` really triggers refresh and updates displayed status

The binding table maps `r` to `refresh_repo` (`vibecode/main_app.py:154-163`).
`action_refresh_repo()` logs a start event, resolves/uses `VibecodeRefreshService`,
spawns a background thread, then uses `call_from_thread()` to publish completion
or failure back onto the TUI thread (`vibecode/main_app.py:212-224`).

On success, `_on_refresh_done()` logs refresh status, warnings/errors, an
artifact count, a next-step hint, and then recomputes repo status through
`RepoStatusService` before re-rendering the left panel
(`vibecode/main_app.py:272-297`).

I verified the real key path in a smoke run by launching `python -m vibecode.cli`
and sending `r` into the running TUI. The shell reported refresh start and
completion, and the left panel changed from `generated index: stale` to
`generated index: fresh`. It also honestly updated `current context` to
`missing` and `checks` to `not run`, which matches the refresh service clearing
runtime/current artifacts during rebuild rather than faking a healthy state.

Smoke excerpt:

```text
[R] Refresh started...
[R] Refresh complete: ok
artifacts: 10 written
generated index: fresh
current context: missing
checks: not run
```

### PASS: no OpenCode or LLM call occurs on startup

`cmd_tui()` resolves the repo and status, then either prints a Textual install
hint or runs `VibecodeMainApp` (`vibecode/main_app.py:319-345`). I found no
startup import or call path into `RunController`, monitor execution, process
runner, OpenCode adapter, or any LLM client. The only subprocess use in the
reviewed startup path is `git status --short` inside `RepoStatusService`
(`vibecode/repo_status.py:94-108`).

Automated tests also cover this directly:

- `tests/test_vibecode_main_tui.py:410-467` verifies `cmd_tui()` runs the app
  rather than launching OpenCode and guards against opencode imports on startup
- `tests/test_vibecode_main_tui.py:469-502` covers the Textual-missing fallback

### MEDIUM: the right event panel is useful, but it does not yet expose exact artifact paths or context-summary detail promised by P21.1

The right panel is not empty or fake. On mount it logs `[ready]` and `[repo]`
(`vibecode/main_app.py:204-206`), and refresh emits start/completion/warning/error
messages (`vibecode/main_app.py:214`, `vibecode/main_app.py:272-285`). That is
useful operator feedback, and the smoke run confirmed those lines appear.

The remaining gap is fidelity. P21.1 asked the right panel to show artifact
paths and context-preview summary when available. The current refresh success
path only logs an artifact count:

```python
arts = list(report.generated_artifacts)
if arts:
    self._log_event(f"    artifacts: {len(arts)} written")
```

That means the UI tells the operator *that* artifacts were written, but not
*which* ones or where. There is also no context-preview summary surfaced in the
right pane when a context pack already exists or later becomes available.

I do not treat this as a Phase 1 blocker because the panel is already useful and
honest, but it is a real shortfall against the PRD's stronger right-panel brief.

### LOW: the tests do not directly exercise the refresh key-binding/action path

The automated coverage is strong on helper rendering, startup routing, repo
resolution, no-OpenCode startup, and injected/default refresh-service selection
(`tests/test_vibecode_main_tui.py:46-544`, `tests/test_vibecode_tui_entrypoint.py:22-192`).

What I did **not** find in the reviewed tests:

- a direct call to `action_refresh_repo()`
- a test asserting the `Binding("r", "refresh_repo", ...)` table
- a Textual-level interaction test proving the `r` key reaches the refresh path
- a compose/layout assertion that locks the three-column widget tree

The manual smoke in this environment confirms `[R]` works today, so this is not
a current functional failure. It is still a gap relative to the PRD's request
for refresh-action wiring coverage, and it leaves a small regression window if
future refactors accidentally break the binding or event-thread handoff.

## Verification

### Commands and results

- `git status --short` -> clean worktree before writing this review
- `python -m compileall vibecode -q` -> PASS
- `python -m pytest -p no:cacheprovider -q tests\test_vibecode_main_tui.py tests\test_vibecode_tui_entrypoint.py tests\test_vibecode_cli.py tests\test_vibecode_repo_status.py tests\test_vibecode_active_project_fallback.py`
  -> PASS, `181 passed, 1 warning in 3.84s`
- `python -m pytest -p no:cacheprovider -q` -> PASS, `2004 passed, 35 warnings in 382.28s`
- `python -m vibecode.cli --help` -> PASS
- `python -m vibecode.cli index --help` -> PASS
- `python -m vibecode.cli context --help` -> PASS
- `python -m vibecode.cli tui --help` -> PASS
- `python -m vibecode.cli` -> PASS as startup smoke; TUI rendered in this environment
- in-app `r` key smoke against the live TUI -> PASS; refresh started, completed,
  and updated left-panel status

### Help/smoke notes

The parser help output still lists the existing commands plus the explicit `tui`
alias, so the no-arg TUI behavior did not break the command surface.

The no-arg smoke render showed the expected three-column shell and the resolved
repo path `C:\DATA\PROJECTS\VibecodeApp`.

### Textual limitations noted during review

Textual's alternate-screen rendering is noisy when captured through a
non-interactive terminal transcript: repeated frames, wrapped columns, and
truncated lines appear in the raw capture even though the live UI is usable.
That affects review evidence formatting, not the correctness of the shell.

The center panel is intentionally **not** an embedded PTY. The implementation is
correctly limited to placeholder/output behavior in Phase 1, and the dedicated
live-stream experience remains `vibecode monitor`.

## Final recommendation

Accept P21.1 as a solid Phase 1 shell implementation. The main command routing,
three-column layout, status display, refresh action, startup safety, and overall
separation of concerns are all in place and backed by credible validation.

Carry one medium follow-up into P21.3 or the next adjacent task: upgrade the
right event panel from "useful summary" to "artifact/path-aware operator truth"
so it shows actual artifact locations and context-summary detail instead of only
aggregate counts.
