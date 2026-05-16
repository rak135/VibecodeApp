# TUI Phase 1 P22 Context Flow — Fix Applied

Date: 2026-05-16

## Fixes applied (P22.1 review → P22.2)

### MEDIUM: Architecture-docs preview overmatched nested source-file bullets

**File**: `vibecode/main_app.py:95-116`

`_extract_architecture_docs()` now only captures top-level bullets (lines
starting with `- ` at column 0). Nested/indented source-file bullets (e.g.
`  - \`vibecode/cli.py\` ...`) are excluded, preventing ordinary source files
from appearing as "Architecture docs" in the right panel.

The fix rewrites the function to iterate over raw markdown content lines
instead of going through `_get_section_content()` (which strips indentation
before matching). The `- ` prefix check is applied against the original
(non-stripped) line.

**Test**: `tests/test_vibecode_context_tui.py:161-163`
`test_excludes_nested_source_file_bullets` asserts that `vibecode/cli.py`
does not appear in the architecture-doc list from the sample pack.

### LOW: Unused imports in reviewed test surface

**File**: `tests/test_vibecode_context_tui.py:29-30`

Removed:
- `from types import SimpleNamespace` (never referenced)
- `MagicMock` from `from unittest.mock import MagicMock, patch` (only `patch` used)

Result: `from unittest.mock import patch`

## Verification

| Check | Result |
|---|---|
| `python -m compileall vibecode -q` | PASS |
| `python -m ruff check vibecode\main_app.py` | PASS (0 errors) |
| `python -m pytest -q tests\test_vibecode_context_tui.py` | 71 passed |
| `python -m pytest -q tests\test_vibecode_context_tui.py tests\test_vibecode_context_pack.py tests\test_vibecode_main_tui.py tests\test_vibecode_tui_entrypoint.py` | 193 passed |
| `python -m pytest -q` (full) | 2083 passed, 35 pre-existing warnings |
| `git status --short` | Only `vibecode/main_app.py` and `tests/test_vibecode_context_tui.py` modified |

## Changed files

- `vibecode/main_app.py`
- `tests/test_vibecode_context_tui.py`
- `docs/audit/TUI_PHASE1_P22_CONTEXT_FLOW_FIX.md` (this file)
