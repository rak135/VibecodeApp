# Invariants

## Project truth

- Human-maintained architecture docs are source-controlled.
- Generated indexes are not source of truth and must be regenerated.
- Runtime/session state must not be committed.

## Implementation scope

- v0.1 implements architecture-map/index generation only.
- No UI work before architecture-map core is stable.
- No OpenCode runtime integration before context pack generation is verified.

## File ownership

- `.vibecode/architecture/*.md` is human-maintained.
- `.vibecode/checks/*.yaml` is human-maintained.
- `.vibecode/index/*.generated.*` is generated.
- `.vibecode/current/*` is runtime/session state.

## Agent behavior

- Agents must not rewrite project structure without updating architecture docs.
- Agents must not mark tasks done without evidence.
- Agents must not treat generated files as canonical truth.
