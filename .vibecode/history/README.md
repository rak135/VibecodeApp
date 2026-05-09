# VibecodeApp – Change History

`.vibecode/history/` holds **compressed project memory**, not raw logs or chat transcripts.

## Policy (explicit and short)

| Rule | Meaning |
|------|---------|
| **Commit only durable truth** | A history file is committed when it captures a real decision or change that future agents must know. Do not commit stubs, drafts, or empty placeholders. |
| **Not a log** | Never dump raw tool output, CI logs, or session transcripts here. Summarise and distill. |
| **`README.md` is always committed** | This policy file is the one exception — it is committed regardless of content. |
| **`*.md` only when valuable** | History summaries (`*.md`) are committed only when they contain durable project truth. Remove or do not create them if the work is trivial or already captured in handoff/NOW.md. |
| **`/runs/` is runtime-only** | `.vibecode/runs/*` is ephemeral output and must never appear in history. |

## Required sections

Every committed history summary **MUST** contain these sections (order matters):

1. **Task** – What was asked or decided.
2. **Changed files** – Which files were modified and why.
3. **Behavior changed** – What the project now does differently.
4. **Tests run** – Which tests were executed and the outcome.
5. **Decisions** – Architectural or design choices made (with rationale if non-obvious).
6. **Follow-up** – Open items or next steps that this change leaves behind.

## Format

Use level-3 headings (`###`) for each section. Example skeleton:

```markdown
# Project Name – Change Summary

Date: YYYY-MM-DD
Author: who made the change

### Task
<!-- What was the task or decision? -->

### Changed files
<!-- List files changed and the purpose of each change. -->

### Behavior changed
<!-- What does the project now do that it did not do before (or no longer does)? -->

### Tests run
<!-- Which tests were run? What passed or failed? -->

### Decisions
<!-- Key choices and why. -->

### Follow-up
<!-- Remaining work, questions, or risks. -->
```

## Ownership

History files are the **author's responsibility** to keep accurate.
The guard/check workflow (future) will validate that `.vibecode/architecture/*.md`
changes are accompanied by a corresponding history entry.
