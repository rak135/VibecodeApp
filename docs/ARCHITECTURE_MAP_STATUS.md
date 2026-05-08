# Architecture Map Status

This document is the short implementation-status companion to the Architecture Map PRD.

## Canonical Source Of Truth

- source code
- tests
- `.vibecode/architecture/*.md`
- `.vibecode/checks/required_checks.yaml`
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
- Tests pass in the latest hygiene audit.
- Generated indexes and runtime/current artifacts are stale until regenerated.
- Regenerate generated/current artifacts before the next agent run.
