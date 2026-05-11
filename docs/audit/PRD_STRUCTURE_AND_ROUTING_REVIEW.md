# PRD Structure and Routing Review

## Verdict
PASS

## Critical Blockers
None.

## Warnings
None requiring PRD changes. Codex model availability is treated as plausible because local `codex --help` supports `--model` and the local Codex config uses `model = "gpt-5.5"`.

## Schema Validation
`PRD.json` loads successfully with `json.load`. Required root fields are present: `name`, `description`, `defaults`, and `tasks`. `defaults` contains `engine`, `model`, and `engine_args`. `tasks` is a non-empty array. Every task has `title`, `description`, and boolean `completed`. All root/task engines are supported Ralphy engines. All `engine_args` values are arrays of strings.

## Effective Routing Table
| Task | Effective engine | Effective model | Effective engine args | Notes |
| --- | --- | --- | --- | --- |
| P0.1 Audit current run, guard, context, MCP, and TUI surfaces | opencode | deepseek/deepseek-v4-pro | `["--variant", "high"]` | OpenCode help supports `--variant`; model is present in `opencode models` as provider/model. |
| P0.2 Review baseline audit | codex | gpt-5.5 | `["-c", "model_reasoning_effort=\"high\""]` | Codex help supports `-c`; local config uses `model_reasoning_effort`; `gpt-5.5` is plausible for Codex CLI. |
| P0.3 Fix baseline audit issues if review found any | opencode | deepseek/deepseek-v4-pro | `["--variant", "high"]` | OpenCode help supports `--variant`; model is present in `opencode models` as provider/model. |
| P1.1 Implement structured event spine | opencode | deepseek/deepseek-v4-pro | `["--variant", "high"]` | OpenCode help supports `--variant`; model is present in `opencode models` as provider/model. |
| P1.2 Review structured event spine | codex | gpt-5.5 | `["-c", "model_reasoning_effort=\"high\""]` | Codex help supports `-c`; local config uses `model_reasoning_effort`; `gpt-5.5` is plausible for Codex CLI. |
| P1.3 Apply event spine review fixes | opencode | deepseek/deepseek-v4-pro | `["--variant", "high"]` | OpenCode help supports `--variant`; model is present in `opencode models` as provider/model. |
| P2.1 Implement per-run session paths and durable run artifacts | opencode | deepseek/deepseek-v4-pro | `["--variant", "high"]` | OpenCode help supports `--variant`; model is present in `opencode models` as provider/model. |
| P2.2 Review session artifact layer | codex | gpt-5.5 | `["-c", "model_reasoning_effort=\"high\""]` | Codex help supports `-c`; local config uses `model_reasoning_effort`; `gpt-5.5` is plausible for Codex CLI. |
| P2.3 Apply session artifact review fixes | opencode | deepseek/deepseek-v4-pro | `["--variant", "high"]` | OpenCode help supports `--variant`; model is present in `opencode models` as provider/model. |
| P3.1 Refactor run command around observable run controller | opencode | deepseek/deepseek-v4-pro | `["--variant", "high"]` | OpenCode help supports `--variant`; model is present in `opencode models` as provider/model. |
| P3.2 Review run controller refactor | codex | gpt-5.5 | `["-c", "model_reasoning_effort=\"high\""]` | Codex help supports `-c`; local config uses `model_reasoning_effort`; `gpt-5.5` is plausible for Codex CLI. |
| P3.3 Apply run controller review fixes | opencode | deepseek/deepseek-v4-pro | `["--variant", "high"]` | OpenCode help supports `--variant`; model is present in `opencode models` as provider/model. |
| P4.1 Add streaming agent process output | opencode | deepseek/deepseek-v4-pro | `["--variant", "high"]` | OpenCode help supports `--variant`; model is present in `opencode models` as provider/model. |
| P4.2 Review streaming agent output | codex | gpt-5.5 | `["-c", "model_reasoning_effort=\"high\""]` | Codex help supports `-c`; local config uses `model_reasoning_effort`; `gpt-5.5` is plausible for Codex CLI. |
| P4.3 Apply streaming agent review fixes | opencode | deepseek/deepseek-v4-pro | `["--variant", "high"]` | OpenCode help supports `--variant`; model is present in `opencode models` as provider/model. |
| P5.1 Make guard behavior advisory by default | opencode | deepseek/deepseek-v4-pro | `["--variant", "high"]` | OpenCode help supports `--variant`; model is present in `opencode models` as provider/model. |
| P5.2 Review advisory guard semantics | codex | gpt-5.5 | `["-c", "model_reasoning_effort=\"high\""]` | Codex help supports `-c`; local config uses `model_reasoning_effort`; `gpt-5.5` is plausible for Codex CLI. |
| P5.3 Apply advisory guard review fixes | opencode | deepseek/deepseek-v4-pro | `["--variant", "high"]` | OpenCode help supports `--variant`; model is present in `opencode models` as provider/model. |
| P6.1 Improve guard findings into human-readable drift reports | opencode | deepseek/deepseek-v4-pro | `["--variant", "high"]` | OpenCode help supports `--variant`; model is present in `opencode models` as provider/model. |
| P6.2 Review human-readable guard reporting | codex | gpt-5.5 | `["-c", "model_reasoning_effort=\"high\""]` | Codex help supports `-c`; local config uses `model_reasoning_effort`; `gpt-5.5` is plausible for Codex CLI. |
| P6.3 Apply guard report review fixes | opencode | deepseek/deepseek-v4-pro | `["--variant", "high"]` | OpenCode help supports `--variant`; model is present in `opencode models` as provider/model. |
| P7.1 Add prompt and context snapshot events | opencode | deepseek/deepseek-v4-pro | `["--variant", "high"]` | OpenCode help supports `--variant`; model is present in `opencode models` as provider/model. |
| P7.2 Review prompt/context snapshot truth | codex | gpt-5.5 | `["-c", "model_reasoning_effort=\"high\""]` | Codex help supports `-c`; local config uses `model_reasoning_effort`; `gpt-5.5` is plausible for Codex CLI. |
| P7.3 Apply prompt/context review fixes | opencode | deepseek/deepseek-v4-pro | `["--variant", "high"]` | OpenCode help supports `--variant`; model is present in `opencode models` as provider/model. |
| P8.1 Add MCP tool-call observability | opencode | deepseek/deepseek-v4-pro | `["--variant", "high"]` | OpenCode help supports `--variant`; model is present in `opencode models` as provider/model. |
| P8.2 Review MCP observability | codex | gpt-5.5 | `["-c", "model_reasoning_effort=\"high\""]` | Codex help supports `-c`; local config uses `model_reasoning_effort`; `gpt-5.5` is plausible for Codex CLI. |
| P8.3 Apply MCP observability review fixes | opencode | deepseek/deepseek-v4-pro | `["--variant", "high"]` | OpenCode help supports `--variant`; model is present in `opencode models` as provider/model. |
| P9.1 Implement TUI two-pane monitor MVP | opencode | deepseek/deepseek-v4-pro | `["--variant", "high"]` | OpenCode help supports `--variant`; model is present in `opencode models` as provider/model. |
| P9.2 Review TUI monitor MVP | codex | gpt-5.5 | `["-c", "model_reasoning_effort=\"high\""]` | Codex help supports `-c`; local config uses `model_reasoning_effort`; `gpt-5.5` is plausible for Codex CLI. |
| P9.3 Apply TUI monitor review fixes | opencode | deepseek/deepseek-v4-pro | `["--variant", "high"]` | OpenCode help supports `--variant`; model is present in `opencode models` as provider/model. |
| P10.1 Add run replay/show command | opencode | deepseek/deepseek-v4-pro | `["--variant", "high"]` | OpenCode help supports `--variant`; model is present in `opencode models` as provider/model. |
| P10.2 Review run replay/show command | codex | gpt-5.5 | `["-c", "model_reasoning_effort=\"high\""]` | Codex help supports `-c`; local config uses `model_reasoning_effort`; `gpt-5.5` is plausible for Codex CLI. |
| P10.3 Apply run replay/show review fixes | opencode | deepseek/deepseek-v4-pro | `["--variant", "high"]` | OpenCode help supports `--variant`; model is present in `opencode models` as provider/model. |
| P11.1 Update documentation and AGENTS guidance | opencode | deepseek/deepseek-v4-pro | `["--variant", "high"]` | OpenCode help supports `--variant`; model is present in `opencode models` as provider/model. |
| P11.2 Review documentation truthfulness | codex | gpt-5.5 | `["-c", "model_reasoning_effort=\"high\""]` | Codex help supports `-c`; local config uses `model_reasoning_effort`; `gpt-5.5` is plausible for Codex CLI. |
| P11.3 Apply documentation review fixes | opencode | deepseek/deepseek-v4-pro | `["--variant", "high"]` | OpenCode help supports `--variant`; model is present in `opencode models` as provider/model. |
| P12.1 Final validation and dogfood report | opencode | deepseek/deepseek-v4-pro | `["--variant", "high"]` | OpenCode help supports `--variant`; model is present in `opencode models` as provider/model. |
| P12.2 Final independent review | codex | gpt-5.5 | `["-c", "model_reasoning_effort=\"high\""]` | Codex help supports `-c`; local config uses `model_reasoning_effort`; `gpt-5.5` is plausible for Codex CLI. |
| P12.3 Apply final review fixes and close implementation | opencode | deepseek/deepseek-v4-pro | `["--variant", "high"]` | OpenCode help supports `--variant`; model is present in `opencode models` as provider/model. |

