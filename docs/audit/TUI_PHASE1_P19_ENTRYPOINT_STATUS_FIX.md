# TUI Phase1 P19 Entrypoint Status Fix

Generated: 2026-05-15

## Fix Applied

P19.2 review identified one medium-risk issue: `_compute_index_freshness()` in
`vibecode/repo_status.py` returned `"fresh"` on **any** exception, fabricating
a healthy status when the freshness check could not actually complete.

### Changes

1. **`vibecode/repo_status.py:16`** — Added `"unknown"` to `IndexFreshnessStr`
   literal type.

2. **`vibecode/repo_status.py:120-121`** — Changed exception fallback from
   `"fresh"` to `"unknown"`, and removed the misleading comment.

3. **`tests/test_vibecode_repo_status.py:380-392`** — Added
   `test_freshness_unknown_when_check_raises` to cover the exception path,
   ensuring `index_freshness` is `"unknown"` when `check_index_freshness`
   raises.

### Verification

- `git status --short` — 2 modified files
- `python -m compileall vibecode -q` — PASS
- `python -m pytest tests\test_vibecode_tui_entrypoint.py tests\test_vibecode_repo_status.py tests\test_vibecode_cli.py tests\test_vibecode_active_project_fallback.py -p no:cacheprovider -q` — PASS (109 passed)
- `python -m pytest -p no:cacheprovider -q` — PASS (1908 passed)
- `python -m vibecode.cli --help` — PASS

### Rationale for no other changes

The audit review confirmed PASS on all other items: no-argument routing,
`--help` preservation, explicit `tui` alias, repo resolution priority, and
UI-independent status design. No CLI routing, help, resolution, or other
fixes were needed.
