# TUI Phase1 P19 Entrypoint Status Review

Generated: 2026-05-15

## Verdict

PASS WITH FOLLOW-UP. P19.1 delivers the requested no-argument `vibecode`
entrypoint, keeps explicit subcommands and `--help` working, adds the explicit
`vibecode tui [repo]` alias, resolves repositories in the required priority
order, and keeps repo-status computation outside Textual so it is testable
without launching a UI.

I found one medium-risk follow-up in the status service: the index-freshness
helper currently returns `"fresh"` if its freshness check raises any exception,
which can fabricate a healthy status instead of reporting an indeterminate one.

This review only adds this document, per task scope.

## Findings

### PASS: no-argument routing is intentional and does not break help or explicit commands

`vibecode/cli.py:568-576` parses arguments first, then routes to the TUI only
when `args.command is None`. That is the key detail that keeps the command
surface stable:

- `python -m vibecode.cli --help` is still handled by argparse before the
  no-argument TUI branch runs.
- Explicit commands still populate `args.command` and continue through
  `_dispatch()` (`vibecode/cli.py:607-721`).
- The explicit alias is also wired cleanly: the parser registers `tui` with an
  optional `repo` argument (`vibecode/cli.py:447-467`), and dispatch forwards
  that command to `vibecode.main_app.cmd_tui()` (`vibecode/cli.py:717-719`).

This avoids breaking scripted use of existing commands because only the exact
"no subcommand" path changed; all existing named subcommands still use the same
dispatch table.

### PASS: explicit `tui` alias and repo resolution priority are correct

`vibecode/main_app.py:71-98` resolves `args.repo` through
`RepoResolutionService` before any UI launch. `vibecode/repo_resolution.py:19-42`
implements the required order exactly:

1. explicit path argument;
2. active project from the registry;
3. current working directory.

The implementation uses `vibecode.paths.normalise_root()`
(`vibecode/paths.py:40-59`), which converts backslashes before resolving the
path. That is cross-platform normalization, not a Windows-only assumption.

Test evidence is strong here:

- `tests/test_vibecode_tui_entrypoint.py` covers `main([])`, `main(["tui"])`,
  `main(["tui", <repo>])`, and `main(["tui", "--help"])`.
- `tests/test_vibecode_repo_status.py` covers explicit path, registry fallback,
  and cwd fallback for `RepoResolutionService`.
- `tests/test_vibecode_active_project_fallback.py` confirms the broader CLI
  still honors explicit-path-over-registry behavior and accepts Windows-style
  path strings.

### PASS: repo status logic is UI-independent and separated from rendering

`vibecode/repo_status.py` contains the status model and service with no Textual
imports. `vibecode/main_app.py:78-97` simply resolves the repo, computes the
status, and passes the result into the app.

That separation keeps the business logic testable without any TUI bootstrap:

- `RepoStatus` stores the data shape.
- `RepoStatusService.get_status()` computes it from filesystem state and git.
- `VibecodeMainApp.compose()` only reads the already-computed status object to
  render labels.

The dedicated test file `tests/test_vibecode_repo_status.py` exercises the
service directly, which satisfies the requirement to keep UI-independent logic
outside Textual widgets.

### PASS: status categories are separated and backed by real checks

The model distinguishes:

- manual truth files via `manual_truth`;
- generated index artifacts via `generated_index`;
- current/runtime artifacts via `context_pack_exists`,
  `opencode_prompt_exists`, and `check_results_exist`;
- git state via `git_state`;
- freshness via `index_freshness`.

That matches the requested distinction between manual truth, generated
artifacts, and current/check outputs. The data is backed by direct
`Path.exists()` checks plus a real git probe:

- `vibecode/repo_status.py:84-89` checks file presence directly.
- `vibecode/repo_status.py:94-108` runs `git status --short` with a 5-second
  timeout and returns only `clean`, `dirty`, or `unknown`.

Tests cover missing `.vibecode`, partial `.vibecode`, complete manual truth,
generated index present/missing, current context/check artifacts, and
clean/dirty/unknown git states.

### PASS: no LLM call or external OpenCode launch is introduced in startup

I found no OpenCode or LLM invocation in the reviewed startup path.

- `vibecode/cli.py:573-575` routes no-arg startup into `vibecode.main_app`.
- `vibecode/main_app.py:71-98` resolves the repo, computes status, and either
  launches the TUI or prints a Textual-install hint.
- The only subprocess call in the reviewed path is the git-status probe inside
  `RepoStatusService` (`vibecode/repo_status.py:96-103`).

No reviewed entrypoint code imports or calls the run controller, process
runner, OpenCode adapter, or any LLM client as part of app startup.

### MEDIUM: index freshness can report a false "fresh" state on exceptions

`vibecode/repo_status.py:115-122` imports `check_index_freshness()` and returns
`"fresh"` or `"stale"` when that helper succeeds, which is fine. The problem is
the fallback:

```python
except Exception:
    return "fresh"
```

That means an unexpected failure in freshness evaluation can surface as a
healthy status value that is not backed by a successful metadata check. This is
exactly the kind of optimistic/fake status the review brief said to watch for.

I did not find a matching exception-path test in `tests/test_vibecode_repo_status.py`.
The existing freshness tests cover:

- missing metadata -> `"missing"`
- helper returns `True` -> `"fresh"`
- helper returns `False` -> `"stale"`

The entrypoint work is still solid, so I do not treat this as a release-blocking
CLI routing failure, but the freshness fallback should be tightened before the
TUI relies on that indicator for operator trust.

## Verification

### Commands and results

- `git status --short` -> clean worktree
- `python -m compileall vibecode -q` -> PASS
- `python -m pytest tests\test_vibecode_tui_entrypoint.py tests\test_vibecode_repo_status.py tests\test_vibecode_cli.py tests\test_vibecode_active_project_fallback.py`
  -> PASS, `108 passed, 1 warning in 2.58s`
- `python -m pytest` -> PASS, `1907 passed, 35 warnings in 328.28s`
- `python -m vibecode.cli --help` -> PASS
- `python -m vibecode.cli tui --help` -> PASS
- `python -m vibecode.cli index --help` -> PASS
- `python -m vibecode.cli context --help` -> PASS

### CLI help behavior

Top-level help still works and lists the new `tui` command alongside the
existing subcommands. `vibecode tui --help` prints the explicit alias help text
and documents the repo-resolution order:

1. explicit `[repo]` argument;
2. active project from the project registry;
3. current working directory.

This confirms the parser is not launching the TUI when the user explicitly asks
for help.

### Parser ambiguity note

Risk is low. The implementation does not create a new ambiguous positional form;
it keeps the subcommand parser intact and adds a post-parse branch for the
specific `args.command is None` case.

The only nuance worth documenting is behavioral, not ambiguous parsing:
top-level flags that do not themselves exit argparse (for example `--debug`)
still leave `args.command` unset, so `vibecode --debug` follows the same TUI
bootstrap path as bare `vibecode`. That is deterministic and consistent with
the new design, but it is the one edge worth remembering if more top-level
flags are added later.

### Linting note

I did not run a lint command because this repository does not define one in
`pyproject.toml`; it contains packaging metadata and pytest configuration, but
no Ruff/Flake8/Pylint/Mypy tool configuration or required lint check.

## Final Recommendation

Accept P19.1 as a solid Phase 1 entrypoint/status foundation. The no-argument
routing, explicit alias, resolution priority, help preservation, and non-UI
status design all check out.

Add one follow-up to replace the optimistic `index_freshness` exception fallback
with an explicit non-success state or surfaced error, and cover that path with a
test so the TUI does not overstate index health.
