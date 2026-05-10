<!-- vibecode:agents:start -->
# Agent Instructions

## Before you start

1. Run `python -m vibecode.cli context . --task "<task>"` to generate a task-specific context pack; start from `Relevant files with reasons`.
2. Read `.vibecode/architecture/INVARIANTS.md` and `.vibecode/architecture/STRUCTURE.md` when present.
3. Read `.vibecode/handoff/NOW.md` for current scope.
4. Check `.vibecode/checks/required_checks.yaml` for required checks.

## Source of truth

Treat source code, tests, `PRD.json`, and human-maintained docs (`.vibecode/architecture/`, `.vibecode/handoff/`, `.vibecode/checks/`, `.vibecode/history/`, `.vibecode/agents/`) as truth.

## Do not manually edit

- `.vibecode/current/*` — session state
- `.vibecode/index/*.generated.*` — generated index
- `.vibecode/generated/*` — export artifacts
- `.vibecode/logs/*` — runtime logs
- `.vibecode/runs/*` — run metadata

## Rules

- Do not perform unrelated refactors.
- Do not modify protected files without an explicit task.
- Do not update README outside marked generated blocks.
- Run required checks before finalizing changes.
- Report changed files and checks run before marking work complete.
- Update the handoff document when done.

## Available commands

- `vibecode init` — initialize `.vibecode/` project layer
- `vibecode index` — scan and generate architecture maps
- `vibecode map` — print one-page project summary
- `vibecode context` — generate task-scoped context pack
- `vibecode validate` — check artifact consistency (run this first)
- `vibecode export-agents` — write/update root AGENTS.md
- `vibecode guard` — check diff against protected/generated paths
- `vibecode check` — run required checks from `.vibecode/checks/required_checks.yaml`
- `vibecode handoff-check` — validate handoff file quality
- `vibecode run` — explicitly orchestrate an external OpenCode run and then run guard/check/handoff
- `vibecode project` — manage the local project registry outside the repo
<!-- vibecode:agents:end -->
