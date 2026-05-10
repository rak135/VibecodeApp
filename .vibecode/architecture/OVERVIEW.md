# Architecture Overview

VibecodeApp is a local CLI for preparing repositories before coding agents edit a project.
The current control layer is deterministic and filesystem-based.

## Control layer role

- VibecodeApp owns project orientation artifacts, not code editing.
- Coding agents may consume Vibecode context; `vibecode run` can explicitly launch an external OpenCode process and evaluate the post-run working tree.
- Human-maintained architecture docs define project truth that generated indexes must reflect.

## Current implementation scope

- `vibecode init` creates the `.vibecode/` project layer.
- `vibecode index` scans files and writes generated architecture-map indexes.
- `vibecode validate` checks `.vibecode/` structure and generated artifacts.
- `vibecode map` reads generated indexes and renders them for humans.
- `vibecode context` generates task-specific context packs.
- `vibecode guard`, `vibecode check`, `vibecode handoff-check` handle post-run audit.
- `vibecode run` orchestrates the full agent loop.
- `vibecode project` manages a local registry outside the repository.
- `vibecode export-agents` writes agent-facing instructions to AGENTS.md.
- Root `AGENTS.md` and `vibecode export-agents` provide agent-facing instructions and safe export support.
- `.vibecode/agents/safe.json`, `fast.json`, and `audit.json` are committed permission profile defaults.

## Not implemented yet

- GUI work
- MCP server integration
- Swarm coordination
