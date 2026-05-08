# Data Flow

## Init flow

1. CLI receives `vibecode init <repo_root>`.
2. Project layer creates `.vibecode/` directories.
3. Project layer creates missing human-maintained files.
4. Existing human-maintained files remain unchanged unless `--force` is explicit.

## Index flow

1. CLI receives `vibecode index <repo_root>`.
2. Config layer loads `.vibecode/project.yaml` and `.vibecode/checks/required_checks.yaml`.
3. Scanner collects source files while respecting include and exclude rules.
4. Index builders generate inventory, symbols, dependencies, tests, entrypoints, risk files, and repo tree outputs.
5. Validation checks generated artifacts.
6. Run record writes `.vibecode/current/last_index.json` and `.vibecode/logs/index_runs/*.json`.

## Context flow

1. CLI receives task text through `vibecode context`.
2. Context layer reads committed architecture docs.
3. Context layer reads generated index outputs.
4. Scoring ranks task-relevant files.
5. Renderer writes `.vibecode/current/context_pack.md`.

## Truth precedence

1. Human-maintained `.vibecode/architecture/*.md`
2. Human-maintained `.vibecode/checks/*.yaml`
3. Source code and package/config files
4. Generated indexes
5. Runtime/session outputs

