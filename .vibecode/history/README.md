# VibecodeApp – Change History

`.vibecode/history/` holds **compressed project memory**, not raw logs or chat transcripts.

## Policy (explicit and short)

| Rule | Meaning |
|------|---------|
| **Commit only durable truth** | A history file is committed when it captures a real decision or change that later agents must know. Do not commit stubs, drafts, or empty placeholders. |
| **Not a log** | Never dump raw tool output, CI logs, or session transcripts here. Summarise and distill. |
| **`README.md` is always committed** | This policy file is the one exception — it is committed regardless of content. |
| **`*.md` only when valuable** | History summaries (`*.md`) are durable project memory only when they contain real project truth. Remove or do not create them if the work is trivial, already captured in handoff/NOW.md, or still a placeholder draft. |
| **`/runs/` is runtime-only** | `.vibecode/runs/*` is ephemeral runtime output, ignored by source control, and must never appear in history. |

## Required sections

Every committed history summary **MUST** contain these sections (order matters):

1. **Task** – What was asked or decided.
2. **Changed files** – Which files were modified and why.
3. **Behavior changed** – What the project now does differently.
4. **Tests run** – Which tests were executed and the outcome.
5. **Decisions** – Architectural or design choices made (with rationale if non-obvious).
6. **Follow-up** – Open items or next steps that this change leaves behind.

Every required section must contain real content. `_Not yet filled._`, TODO/TBD,
placeholder text, heading-only sections, and empty bullets are drafts and do not
pass durable-history validation.

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
The guard/check/handoff workflow exists for standalone and post-run audits.
Architecture truth guard evaluation requires handoff/history acknowledgement for
`.vibecode/architecture/*.md` changes; history summaries only count when they
contain durable project truth.
