# TUI Phase 2 P25 External Terminal Review

Generated: 2026-05-16

## Verdict

PASS WITH CORRECTIONS. P25.1 keeps external-terminal launch separate from the
Phase 1 internal run/monitor flow, stays honest that Textual is not an embedded
interactive terminal, uses the generated `opencode_prompt.md` path end to end,
reports launch status usefully in the center/right panels, handles unsupported
platforms and missing terminal executables without pretending launch succeeded,
and relies on mocked/fake launch paths in automated tests instead of requiring a
real Windows Terminal or OpenCode install.

I found one medium implementation issue and one low follow-up:

1. The adapter advertises a `cmd.exe` fallback, but `launch()` has no `cmd`
   branch and still constructs a PowerShell launch when `detect_terminal()`
   returns `"cmd"`.
2. The tests cover the adapter, service, and panel renderers well, but they do
   not directly execute the bound `[E]` action / worker / callback path in
   `VibecodeMainApp`.

This review only adds this document, per task scope.

## Findings

### PASS: the TUI stays honest about interactivity and keeps external launch separate from internal orchestration

The reviewed code does **not** fake an interactive terminal inside Textual:

- the center placeholder explicitly says an interactive terminal is not
  implemented inside the TUI and directs users to `[E]` for a real external
  terminal window (`vibecode/main_app.py:53-65`);
- `monitor_app.py` also states that `vibecode monitor` is streaming text mode,
  not a PTY (`vibecode/monitor_app.py:1-13`).

The Phase 2 external path is also cleanly separated from the existing
Vibecode-orchestrated run flow:

- `[A]` / `[S]` use `AgentRunService` and `RunController`
  (`vibecode/main_app.py:664-781`, `vibecode/main_app.py:1480-1533`);
- `[E]` is a separate explicit binding and action
  (`vibecode/main_app.py:1158-1168`, `vibecode/main_app.py:1314-1316`);
- external launch uses `ExternalTerminalService`, which only generates context,
  resolves the command, and calls the adapter
  (`vibecode/main_app.py:866-954`);
- startup does not launch anything unexpectedly: `on_mount()` only logs ready
  state, and the external service is resolved lazily
  (`vibecode/main_app.py:1236-1239`, `vibecode/main_app.py:1261-1263`).

That satisfies the review checks about not faking embedded interactivity,
keeping external launch distinct from internal orchestration, and not launching
an external terminal unexpectedly.

### PASS: Windows command construction is mostly safe, and the generated prompt path is really used

The command construction is safer than a naive shell-string approach:

- prompt/profile/session values are inserted via single-quoted PowerShell
  strings, with embedded `'` doubled by `_quote_ps_single()`
  (`vibecode/adapters/external_terminal.py:70-116`);
- the Windows Terminal path, repo root, and PowerShell executable are passed as
  separate `Popen(args)` list elements rather than concatenated into one shell
  string (`vibecode/adapters/external_terminal.py:271-290`);
- the PowerShell fallback also quotes the repo path inside `Set-Location`
  (`vibecode/adapters/external_terminal.py:281-287`).

The generated prompt artifact is used end to end:

- `ExternalTerminalService.run()` writes `context_pack.md`, reads it back, writes
  `opencode_prompt.md`, stores both paths in the result, and passes the prompt
  path to `adapter.launch()`
  (`vibecode/main_app.py:919-947`);
- the center/right renderers surface that prompt path back to the user
  (`vibecode/main_app.py:957-1016`);
- tests explicitly assert that the generated prompt path is passed to the
  adapter and shown in both panel renderers
  (`tests/test_vibecode_external_terminal.py:518-538`,
  `tests/test_vibecode_external_terminal.py:556-694`).

Example constructed command from a review-time injected launch capture:

```text
wt.exe new-tab -d "C:\Work\Repo With Spaces" -- pwsh.exe -NoExit -Command <opencode_cmd>
```

Captured argv shape:

```text
[
  'C:\\Program Files\\WindowsApps\\wt.exe',
  'new-tab',
  '-d',
  'C:\\Work\\Repo With Spaces',
  '--',
  'C:\\Program Files\\PowerShell\\7\\pwsh.exe',
  '-NoExit',
  '-Command',
  "$env:VIBECODE_PROMPT_PATH = 'C:\\Work\\Repo With Spaces\\.vibecode\\current\\opencode_prompt.md'; ...; opencode run"
]
```

