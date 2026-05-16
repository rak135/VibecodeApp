# TUI Phase 1+2 Validation

**Date:** 2026-05-16  
**Repo:** `C:\DATA\PROJECTS\VibecodeApp`  
**HEAD:** `d70f746` (`master`)  
**Environment:** Windows / PowerShell / Python 3.12

## Verdict

**Partially ready with one blocker.**

The core TUI, refresh/rebuild, context, guard/check, fake OpenCode, provider abstraction, and external-terminal surfaces all passed fresh validation. The blocker is handoff hygiene: `handoff-check` fails because `.vibecode/handoff/NOW.md` still contains placeholder wording, and `vibecode validate .` reports the same warning.

## Commands run

```text
git status --short
python -m compileall vibecode -q
python -m pytest -p no:cacheprovider -q tests/test_vibecode_cli.py tests/test_vibecode_tui_entrypoint.py tests/test_vibecode_repo_status.py tests/test_vibecode_refresh.py tests/test_vibecode_context_pack.py tests/test_vibecode_guard.py tests/test_vibecode_check.py tests/test_vibecode_handoff.py tests/test_vibecode_handoff_cli.py
python -m pytest -p no:cacheprovider -q tests/test_vibecode_main_tui.py tests/test_vibecode_run_action_tui.py tests/test_vibecode_context_tui.py tests/test_vibecode_debug_cockpit.py tests/test_vibecode_monitor.py tests/test_vibecode_dashboard.py
python -m pytest -p no:cacheprovider -q tests/test_vibecode_run_controller.py tests/test_vibecode_opencode_adapter.py tests/test_vibecode_run_post.py tests/test_vibecode_run.py tests/test_vibecode_external_terminal.py tests/test_vibecode_agent_provider.py tests/test_vibecode_show_run.py
python -m pytest -p no:cacheprovider -q
python -m vibecode.cli --help
python -m vibecode.cli init --help
python -m vibecode.cli index --help
python -m vibecode.cli context --help
python -m vibecode.cli run --help
python -m vibecode.cli monitor --help
python -m vibecode.cli runs --help
python -m vibecode.cli guard --help
python -m vibecode.cli check --help
python -m vibecode.cli handoff-check --help
python -m vibecode.cli serve --help
python -m vibecode.cli guard .
python -m vibecode.cli handoff-check .
python -m vibecode.cli check .
python -m vibecode.cli validate .
git rev-parse --short HEAD
git branch --show-current
```

## Pass / fail / skipped

| Area | Result | Evidence |
|---|---:|---|
| Baseline repo state | PASS | `git status --short` was clean at start. |
| Compile | PASS | `python -m compileall vibecode -q` completed cleanly. |
| CLI / status / refresh / context / guard / check / handoff subsets | PASS | `238 passed in 17.58s`. |
| TUI / debug cockpit / monitor / dashboard subsets | PASS | `434 passed in 63.77s`. |
| Run / provider / adapter / replay subsets | PASS | `387 passed in 198.97s`. |
| Full pytest | PASS | `2396 passed, 35 warnings in 377.36s`. |
| CLI discovery | PASS | All help commands exited `0`. |
| Guard action | PASS | `python -m vibecode.cli guard .` printed `Guard check passed. No violations found.` |
| Check wrapper | PASS | `python -m vibecode.cli check .` returned `PASS` for unit tests, cli help, index help, and context help. |
| Handoff action | FAIL | `python -m vibecode.cli handoff-check .` failed on `.vibecode/handoff/NOW.md`. |
| Repo validation | PASS with warning | `python -m vibecode.cli validate .` warned about placeholder text in `NOW.md`. |
| Live interactive TUI smoke | SKIPPED | Non-interactive PowerShell session; no safe live TUI smoke available here. |
| Real OpenCode smoke | SKIPPED | Not run; the validation used fake/local OpenCode coverage to avoid external model spend and workspace risk. |

## Evidence

- Fake OpenCode and provider abstraction are covered by local-only tests that generate fake `opencode.cmd` wrappers and do not require a real model call.
- Refresh/rebuild preservation is covered by `tests/test_vibecode_refresh.py`, including checks that customized manual files are preserved and `.vibecode/logs/*` / `.vibecode/runs/*` are not deleted.
- Right-panel event/artifact surfacing is covered by the TUI/debug/monitor slices and the run replay tests.

## Artifact paths inspected

- `.vibecode/current/check_results.json`
- `.vibecode/current/validation.json`
- `.vibecode/index/file_inventory.json`
- `.vibecode/index/symbol_map.json`
- `.vibecode/index/dependency_map.json`
- `.vibecode/index/test_map.json`
- `.vibecode/handoff/NOW.md`

## Manual file preservation

`python -m vibecode.cli validate .` reported that human-maintained files are outside the generated artifact set, and the refresh slice passed the preservation tests that keep customized manual truth files byte-for-byte while leaving logs and runs intact.

## Known limitations

1. `.vibecode/handoff/NOW.md` still contains placeholder wording, so `handoff-check` fails.
2. `python -m vibecode.cli validate .` emits the same warning.
3. No live interactive TUI or real OpenCode smoke was run in this non-interactive session.

## Final assessment

The product surfaces needed for supervised Phase 1+2 use are in good shape, but the workspace is not fully ready until the handoff placeholder wording is cleaned up.
