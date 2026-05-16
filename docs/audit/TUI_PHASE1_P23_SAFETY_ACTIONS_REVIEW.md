# TUI Phase 1 P23 Safety Actions Review

Generated: 2026-05-16

## Verdict

PASS WITH FOLLOW-UP. P23.1 wires the non-agent safety actions into
`VibecodeMainApp`, keeps them off the OpenCode/LLM path, reuses the existing
guard/check/handoff implementations, keeps failures visible in the right panel,
and runs each action on a background thread so the TUI stays alive after
failures.

I found one medium implementation issue and one low follow-up:

1. `[I]` does not use the existing freshness checker, so a stale-but-present
   index can still be shown as current.
2. The tests cover services, renderers, and callback output well, but they do
   not directly execute the bound action methods or cover the stale-age /
   changed-HEAD / changed-file-set inspect cases.

This review only adds this document, per task scope.

## Findings

### PASS: `[G]`, `[T]`, and `[H]` are thin wrappers over the existing shared logic

The service split is real and appropriately narrow:

- `GuardService.run()` calls `inspect_git_state()`,
  `evaluate_project_guard()`, and `write_guard_result()`
  (`vibecode/main_app.py:252-318`).
- `CheckService.run()` calls `run_checks()` and `write_check_results()`
  (`vibecode/main_app.py:349-408`), matching the existing CLI behavior in
  `vibecode/check.py:174-236`.
- `HandoffService.run()` calls `validate_handoff_files()` and feeds it the same
  git-derived diff shape used by the CLI path
  (`vibecode/main_app.py:444-494`, `vibecode/handoff.py:111-247`).

That satisfies the main reuse requirement for the safety actions: the TUI does
not duplicate the guard, check, or handoff engines. It only adapts their return
shapes for panel rendering.

I also found no OpenCode or LLM call in these actions. The bindings and action
methods only resolve a local service, start a worker thread, and route the
result back through `call_from_thread()` (`vibecode/main_app.py:751-760`,
`vibecode/main_app.py:859-928`).

### PASS: failures remain visible, artifact paths are surfaced, and the TUI stays alive after service errors

The right-panel summaries are concise but honest:

- inspect shows the repo-map path and a refresh hint on error
  (`vibecode/main_app.py:219-249`);
- guard shows pass/fail, error/warning counts, finding summaries, and
  `guard_result.json` when it was written (`vibecode/main_app.py:321-346`);
- checks show pass/fail, totals, per-check PASS/FAIL/WARN lines, and
  `.vibecode/current/check_results.json` when it was written
  (`vibecode/main_app.py:411-441`);
- handoff shows pass/fail and the concrete file/message pairs returned by the
  validator (`vibecode/main_app.py:497-519`).

Example failure output from the reviewed render path:

```text
─── Guard ───
Result: ✗ FAILED
Errors: 2  Warnings: 1
Report: C:/tmp/guard_result.json
Findings:
  [ERROR] a.py: Rule X
```

```text
─── Checks ───
Result: ✗ FAIL
Total: 2  Passed: 1  Failed: 1  Warnings: 0
Report: C:/tmp/check_results.json
Results:
  [FAIL] unit tests (exit 1, 5.00s)
```

The callback/error path is also safe. Each action runs on a daemon thread and
logs completion or failure instead of letting the exception escape the TUI loop
(`vibecode/main_app.py:864-928`, `vibecode/main_app.py:943-992`). The callback
tests cover the visible failure cases for inspect, guard, checks, and handoff
(`tests/test_vibecode_main_tui.py:1408-1561`).

### MEDIUM: `[I]` bypasses the existing index freshness logic, so stale indexes are not handled honestly

This is the clearest implementation gap I found.

`InspectMapService.run()` marks the index as stale only when
`.vibecode/current/last_index.json` is missing
(`vibecode/main_app.py:211-216`). It does **not** call the existing
`check_index_freshness()` helper, even though the rest of the repo already uses
that helper to detect age-based, commit-based, and file-set-fingerprint-based
staleness (`vibecode/repo_status.py:110-121`, `vibecode/indexer/__init__.py:76-146`).

That creates a real honesty gap for `[I]`:

- missing index -> handled correctly;
- stale but present index -> reported as usable/current;
- changed HEAD or changed tracked file set -> also missed.

I reproduced the mismatch directly during this review with a temporary repo
whose `last_index.json` was 15 minutes old:

```text
check_index_freshness: False Index is 900s old (>300s) -- run 'vibecode index' to refresh.
InspectMapService: {'stale': False, 'error': None, 'path': '...repo_tree.generated.md'}
```

