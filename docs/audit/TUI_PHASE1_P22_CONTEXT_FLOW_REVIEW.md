# TUI Phase 1 P22 Context Flow Review

Generated: 2026-05-16

## Verdict

PASS WITH FOLLOW-UP. P22.1 correctly wires `[C] Create context for task` into the
existing context-pack flow, writes full context artifacts to
`.vibecode/current/`, updates the center panel with the current task and artifact
paths, surfaces stale-index and failure information honestly, and does not call
an LLM or launch OpenCode.

I found one medium implementation issue and one low follow-up:

1. the right-panel "Architecture docs" preview can mislabel ordinary source files
   as architecture docs because the extractor matches nested bullets inside the
   `## Relevant architecture` section;
2. the reviewed test surface is not lint-clean because
   `tests/test_vibecode_context_tui.py` still has two unused imports.

This review only adds this document, per task scope.

## Findings

### PASS: `[C]` reuses the existing context-generation path and does not invoke OpenCode/LLM runtime

`ContextPreviewService.run()` is a thin wrapper around the existing shared
writers: it imports and calls `write_context_pack()` from
`vibecode.context.renderer` and `write_opencode_prompt()` from
`vibecode.context.platform_export` (`vibecode/main_app.py:136-185`). Those
helpers only write files under `.vibecode/current/`
(`vibecode/context/renderer.py:36-84`, `vibecode/context/platform_export.py:43-49`);
they do not route through `RunController`, the process runner, or any OpenCode
adapter.

That satisfies the core safety requirement:

- `[C]` does not launch OpenCode;
- `[C]` does not call an LLM;
- existing context generation logic is reused instead of duplicated.

Automated evidence is good here:

- `tests/test_vibecode_context_tui.py:234-387` covers the writer calls, expected
  return shape, and the explicit "does not call OpenCode or any LLM" guard.
- `tests/test_vibecode_context_pack.py:19-145` confirms the existing CLI
  `context` command still writes a real context pack and still supports the
  legacy shape.

### PASS: full context remains in artifacts while the UI preview stays intentionally concise

The full artifact path is preserved exactly as expected:

- `write_context_pack()` writes the full markdown pack to
  `.vibecode/current/context_pack.md` (`vibecode/context/renderer.py:36-47`);
- `write_opencode_prompt()` writes `.vibecode/current/opencode_prompt.md` and
  embeds the full context-pack content under the wrapper instructions
  (`vibecode/context/platform_export.py:27-49`).

The preview path is deliberately smaller. `ContextPreviewService` extracts only
summary fields, and the render path limits what is shown:

- relevant files: extractor capped at 10, renderer shows 8
  (`vibecode/main_app.py:85-92`, `vibecode/main_app.py:220-223`);
- required checks: extractor capped at 5, renderer shows 4
  (`vibecode/main_app.py:105-112`, `vibecode/main_app.py:228-230`);
- protected files: extractor capped at 8, renderer shows 5
  (`vibecode/main_app.py:115-122`, `vibecode/main_app.py:232-234`);
- warnings: capped at 5 (`vibecode/main_app.py:125-133`).

The underlying context pack is also bounded by the existing renderer's
`DEFAULT_CHAR_LIMIT = 32_000` and drops lower-priority sections with an explicit
omission notice rather than dumping arbitrarily large content
(`vibecode/context/renderer.py:22-27`, `vibecode/context/renderer.py:87-125`).
`tests/test_vibecode_context_pack.py:162-249` verifies the length limit and the
truncation notice, and `tests/test_vibecode_context_pack.py:116` explicitly
checks that long source content is not dumped into the pack.

Smoke evidence from this review session:

- `context_pack_path`:
  `C:\DATA\PROJECTS\VibecodeApp\.vibecode\current\context_pack.md`
- `opencode_prompt_path`:
  `C:\DATA\PROJECTS\VibecodeApp\.vibecode\current\opencode_prompt.md`
- `context_pack_exists`: `true`
- `opencode_prompt_exists`: `true`
- preview summary counts: `relevant_files=10`, `architecture_docs=16`,
  `required_checks=5`, `protected_files=8`
- warning surfaced: stale generated index

### PASS: center-panel status and failure handling are honest and safe

The TUI action wiring is straightforward and safe:

- `action_cmd_context()` refuses to proceed when `.vibecode` is missing and logs
  an actionable message instead of pushing the input screen
  (`vibecode/main_app.py:460-467`);
- `_on_context_task_received()` stores the current task, logs a generation
  message, and runs the work on a background thread
  (`vibecode/main_app.py:497-513`);
- `_on_context_done()` updates the center panel with provider, current task,
  artifact paths, and `Status: context ready`, then logs the preview
  (`vibecode/main_app.py:515-538`);
- `_on_context_done()` returns early on preview errors and logs the failure
  instead of crashing (`vibecode/main_app.py:517-520`);
- `_on_context_error()` logs unexpected worker exceptions
  (`vibecode/main_app.py:540-541`).

