# Repository Structure

## Source package

- `vibecode/cli.py` defines the command-line interface.
- `vibecode/project.py` owns project initialization and map rendering commands.
- `vibecode/config.py` loads `.vibecode/project.yaml` and required check configuration.
- `vibecode/indexer/` owns deterministic scan and index generation.
- `vibecode/context/` owns task relevance and context-pack generation.
- `vibecode/validation.py` owns `.vibecode/` validation checks.
- `vibecode/guard.py` owns guard rule evaluation for protected paths and runtime edits.
- `vibecode/check.py` owns required checks runner (subprocess execution).
- `vibecode/handoff.py` owns handoff file validation (NOW/NEXT/BLOCKERS).
- `vibecode/history.py` owns history summary creation and validation.
- `vibecode/run.py` owns agent session orchestration (index, context, invoke, post-run audit).
- `vibecode/run_plan.py` owns run-plan assembly and preflight checks.
- `vibecode/registry.py` owns project registry (~/.vibecode/projects.yaml).
- `vibecode/diff_summary.py` owns post-run diff summary generation.
- `vibecode/git_state.py` owns git working tree inspection helpers.
- `vibecode/project_cli.py` owns project subcommand handlers (add, use, list, remove, current).

## Tests

- `tests/test_vibecode_init.py` verifies `.vibecode/` project creation.
- `tests/test_vibecode_indexer.py` verifies file scanning and ignore behavior.
- `tests/test_vibecode_*map.py` files verify generated index builders.
- `tests/test_vibecode_run_record.py` verifies index run records.
- `tests/test_vibecode_validation.py` verifies validation behavior.
- `tests/test_vibecode_guard.py` verifies guard rule engine (protected paths, generated/runtime edits).
- `tests/test_vibecode_context_pack.py` verifies context pack generation and content quality.
- `tests/test_vibecode_write_rules.py` verifies rule-writing workflows.
- `tests/test_vibecode_platform_export.py` verifies platform-specific prompt export.
- `tests/test_vibecode_agents_export.py` verifies AGENTS.md export safety.
- `tests/test_vibecode_check.py` verifies required checks runner.
- `tests/test_vibecode_handoff.py` and `tests/test_vibecode_handoff_cli.py` verify handoff file validation.
- `tests/test_vibecode_history.py` verifies history summary creation and validation.
- `tests/test_vibecode_run.py` verifies agent session orchestration.
- `tests/test_vibecode_run_plan.py` verifies run-plan assembly.
- `tests/test_vibecode_run_post.py` verifies post-run guard/check/handoff audit.
- `tests/test_vibecode_registry.py` verifies project registry CRUD.
- `tests/test_vibecode_diff_summary.py` verifies diff summary generation.
- `tests/test_vibecode_project_cli.py` verifies project subcommand CLI.
- `tests/test_vibecode_full_workflow.py` verifies full end-to-end workflow (init → index → context → export → guard → check → handoff).
- `tests/test_vibecode_stale_index.py` verifies stale index detection.
- `tests/test_vibecode_active_project_fallback.py` verifies active project fallback from registry.
- `tests/test_vibecode_e2e.py` runs end-to-end integration tests.
- `tests/test_vibecode_quickstart.py` verifies quickstart-level happy path.

## Project memory

- `.vibecode/architecture/*.md` contains committed architecture truth.
- `.vibecode/checks/required_checks.yaml` contains committed required check commands.
- `.vibecode/handoff/*.md` contains project-level handoff state when maintained by humans.
- `.vibecode/index/README.md` and `.vibecode/index/schema.json` define generated index policy.

## Generated/runtime locations

- Generated `.vibecode/index/*` outputs such as file inventory, symbol map, dependency map, test map, entrypoint/risk maps, and repo tree are regenerated indexes; only `README.md` and `schema.json` there are human-maintained.
- `.vibecode/current/*` contains current task/session outputs.
- `.vibecode/generated/*` contains export artifacts.
- `.vibecode/logs/*` contains runtime logs.
- `.vibecode/runs/*` contains run metadata.
- `.vibecode/tmp/*` contains temporary files.
- `.vibecode/cache/*` contains cached artifacts.
