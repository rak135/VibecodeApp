# Architecture Overview

VibecodeApp is a local CLI for preparing repositories before coding agents edit a project.
The current control layer is deterministic and filesystem-based.

## Control layer role

- VibecodeApp owns project orientation artifacts, not code editing.
- Coding agents may consume Vibecode context, but VibecodeApp does not launch them yet.
- Human-maintained architecture docs define project truth that generated indexes must reflect.

## Current implementation scope

- `vibecode init` creates the `.vibecode/` project layer.
- `vibecode index` scans files and writes generated architecture-map indexes.
- `vibecode validate` checks `.vibecode/` structure and generated artifacts.
- `vibecode map` reads generated indexes and renders them for humans.
- `vibecode context` generates task-specific context packs.
- Root `AGENTS.md` and `vibecode export-agents` provide agent-facing instructions and safe export support.

## Not implemented yet

- Guard, check, and handoff-check CLI commands (guard rule engine implemented; CLI commands pending)
- OpenCode run adapter
- Project registry
- GUI work
- MCP server integration
