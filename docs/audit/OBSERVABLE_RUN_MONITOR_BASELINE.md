# Observable Run Monitor — Baseline Audit

> Generated: 2026-05-11
> Scope: run/context/guard/check/handoff/dashboard/serve CLI entry points
> Validation: compileall + 226 targeted tests

---

## 1. CLI Entry Points

All entry points dispatch through `vibecode/cli.py:462` (`_dispatch`). The parser is built in `vibecode/cli.py:10` (`create_parser`).

| Command | Handler | Module | Repo Resolution |
|---|---|---|---|
| `run` | `cmd_run(args)` | `vibecode/run.py:355` | Registry fallback via `_resolve_repo_root` |
| `run-plan` | `cmd_run_plan(args)` | `vibecode/run_plan.py:517` | Defaults to `.` (no registry fallback) |
| `context` | `cmd_context(args)` | `vibecode/context/__init__.py:12` | Custom `_resolve_repo` with registry fallback |
| `guard` | `cmd_guard(args)` | `vibecode/guard.py:638` | Registry fallback |
| `check` | `cmd_check(args)` | `vibecode/check.py:221` | Registry fallback |
| `handoff-check` | `cmd_handoff_check(args)` | `vibecode/handoff.py:211` | Registry fallback |
| `serve` | `cmd_serve(args)` | `vibecode/mcp_server.py:201` | Registry fallback |
| `dashboard` | Inline in `_dispatch` | `vibecode/cli.py:539` | Registry fallback |

Each command returns an `int` exit code (0 = success, 1 = failure/error, 2 = incomplete).

---

## 2. How `vibecode run` Creates Context Packs and OpenCode Prompts

**Source**: `vibecode/run.py:478-493`

1. `cmd_run` calls `cmd_context(...)` from `vibecode/context/__init__.py:12`, which:
   - Resolves the repo root via `_resolve_repo` (registry fallback or `.`)
   - Prints risk-file warnings from `.vibecode/index/risky_files.md` to stderr
   - Calls `write_context_pack(repo, task)` in `vibecode/context/renderer.py:36`
   - `render_context_pack()` (line 50) assembles 10 `_Section` objects with priorities
   - Sections: project, task, invariants, architecture, relevant files, index status, required checks, protected paths, handoff, working rule
   - Applies a 32,000-character limit (`DEFAULT_CHAR_LIMIT`), dropping lowest-priority sections first
   - Writes to `.vibecode/current/context_pack.md`
   - If `--platform opencode`, exports via `write_opencode_prompt()` in `vibecode/context/platform_export.py:43`
   - The OpenCode prompt wraps the context pack with pre-edit and post-edit instructions
   - Written to `.vibecode/current/opencode_prompt.md`

**Key files involved**:
- `vibecode/context/__init__.py` — `cmd_context` dispatcher
- `vibecode/context/renderer.py` — section assembly, length limiting, file I/O
- `vibecode/context/scoring.py` — `score_relevant_files()` for relevance ranking
- `vibecode/context/platform_export.py` — `render_opencode_prompt()` / `write_opencode_prompt()`
- `vibecode/context/platform_registry.py` — plugin registry for exporters

---

## 3. How `vibecode run` Invokes OpenCode

**Source**: `vibecode/run.py:500-598`

1. **Command resolution** (line 509): `_get_opencode_command(cfg, os.environ)` calls `resolve_opencode_command()` from `vibecode/adapters/opencode.py:38`
   - Checks `OPENCODE_COMMAND` env var first
   - Falls back to `opencode` on PATH
   - Returns `None` if nothing found → error exit

2. **Availability check** (line 525): `check_opencode(command)` from `vibecode/adapters/opencode.py:55`
   - For simple commands: runs `{binary} --version` with `shell=False`
   - For compound commands (multi-word, e.g. `python wrapper.py`): checks `shutil.which` only
   - Returns `OpenCodeStatus(available, command, message)`

