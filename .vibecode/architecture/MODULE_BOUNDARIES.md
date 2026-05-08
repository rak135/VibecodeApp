# Module Boundaries

## CLI layer

- `vibecode/cli.py` parses commands and delegates work.
- CLI code must not implement scanner, validation, scoring, or rendering logic directly.

## Project layer

- `vibecode/project.py` creates human-maintained `.vibecode/` files and generated directories.
- Init may create missing human-maintained files but must not overwrite them without `--force`.

## Config layer

- `vibecode/config.py` loads project identity, indexing rules, protected paths, risk rules, and required checks.
- Config loading must not mutate configuration files.

## Indexer layer

- `vibecode/indexer/` reads source repositories and writes generated indexes.
- Indexers may overwrite generated files only.
- Indexers must not modify `.vibecode/architecture/*.md`, `.vibecode/checks/*.yaml`, or `.vibecode/handoff/*.md`.

## Context layer

- `vibecode/context/` builds task-scoped context from committed architecture truth and generated indexes.
- Context packs are derived runtime artifacts and belong under `.vibecode/current/`.

## Validation layer

- `vibecode/validation.py` checks repository state and writes validation reports.
- Validation may report weak architecture docs, but must not silently fill them.
