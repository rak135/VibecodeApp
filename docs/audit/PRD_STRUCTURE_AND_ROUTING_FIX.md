# PRD Structure and Routing Fix Report

## Changes Made
- Changed `defaults.model` from `deepseek-v4-pro` to `deepseek/deepseek-v4-pro` for OpenCode provider/model compatibility.
- Changed every OpenCode task model from `deepseek-v4-pro` to `deepseek/deepseek-v4-pro`.
- Changed OpenCode `engine_args` from `["--reasoning-effort", "high"]` to `["--variant", "high"]`.
- Changed Codex review-task `engine_args` from `["--reasoning-effort", "high"]` to `["-c", "model_reasoning_effort=\"high\""]`.
- Added explicit no-op artifact path `docs/audit/OBSERVABLE_RUN_MONITOR_FINAL_FIX.md` to `P12.3 Apply final review fixes and close implementation`.

## Validation Commands
- `python -m json.tool PRD.json > $null`
- `opencode run --help`
- `opencode models --help`
- `opencode models`
- `codex --help`
- `codex exec --help`
- `codex debug --help`
- `python docs/audit/prd_validate_tmp.py`, then removed the temporary validator script

## Validation Result
PASS. The validator reported `PRD validation` and `PASS` with no warnings.

## Remaining Warnings
None requiring PRD changes.

## Final Status
SAFE TO RUN
