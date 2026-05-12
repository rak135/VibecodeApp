# Observable Run Monitor — Final Fix Report

Generated: 2026-05-12

## Fixes Applied

All fixes are concrete, safe, and targeted to the issues identified in the final review.

### 1. Preflight: run artifacts no longer affect git dirty-tree check

**Problem**: `RunController.execute()` created `.vibecode/runs/<session_id>/events.jsonl`
before running the git preflight check, so the run's own observability artifact
could appear as a dirty-tree change and mask the intended preflight error.

**Fix** (`vibecode/run.py`): Early events are now buffered in an `InMemoryEventSink`.
The durable `JsonlEventSink` (which writes `events.jsonl`) is only created and
activated after the git preflight check passes. Buffered events are replayed into
the JSONL sink so no events are lost.

This resolves the pre-existing `test_missing_gitignore_blocks_agent_launch` test
failure documented in the dogfood report.

### 2. Ruff lint: 7 issues fixed

| File | Rule | Fix |
|------|------|-----|
| `indexer/classifier.py:104` | F841 | Removed unused `name` local in `_is_doc` |
| `indexer/classifier.py:135` | F841 | Removed unused `name` local in `guess_role` |
| `indexer/dependency_map.py:21` | F401 | Removed unused `PurePosixPath` import |
| `indexer/repo_tree.py:554` | F841 | Removed unused `present_ignored` list |
| `indexer/test_map.py:6` | F401 | Removed unused `re` import |
| `indexer/ts_symbols.py:57` | F821 | Fixed undefined `posix` reference (`{p}`) |
| `registry.py:16` | F401 | Removed unused `to_posix_str` import |

## Verification

- `python -m compileall vibecode -q` — PASS
- `python -m ruff check vibecode` — PASS (0 issues)
- `python -m pytest -p no:cacheprovider -q` — 1754 passed (was 1753; +1 from the preflight fix)
- `python -m vibecode.cli check .` — All 4 checks PASS

## Changed Files

- `vibecode/run.py` — preflight event buffering
- `vibecode/indexer/classifier.py` — unused local removal (x2)
- `vibecode/indexer/dependency_map.py` — unused import removal
- `vibecode/indexer/repo_tree.py` — dead code removal
- `vibecode/indexer/test_map.py` — unused import removal
- `vibecode/indexer/ts_symbols.py` — undefined name fix
- `vibecode/registry.py` — unused import removal
- `docs/audit/OBSERVABLE_RUN_MONITOR_FOLLOWUPS.md` — new: larger follow-up items
- `docs/audit/OBSERVABLE_RUN_MONITOR_FINAL_FIX.md` — new: this document
