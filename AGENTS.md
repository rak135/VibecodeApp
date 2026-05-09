<!-- vibecode:agents:start -->
# Agent Instructions

## Before you start

1. Run `python -m vibecode.cli context . --task "<task>"` to generate a task-specific context pack; start from `Relevant files with reasons`.
2. Read `.vibecode/architecture/INVARIANTS.md` and `.vibecode/architecture/STRUCTURE.md` when present.
3. Read `.vibecode/handoff/NOW.md` for current scope.
4. Check `.vibecode/checks/required_checks.yaml` for required checks.

## Source of truth

Treat source code, tests, and human-maintained docs (`.vibecode/architecture/`, `.vibecode/handoff/`, `.vibecode/checks/`) as truth.

## Do not manually edit

- `.vibecode/current/*` — session state
- `.vibecode/index/*.generated.*` — generated index
- `.vibecode/generated/*` — export artifacts
- `.vibecode/logs/*` — runtime logs

## Rules

- Do not perform unrelated refactors.
- Do not modify protected files without an explicit task.
- Do not update README outside marked generated blocks.
- Run required checks before finalizing changes.
- Report changed files and checks run before marking work complete.
- Update the handoff document when done.
<!-- vibecode:agents:end -->