That result violates one of the explicit P23.1/P23.2 review checks:
"Missing/stale index is handled honestly." The inspect action is close, but the
freshness decision is currently weaker than the rest of the codebase's existing
truth source.

### LOW: the highest-risk action wiring is still only indirectly tested

The automated coverage is broad but not quite at the requested level.

What *is* covered:

- service-level behavior for inspect/guard/check/handoff
  (`tests/test_vibecode_main_tui.py:747-1399`);
- callback rendering and failure visibility
  (`tests/test_vibecode_main_tui.py:1408-1561`);
- binding/method presence and lazy service injection
  (`tests/test_vibecode_main_tui.py:1569-1742`);
- command-level guard/check/handoff/map behavior in the existing CLI suites
  (`tests/test_vibecode_guard_cli.py`, `tests/test_vibecode_check.py`,
  `tests/test_vibecode_handoff_cli.py`, `tests/test_vibecode_validation.py`).

What I did **not** find:

- a direct test that calls `action_inspect_map()`, `action_cmd_guard()`,
  `action_cmd_tests()`, or `action_cmd_handoff()`;
- a regression test proving the worker thread invokes the injected service and
  routes the result back through the callback path;
- a stale-index test for age, commit drift, or file-set drift.

So the reviewed behavior is mostly proven by service tests plus callback tests,
not by an end-to-end action-wiring regression. That is a follow-up risk, not a
current functional failure.

## Verification

### Commands run

```text
python -m vibecode.cli context . --task "Review P23.1 safety actions"
git --no-pager status --short
python -m vibecode.cli --help
python -m vibecode.cli map .
python -m vibecode.cli handoff-check .
python -m compileall vibecode -q
python -m ruff check vibecode\main_app.py tests\test_vibecode_main_tui.py tests\test_vibecode_guard_cli.py tests\test_vibecode_check.py tests\test_vibecode_handoff_cli.py tests\test_vibecode_validation.py
python -m pytest -p no:cacheprovider -q tests\test_vibecode_main_tui.py tests\test_vibecode_guard_cli.py tests\test_vibecode_check.py tests\test_vibecode_handoff_cli.py tests\test_vibecode_validation.py
python -m vibecode.cli guard . --task "Review P23.1 safety actions"
python -m vibecode.cli check .
python -c "<stale inspect repro>"
python -c "<render summary examples>"
```

### Results

- `git status --short` -> **PASS**, clean worktree before writing this review
- `python -m vibecode.cli --help` -> **PASS**
- `python -m vibecode.cli map .` -> **PASS**
- `python -m vibecode.cli handoff-check .` -> **expected repo-state FAIL**:
  current `.vibecode/handoff/NOW.md` still contains placeholder text, so the
  command correctly returned non-zero. This is not a P23.1 regression.
- `python -m compileall vibecode -q` -> **PASS**
- targeted Ruff -> **FAIL** on pre-existing test lint issues, including
  ambiguous loop variable names in `tests/test_vibecode_main_tui.py` and unused
  imports/locals in `tests/test_vibecode_guard_cli.py` and
  `tests/test_vibecode_validation.py`
- focused review tests -> **PASS**, `221 passed in 21.37s`
- `python -m vibecode.cli guard . --task "Review P23.1 safety actions"` ->
  **PASS**
- `python -m vibecode.cli check .` -> **PASS**
  - `unit tests`
  - `cli help`
  - `index command help`
  - `context command help`

### Existing CLI command compatibility

The command surface requested in P23.1 remains healthy:

- live smoke on this repo: `map` and `guard` both passed;
- live `check .` passed the repository's required checks;
- `handoff-check .` executed correctly and failed for an existing handoff-content
  issue, not for a command/runtime regression;
- the focused command-level suite covering `check`, `guard`, `handoff-check`,
  and `map` passed in full (`221 passed` across
  `tests/test_vibecode_main_tui.py`, `tests/test_vibecode_guard_cli.py`,
  `tests/test_vibecode_check.py`, `tests/test_vibecode_handoff_cli.py`, and
  `tests/test_vibecode_validation.py`).

## Final recommendation

Accept P23.1 as mostly correct for Phase 1, but queue one implementation follow-up:
make `[I]` call the shared freshness logic (`check_index_freshness()` or an
equivalent shared helper) before claiming the index is current.

Also add one regression test layer that executes the bound action methods
themselves, especially the stale inspect path and the guard/check/handoff worker
handoff path.

## Changed files

- `docs/audit/TUI_PHASE1_P23_SAFETY_ACTIONS_REVIEW.md`
