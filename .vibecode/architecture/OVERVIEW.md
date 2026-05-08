# Architecture Overview

VibecodeApp is a local CLI for building repository architecture maps before coding agents edit a project.
The initial implementation is intentionally deterministic and filesystem-based.

## Control layer role

- VibecodeApp owns project orientation artifacts, not code editing.
- Coding agents may consume Vibecode context, but VibecodeApp does not launch them in this scope.
- Human-maintained architecture docs define project truth that generated indexes must reflect.

## Current implementation scope

- `vibecode init` creates the `.vibecode/` project layer.
- `vibecode index` scans files and writes generated architecture-map indexes.
- `vibecode validate` checks `.vibecode/` structure and generated artifacts.
- `vibecode map` reads generated indexes and renders them for humans.
- `vibecode context` will generate task-scoped context packs after the scoring and renderer tasks are complete.

## Out of scope until context packs are verified

- GUI work
- OpenCode runtime integration
- MCP server integration
- automatic commits
- autonomous agent orchestration

