# TUI Phase 1 P20 Refresh/Rebuild Review

Generated: 2026-05-15

## Verdict

PASS. The refresh/rebuild service currently meets the P20.1 scope: it preserves customized human-maintained truth files byte-for-byte, creates missing manual truth files without overwriting existing ones, cleans only explicit disposable allowlists, leaves `.vibecode/logs/*` and `.vibecode/runs/*` untouched, reuses the existing init/index/validation machinery, is independent of Textual/LLM/OpenCode, and all reviewed checks passed.

This review did not modify implementation or test files. The task scope allowed only this review document.

## Findings

### PASS: customized manual truth files are preserved and missing manual files are created

`VibecodeRefreshService._ensure_vibecode()` reuses `project._file_templates()` plus `permissions.write_profile(..., force=False)`. Existing files are only recorded in `preserved_manual_files`; absent files are created once and recorded in `created_missing_manual_files` (`vibecode/refresh.py:123-160`, `vibecode/project.py:219-374`, `vibecode/permissions.py:62-86`).

I also checked the current policy alignment directly: `_file_templates() + PROFILES` matches `write_rules.HUMAN_MAINTAINED_PATHS` exactly (`missing_from_refresh []`, `extra_in_refresh []`), so the refresh service currently covers every declared human-maintained file (`vibecode/write_rules.py:18-37`).

Focused evidence: `test_refresh_creates_vibecode_when_missing`, `test_refresh_creates_standard_human_maintained_files`, `test_refresh_creates_missing_manual_files_on_partial_vibecode`, `test_refresh_preserves_customized_manual_files_byte_for_byte`, and `test_refresh_preserves_all_human_maintained_files_on_second_run` all passed.

### PASS: cleanup is explicit allowlist cleanup, not broad deletion

Cleanup is limited to `_DISPOSABLE_DIR_CONTENTS` (`.vibecode/current`, `.vibecode/generated`, `.vibecode/cache`, `.vibecode/tmp`) plus `_DISPOSABLE_INDEX_FILES` (`vibecode/refresh.py:27-46`, `vibecode/refresh.py:162-186`). There is no `shutil.rmtree(".vibecode")` or similar broad removal path.

Direct inspection confirmed `logs_in_cleanup False` and `runs_in_cleanup False`, and the code never includes `.vibecode/logs/*` or `.vibecode/runs/*` in either cleanup tuple. That means logs and run records survive refresh by default, exactly as required.

Focused evidence: `test_refresh_removes_stale_current_files`, `test_refresh_removes_stale_generated_files`, `test_refresh_removes_disposable_index_files_before_regen`, `test_refresh_does_not_delete_logs`, and `test_refresh_does_not_delete_runs` all passed.

### PASS: refresh reuses existing init/index/validation logic instead of duplicating it

The service reuses the shared project/init helpers rather than maintaining a second copy of those rules: `_GENERATED_DIRS`, `_file_templates()`, `PROFILES`, and `write_profile()` are imported from the existing modules (`vibecode/refresh.py:125-160`, `vibecode/project.py:13-20`, `vibecode/project.py:219-374`, `vibecode/permissions.py:29-86`).

Regeneration and validation go through `cmd_index()`, which already performs the inventory/symbol/dependency/test/risk writes and then runs `validate_project()` / `write_validation_report()` (`vibecode/refresh.py:188-245`, `vibecode/indexer/__init__.py:222-391`, `vibecode/validation.py:58-120`). That avoids a separate refresh-only implementation of index or validation behavior.

This also means validation failure is not silent. Refresh reads `.vibecode/current/validation.json` back into the report and promotes validation `ERROR` / `WARN` items into `report.errors` and `report.warnings` (`vibecode/refresh.py:219-245`). If `cmd_index()` raises instead of returning, refresh records `Index failed with exception: ...` and still attempts to read the validation artifact (`vibecode/refresh.py:194-200`).

### PASS: the refresh report is structured enough for a phase-1 TUI

`RefreshReport` exposes repo path, whether `.vibecode` already existed, preserved and created manual files, removed disposable files, generated outputs, validation status and summary, warnings, errors, and a next-step recommendation. `as_dict()` converts that into a plain JSON-serializable dict (`vibecode/refresh.py:49-79`).

That is enough structure for a TUI to render a summary plus expandable sections without needing to scrape CLI text. The service itself is also intentionally decoupled from Textual and described as callable from the TUI, CLI, or tests (`vibecode/refresh.py:1-14`, `vibecode/refresh.py:82-117`).

