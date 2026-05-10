# Control Layer Final Audit

Generated: 2026-05-10
Scope: Post-repair audit of the VibecodeApp control layer against PRD tasks 1-57.

This audit is a source-truth status note, not a claim that every limitation has been removed. The implementation is complete enough for CLI dogfooding, with accepted limitations listed below.

## Verification Snapshot

- `python -m json.tool PRD.json`: passed.
- `python -m pytest -p no:cacheprovider`: 1230 passed, 11 warnings on Windows / Python 3.12.
- No real OpenCode binary is required by the test suite; OpenCode behavior is covered with fake commands.
- Generated/runtime directories remain doctrine-level runtime output, not source truth.

## Implementation Stage by Subsystem

| Subsystem | Status | Notes |
|-----------|--------|-------|
| Indexer | Stable with accepted limitation | Builds file inventory, symbol map, dependency map, test map, entrypoint/risk maps, repo tree, and run records with file-set fingerprints. Stale detection does not detect uncommitted content edits inside already-indexed files. |
| Context | Stable | Renders task context with relevant-file scoring, protected-path policy, required checks, handoff/history guidance, generated index status, and stale-index freshness warnings. |
| Guard | Stable | Enforces protected paths, generated/runtime edit detection, README/manual-doc rules, architecture handoff/history requirements, and source/test mismatch warnings. |
| Check | Stable with accepted limitation | Runs required checks from `.vibecode/checks/required_checks.yaml`. Shell execution is trusted local execution from repo/user configuration. |
| Handoff/history | Stable with accepted limitation | Rejects placeholders and weak summaries. Durable history remains human-maintained; `history new` creates a template only. |
| Run | Stable with accepted limitation | Orchestrates context generation, OpenCode launch, post-run guard/check/handoff pipeline, diff summary, and run metadata. Only OpenCode is implemented. Permission profiles are advisory. |
| Run plan | Stable | Uses the same OpenCode command resolution as `run`, including `OPENCODE_COMMAND`; reports dirty state, stale index, ignore-policy gaps, and platform availability before launch. |
| Registry | Stable | Named local project registry supports active project fallback only when repo argument is omitted. Explicit repo arguments, including `.`, target that path. |
| Permissions | Stable with accepted limitation | Profiles are validated and recorded but do not enforce OpenCode permissions. Actual tool constraints must be configured in OpenCode. |
| Write rules / AGENTS export | Stable | Source-truth vs generated/runtime doctrine is aligned across write rules, protected paths, docs, and exported AGENTS blocks. |
| CLI | Stable | CLI-only control layer. No GUI, MCP implementation, swarm, or server is present or claimed. |

## CLI Command List

| Command | Status |
|---------|--------|
| `init` | Implemented |
| `index` | Implemented |
| `context` | Implemented, including `--platform opencode` prompt export |
| `map` | Implemented |
| `validate` | Implemented |
| `export-agents` | Implemented |
| `guard` | Implemented |
| `check` | Implemented |
| `handoff-check` | Implemented |
| `history new` | Implemented |
| `run` | Implemented for `--platform opencode` |
| `run-plan` | Implemented |
| `project add/use/list/remove/current` | Implemented |

## Source-Truth vs Generated/Runtime Doctrine

Source truth, committed and human-maintained:

- Source code and tests.
- `PRD.json`, root `AGENTS.md`, README/docs.
- `.vibecode/architecture/*.md`.
- `.vibecode/checks/*.yaml`.
- `.vibecode/handoff/*.md`.
- `.vibecode/history/README.md` and filled durable history summaries.
- `.vibecode/agents/*.json`.
- `.vibecode/index/README.md` and `.vibecode/index/schema.json`.

Generated/runtime, ignored and not manually edited:

- `.vibecode/current/*`.
- `.vibecode/generated/*`.
- `.vibecode/logs/*`.
- `.vibecode/runs/*`.
- `.vibecode/tmp/*`.
- `.vibecode/cache/*`.
- `.ralphy/*`.
- All other generated `.vibecode/index/*` outputs, including file inventory, symbol map, dependency map, test map, entrypoint/risk maps, repo tree, last-index records, and similar generated artifacts.

## Known Remaining Limitations

1. Permission profiles are advisory. Vibecode validates and records the selected profile, but OpenCode permission enforcement remains outside Vibecode.
2. Required checks and OpenCode invocation use a trusted local shell execution model. This is acceptable for local control-layer use, but repo/user configuration must be treated as trusted input.
3. Stale index detection uses commit metadata and a generated/runtime-aware file-set fingerprint. It does not detect uncommitted content changes inside files already present in the indexed file set.
4. Only the OpenCode platform is implemented. Other platform adapters are future work.
5. The product is CLI-only. There is no GUI, MCP implementation, swarm, or server.
6. History summaries are human-maintained durable truth. Templates are not truth until filled.
7. `run-plan` defaults to the current directory; most other commands use active project fallback only when their repo argument is omitted.
8. `SerenaProvider` remains a stub and is not wired to CLI behavior. MCP/Serena integration is outside current scope.

## Bottom Line

VibecodeApp is suitable for controlled CLI dogfooding on real repositories, provided users keep generated/runtime artifacts ignored, treat local check commands as trusted, and understand that permission profiles are advisory. It is not ready to be treated as a fully autonomous permission-enforcing agent loop; it is a control layer that prepares, constrains, checks, and documents external agent work.
