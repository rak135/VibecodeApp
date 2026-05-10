VibecodeApp PRD Task Gap Audit

1. Executive Verdict

All 42 of 43 PRD tasks show completed=True; task 43 is the audit being done now. The full test suite passes: 1,158 tests, 0 failures, 4 non-critical
warnings. The git working tree is clean; no generated or runtime files are tracked; PRD.json is correctly tracked. The core control-layer pipeline —
init → index → context → guard → check → handoff-check → run — is genuinely implemented, tested, and documented.

However, three real gaps prevent a clean DONE verdict on several tasks. First, vibecode/context/agents_export.py's render_agents_block() generates
content that is materially weaker than the committed AGENTS.md: it omits PRD.json from the source-of-truth list, omits .vibecode/runs/* from the "do not
edit" list, and omits the entire "Available commands" section. Running vibecode export-agents . today would downgrade the repo's own agent instructions.
Second, .vibecode/history/README.md still says the architecture-change guard is a "future" feature, but it has been implemented since the prior repair.
Third, the --no-index help text in the CLI has a typo ("refres" instead of "refresh"). None of these are blockers for the pipeline itself, but they
introduce a meaningful documentation self-consistency failure and a real AGENTS degradation hazard.

The repository is safe for a narrow next implementation loop with explicit scope constraints, but is not clean enough for a fully autonomous loop
without first fixing the agents_export.py / AGENTS.md alignment gap.

-------------------------------------------------------------------------------------------------------------------------------------------------------

2. Test and Repo-State Results

┌───────────────────────────────────────────────────┬─────────────────────────┬────────────────────────────────────────────────────────────────────────┐
│ Command                                           │ Result                  │ Notes                                                                  │
├───────────────────────────────────────────────────┼─────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ git status --short                                │ Clean                   │ No uncommitted changes                                                 │
├───────────────────────────────────────────────────┼─────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ git diff --stat                                   │ Empty                   │ Nothing staged or unstaged                                             │
├───────────────────────────────────────────────────┼─────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ git log -20                                       │ 20 commits shown        │ Most recent: "Fix run safety pipeline and control-layer truth"         │
├───────────────────────────────────────────────────┼─────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ python -m json.tool PRD.json                      │ Valid JSON              │ 43 tasks, all well-formed                                              │
├───────────────────────────────────────────────────┼─────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ git ls-files .vibecode                            │ 19 files                │ Only committed human-maintained files                                  │
├───────────────────────────────────────────────────┼─────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ git ls-files .ralphy                              │ Empty                   │ Correctly untracked                                                    │
├───────────────────────────────────────────────────┼─────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ git ls-files ".vibecode/index/*.generated.*"      │ Empty                   │ Generated indexes not tracked ✓                                        │
├───────────────────────────────────────────────────┼─────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ git ls-files .vibecode/current                    │ Empty                   │ Runtime dirs not tracked ✓                                             │
│ .vibecode/generated .vibecode/logs .vibecode/runs │                         │                                                                        │
├───────────────────────────────────────────────────┼─────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ git check-ignore                                  │ Ignored via             │ ✓                                                                      │
│ .vibecode/current/context_pack.md                 │ .gitignore:49           │                                                                        │
├───────────────────────────────────────────────────┼─────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ git check-ignore                                  │ Ignored via             │ ✓                                                                      │
│ .vibecode/generated/AGENTS.generated.md           │ .gitignore:50           │                                                                        │
├───────────────────────────────────────────────────┼─────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ git check-ignore                                  │ Ignored via             │ ✓                                                                      │
│ .vibecode/index/repo_tree.generated.md            │ .gitignore:65           │                                                                        │
├───────────────────────────────────────────────────┼─────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ git check-ignore .vibecode/logs/...               │ Ignored via             │ ✓                                                                      │
│                                                   │ .gitignore:54           │                                                                        │
├───────────────────────────────────────────────────┼─────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ git check-ignore .vibecode/runs/...               │ Ignored via             │ ✓                                                                      │
│                                                   │ .gitignore:51           │                                                                        │
├───────────────────────────────────────────────────┼─────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ git check-ignore .ralphy/...                      │ Ignored via             │ ✓                                                                      │
│                                                   │ .gitignore:44           │                                                                        │
├───────────────────────────────────────────────────┼─────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ git check-ignore PRD.json                         │ Not ignored (exit 1)    │ ✓ — correctly tracked                                                  │
├───────────────────────────────────────────────────┼─────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ python -m pytest -p no:cacheprovider              │ 1158 passed, 4          │ 107.95s                                                                │
│                                                   │ warnings, 0 failures    │                                                                        │
├───────────────────────────────────────────────────┼─────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ vibecode --help                                   │ 13 commands listed      │ init, index, context, map, validate, guard, check, handoff-check, run, │
│                                                   │                         │ run-plan, history, project, export-agents                              │
├───────────────────────────────────────────────────┼─────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ vibecode init --help                              │ Present                 │ --id, --name, --force                                                  │
├───────────────────────────────────────────────────┼─────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ vibecode index --help                             │ Present                 │ Registry fallback                                                      │
├───────────────────────────────────────────────────┼─────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ vibecode map --help                               │ Present                 │ Registry fallback                                                      │
├───────────────────────────────────────────────────┼─────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ vibecode context --help                           │ Present                 │ --task, --repo, --platform                                             │
├───────────────────────────────────────────────────┼─────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ vibecode validate --help                          │ Present                 │ Registry fallback                                                      │
├───────────────────────────────────────────────────┼─────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ vibecode export-agents --help                     │ Present                 │ --force                                                                │
├───────────────────────────────────────────────────┼─────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ vibecode guard --help                             │ Present                 │ --strict                                                               │
├───────────────────────────────────────────────────┼─────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ vibecode check --help                             │ Present                 │ Registry fallback                                                      │
├───────────────────────────────────────────────────┼─────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ vibecode handoff-check --help                     │ Present                 │ --json                                                                 │
├───────────────────────────────────────────────────┼─────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ vibecode history --help                           │ Present                 │ history new subcommand                                                 │
├───────────────────────────────────────────────────┼─────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ vibecode run --help                               │ Present                 │ --task, --platform, --profile, --allow-dirty, --no-index               │
├───────────────────────────────────────────────────┼─────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ vibecode run-plan --help                          │ Present                 │ No registry fallback (intentional, defaults ".")                       │
├───────────────────────────────────────────────────┼─────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ vibecode project --help                           │ Present                 │ add, use, list, remove, current                                        │
└───────────────────────────────────────────────────┴─────────────────────────┴────────────────────────────────────────────────────────────────────────┘

-------------------------------------------------------------------------------------------------------------------------------------------------------

3. Actual Implementation Map

Architecture / Index

 - vibecode/indexer/scanner.py — git-based file collection with filesystem fallback
 - vibecode/indexer/classifier.py — language/role detection
 - vibecode/indexer/symbols.py, ts_symbols.py, symbol_map.py — Python AST + TS regex symbol extraction
 - vibecode/indexer/dependency_map.py — lightweight import edge map
 - vibecode/indexer/test_map.py — source↔test pairing
 - vibecode/indexer/risk_engine.py, risky_files.py — risk scoring
 - vibecode/indexer/repo_tree.py — compact tree rendering
 - vibecode/indexer/run_record.py — index run record writing
 - vibecode/indexer/__init__.py — cmd_index(), check_index_freshness()
 - vibecode/project.py — cmd_init(), cmd_map(), template preservation

Context / Scoring

 - vibecode/context/scoring.py — two-pass source/test pairing, phrase routing, hub-file suppression, dep-boost cap/threshold, low-value token filtering
 - vibecode/context/renderer.py — context pack assembly, protected path rendering, handoff/history section
 - vibecode/context/platform_export.py — OpenCode prompt file export
 - vibecode/context/platform_registry.py — platform lookup

AGENTS / Export

 - vibecode/context/agents_export.py — write_agents_export(), marker-safe update, cmd_export_agents()
 - Root AGENTS.md — manually extended beyond what render_agents_block() generates (gap)

Protected Paths

 - .vibecode/checks/protected_paths.yaml — committed policy file with 8 path rules
 - vibecode/config.py — load_config(), ProtectedPathRule, DEFAULT_PROTECTED_PATH_RULES
 - Context renderer surfaces protected paths in context packs

Guard

 - vibecode/guard.py — 5 rules: generated-runtime, protected-path, readme-manual-only, architecture-truth-record, source-test-balance
 - write_guard_result() → .vibecode/current/guard_result.json
 - CLI: vibecode guard [--strict]

Required Checks

 - .vibecode/checks/required_checks.yaml — 4 checks (unit tests, CLI help x3)
 - vibecode/check.py — run_checks(), write_check_results()
 - CLI: vibecode check

Handoff / History

 - vibecode/handoff.py — placeholder detection, architecture-change validation, validate_handoff_files(), CLI handoff-check [--json]
 - vibecode/history.py — create_summary(), validate_history_dir(), CLI history new; cmd_history_check() raises NotImplementedError (not wired to CLI)
 - .vibecode/history/README.md — committed policy with required sections

OpenCode Run

 - vibecode/run.py — full cmd_run() pipeline: git check → stale-index detection → context generation → profile validation → agent subprocess → 
post-agent delta git state → guard/check/handoff → diff summary → run summary JSON
 - vibecode/run_plan.py — build_run_plan(), cmd_run_plan()
 - vibecode/diff_summary.py — diff_summarise(), DiffSummary

Permission Profiles

 - vibecode/permissions.py — PROFILES dict (safe/fast/audit), write_profile(), profile_path()
 - Committed: .vibecode/agents/safe.json, fast.json, audit.json
 - Validated before launch in _validate_permission_profile()

Project Registry

 - vibecode/registry.py — ProjectRegistry, ProjectEntry, ~/.vibecode/projects.yaml
 - vibecode/project_cli.py — cmd_project() with add/use/list/remove/current
 - Registry fallback in _resolve_repo_root() for all relevant commands

CLI UX

 - vibecode/cli.py — single create_parser() + _dispatch(), 13 commands, --debug flag, _resolve_repo_root() with registry fallback

Docs / Handoff

 - docs/QUICKSTART.md — covers all 13 commands, two workflows (explicit + registry)
 - docs/ARCHITECTURE_MAP_PRD.md — scope boundary document
 - docs/ARCHITECTURE_MAP_STATUS.md — accurate current-status document
 - AGENTS.md — manually extended; better than what export-agents would generate
 - .vibecode/architecture/*.md — OVERVIEW, INVARIANTS, STRUCTURE, DATA_FLOW, MODULE_BOUNDARIES, PROTECTED_AREAS

Tests

 - 1,158 tests across ~40 test files
 - Coverage: scoring (37 tests), guard (2 files), agents export, context pack, check, handoff (2 files), history, run (2 files), stale index, e2e, full 
workflow, registry, project CLI, active-project fallback, diff summary, opencode adapter, run plan, run record, platform export/registry

-------------------------------------------------------------------------------------------------------------------------------------------------------

4. PRD Task-by-Task Audit

┌────┬─────────────────────┬───────────┬─────────────┬───────────────────────────────────────────────────────────────────────┬─────────────────────────┐
│ #  │ Task title          │ completed │ Audit       │ Evidence                                                              │ Gap / fix needed        │
│    │                     │ flag      │ status      │                                                                       │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 1  │ Harden              │ True      │ DONE        │ scoring.py pass-1/pass-2, 37 tests (labels A–Z6b)                     │ None                    │
│    │ relevant-file       │           │             │                                                                       │                         │
│    │ scoring with        │           │             │                                                                       │                         │
│    │ two-pass            │           │             │                                                                       │                         │
│    │ source/test pairing │           │             │                                                                       │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 2  │ Add compound phrase │ True      │ DONE        │ _PHRASE_ROUTES, _active_phrase_patterns(), tests O–V                  │ None                    │
│    │ routing for task    │           │             │                                                                       │                         │
│    │ domains             │           │             │                                                                       │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 3  │ Refine dependency   │ True      │ DONE        │ _DEP_FANOUT_CAP=5, _DEP_RECEIVE_THRESHOLD=4, hub-file suppression     │ None                    │
│    │ boost to avoid hub  │           │             │                                                                       │                         │
│    │ fan-out             │           │             │                                                                       │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 4  │ Add relevant-file   │ True      │ DONE        │ 37 parameterized tests, test_vibecode_relevant_files.py               │ None                    │
│    │ scoring quality     │           │             │                                                                       │                         │
│    │ smoke tests         │           │             │                                                                       │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 5  │ Add root AGENTS.md  │ True      │ DONE        │ AGENTS.md exists at root with marker blocks                           │ None                    │
│    │ with strict agent   │           │             │                                                                       │                         │
│    │ instructions        │           │             │                                                                       │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 6  │ Harden AGENTS       │ True      │ PARTIAL     │ Marker-safe update implemented, test for unmanaged files passes. BUT  │ Fix                     │
│    │ export workflow     │           │             │ render_agents_block() omits PRD.json, .vibecode/runs/*, and           │ render_agents_block()   │
│    │ safety              │           │             │ "Available commands" — running export-agents degrades committed       │ to match AGENTS.md      │
│    │                     │           │             │ AGENTS.md                                                             │ content                 │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 7  │ Include AGENTS      │ True      │ PARTIAL     │ QUICKSTART documents it; AGENTS.md documents it. BUT the generated    │ Same fix as Task 6      │
│    │ export workflow in  │           │             │ block agents_export.py would write loses the commands list            │                         │
│    │ context and docs    │           │             │                                                                       │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 8  │ Create protected    │ True      │ DONE        │ .vibecode/checks/protected_paths.yaml, ProtectedPathRule in config,   │ None                    │
│    │ paths policy file   │           │             │ tests                                                                 │                         │
│    │ and schema          │           │             │                                                                       │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 9  │ Expose protected    │ True      │ DONE        │ renderer.py renders protected path section, test coverage in          │ None                    │
│    │ paths in context    │           │             │ test_vibecode_context_pack.py                                         │                         │
│    │ pack                │           │             │                                                                       │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 10 │ Implement git diff  │ True      │ DONE        │ vibecode/git_state.py, inspect_git_state(), tests in                  │ None                    │
│    │ collection utility  │           │             │ test_vibecode_git_state.py                                            │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 11 │ Implement guard     │ True      │ DONE        │ check_generated_runtime_changes(), GENERATED_RUNTIME_RULE_ID, test    │ None                    │
│    │ rule for            │           │             │ coverage                                                              │                         │
│    │ generated/runtime   │           │             │                                                                       │                         │
│    │ edits               │           │             │                                                                       │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 12 │ Implement guard     │ True      │ DONE        │ check_protected_path_changes(), scope+required-test+handoff findings  │ None                    │
│    │ rule for protected  │           │             │                                                                       │                         │
│    │ paths               │           │             │                                                                       │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 13 │ Implement README    │ True      │ DONE        │ check_readme_changes(), README_RULE_ID, task-scope suppression        │ None                    │
│    │ generated-block     │           │             │                                                                       │                         │
│    │ guard               │           │             │                                                                       │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 14 │ Implement           │ True      │ DONE        │ check_architecture_truth_recorded(),                                  │ None                    │
│    │ architecture-change │           │             │ ARCHITECTURE_TRUTH_RECORD_RULE_ID                                     │                         │
│    │ handoff guard       │           │             │                                                                       │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 15 │ Implement           │ True      │ DONE        │ check_source_test_change_balance(), test-map suggestions, test-only   │ None                    │
│    │ source/test         │           │             │ task suppression                                                      │                         │
│    │ mismatch guard      │           │             │                                                                       │                         │
│    │ warnings            │           │             │                                                                       │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 16 │ Add guard CLI       │ True      │ DONE        │ vibecode guard [--strict], exit codes, test_vibecode_guard_cli.py     │ None                    │
│    │ command             │           │             │                                                                       │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 17 │ Add guard report    │ True      │ DONE        │ write_guard_result() → .vibecode/current/guard_result.json (ignored), │ None                    │
│    │ JSON output         │           │             │ schema versioned                                                      │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 18 │ Implement required  │ True      │ DONE        │ load_config() loads required_checks.yaml, test_vibecode_check.py      │ None                    │
│    │ checks schema       │           │             │ validates schema                                                      │                         │
│    │ validation          │           │             │                                                                       │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 19 │ Implement required  │ True      │ DONE        │ run_checks(), write_check_results(), cmd_check(), subprocess-based    │ None                    │
│    │ checks runner       │           │             │                                                                       │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 20 │ Add check command   │ True      │ DONE        │ QUICKSTART covers it, context pack includes required checks section   │ None                    │
│    │ docs and context    │           │             │                                                                       │                         │
│    │ integration         │           │             │                                                                       │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 21 │ Implement handoff   │ True      │ DONE        │ _detect_placeholders() in handoff.py, tests in                        │ None                    │
│    │ placeholder         │           │             │ test_vibecode_handoff.py                                              │                         │
│    │ detection           │           │             │                                                                       │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 22 │ Implement handoff   │ True      │ DONE        │ validate_handoff_files(diff=...) checks arch-doc changes against      │ None                    │
│    │ architecture-change │           │             │ handoff state                                                         │                         │
│    │ validation          │           │             │                                                                       │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 23 │ Add handoff-check   │ True      │ DONE        │ vibecode handoff-check [--json], writes to                            │ None                    │
│    │ CLI command         │           │             │ .vibecode/current/handoff_check.json                                  │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 24 │ Define history      │ True      │ DONE        │ .vibecode/history/README.md with 6 required sections, format,         │ None                    │
│    │ summary policy      │           │             │ ownership                                                             │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 25 │ Implement history   │ True      │ DONE        │ create_summary(), timestamped slugs, _next_summary_path(), tests      │ None                    │
│    │ summary template    │           │             │                                                                       │                         │
│    │ writer              │           │             │                                                                       │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 26 │ Integrate           │ True      │ DONE        │ Renderer adds handoff/history section, test_vibecode_context_pack.py  │ None                    │
│    │ handoff/history     │           │             │                                                                       │                         │
│    │ requirements into   │           │             │                                                                       │                         │
│    │ context pack        │           │             │                                                                       │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 27 │ Add OpenCode        │ True      │ DONE        │ vibecode/adapters/opencode.py, check_opencode(), version check,       │ None                    │
│    │ availability        │           │             │ compound command support                                              │                         │
│    │ detection           │           │             │                                                                       │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 28 │ Add OpenCode        │ True      │ DONE        │ vibecode/permissions.py, committed safe.json, fast.json, audit.json   │ None                    │
│    │ permission profile  │           │             │                                                                       │                         │
│    │ templates           │           │             │                                                                       │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 29 │ Build OpenCode      │ True      │ DONE        │ vibecode/run_plan.py, build_run_plan(), preflight warnings/errors,    │ None                    │
│    │ prompt/run plan     │           │             │ test_vibecode_run_plan.py                                             │                         │
│    │ assembly            │           │             │                                                                       │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 30 │ Implement OpenCode  │ True      │ DONE        │ _run_git_check(), _validate_permission_profile() in run.py,           │ None                    │
│    │ run preflight       │           │             │ stale-index check                                                     │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 31 │ Implement OpenCode  │ True      │ DONE        │ cmd_run(), fake opencode .cmd wrapper pattern, OPENCODE_COMMAND env   │ None                    │
│    │ run adapter with    │           │             │ override, test_vibecode_run.py                                        │                         │
│    │ fake runner tests   │           │             │                                                                       │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 32 │ Run post-OpenCode   │ True      │ DONE        │ _agent_delta_git_state() delta computation, _run_post_checks(),       │ None                    │
│    │ guard and check     │           │             │ test_run_guard_catches_readme_modified_by_agent                       │                         │
│    │ pipeline            │           │             │                                                                       │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 33 │ Add OpenCode run    │ True      │ DONE        │ vibecode/diff_summary.py, diff_summarise(),                           │ None                    │
│    │ diff summary        │           │             │ test_vibecode_diff_summary.py                                         │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 34 │ Document OpenCode   │ True      │ DONE        │ docs/QUICKSTART.md covers full workflow, two-workflow pattern,        │ None                    │
│    │ run workflow        │           │             │ non-goal disclaimer                                                   │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 35 │ Keep canonical CLI  │ True      │ DONE        │ 13 commands, no drift observed, all help texts consistent             │ Minor typo in           │
│    │ command set small   │           │             │                                                                       │ --no-index help         │
│    │ and consistent      │           │             │                                                                       │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 36 │ Implement project   │ True      │ DONE        │ vibecode/registry.py, ~/.vibecode/projects.yaml, VIBECODE_HOME        │ None                    │
│    │ registry storage    │           │             │ override for tests                                                    │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 37 │ Add project         │ True      │ DONE        │ vibecode project add/use/list/remove/current,                         │ None                    │
│    │ registry CLI        │           │             │ test_vibecode_project_cli.py                                          │                         │
│    │ commands            │           │             │                                                                       │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 38 │ Allow commands to   │ True      │ DONE        │ _resolve_repo_root() registry fallback in CLI,                        │ None                    │
│    │ use active project  │           │             │ test_vibecode_active_project_fallback.py                              │                         │
│    │ when repo is        │           │             │                                                                       │                         │
│    │ omitted             │           │             │                                                                       │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 39 │ Update docs for     │ True      │ DONE        │ QUICKSTART has "Registry workflow" section with project add/use       │ None                    │
│    │ project registry    │           │             │ examples                                                              │                         │
│    │ workflow            │           │             │                                                                       │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 40 │ Add end-to-end      │ True      │ DONE        │ test_vibecode_full_workflow.py                                        │ None                    │
│    │ smoke for           │           │             │ (init→index→context→export-agents→guard→check→handoff-check),         │                         │
│    │ controlled agent    │           │             │ test_vibecode_e2e.py                                                  │                         │
│    │ preparation         │           │             │                                                                       │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 41 │ Add stale index     │ True      │ DONE        │ check_index_freshness(), 5-minute age check + commit hash comparison, │ None                    │
│    │ detection           │           │             │ test_vibecode_stale_index.py                                          │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 42 │ Add context-pack    │ True      │ DONE        │ test_vibecode_context_pack.py quality regression, VibecodeApp's own   │ None                    │
│    │ quality regression  │           │             │ context used as regression fixture                                    │                         │
│    │ test                │           │             │                                                                       │                         │
├────┼─────────────────────┼───────────┼─────────────┼───────────────────────────────────────────────────────────────────────┼─────────────────────────┤
│ 43 │ Final control-layer │ False     │ NOT STARTED │ This is the task being performed now; no audit report file exists     │ Write this report       │
│    │ audit report        │           │             │                                                                       │                         │
└────┴─────────────────────┴───────────┴─────────────┴───────────────────────────────────────────────────────────────────────┴─────────────────────────┘

-------------------------------------------------------------------------------------------------------------------------------------------------------

5. Non-DONE Task Detail

Task 6 — Harden AGENTS export workflow safety

Status: PARTIAL

Problem: vibecode/context/agents_export.py's render_agents_block() generates content materially weaker than the committed AGENTS.md. The committed file
contains three things the generated block does not:

 1. PRD.json in the "Source of truth" list
 2. .vibecode/runs/* in the "Do not manually edit" list
 3. An entire "Available commands" section listing all 13 CLI commands

Because the entire AGENTS.md is wrapped inside the vibecode marker blocks, running vibecode export-agents . (without --force) will detect the markers,
call _update_marker_block(), and replace the block contents with the weaker render_agents_block() output — silently degrading agent orientation.

Evidence:

 - vibecode/context/agents_export.py:14-42 — render_agents_block() generates ~16 lines
 - AGENTS.md:1-45 — committed file has ~45 lines including PRD.json, runs/*, and full commands list
 - agents_export.py search for PRD.json returns no matches

Step-by-step fix:

 1. Update render_agents_block() in vibecode/context/agents_export.py to include:
  - PRD.json in the "Source of truth" sentence alongside tests
  - .vibecode/runs/* in the "Do not manually edit" list
  - The "## Available commands" section with all 13 commands
 2. Update vibecode/context/agents_export.py to keep the generated block in sync with the committed AGENTS.md content
 3. Run vibecode export-agents .  and confirm the diff between before and after is empty (idempotent)
 4. Update test_vibecode_agents_export.py to assert the generated block contains PRD.json, runs/*, and at least one command entry

Acceptance criteria:

 - vibecode export-agents . produces no diff to AGENTS.md (idempotent)
 - render_agents_block() output contains PRD.json, .vibecode/runs/*, and ## Available commands section
 - Tests assert specific required strings in the generated block

Verification:

 python -m vibecode.cli export-agents .
 git diff AGENTS.md  # should be empty
 python -m pytest tests/test_vibecode_agents_export.py -v

-------------------------------------------------------------------------------------------------------------------------------------------------------

Task 7 — Include AGENTS export workflow in context and docs

Status: PARTIAL (same root cause as Task 6)

Problem: The documentation commitment in AGENTS.md is stronger than what export-agents generates. This makes the export workflow unsafe — it would
silently remove agent-facing documentation about available commands.

Evidence: Same as Task 6.

Step-by-step fix: Same as Task 6 (the fix to render_agents_block() resolves both tasks).

Acceptance criteria: After fix, the "Available commands" section appears in generated agent block.

Verification: Same as Task 6.

-------------------------------------------------------------------------------------------------------------------------------------------------------

Task 43 — Final control-layer audit report

Status: NOT STARTED (intentionally — this IS the report)

Problem: The PRD describes this as an audit report to be produced after implementing tasks 1-42. This document IS that report.

Step-by-step fix:

 1. This audit report constitutes the deliverable for Task
  43.
 2. After review, mark Task 43 completed: true in PRD.json.

Acceptance criteria:

 - PRD.json task 43 marked completed: true
 - Report covers every PRD task with status, evidence, and gaps

-------------------------------------------------------------------------------------------------------------------------------------------------------

6. Repo Hygiene Findings

Critical

(None found)

High

(None found)

Medium

Problem: render_agents_block() in agents_export.py is out of sync with committed AGENTS.md Evidence: agents_export.py:14-42; AGENTS.md:1-45; running 
export-agents would silently downgrade AGENTS.md Why it matters: Any autonomous loop that refreshes AGENTS.md will strip agent-facing PRD.json reference
and all command documentation Fix: Update render_agents_block() to match AGENTS.md content; add idempotency test

Low

Problem: --no-index help text has a typo: "Skip automatic index generation/refres." Evidence: vibecode/cli.py:172 — "refres" missing the trailing 'h' 
Why it matters: Minor UX polish issue; does not affect behavior Fix: Change "refres" to "refresh" in cli.py:172

Problem: cmd_history_check() in history.py raises NotImplementedError but is never reachable via CLI Evidence: vibecode/history.py:322-325 — comment
says "Not yet wired into CLI — reserved for future use" Why it matters: Dead code that would fail loudly if ever called; confusing for future
contributors Fix: Either remove the function or wire it to a history check subcommand

Problem: run.py uses shell=True in subprocess.run for the OpenCode command Evidence: vibecode/run.py:500 Why it matters: shell=True with an
externally-configurable command introduces command-injection surface if OPENCODE_COMMAND contains shell metacharacters Fix: Parse the command into a
list using shlex.split() and use shell=False; test compound commands still work

-------------------------------------------------------------------------------------------------------------------------------------------------------

7. Documentation Hygiene Findings

Critical

(None found)

High

(None found)

Medium

Problem: .vibecode/history/README.md says the guard/check workflow for architecture changes is a "future" feature Evidence: history/README.md:57 — "The
guard/check workflow (future) will validate that .vibecode/architecture/*.md changes are accompanied by a corresponding history entry." Why it matters: 
check_architecture_truth_recorded() in guard.py already implements this. The stale doc may mislead future implementers into re-implementing or skipping
it. Fix: Update the sentence to: "The vibecode guard command validates that .vibecode/architecture/*.md changes are accompanied by a corresponding
history or handoff entry."

Low

Problem: STRUCTURE.md lists test files but is missing newer test files added since the last architecture update Evidence: 
.vibecode/architecture/STRUCTURE.md:14-26 — omits test_vibecode_stale_index.py, test_vibecode_full_workflow.py, test_vibecode_run.py, 
test_vibecode_run_post.py, and others Why it matters: Architecture doc is a source of truth; incomplete test listing could cause an agent to miss
important test coverage Fix: Add the missing test file entries to STRUCTURE.md

Problem: AGENTS.md "Available commands" section omits run-plan and history commands Evidence: AGENTS.md:34-44 — lists 10 of 13 CLI commands; run-plan
and history are absent Why it matters: Agents using AGENTS.md as sole reference won't know these commands exist Fix: Add run-plan and history new to the
"Available commands" list in AGENTS.md (and keep render_agents_block() in sync)

Problem: docs/ARCHITECTURE_MAP_PRD.md still states "OpenCode run adapter: Launching or orchestrating OpenCode is a later phase" in the Non-goals table 
Evidence: docs/ARCHITECTURE_MAP_PRD.md:37 — "OpenCode run adapter | A separate integration layer; depends on the index being stable" Why it matters:
This was the PRD for the Architecture Map Core phase, which is now complete; the run adapter IS implemented. Any agent reading this PRD phase doc gets a
false "not yet done" signal. Fix: Add a note at the top of docs/ARCHITECTURE_MAP_PRD.md that this is the Phase 1 (Architecture Map Core) PRD, now
superseded by the full PRD.json which covers all completed phases.

-------------------------------------------------------------------------------------------------------------------------------------------------------

8. Control-Layer Safety Findings

Post-run guard/check/handoff

Status: Correct. _agent_delta_git_state() correctly computes the per-agent delta by subtracting the pre-agent git state from the post-run state. The
test test_run_guard_catches_readme_modified_by_agent verifies that a fake OpenCode script that modifies README.md causes guard["passed"] == False with 
rule_id == "readme-manual-only". The test test_run_summary_reports_guard_failure verifies generated-runtime file edits cause overall_status == "failure"
.

Protected path enforcement

Status: Correct. The _validate_permission_profile() function validates the profile file exists and is valid JSON before launch. The guard rules evaluate
post-agent changes against protected paths. Permission profiles themselves (the allows/denies fields) are declarative metadata only — they do not
mechanically constrain the subprocess. This is inherent in the design (OpenCode enforces its own constraints using its own tool-permission system).

Permission profiles

Status: Correct. All three profile files (safe.json, fast.json, audit.json) are committed under .vibecode/agents/ and match the PROFILES constant in 
permissions.py. _validate_permission_profile() checks existence + valid JSON before any launch. Run plan assembly also includes the profile name in the
plan output.

Generated/runtime tracking

Status: Clean. All .vibecode/current/*, .vibecode/generated/*, .vibecode/logs/*, .vibecode/runs/*, .vibecode/index/*.generated.*, .ralphy/* are
correctly gitignored and absent from git ls-files. No runtime files are tracked.

Stale index/context detection

Status: Correct. check_index_freshness() checks: (a) whether last_index.json exists, (b) whether it is older than 5 minutes (configurable), (c) whether
the recorded git commit matches HEAD. vibecode run auto-refreshes the index if stale before generating context.

Registry resolution

Status: Correct. _resolve_repo_root() prioritizes explicit CLI arg over registry active project. reg.pick(None) raises FileNotFoundError with a clear
message when no active project is set. Missing paths are detected at pick time.

External process safety

Concern (Low). subprocess.run(command, ..., shell=True) on line 500 of run.py uses shell invocation. The command string comes from shutil.which()
resolution or the OPENCODE_COMMAND environment variable. If that env variable contains shell metacharacters, code injection is possible. This is low
risk in practice (user-controlled env var on their own machine) but violates least-privilege design. Recommend switching to shlex.split() + shell=False.

-------------------------------------------------------------------------------------------------------------------------------------------------------

9. Agent-Readiness Verdict

SAFE FOR NEXT NARROW IMPLEMENTATION TASK ONLY

The full pipeline is implemented and all 1,158 tests pass. The repository is not in an unsafe or broken state. However, the render_agents_block() / 
AGENTS.md misalignment means an autonomous loop that runs export-agents as part of its workflow will silently degrade the project's own agent-facing
documentation. This is a self-referential safety failure: VibecodeApp's own control layer would corrupt its own AGENTS.md. Until that is fixed, the next
implementation task should be scoped narrowly to the exact fix, not a broad autonomous loop.

-------------------------------------------------------------------------------------------------------------------------------------------------------

10. Ordered Repair Plan

A. Must fix before more implementation

1. Fix render_agents_block() to match committed AGENTS.md

 - Files: vibecode/context/agents_export.py, tests/test_vibecode_agents_export.py
 - Action: Add PRD.json to source-of-truth sentence; add .vibecode/runs/* to "do not edit" list; add "## Available commands" section with all 13 
commands (including run-plan and history new); also add these to AGENTS.md itself
 - What not to touch: vibecode/guard.py, vibecode/run.py, scoring, test fixtures
 - Acceptance: vibecode export-agents . produces no diff; test_vibecode_agents_export.py asserts the new content
 - Verification: git diff AGENTS.md is empty after running export-agents; python -m pytest tests/test_vibecode_agents_export.py -v

2. Mark PRD task 43 completed: true

 - Files: PRD.json
 - Action: Set "completed": true for task 43
 - What not to touch: All other task entries, task content
 - Acceptance: python -m json.tool PRD.json is valid; all tasks show completed: true
 - Verification: python -c "import json; d=json.load(open('PRD.json')); print(all(t['completed'] for t in d['tasks']))"

B. Should fix soon

3. Fix stale "future" in .vibecode/history/README.md

 - Files: .vibecode/history/README.md
 - Action: Replace "The guard/check workflow (future) will validate..." with "The vibecode guard command validates..."
 - What not to touch: Required sections list, format example, ownership section
 - Acceptance: No "future" wording about guard; doc correctly describes implemented behavior

4. Fix --no-index typo in CLI

 - Files: vibecode/cli.py:172
 - Action: Change "refres" to "refresh"
 - What not to touch: All other CLI help text
 - Acceptance: python -m vibecode.cli run --help shows "refresh" not "refres"

5. Fix shell=True in run.py subprocess call

 - Files: vibecode/run.py:494-502
 - Action: Replace subprocess.run(command, ..., shell=True) with shlex.split(command) + shell=False; ensure compound commands (e.g. python wrapper.py) 
still work; update tests that use .cmd wrapper
 - What not to touch: Pre/post logic, git state capture, post-run checks
 - Acceptance: All test_vibecode_run.py and test_vibecode_run_post.py tests pass; no shell injection surface

C. Can defer

6. Add missing test files to STRUCTURE.md

 - Files: .vibecode/architecture/STRUCTURE.md
 - Action: Add entries for test_vibecode_stale_index.py, test_vibecode_full_workflow.py, test_vibecode_run.py, test_vibecode_run_post.py, 
test_vibecode_diff_summary.py, test_vibecode_registry.py, test_vibecode_project_cli.py, test_vibecode_active_project_fallback.py

7. Add note to docs/ARCHITECTURE_MAP_PRD.md

 - Files: docs/ARCHITECTURE_MAP_PRD.md
 - Action: Add a header note: "This document describes the Phase 1 Architecture Map Core PRD. The run adapter, guard, check, handoff, history, project 
registry, and OpenCode integration are implemented and documented in PRD.json."

8. Remove or wire cmd_history_check()

 - Files: vibecode/history.py:322-325
 - Action: Either remove the dead function or implement vibecode history check subcommand

-------------------------------------------------------------------------------------------------------------------------------------------------------

11. Recommended Next Single Task

Fix render_agents_block() to match the committed AGENTS.md content.

This is the highest-priority narrowly-scoped fix. It eliminates the risk of autonomous loops degrading the project's own agent instructions, closes the
PARTIAL gaps on Tasks 6 and 7, and is low-risk (no behavioral changes to any command except the content of the generated block). It requires changes to
exactly two files: vibecode/context/agents_export.py and tests/test_vibecode_agents_export.py. Verification is a one-line git check: git diff AGENTS.md
after running export-agents must be empty.

-------------------------------------------------------------------------------------------------------------------------------------------------------

12. Final Judgment

The VibecodeApp control layer is substantially complete and its pipeline is genuinely functional: 1,158 tests pass, every PRD command exists and behaves
as specified, generated/runtime files are correctly ignored, the post-run guard correctly evaluates only agent-introduced delta (verified by explicit
fake-OpenCode README.md modification test), and permission profiles are committed and validated before launch. The repository is not broken and is not
unsafe in any hard sense. The one genuine failure is that VibecodeApp's own export-agents command would degrade VibecodeApp's own AGENTS.md — silently
stripping PRD.json from agent source-of-truth instructions, removing .vibecode/runs/* from the "do not edit" list, and deleting the entire "Available
commands" section — because render_agents_block() was never updated to reflect the manually-extended AGENTS.md content. This is a self-referential
control-layer failure: the tool that manages agent instructions cannot safely regenerate its own. Fix that first, then this repository earns a clean
bill of health for autonomous implementation loops.