3. **Preflight check** (line 540): `build_run_plan(...)` from `vibecode/run_plan.py:160`
   - Checks git status, project config, index freshness, inventory health, gitignore policy, OpenCode availability
   - Returns `RunPlan` with `preflight_errors` and `preflight_warnings`
   - Hard preflight errors → exit code 1

4. **Invocation** (line 564-588): `subprocess.run(...)` with:
   - `shell=True` (trusted local command; Windows `.cmd`/`.bat` wrappers require it)
   - `input=prompt_content` (the OpenCode prompt text piped to stdin)
   - `capture_output=True`, `text=True`
   - `timeout=300` seconds
   - `cwd=str(root)`
   - Handles `TimeoutExpired` (exit code -1) and `OSError` (exit code -1)

**Trust model documented at line 26-38 of `run.py`**: the platform command is a trusted local shell command.

---

## 4. Where stdout/stderr/exit Code Are Captured

**Source**: `vibecode/run.py:564-590`

```python
result = subprocess.run(
    command,
    input=prompt_content,
    capture_output=True,
    text=True,
    timeout=300,
    cwd=str(root),
    shell=True,
)
exit_code = result.returncode
stdout = result.stdout
stderr = result.stderr
```

- Captured via `subprocess.run` with `capture_output=True`
- Timeout → `exit_code = -1`, `stdout = ""`, `stderr = "Command timed out after 300 seconds."`
- OSError → `exit_code = -1`, `stdout = ""`, `stderr = f"Failed to execute {command}: {exc}"`
- Agent output is printed to the user (stdout to stdout, stderr to stderr) at lines 595-601
- The captured values are stored in `RunSummary` (lines 642-643) and written to run metadata

**Also relevant**: `vibecode/check.py:117` (`run_command`) captures check subprocess output similarly (`capture_output=True`, `text=True`, `timeout=300`).

---

## 5. Where Run Summary Files Are Written Today

### Legacy metadata (flat)
**Source**: `vibecode/run.py:141-182` (`_write_run_metadata`)
- Path: `.vibecode/runs/{session_id}.json`
- Contains: session_id, timestamps, platform, profile, repo_root, task, dirty, index_fresh, command, exit_code, stdout, stderr, preflight_errors/warnings, error

### Nested summary (structured)
**Source**: `vibecode/run.py:185-194` (`_write_run_summary`)
- Path: `.vibecode/runs/{session_id}/summary.json`
- Contains: full `RunSummary.as_dict()` with `$schema: vibecode/run-summary/v1` — includes guard, checks, handoff, and diff results

### Run plan (preflight)
**Source**: `vibecode/run_plan.py:537-562` (`cmd_run_plan`)
- Path: `.vibecode/current/run_plan.json`
- Schema: `vibecode/run-plan/v1`

### Guard result
**Source**: `vibecode/guard.py:180-193` (`write_guard_result`)
- Path: `.vibecode/current/guard_result.json`
- Schema: `vibecode/guard-result/v1`

### Check results
**Source**: `vibecode/check.py:205-210` (`write_check_results`)
- Path: `.vibecode/current/check_results.json`
- Schema: `vibecode/check-results/v1`

### Handoff check report
**Source**: `vibecode/handoff.py:229-235` (`cmd_handoff_check`, `--json` flag)
- Path: `.vibecode/current/handoff_check.json`
- Schema: `vibecode/handoff-validation/v1`

### Context pack
**Source**: `vibecode/context/renderer.py:36`
- Path: `.vibecode/current/context_pack.md`

### OpenCode prompt
**Source**: `vibecode/context/platform_export.py:43`
- Path: `.vibecode/current/opencode_prompt.md`

### Last index record
**Source**: `vibecode/indexer/__init__.py` via `cmd_index`
- Path: `.vibecode/current/last_index.json`

All writes go to `.vibecode/current/` or `.vibecode/runs/` which are generated/runtime paths.

---

## 6. How Guard Findings Are Represented Today

