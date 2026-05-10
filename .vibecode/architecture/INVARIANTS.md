# Invariants

## Project truth

- Human-maintained architecture docs are source-controlled.
- Generated indexes are not source of truth and must be regenerated.
- Runtime/session state must not be committed.

## Implementation scope

- Current control-layer scope covers architecture-map/index generation, context packs, AGENTS export, and post-run audit (guard/check/handoff-check).
- No UI work before architecture-map core is stable.
- No OpenCode run or project registry work before protected paths policy exists.

## File ownership

- `.vibecode/architecture/*.md` is human-maintained.
- `.vibecode/checks/*.yaml` is human-maintained.
- `.vibecode/handoff/*.md` is human-maintained.
- `.vibecode/history/README.md` is human-maintained.
- `.vibecode/agents/*.json` is human-maintained.
- `.vibecode/index/schema.json` and `.vibecode/index/README.md` are human-maintained.
- `.vibecode/index/*.generated.*` is generated.
- `.vibecode/current/*` is runtime/session state.
- `.vibecode/generated/*` is generated/export.
- `.vibecode/logs/*` is runtime logs.
- `.vibecode/runs/*` is runtime metadata.
- `.vibecode/tmp/*` is transient scratch.
- `.vibecode/cache/*` is cache.

## Agent behavior

- Agents must not rewrite project structure without updating architecture docs.
- Agents must not mark tasks done without evidence.
- Agents must not treat generated files as canonical truth.
