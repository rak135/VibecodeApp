# .vibecode directory policy

## Human-maintained and committed

- `.vibecode/architecture/*.md`
- `.vibecode/checks/*.yaml`
- `.vibecode/handoff/*.md`
- `.vibecode/history/README.md`
- `.vibecode/index/README.md`
- `.vibecode/index/schema.json`

## Generated and ignored

- `.vibecode/current/*`
- `.vibecode/generated/*`
- `.vibecode/logs/*`
- `.vibecode/runs/*`
- `.vibecode/tmp/*`
- `.vibecode/cache/*`
- `.vibecode/index/*.generated.*`

## Rule

If a file can be regenerated from source code and human-maintained docs, it is generated.
If a future agent must know it after cloning the repo, it should be committed.