**Data structures** (`vibecode/guard.py`):
- `GuardFinding` (frozen dataclass, line 50): `rule_id`, `path`, `severity` (error/warning), `message`, `rule`, `recommended_fix`, `required_tests`
- `GuardResult` (frozen dataclass, line 78): `findings: tuple[GuardFinding, ...]`
  - `passed` property (line 84): `True` if no findings have `severity == "error"`
  - `suggested_tests()` (line 101): collects unique required_test paths across findings
  - `as_dict()` (line 88): serializes to JSON schema `vibecode/guard-result/v1`

**Evaluation rules checked** (in `evaluate_guard`, line 113):
1. `check_protected_path_changes` — policy-driven protected path rules (from `.vibecode/checks/protected_paths.yaml`)
2. `check_generated_runtime_changes` — hard-error on generated/runtime file edits
3. `check_readme_changes` — hard-error on README.md edit unless task is docs-scoped
4. `check_architecture_truth_recorded` — hard-error if `.vibecode/architecture/*.md` changed without handoff/history record
5. `check_source_test_change_balance` — warning when source/test changes are unbalanced

**Findings are deduplicated** by `(severity, path, rule_id)` via `_dedupe_findings` (line 622).

**Output**:
- CLI (`cmd_guard`, line 638): prints errors and warnings to stderr, writes `guard_result.json`
- Run post-check: passes `task` and `test_map` for contextualized findings

---

## 7. Whether Guard Failures Affect Overall Status or Process Exit Behavior

**Yes**, guard failures directly affect overall run status:

**In `RunSummary.overall_status`** (`vibecode/run.py:94-107`):
```python
if self.guard and not self.guard.passed:
    return "failure"
```

**In `cmd_run` exit code** (`vibecode/run.py:693-700`):
- `"failure"` → exit code 1
- `"error"` → exit code 1
- `"incomplete"` → exit code 2
- `"success"` → exit code 0

**In standalone `cmd_guard`** (`vibecode/guard.py:711-716`):
- Errors → exit code 1
- `--strict` + warnings → exit code 1
- Otherwise → exit code 0

**Guard failures do NOT block check/handoff execution** — errors in `_run_post_checks` are caught and printed as warnings (line 332-350 of `run.py`). The guard/check/handoff results are collected, and the summary determines the final exit code.

---

## 8. How MCP Server Tools Are Implemented Today and Whether They Can Be Instrumented

**Source**: `vibecode/mcp_server.py`

**Architecture**:
- `VibecodeServer` class (line 10): loads `file_inventory.json` and `risk_report.json` once at construction
  - Builds three in-memory indices: `_cards` (path→card), `_symbols` (name→list of locations), `_risks` (path→risk item)
  - JSON loading delegates to `data_loader._load_json` (shared with TUI)
- `build_mcp_server()` (line 176): creates a `FastMCP("vibecode")` instance and registers three tools as decorated functions

**Three exposed tools**:
1. `get_file_card(file_path: str) → str` — returns markdown card with purpose, symbols, snippet, facts, heuristics
2. `find_symbol(symbol_name: str) → str` — searches exact name, falls back to case-insensitive; returns markdown list of locations
3. `list_high_risk() → str` — returns markdown report of files with `risk_level=="high"` or high-severity heuristics

**Transport**: stdio via `mcp.run(transport="stdio")` (line 239)

**Instrumentability**:
- `VibecodeServer` is a plain Python class with no telemetry hooks. Adding instrumentation would require:
  - Wrapping or monkey-patching tool methods
  - Adding middleware via `FastMCP`'s decorator pattern
  - The class is stateless after construction (only reads from immutable indices) — tracking call counts, timing, and errors is straightforward
- `cmd_serve` currently has no observable hooks before/after `mcp.run()` — the call is blocking

**Data dependency**: Both MCP server and dashboard share `data_loader.load_project_data()`, which normalizes cards and derives `high_risk_count`.

---

## 9. How Existing TUI/Dashboard Code Is Structured and Whether It Can Be Reused

**Source**: `vibecode/tui_app.py`

