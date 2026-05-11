# Observable Run Monitor P5 Advisory Guard Fix

Generated: 2026-05-11

## Source

Review document: `docs/audit/OBSERVABLE_RUN_MONITOR_P5_ADVISORY_GUARD_REVIEW.md`

## Applied Fixes

### 1. Lint: remove unused `cmd_run` import and dead `plan` assignments

**Rationale:** Ruff reported 1 unused import (`cmd_run`) and 14 unused local variable assignments (`plan = self._make_plan()` / `plan = RunPlan(...)`) in `tests/test_vibecode_run_post.py`.

**Change:** Removed the import and all dead plan assignments. No test logic was affected — `_make_plan()` is a pure constructor and `plan` was never passed to `RunSummary`.

**Files:** `tests/test_vibecode_run_post.py`

### 2. Hardening: validate `guard_mode` in `RunController.__init__`

**Rationale:** Audit finding #4 noted that only the CLI parser enforces `guard_mode` choices (`advisory` / `strict`). Direct `RunController` callers could pass arbitrary strings, which would silently behave as advisory mode. Validating in `__init__` reduces bypass risk for programmatic use.

**Change:** Added an explicit `ValueError` raise in `RunController.__init__` when `guard_mode` is not `"advisory"` or `"strict"`.

**Files:** `vibecode/run.py:437`

## Checks Run

- `ruff check tests/test_vibecode_run_post.py vibecode/run.py vibecode/cli.py` — **pass**
- `pytest tests/test_vibecode_run_post.py` — **52 passed**
- `pytest tests/test_vibecode_run.py` — **32 passed**, 1 pre-existing failure (`test_missing_gitignore_blocks_agent_launch` — test isolation issue, not related)

## Not Actioned

- `.vibecode/handoff/NOW.md` placeholder-text issue — this is a protected file with existing placeholder content, not scoped here.
- `pytest` PermissionError on `C:\Users\...\pytest-of-Martin` — environment-level issue, not a code fix.
