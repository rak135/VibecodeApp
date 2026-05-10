# Control Layer Final Audit

Generated: 2026-05-10
Scope: Post-repair audit of the VibecodeApp control layer (PRD tasks 1–42 completed).
1219 tests pass on Windows / Python 3.12.

## Implementation Stage by Subsystem

| Subsystem | Modules | Status | Tests |
|-----------|---------|--------|-------|
| **Indexer** | `vibecode/indexer/` (13 modules) | Stable. File scanning, classification, risk scoring, symbol extraction (Python AST + TS regex), dependency graphs, test mapping, entrypoint detection, repo tree rendering, run records with file-set fingerprints. | 190+ tests |
| **Context** | `vibecode/context/` (5 modules) | Stable. Two-pass relevant-file scoring with compound phrase routing, dependency hub fan-out capping, context pack rendering with protected paths, handoff/history rules, and required checks sections. | 80+ tests |
| **Guard** | `vibecode/guard.py` | Stable. Evaluates git diff against protected-path rules, generated/runtime edit detection, README manual-only enforcement, architecture-change handoff requirement, source/test mismatch warnings. CLI returns non-zero for hard violations. | 60+ tests |
| **Check** | `vibecode/check.py` | Stable. Runs required checks from `.vibecode/checks/required_checks.yaml` as subprocesses. Supports string and list-form commands. Trusted local execution model (`shell=True`) documented. | 30+ tests |
| **Handoff** | `vibecode/handoff.py` | Stable. Validates NOW.md/NEXT.md/BLOCKERS.md for required sections, placeholder detection (TODO/TBD/unfilled markers), architecture-change recording. CLI `handoff-check` returns non-zero on invalid. | 40+ tests |
| **History** | `vibecode/history.py` | Stable. Creates durable history summaries with 6 required section headings. Validates existing summaries for placeholder content. `history new` subcommand exposed via CLI. | 25+ tests |
| **Run** | `vibecode/run.py` | Stable. Full agent session orchestrator: context generation -> platform invocation -> post-run guard/check/handoff pipeline -> diff summary -> metadata. Preflight verifies git state, index freshness, generated/runtime ignore rules, platform availability, profile existence. | 50+ tests |
| **Run Plan** | `vibecode/run_plan.py` | Stable. Assembles dry-run plan with preflight checks. Surfaces stale-index warnings, dirty repo status, ignore-policy gaps. Available as `run-plan` CLI command. | 35+ tests |
| **Registry** | `vibecode/registry.py`, `vibecode/project_cli.py` | Stable. Named project management (`~/.vibecode/projects.yaml`). CLI: `project add/use/list/remove/current`. Active project fallback for index/map/context/validate/guard/check/handoff-check/run. | 50+ tests |
| **Diff Summary** | `vibecode/diff_summary.py` | Stable. Post-run change classification (source/test/docs/generated/config/other) from pre/post git state. | 30+ tests |
| **Git State** | `vibecode/git_state.py` | Stable. Low-level git inspection: commit hash, status, diff. Handles orphan branches, non-git repos. | 8 tests |
| **Permissions** | `vibecode/permissions.py`, `.vibecode/agents/*.json` | Stable. Three advisory profiles (safe/fast/audit). Validated at run time; recorded in run metadata. Profiles do NOT constrain OpenCode tool permissions — actual enforcement depends on OpenCode configuration. | Covered by run tests |
| **Write Rules** | `vibecode/write_rules.py` | Stable. Canonical list of human-maintained vs generated paths. `safe_write()` enforces write protection without `--force`. Generated/runtime doctrine aligned with `.gitignore`, docs, guard, and AGENTS export. | Covered |
| **AGENTS Export** | `vibecode/context/agents_export.py` | Stable. Managed AGENTS.md blocks include PRD.json, runs/*, full command list. Idempotent when already up to date. Never overwrites manual AGENTS.md without `--force`. | 10+ tests |
| **Platform Export** | `vibecode/context/platform_export.py` | Stable. OpenCode prompt export wraps context pack. Pluggable platform registry. | 15+ tests |
| **Validation** | `vibecode/validation.py` | Stable. End-to-end artifact validation (init -> index -> validate -> check -> guard -> handoff-check). | 3 tests |
| **CLI** | `vibecode/cli.py` | Stable. Argparse dispatch for all 13+ top-level commands. Helper commands consistent with docs. | 20+ tests |
| **Adapter / OpenCode** | `vibecode/adapters/opencode.py` | Stable. Detects OpenCode CLI availability without launching a session. Tests use fake PATH/command. | 10+ tests |

## CLI Command List

| Command | Status |
|---------|--------|
| `init` | Implemented |
| `index` | Implemented |
| `context` | Implemented (`--platform opencode`, `--task`, `--no-index`) |
| `map` | Implemented |
| `validate` | Implemented |
| `guard` | Implemented (non-zero on hard violations) |
| `check` | Implemented (runs required_checks.yaml) |
| `handoff-check` | Implemented (non-zero on invalid handoff) |
| `run` | Implemented (`--platform opencode --task --profile --allow-dirty`) |
| `run-plan` | Implemented |
| `history new` | Implemented |
| `project add/use/list/remove/current` | Implemented |
| `export-agents` | Implemented (`--force` for manual overwrite) |

## Source-Truth vs Generated/Runtime Doctrine

**Source truth** (committed, human-maintained):
- `.vibecode/architecture/*.md`
- `.vibecode/checks/*.yaml`
- `.vibecode/handoff/*.md`
- `.vibecode/history/README.md`
- `.vibecode/history/*.md` (when filled with durable truth)
- `.vibecode/index/schema.json`, `.vibecode/index/README.md`
- `.vibecode/agents/*.json`
- Root `AGENTS.md`

**Generated/runtime** (ignored, not committed, must not be manually edited):
- `.vibecode/current/*` — session state
- `.vibecode/generated/*` — export artifacts
- `.vibecode/logs/*` — runtime logs
- `.vibecode/runs/*` — run metadata
- `.vibecode/tmp/*` — temporary files
- `.vibecode/cache/*` — cache
- `.vibecode/index/*.generated.*` — generated indexes

Doctrine is consistent across `.gitignore`, `INVARIANTS.md`, `STRUCTURE.md`, `write_rules.py`, `guard.py`, `AGENTS.md`, and `renderer.py`.

## Test Result Summary

- **1219 tests collected, 1219 passed, 0 failed** (Windows, Python 3.12)
- No skipped tests. No xfail markers used.
- 10 warnings (expected: empty `protected_paths.yaml` in some test repos; syntax error fixture).
- No real OpenCode required by any test.
- All tests use temporary repos, fake commands, and temp registry paths.

## Known Remaining Limitations

1. **SerenaProvider (`vibecode/indexer/code_intelligence.py:59-69`)**: Placeholder stub raises `NotImplementedError`. Not wired to CLI. MCP integration is not in scope.
2. **Permission profiles are advisory**: Profiles (safe/fast/audit) are validated and recorded in run metadata, but do not constrain OpenCode tool permissions. Actual enforcement depends on OpenCode configuration.
3. **Shell execution model**: `check.py` and `run.py` use `shell=True` for subprocess execution. This is documented as trusted local execution from user/repo configuration. List-form commands are also supported in `required_checks.yaml`.
4. **Platform support**: Only `opencode` platform is implemented. The platform registry pattern supports future additions.
5. **History summaries are human-maintained**: `history new` creates a template. Summaries must be filled manually to qualify as durable truth. Empty/placeholder summaries fail validation.
6. **No GUI, MCP implementation, swarm, or server**: The tool is CLI-only.
7. **`run-plan` defaults to `.`**: Unlike most commands that require an explicit repo argument, `run-plan` defaults to the current directory. This is documented.
8. **Stale index detection**: Uses file-set fingerprint (disk-scan hash of tracked files). Does not detect content changes within files that were not committed. Works best when combined with git commit tracking.

## Next Recommended Tasks

1. **Dogfood**: Use `vibecode` in real agent workflows to find ergonomic gaps.
2. **Stabilize**: Monitor context pack relevance quality across diverse task descriptions.
3. **Flesh out history**: Fill `.vibecode/history/` with summaries of completed PRD tasks.
4. **Harden ignore verification**: Expand preflight to catch `.gitignore` omissions for all generated/runtime dirs in edge cases.
5. **Permission profile passing**: If OpenCode adds profile support, pass advisory profile settings as flags.
6. **Windows CI**: Add CI validation on Windows for all test suites.
7. **Expand platform support**: Add adapters for other coding agents beyond OpenCode.
