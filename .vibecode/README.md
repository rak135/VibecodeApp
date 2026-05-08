# .vibecode directory policy

## Human-maintained and committed

- `.vibecode/architecture/*.md`
- `.vibecode/checks/*.yaml`
- `.vibecode/decisions/*.md`
- `.vibecode/handoff/*.md` if they describe project-level state

## Generated and ignored

- `.vibecode/index/*.generated.*`
- `.vibecode/current/*`
- `.vibecode/generated/*`
- `.vibecode/runs/*`
- `.vibecode/tmp/*`
- `.vibecode/cache/*`
- `.vibecode/logs/*`

## Rule

If a file can be regenerated from source code and human-maintained docs, it is generated.
If a future agent must know it after cloning the repo, it should be committed.