That is the right general shape for Windows paths with spaces: the repo path is
not shell-split, and the prompt path is single-quoted inside PowerShell.

### PASS: missing terminal / unsupported platform behavior is handled honestly, and panel reporting is useful

The adapter handles the obvious failure path honestly:

- `detect_terminal()` returns `"unavailable"` when not on Windows or when none
  of `wt`, PowerShell, or `cmd` are found
  (`vibecode/adapters/external_terminal.py:124-147`);
- `launch()` returns `launched=False`, `terminal_kind="unavailable"`, no PID,
  and a concrete error message instead of pretending success
  (`vibecode/adapters/external_terminal.py:248-261`).

Review-time failure-path capture:

```text
launched=False
terminal_kind=unavailable
error=No supported terminal emulator found. Install Windows Terminal (wt.exe) or ensure PowerShell is available on PATH.
```

The center/right panel output is also useful rather than vague:

- while the worker is running, the center panel says `Status: launching external terminal…`
  (`vibecode/main_app.py:1595-1604`);
- on completion, the center panel shows launched vs failed status, terminal
  kind, optional PID, prompt path, and a reminder that the interactive session
  is in the external window (`vibecode/main_app.py:957-989`);
- the right panel logs task, profile, context path, prompt path, terminal kind,
  command, and either `LAUNCHED` or `FAILED`
  (`vibecode/main_app.py:992-1016`, `vibecode/main_app.py:1630-1645`).

That meets the review requirement that center/right panels report launch status
usefully and that launch failures are not hidden.

### PASS: automated tests do not require a real Windows Terminal, a real OpenCode session, or a direct LLM call

The dedicated external-terminal tests are explicit about using mocks/fakes:

- adapter tests inject fake `which()` and fake `Popen()` functions instead of
  launching a real terminal (`tests/test_vibecode_external_terminal.py:167-425`);
- service tests patch `write_context_pack()` / `write_opencode_prompt()` and
  inject a fake adapter (`tests/test_vibecode_external_terminal.py:436-544`);
- one test explicitly asserts the adapter launch path never directly invokes the
  OpenCode binary as the subprocess being spawned
  (`tests/test_vibecode_external_terminal.py:702-723`);
- another asserts the service result is fire-and-forget and has no fake
  `exit_code` claim (`tests/test_vibecode_external_terminal.py:725-744`);
- `test_no_llm_call()` checks that the external-terminal section of
  `main_app.py` is not introducing a direct LLM client call
  (`tests/test_vibecode_external_terminal.py:540-549`);
- the broader TUI startup tests also assert `cmd_tui` does not import or launch
  OpenCode/LLM machinery on startup (`tests/test_vibecode_main_tui.py:411-466`).

Fresh evidence from this review:

- `python -m pytest -q tests/test_vibecode_external_terminal.py`
  -> **63 passed in 0.43s**
- `python -m pytest -q tests/test_vibecode_external_terminal.py tests/test_vibecode_main_tui.py tests/test_vibecode_monitor.py`
  -> **309 passed in 1.47s**
- `python -m pytest -q`
  -> **2302 passed, 35 warnings in 370.10s**
- `python -m vibecode.cli check .`
  -> **PASS** for `unit tests`, `cli help`, `index command help`, and
  `context command help`

### MEDIUM: the documented `cmd.exe` fallback is not actually implemented

This is the clearest P25.1 issue.

The adapter documentation and detection logic both claim a `cmd.exe` fallback:

- module docs list `cmd.exe` / `cmd` as the fourth terminal option
  (`vibecode/adapters/external_terminal.py:15-23`);
- `detect_terminal()` can return `"cmd"`
  (`vibecode/adapters/external_terminal.py:138-147`);
- tests cover that detection result
  (`tests/test_vibecode_external_terminal.py:198-208`).

But `launch()` only has two real branches:

1. `"windows-terminal"` -> build a `wt new-tab ... -- pwsh/powershell ...` argv
   (`vibecode/adapters/external_terminal.py:271-278`);
2. everything else -> build a PowerShell launch with `Set-Location ...`
   (`vibecode/adapters/external_terminal.py:279-287`).

There is no `terminal == "cmd"` branch. If detection returns `"cmd"`, the code
still calls `_find_ps()` and tries to launch PowerShell while reporting
`terminal_kind="cmd"`.