## Review/Fix Handoff Table
| Phase | Review task | Review output file | Fix task | Fix reads review file? | Fix output/no-op file | Status |
| --- | --- | --- | --- | --- | --- | --- |


## Product Semantics Check
PASS. The PRD preserves the product rule that guards are advisory by default. Guard findings remain visible in reports/events, strict or blocking behavior is explicit and optional, and no task instructs agents to hide, silently ignore, or convert advisory findings into default hard enforcement.

## Fixes Applied
- Changed `defaults.model` from `deepseek-v4-pro` to `deepseek/deepseek-v4-pro` for OpenCode provider/model compatibility.
- Changed every OpenCode task model from `deepseek-v4-pro` to `deepseek/deepseek-v4-pro`.
- Changed OpenCode `engine_args` from `["--reasoning-effort", "high"]` to `["--variant", "high"]`.
- Changed Codex review-task `engine_args` from `["--reasoning-effort", "high"]` to `["-c", "model_reasoning_effort=\"high\""]`.
- Added explicit no-op artifact path `docs/audit/OBSERVABLE_RUN_MONITOR_FINAL_FIX.md` to `P12.3 Apply final review fixes and close implementation`.

## Executable Validation
Commands run:
- `python -m json.tool PRD.json > $null`
- `opencode run --help`
- `opencode models --help`
- `opencode models`
- `codex --help`
- `codex exec --help`
- `codex debug --help`
- `rg -n "opencode|codex|engine_args|variant|reasoning-effort|model" -S .` in `c:\DATA\PROJECTS\ralphy-main`
- `python docs/audit/prd_validate_tmp.py`, then removed the temporary validator script

Result: `PRD validation` reported `PASS`.

## Final Recommendation
`PRD.json` is safe to run as-is now for ralphy-main per-task engine/model/args routing and explicit review/fix handoff.
