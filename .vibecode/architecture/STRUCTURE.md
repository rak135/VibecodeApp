# Repository Structure

## Source package

- `vibecode/cli.py` defines the command-line interface.
- `vibecode/project.py` owns project initialization and map rendering commands.
- `vibecode/config.py` loads `.vibecode/project.yaml` and required check configuration.
- `vibecode/indexer/` owns deterministic scan and index generation.
- `vibecode/context/` owns task relevance and context-pack generation.
- `vibecode/validation.py` owns `.vibecode/` validation checks.

## Tests

- `tests/test_vibecode_init.py` verifies `.vibecode/` project creation.
- `tests/test_vibecode_indexer.py` verifies file scanning and ignore behavior.
- `tests/test_vibecode_*map.py` files verify generated index builders.
- `tests/test_vibecode_run_record.py` verifies index run records.
- `tests/test_vibecode_validation.py` verifies validation behavior.

## Project memory

- `.vibecode/architecture/*.md` contains committed architecture truth.
- `.vibecode/checks/required_checks.yaml` contains committed required check commands.
- `.vibecode/handoff/*.md` contains project-level handoff state when maintained by humans.
- `.vibecode/index/README.md` and `.vibecode/index/schema.json` define generated index policy.

## Generated/runtime locations

- `.vibecode/index/*.generated.*` contains regenerated indexes.
- `.vibecode/current/*` contains current task/session outputs.
- `.vibecode/logs/*` contains runtime logs.