That creates a real mismatch in both design and failure semantics:

- the implementation does not actually provide the documented `cmd` fallback;
- on a machine where only `cmd` is discoverable, the result can claim `cmd`
  while attempting `powershell.exe`;
- the current tests would not catch that, because they only test `cmd`
  detection, not `cmd` launch behavior.

This is not a reason to reject the whole feature, but it is a material adapter
honesty gap that should be corrected before treating `cmd` as supported.

### LOW: the `[E]` binding/callback path is only indirectly tested

The test coverage for the external-terminal feature is good at the service and
renderer level, but it stops short of a direct action-wiring regression:

- I found dedicated coverage for `ExternalTerminalService`,
  `render_center_external_launch_status()`, and
  `render_right_external_launch_log()` in
  `tests/test_vibecode_external_terminal.py`;
- I did **not** find tests that directly call `action_cmd_external()`,
  `_start_external()`, `_on_external_task_received()`, or `_on_external_done()`
  in the way the P24 action path is tested for `[A]` / `[S]`.

The runtime code itself is thin and readable:

- `[E]` binds to `action_cmd_external()`
  (`vibecode/main_app.py:1164`, `vibecode/main_app.py:1314-1316`);
- `_start_external()` prompts for a task when needed, updates the center panel
  to a launching state, runs the service on a daemon thread, and routes results
  back through `_on_external_done()` / `_on_external_error()`
  (`vibecode/main_app.py:1579-1649`).

So this is a follow-up coverage gap rather than a demonstrated product bug.

## Extension path for more providers later

The current shape is reasonably extensible:

- `VibecodeMainApp` only depends on a small service/result contract for external
  launch (`ExternalTerminalService.run()` -> flat result dict);
- `ExternalTerminalService` already accepts an injected adapter, and the adapter
  itself only needs to provide a `launch(...)` method
  (`vibecode/main_app.py:877-885`, `vibecode/main_app.py:939-953`);
- the panel renderers consume generic launch-result fields such as `launched`,
  `terminal_kind`, `pid`, `error_message`, `prompt_path`, and `command`
  (`vibecode/main_app.py:957-1016`).

So a future provider can reuse the same TUI plumbing by supplying a different
provider-specific service/adapter pair with the same result shape.

The main provider-specific seams that would need parameterization are:

1. the hard-coded `Provider: OpenCode` strings in the center/status renderers;
2. `write_opencode_prompt()` and `resolve_opencode_command()`, which are
   currently OpenCode-specific rather than provider-agnostic.

That is a good extension story: the architectural seam already exists, but the
provider label and prompt/command helpers still need one more abstraction layer.

## Verification

### Commands run

```text
python -m vibecode.cli validate
python -m vibecode.cli context . --task "Review P25.1 external terminal adapter design"
python -m pytest -q tests/test_vibecode_external_terminal.py
python -m pytest -q tests/test_vibecode_external_terminal.py tests/test_vibecode_main_tui.py tests/test_vibecode_monitor.py
python -m pytest -q
python -m vibecode.cli check .
python -c "<capture example Windows Terminal launch argv>"
python -c "<capture missing terminal / unsupported platform result>"
git --no-pager status --short
```

### Results

- `python -m vibecode.cli validate` -> **PASS with existing repo-state warning**:
  `NOW.md` still contains placeholder text; that is unrelated to P25.1
- `python -m pytest -q tests/test_vibecode_external_terminal.py`
  -> **PASS**, `63 passed in 0.43s`
- `python -m pytest -q tests/test_vibecode_external_terminal.py tests/test_vibecode_main_tui.py tests/test_vibecode_monitor.py`
  -> **PASS**, `309 passed in 1.47s`
- `python -m pytest -q`
  -> **PASS**, `2302 passed, 35 warnings in 370.10s`
- `python -m vibecode.cli check .`
  -> **PASS** for all required checks
- example launch capture -> **PASS**, produced a `wt.exe new-tab -d ... -- pwsh.exe -NoExit -Command ...` argv with the repo path and prompt path preserved
- missing-terminal capture -> **PASS**, returned `launched=False`, `terminal_kind=unavailable`, and a concrete error message
- `git --no-pager status --short` before writing this review -> **PASS**, clean worktree

## Changed files

- `docs/audit/TUI_PHASE2_P25_EXTERNAL_TERMINAL_REVIEW.md`
