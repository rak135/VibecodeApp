# Now

- Architecture-map and context-pack core exists.
- Relevant-file scoring hardening is implemented and tested.
- Root `AGENTS.md` exists.
- AGENTS export safety is implemented, tested, and committed.
- Generated/runtime files are ignored and are not source of truth.
- Agent-facing docs now distinguish stable root `AGENTS.md`, task-specific context packs, and ignored generated AGENTS export output.
- Protected paths policy definition is implemented with loader/schema tests.
- Context packs now render protected path edit constraints from `.vibecode/checks/protected_paths.yaml`.
- Internal git changed-file inspection utility is implemented and tested for future guard/check/run workflows.
- Internal guard rule evaluation now fails generated/runtime file changes with tests.
- Protected path guard evaluation now reports protected path scope failures, required tests, generated-artifact hard failures, and handoff/explanation requirements.