Focused evidence: `test_refresh_returns_refresh_report_instance`, `test_refresh_report_as_dict_has_required_keys`, `test_refresh_report_list_fields_are_lists`, `test_refresh_report_next_recommended_action_is_non_empty`, and `test_refresh_validation_status_is_set` all passed.

### PASS: refresh is idempotent and Windows-path-safe

The service resolves the repo root once with `Path.resolve()`, uses `relative_to()` plus `as_posix()` for reported relative paths, and passes `str(root)` into `cmd_index()`, which reconstructs a `Path` and resolves it again (`vibecode/refresh.py:93-117`, `vibecode/refresh.py:169`, `vibecode/refresh.py:192`, `vibecode/indexer/__init__.py:223`). That is safe on Windows while still normalizing report output into stable POSIX-style strings for UI/JSON use.

Focused evidence: `test_refresh_report_repo_path_is_posix`, `test_refresh_report_repo_path_matches_root`, `test_refresh_is_idempotent`, `test_refresh_vibecode_existed_false_on_first_call`, and `test_refresh_vibecode_existed_true_on_second_call` all passed.

### PASS: no LLM or OpenCode call is made during refresh

The reviewed refresh path only imports local project/init/index/validation helpers (`vibecode/refresh.py:123-245`). The only `opencode` occurrence I found in that dependency surface is explanatory text in `vibecode/permissions.py`; there is no runtime OpenCode/LLM invocation path inside refresh (`vibecode/permissions.py:1-19`).

## Uncovered preservation / drift edge cases

1. `VibecodeRefreshService` currently derives its manual-file knowledge from `_file_templates()` plus `PROFILES`, while the canonical policy lives in `write_rules.HUMAN_MAINTAINED_PATHS`. They match today, but a future human-maintained path added only to `write_rules.py` would not be created or reported by refresh until refresh's inputs were updated too (`vibecode/refresh.py:125-160`, `vibecode/write_rules.py:18-37`).
2. The disposable index allowlist is another manually maintained list. It matches current refresh behavior, but it can drift from other generated-output declarations. There is already one documentation mismatch: `risk_report.json` is treated as disposable/generated by refresh and `cmd_index()`, but it is missing from the committed `.vibecode/index/schema.json` legacy-generated list (`vibecode/refresh.py:27-37`, `vibecode/indexer/__init__.py:287-297`, `.vibecode/index/schema.json:12-20`).
3. If an existing `.vibecode/project.yaml` is malformed, `_ensure_vibecode()` swallows the config-load exception and falls back to repo-derived `project_id` / `project_name` for any missing template files before `cmd_index()` later reports the failure. That does not overwrite customized truth files, but it is an uncovered malformed-config path worth testing (`vibecode/refresh.py:132-139`, `vibecode/refresh.py:188-200`).

## Checks run

- `python -m pytest tests\test_vibecode_refresh.py -v`
  - PASS: 21/21 tests passed
  - PASS `test_refresh_creates_vibecode_when_missing`
  - PASS `test_refresh_creates_standard_human_maintained_files`
  - PASS `test_refresh_creates_missing_manual_files_on_partial_vibecode`
  - PASS `test_refresh_preserves_customized_manual_files_byte_for_byte`
  - PASS `test_refresh_preserves_all_human_maintained_files_on_second_run`
  - PASS `test_refresh_removes_stale_current_files`
  - PASS `test_refresh_removes_stale_generated_files`
  - PASS `test_refresh_removes_disposable_index_files_before_regen`
  - PASS `test_refresh_does_not_delete_logs`
  - PASS `test_refresh_does_not_delete_runs`
  - PASS `test_refresh_returns_refresh_report_instance`
  - PASS `test_refresh_report_as_dict_has_required_keys`
  - PASS `test_refresh_report_repo_path_is_posix`
  - PASS `test_refresh_report_next_recommended_action_is_non_empty`
  - PASS `test_refresh_report_list_fields_are_lists`
  - PASS `test_refresh_regenerates_index_artifacts_or_records_failure`
  - PASS `test_refresh_validation_status_is_set`
  - PASS `test_refresh_is_idempotent`
  - PASS `test_refresh_vibecode_existed_false_on_first_call`
  - PASS `test_refresh_vibecode_existed_true_on_second_call`
  - PASS `test_refresh_report_repo_path_matches_root`
- `python -m ruff check vibecode\refresh.py tests\test_vibecode_refresh.py`
  - PASS
- `vibecode check C:\DATA\PROJECTS\VibecodeApp`
  - PASS `unit tests`
  - PASS `cli help`
  - PASS `index command help`
  - PASS `context command help`

## Changed files

- `docs/audit/TUI_PHASE1_P20_REFRESH_REBUILD_REVIEW.md`
