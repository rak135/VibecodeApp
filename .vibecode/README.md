# .vibecode directory policy

## Human-maintained and committed

- `.vibecode/architecture/*.md`
- `.vibecode/checks/*.yaml`
- `.vibecode/handoff/*.md`
- `.vibecode/history/` (policy + summaries when durable; see `history/README.md`)
- `.vibecode/agents/*.json`
- `.vibecode/index/README.md`
- `.vibecode/index/schema.json`

## Generated and ignored

- `.vibecode/current/*`
- `.vibecode/generated/*`
- `.vibecode/logs/*`
- `.vibecode/runs/*`
- `.vibecode/tmp/*`
- `.vibecode/cache/*`
- generated `.vibecode/index/*` outputs other than `README.md` and `schema.json`

Generated index outputs include `file_inventory.json`, `symbol_map.json`,
`dependency_map.json`, `test_map.json`, `entrypoints.md`, `risky_files.md`,
`repo_tree.generated.md`, and similar maps written by `vibecode index`.

## Rule

If a file can be regenerated from source code and human-maintained docs, it is generated.
If a future agent must know it after cloning the repo, it should be committed.