This is backed by tests:

- missing `.vibecode` guard:
  `tests/test_vibecode_context_tui.py:789-822`
- task handoff/thread launch:
  `tests/test_vibecode_context_tui.py:598-667`
- center-panel success/error behavior:
  `tests/test_vibecode_context_tui.py:675-760`
- worker error logging:
  `tests/test_vibecode_context_tui.py:768-781`

The current repo smoke also surfaced the stale-index warning through the preview
without blocking context generation, which is the honest/safe behavior the brief
asked for.

### MEDIUM: "Architecture docs" preview overmatches nested bullets and can show source files as docs

`_get_section_content()` strips indentation from every non-empty line in the
target section (`vibecode/main_app.py:68-82`). `_extract_architecture_docs()`
then treats any resulting bullet line that starts with ``- `path` `` as an
architecture-doc entry (`vibecode/main_app.py:95-102`).

That is too broad for the current context-pack shape. The `## Relevant
architecture` section contains top-level architecture doc bullets followed by
nested bullets describing source files inside those docs. In the generated pack
from this review session, the section includes entries such as:

- `.vibecode/architecture/MODULE_BOUNDARIES.md`
- nested bullets for `vibecode/cli.py` and `vibecode/project.py`
  (`.vibecode/current/context_pack.md:42-45`)

Because indentation is stripped before matching, those nested source-file bullets
are reclassified as "architecture docs." The live smoke preview printed exactly
that misclassification:

```text
Architecture docs:
  .vibecode/architecture/DATA_FLOW.md
  .vibecode/architecture/MODULE_BOUNDARIES.md
  vibecode/cli.py
  vibecode/project.py
```

This is not catastrophic — the full artifacts are still correct — but it makes
the right-panel preview less trustworthy and can crowd out real architecture-doc
entries.

The test gap is visible too. `tests/test_vibecode_context_tui.py:152-159` only
checks that real architecture docs are returned and that the extractor returns
empty when the section is missing. I did not find a regression test that asserts
nested bullets are excluded from the architecture-doc list.

### LOW: the P22.1 review surface is not lint-clean

Targeted Ruff on the reviewed files failed immediately on two unused imports in
`tests/test_vibecode_context_tui.py`:

- `from types import SimpleNamespace` (`tests/test_vibecode_context_tui.py:29`)
- `from unittest.mock import MagicMock` (`tests/test_vibecode_context_tui.py:30`)

This does not undercut the runtime behavior of P22.1, but it means the new test
surface is not fully clean under lint.

## Verification

### Commands run

```text
python -m vibecode.cli context . --task "Review P22.1"
python -m vibecode.cli validate
git --no-pager status --short
git --no-pager log --oneline --decorate -n 20
python -m ruff check vibecode\main_app.py tests\test_vibecode_context_tui.py tests\test_vibecode_context_pack.py tests\test_vibecode_main_tui.py tests\test_vibecode_tui_entrypoint.py
python -m pytest -p no:cacheprovider -q tests\test_vibecode_context_tui.py tests\test_vibecode_context_pack.py tests\test_vibecode_main_tui.py tests\test_vibecode_tui_entrypoint.py
python -m vibecode.cli --help
python -m vibecode.cli index --help
python -m vibecode.cli context --help
python -m vibecode.cli tui --help
python -c "from pathlib import Path; import json; from vibecode.main_app import ContextPreviewService; ..."
python -c "from pathlib import Path; from vibecode.main_app import ContextPreviewService, render_context_preview, render_center_context_status; ..."
python -m compileall vibecode -q
python -m pytest -p no:cacheprovider -q
python -m vibecode.cli check .
```

### Results

- `git status --short` -> clean worktree before writing this review
- targeted Ruff -> **FAIL** on two unused imports in
  `tests/test_vibecode_context_tui.py:29-30`
- focused tests -> **PASS**, `192 passed in 2.61s`
- `python -m vibecode.cli --help` -> **PASS**
- `python -m vibecode.cli index --help` -> **PASS**
- `python -m vibecode.cli context --help` -> **PASS**
- `python -m vibecode.cli tui --help` -> **PASS**
- context-preview smoke -> **PASS**, both artifacts written and preview returned a
  non-error summary with stale-index warning
- `python -m compileall vibecode -q` -> **PASS**
- full suite -> **PASS**, `2082 passed, 35 warnings in 319.54s`
- `python -m vibecode.cli check .` -> **PASS**
  - `unit tests`
  - `cli help`
  - `index command help`
  - `context command help`

## Final recommendation

Accept P22.1 as functionally correct and safe for the requested Phase 1 scope.

Add one focused follow-up to tighten `_extract_architecture_docs()` so it only
captures top-level architecture document bullets, and cover that with a test that
rejects nested source-file bullets in the preview.

Optionally clean the two unused imports so the reviewed test surface is lint-clean.

## Changed files

- `docs/audit/TUI_PHASE1_P22_CONTEXT_FLOW_REVIEW.md`
