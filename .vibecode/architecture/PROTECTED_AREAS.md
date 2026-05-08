# Protected Areas

## Human-maintained project truth

- `.vibecode/architecture/*.md` requires explicit task scope before editing.
- `.vibecode/checks/*.yaml` requires explicit task scope before editing.
- `.vibecode/project.yaml` requires explicit task scope before editing.
- `.vibecode/handoff/*.md` requires care because it may describe active project state.

## Generated and runtime areas

- `.vibecode/index/*.generated.*` must be regenerated, not manually edited.
- `.vibecode/current/*` is runtime/session state and must not be committed.
- `.vibecode/logs/*` is runtime output and must not be committed.
- `.vibecode/cache/*`, `.vibecode/tmp/*`, and `.vibecode/runs/*` are runtime/generated areas.

## Code areas requiring extra review

- `vibecode/project.py` controls `.vibecode/` initialization and human-file preservation.
- `vibecode/config.py` controls project configuration and required checks.
- `vibecode/indexer/` controls generated architecture-map artifacts.
- `vibecode/context/` controls task context presented to future agents.
- `vibecode/validation.py` controls whether generated artifacts and project truth are considered safe.

## Rule

- If a change modifies protected areas, the final handoff must name the protected file and the reason it was touched.