**Key components**:
- `DashboardData` (NamedTuple, line 15): `cards`, `total_files`, `high_risk_count`
- `load_dashboard_data(repo_root)` (line 21): delegates to `data_loader.load_project_data()`
- `VibecodeTUI(App)` (line 147): Textual `App` subclass
  - `CSS_PATH` = `vibecode/tui_theme.tcss`
  - Constructor takes `repo_root: Path`
  - `on_mount`: loads data, pushes `MainScreen`
- `MainScreen(Screen)` (line 109): DataTable with File/Purpose/Symbols columns; Footer showing counts
- `CardDetailScreen(Screen)` (line 49): scrollable detail view showing purpose, symbols table, facts, heuristics, snippet

**Key bindings**:
- `MainScreen`: Enter → push `CardDetailScreen`, Q → quit
- `CardDetailScreen`: Escape/Q → pop screen

**Reusability assessment**:
- `MainScreen` and `CardDetailScreen` are existing, working, tested screens — they could be extended or subclassed for a monitor view
- `VibecodeTUI` could gain additional screens/modes without changing existing screens
- `DashboardData` and `load_dashboard_data` are shared with the data loader pipeline
- Widget styles are in `vibecode/tui_theme.tcss` — additional styling would follow the same pattern
- No modal or background-refresh patterns exist yet; a monitor would need periodic data refresh (the current TUI is static after mount)
- Textual's `set_interval` or `worker` patterns could be used for live updates

**Launch**: In `cli.py:550`, the TUI is invoked as `VibecodeTUI(repo_root=args.repo_root).run()` — a synchronous blocking call.

---

## 10. Current Tests That Cover Run/Guard/Context/MCP/TUI Behavior

| Test File | Coverage | Test Count (targeted) |
|---|---|---|
| `tests/test_vibecode_run.py` | `cmd_run`, `_run_git_check`, `_write_run_metadata`, profile validation, git status, preflight errors, session metadata, context pack generation integration | ~50+ |
| `tests/test_vibecode_run_post.py` | `RunSummary` overall_status, `_run_post_checks`, `_write_run_summary`, guard/check/handoff integration in run pipeline, exit code behavior | ~60+ |
| `tests/test_vibecode_guard.py` | All 5 guard rule functions (`check_protected_path_changes`, `check_generated_runtime_changes`, `check_readme_changes`, `check_architecture_truth_recorded`, `check_source_test_change_balance`), `cmd_guard` CLI, `GuardFinding`/`GuardResult` serialization, `write_guard_result`, `evaluate_guard`, `evaluate_project_guard`, `--strict` mode | ~40+ |
| `tests/test_vibecode_context_pack.py` | Context pack generation, section rendering, length limiting, relevant file scoring integration | ~30+ |
| `tests/test_vibecode_mcp_server.py` | `VibecodeServer` construction, `get_file_card`, `find_symbol`, `list_high_risk`, missing file handling, markdown output format, `cmd_serve`, config snippet format | ~50+ |
| `tests/test_vibecode_dashboard.py` | `load_dashboard_data`, `DashboardData`, null normalization, card rendering helpers, `_symbols_summary` | ~25+ |
| `tests/test_integration.py` | Cross-component integration: inventory→dashboard, inventory→MCP server, data loader pipeline, project data consistency | ~20+ |

**Total targeted tests run**: 226 (all passed)

**Additional test files** (not in targeted run but covering related areas):
- `tests/test_vibecode_check.py` — required checks runner
- `tests/test_vibecode_handoff.py` / `tests/test_vibecode_handoff_cli.py` — handoff validation
- `tests/test_vibecode_run_plan.py` — run plan assembly
- `tests/test_vibecode_context_pack.py` — context pack generation
- `tests/test_vibecode_full_workflow.py` — end-to-end init→index→context→export→guard→check→handoff
- `tests/test_vibecode_e2e.py` — end-to-end integration

---

## 11. Known Risk Areas and Likely Files to Touch

