# Architecture Map Status

This document is the short implementation-status companion to the Architecture Map PRD.

## Canonical Source Of Truth

- source code
- tests
- `.vibecode/architecture/*.md`
- `.vibecode/checks/required_checks.yaml`
- `.vibecode/agents/*.json`
- `docs/ARCHITECTURE_MAP_PRD.md`
- `docs/ARCHITECTURE_MAP_STATUS.md`

## Not Source Of Truth

- `.vibecode/current/*`
- `.vibecode/index/*.generated.*`
- `.ralphy/progress.txt`
- README roadmap checkboxes
- generated context packs
- stale generated indexes

## Current Status

- Architecture Map Core implementation exists.
- Task-specific context pack generation exists.
- Relevant-file scoring hardening exists.
- Root `AGENTS.md` exists.
- Safe AGENTS export workflow exists.
- Guard/check/handoff-check CLI commands exist.
- OpenCode run orchestration exists as external process control; Vibecode does not edit code itself.
- Project registry exists as local machine state outside repositories.
- Permission profiles are committed under `.vibecode/agents/` and selected run profiles must exist before launch.
- Full test suite passes after the run safety repair.
- Generated indexes and runtime/current artifacts are stale until regenerated.
- Regenerate generated/current artifacts before the next agent run.
