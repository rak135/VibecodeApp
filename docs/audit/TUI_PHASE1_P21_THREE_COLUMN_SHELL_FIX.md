# TUI Phase 1 P21.2 Three-Column Shell Fix Report

Generated: 2026-05-16

## Findings addressed

### MEDIUM: Right event panel now shows artifact paths, not just counts

**Source**: `vibecode/main_app.py:280-285`

**Before**: `_on_refresh_done()` logged only the count (`artifacts: {n} written`).

**After**: Also logs up to 20 individual artifact paths below the count line:

```
[R] Refresh complete: ok
    artifacts: 10 written
      .vibecode/index/file_inventory.json
      .vibecode/index/symbol_map.json
      ...
```

Additionally, after status recomputation, the presence of a context pack is logged:

```
    context pack: C:\...\\.vibecode\\current\\context_pack.md
```

**Test**: `TestActionRefreshRepo::test_on_refresh_done_logs_artifact_paths` verifies both the count line and individual paths appear in the event log.

### LOW: Tests now cover refresh wiring and binding table

**New test classes in** `tests/test_vibecode_main_tui.py`:

| Test class | Coverage |
|---|---|
| `TestActionRefreshRepo` | `_on_refresh_done()` logs artifact paths (not just count), completion status, and `_on_refresh_error()` logs failure |
| `TestRefreshBindingsTable` | `r` maps to `refresh_repo` action; binding keys match actions text |
| `TestComposeThreeColumnLayout` | Every binding action has a matching `action_*` method on the app; `on_mount` logs ready/repo; TITLE and CSS_PATH are set |

### Not implemented (out of P21.2 scope)

- Full three-column widget-tree compose tests (Textual requires a running app context for `with Horizontal(...)` syntax; covered manually in the P21.1 review smoke run).
- Async `run_test()` compose assertions (no `pytest-asyncio` in this environment).

## Validation

| Command | Result |
|---|---|
| `git status --short` | 2 files modified |
| `python -m compileall vibecode -q` | PASS |
| `python -m pytest -p no:cacheprovider -q tests\test_vibecode_main_tui.py ...` | 189 passed |
| `python -m pytest -p no:cacheprovider -q` (full suite) | 2012 passed |

## Changed files

- `vibecode/main_app.py` — artifact paths and context-pack info in right event log
- `tests/test_vibecode_main_tui.py` — new test classes for refresh wiring, bindings, and layout