### High-risk files (protected or architecturally sensitive)

| Path | Risk | Reason |
|---|---|---|
| `vibecode/run.py` | **HIGH** | Core orchestrator — `cmd_run` controls the entire agent pipeline (context, subprocess, post-checks, exit code). Any monitor would need hooks here. The subprocess call with `shell=True` is the main execution surface. |
| `vibecode/guard.py` | **HIGH** | Guard rule evaluation — findings representation, `passed` property, and result serialization are tightly coupled to the monitor's judgment logic. |
| `vibecode/check.py` | **MEDIUM** | Check runner — subprocess execution and result serialization are straightforward. `run_checks` returns `CheckRun` which can be reused as-is. |
| `vibecode/handoff.py` | **MEDIUM** | Handoff validation — `HandoffResult` serialization is already factored; findings are `HandoffIssue` objects. |
| `vibecode/cli.py` | **LOW** | CLI dispatch — adding a `monitor` subcommand would add ~15 lines to `create_parser()` and ~8 lines to `_dispatch()`. |
| `vibecode/mcp_server.py` | **MEDIUM** | MCP server — `VibecodeServer` is a plain class; instrumenting tool calls requires wrapping or FastMCP middleware. `cmd_serve` has no pre/post hooks. |
| `vibecode/tui_app.py` | **MEDIUM** | TUI dashboard — existing `VibecodeTUI`, `MainScreen`, `CardDetailScreen` are reusable. A monitor screen would be an additional `Screen` subclass with live refresh. |
| `vibecode/data_loader.py` | **LOW** | Data loader — shared between MCP server and TUI. `ProjectData` dataclass is the canonical data model. |
| `vibecode/context/renderer.py` | **LOW** | Context pack renderer — `write_context_pack` and `render_context_pack` are well-factored. A monitor would call them (or skip them if already generated). |
| `vibecode/context/__init__.py` | **LOW** | `cmd_context` — already called by `cmd_run`; no changes needed for a monitor unless it needs to capture context pack content directly. |
| `vibecode/adapters/opencode.py` | **LOW** | OpenCode adapter — `resolve_opencode_command` and `check_opencode` are command-line readiness checks. A monitor would reuse them as-is. |
| `vibecode/diff_summary.py` | **LOW** | Diff summary — `diff_summarise` compares pre/post git states. Already called in `cmd_run`. |
| `vibecode/permissions.py` | **LOW** | Permission profiles — advisory metadata. `PROFILES` dict and `profile_path` are stable. |

### Key integration points for a monitor

1. **Execution hook**: The monitor needs to observe or replace `subprocess.run` in `run.py:564`. Currently, stdout/stderr/exit_code are captured but only available after the process completes. Real-time streaming would require `Popen` + line-by-line reading instead of `capture_output=True`.

2. **Post-run audit hook**: `_run_post_checks` in `run.py:304` runs guard/check/handoff sequentially. A monitor would need to receive these results as they become available (currently all three are computed before `RunSummary` is assembled).

3. **Run summary assembly**: `RunSummary` in `run.py:71` is the canonical aggregation point. A monitor could consume it directly or observe its construction.

4. **MCP tool telemetry**: No existing telemetry in `VibecodeServer`. Adding call counting, timing, and error tracking would require either subclassing or decorators.

5. **TUI live refresh**: The current TUI is static on mount. A monitor would need Textual workers or `set_interval` for periodic updates, plus data structures that support incremental diffs.

6. **Event stream**: There is no event bus or observable pattern today. All results flow through return values, printed output, and file writes. A monitor would need to intercept or duplicate these flows.

### Validation performed

- `python -m compileall vibecode` — passed (all modules compile)
- `pytest tests/test_vibecode_run.py tests/test_vibecode_run_post.py tests/test_vibecode_guard.py tests/test_vibecode_context_pack.py tests/test_vibecode_mcp_server.py tests/test_vibecode_dashboard.py tests/test_integration.py -x -q` — **226 passed** in 61.24s
