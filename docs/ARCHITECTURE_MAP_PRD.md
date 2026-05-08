# PRD — Vibecode Architecture Map

> This document defines the implementation boundary for the Architecture Map Core.
> It is a reference for contributors and automated loops to prevent scope creep
> before the architecture map and context engine are working.

---

## Scope

This capability implements **only** the Vibecode architecture map and context engine:

- `vibecode init` — create the `.vibecode/` project layer in a target repository
- File scanning — collect the repository file list via `git ls-files` with a filesystem fallback
- Language detection and role guessing — classify every file deterministically
- Symbol extraction — Python via `ast`, TypeScript/TSX via regex heuristics
- Import and dependency map — lightweight edge map (`dependency_map.json`)
- Test discovery — map source files to their tests (`test_map.json`)
- Risk and protected-area mapping — mark risky and protected files
- Index generation — write `file_inventory.json`, `symbol_map.json`, `repo_tree.generated.md`, `entrypoints.md`, `risky_files.md` under `.vibecode/index/`
- Context pack generation — assemble a short, task-scoped context pack from the index
- OpenCode prompt export — write the context pack to a file that can be passed to an external agent as a prompt

**This capability ends at prompt export.** No code in this capability launches OpenCode, calls an AI model, or executes any external agent.

---

## Non-goals

The following are explicitly out of scope until the architecture map is working:

| Out of scope | Reason |
|---|---|
| Custom coding agent runtime | Agent work requires a reliable map as a foundation |
| Graphical user interface (GUI) | Not needed for CLI-first tooling |
| MCP server | A separate integration layer; depends on the index being stable |
| OpenCode run adapter | Launching or orchestrating OpenCode is a later phase |
| Auto-commit or auto-approve behavior | Dangerous without validated index; deferred deliberately |
| LLM API calls of any kind | This phase is fully deterministic and offline |

> ⚠️ **Warning:** Do not begin agent runtime work until the map, indexer, and context
> pack are verified as working. Adding an agent runtime before the index is stable
> produces an unreliable agent and makes both layers harder to debug.

---

## Generated vs human-maintained files

### Human-maintained (never overwritten without `--force`)

These files are authored or edited by developers and must survive repeated `vibecode init` or `vibecode index` runs:

```
.vibecode/project.yaml
.vibecode/architecture/INVARIANTS.md
.vibecode/architecture/STRUCTURE.md
.vibecode/architecture/MODULE_BOUNDARIES.md
.vibecode/architecture/PROTECTED_AREAS.md
.vibecode/handoff/NOW.md
.vibecode/handoff/NEXT.md
.vibecode/handoff/BLOCKERS.md
.vibecode/history/README.md
```

### Generated (safe to overwrite on every index run)

These files are produced by `vibecode index` and must not be manually edited:

```
.vibecode/index/file_inventory.json
.vibecode/index/symbol_map.json
.vibecode/index/dependency_map.json
.vibecode/index/test_map.json
.vibecode/index/repo_tree.generated.md
.vibecode/index/entrypoints.md
.vibecode/index/risky_files.md
.vibecode/current/          (context pack output)
.vibecode/logs/index_runs/  (run logs)
```

The distinction matters: the init command must be **idempotent** — a second run
must not overwrite human-maintained files unless `--force` is given.

---

## Acceptance criteria

- [ ] `vibecode init` creates the `.vibecode/` structure without overwriting human-maintained files on repeated runs.
- [ ] `vibecode index` produces valid JSON for `file_inventory.json`, `symbol_map.json`, `dependency_map.json`, and `test_map.json`.
- [ ] `vibecode map` renders `repo_tree.generated.md` that is compact and human-readable.
- [ ] `vibecode context` assembles a context pack scoped to a named task.
- [ ] The context pack can be exported as a plain text prompt file for use with OpenCode or any other external agent.
- [ ] No CLI command in this phase starts a subprocess that calls an AI model or launches OpenCode.
- [ ] All generated files have a `schema` marker and a `generated_at` timestamp.
- [ ] Human-maintained files are never silently overwritten.
- [ ] The tool runs on Windows and Unix-like systems without platform-specific hacks.
- [ ] Unit tests cover: init idempotence, file scanning, language detection, symbol extraction, context pack assembly.
