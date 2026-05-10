VibecodeApp PRD Task Gap Audit
1. Executive verdict
Not all PRD tasks are truly done. The repository is in much better shape than a broken control layer: the full test suite passes, the requested CLI surfaces exist, PRD.json is tracked, generated/runtime paths are ignored, and the repaired vibecode run path now evaluates post-agent changes. The main implementation gap is not broad missing functionality; it is safety completeness around custom protected-path policy enforcement in vibecode run, generated/runtime ignore verification in run preflight, advisory-only permission profiles, and coarse stale-index detection. Documentation is the weakest area: docs/ARCHITECTURE_MAP_PRD.md still says OpenCode launch/run adapter is out of scope even though vibecode run exists. History docs also still call guard/check workflow “future.” The repo is not safe for a broad autonomous implementation loop without prompt constraints, but it is safe for a narrow repair task. The completed flags are mostly directionally true for implementation existence, but several are too optimistic under strict audit criteria.
2. Test and repo-state results
Command	Result	Notes
git status --short	Dirty	Initial: D VibecodeApp_plan_dalsich_kroku.md, ?? ring_PRD_audit.md, ?? sonnet_PRD_audit.md. Later also ?? gpt_PRD_audit.md appeared; I did not create it.
git diff --stat	Dirty	One tracked deletion: VibecodeApp_plan_dalsich_kroku.md, 765 deletions.
git diff --name-only	Dirty	VibecodeApp_plan_dalsich_kroku.md.
git log --oneline -n 20	OK	Latest commit: bd8caa5 Fix run safety pipeline and control-layer truth.
python -m json.tool PRD.json	OK	Valid JSON; 43 tasks.
git ls-files	OK	PRD.json tracked; source/tests/docs/policy files tracked.
git ls-files .vibecode	OK	Human-maintained .vibecode docs, checks, agents, schema, project config tracked.
git ls-files .ralphy	OK	No tracked .ralphy files.
git ls-files ".vibecode/index/*.generated.*"	OK	No tracked generated index files.
git ls-files .vibecode/current .vibecode/generated .vibecode/logs .vibecode/runs .ralphy	OK	No tracked runtime/generated output paths.
git check-ignore -v .vibecode/current/context_pack.md	OK	Ignored by .gitignore:49.
git check-ignore -v .vibecode/generated/AGENTS.generated.md	OK	Ignored by .gitignore:50.
git check-ignore -v .vibecode/index/repo_tree.generated.md	OK	Ignored by .gitignore:65.
git check-ignore -v .vibecode/logs/index_runs/example.json	OK	Ignored by .gitignore:54.
git check-ignore -v .vibecode/runs/example/summary.json	OK	Ignored by .gitignore:51.
git check-ignore -v .ralphy/progress.txt	OK	Ignored by .gitignore:44.
git check-ignore -v PRD.json	OK	Not ignored.
python -m pytest -p no:cacheprovider	PASS	1158 passed, 4 warnings, 102.60s.
python -m vibecode.cli --help	PASS	Root help lists all expected commands plus run-plan and history.
python -m vibecode.cli init --help	PASS	Exists.
python -m vibecode.cli index --help	PASS	Exists.
python -m vibecode.cli map --help	PASS	Exists.
python -m vibecode.cli context --help	PASS	Exists.
python -m vibecode.cli validate --help	PASS	Exists.
python -m vibecode.cli export-agents --help	PASS	Exists.
python -m vibecode.cli guard --help	PASS	Exists.
python -m vibecode.cli check --help	PASS	Exists.
python -m vibecode.cli handoff-check --help	PASS	Exists.
python -m vibecode.cli history --help	PASS	Exists.
python -m vibecode.cli run --help	PASS	Exists; help typo says generation/refres.
python -m vibecode.cli run-plan --help	PASS	Exists.
python -m vibecode.cli project --help	PASS	Exists.
Optional smoke test	Not run	Not necessary; full suite includes temp-repo workflow and fake OpenCode tests.
3. Actual implementation map
Subsystem	Actual state
Architecture/index	Implemented. vibecode/indexer/__init__.py writes inventory, symbols, dependencies, tests, entrypoints, risk, repo tree, validation, and run records. Generated outputs are ignored.
Context/scoring	Strong implementation. Two-pass test pairing, phrase routing, hub suppression, dependency fan-out caps, protected path rendering, handoff/history rendering, and quality regression tests exist.
AGENTS/export	Root AGENTS.md exists and export safety exists. Gap: generated AGENTS block is less complete than committed root AGENTS.md, so export-agents can downgrade a managed root block.
Protected paths	Policy/schema/loader exist. CLI guard loads project policy. Gap: post-run vibecode run uses evaluate_guard() defaults and does not include custom protected_paths.yaml records.
Guard	Implemented for generated/runtime edits, protected paths, README, architecture truth recording, source/test mismatch, CLI, and JSON report.
Required checks	Schema validation and runner exist. Gap: runner uses shell=True on repo-defined commands, which is flexible but not hardened for untrusted configs.
Handoff/history	Handoff validation and CLI exist. History policy/template writer exists. Gaps: blocker wording is not semantically enforced, history templates can contain _Not yet filled._, and history docs still call guard/check future.
OpenCode run	Implemented with fake-runner tests. It generates/refreshes index, writes context/prompt, invokes external command, evaluates post-agent diff, runs guard/check/handoff, and writes run summaries.
Permission profiles	Profiles are committed and selected profile JSON is validated before launch. Gap: Vibecode does not pass or translate permissions into OpenCode enforcement; profiles are mostly advisory unless OpenCode separately consumes them.
Project registry	Implemented with local machine registry, CLI, active project fallback for core commands, Windows path tests, and non-overwriting duplicate behavior at CLI level.
CLI UX	All requested command help surfaces exist. Gaps: run-plan intentionally does not use registry fallback, AGENTS command list omits run-plan and history, and run --no-index help has a typo.
Docs/handoff	Mostly current in README/Quickstart/status. Significant stale contradictions remain in docs/ARCHITECTURE_MAP_PRD.md, .vibecode/history/README.md, and some generated/runtime doctrine wording.
Tests	Strong. 1158 passed. Fake OpenCode post-run README/protected behavior is covered in tests/test_vibecode_run_post.py.
4. PRD task-by-task audit
#	Task title	completed flag	Audit status	Evidence
1	Harden relevant-file scoring with two-pass source/test pairing	true	DONE	scoring.py:380-400; tests/test_vibecode_relevant_files.py pairing tests.
2	Add compound phrase routing for task domains	true	DONE	scoring.py:190-228, 319-326; tests cover context/repo/OpenCode/AGENTS/check/guard routes.
3	Refine dependency boost to avoid hub fan-out	true	DONE	scoring.py:142-188, 402-432; tests cover hub suppression.
4	Add relevant-file scoring quality smoke tests	true	DONE	tests/test_vibecode_relevant_files.py scenario tests; context quality test exists.
5	Add root AGENTS.md with strict agent instructions	true	DONE	AGENTS.md:1-45.
6	Harden AGENTS export workflow safety	true	PARTIAL	agents_export.py:64-115; tests cover manual/managed/force.
7	Include AGENTS export workflow in context and docs	true	PARTIAL	README.md:192-201; docs/QUICKSTART.md:381-393.
8	Create protected paths policy file and schema	true	DONE	.vibecode/checks/protected_paths.yaml:4-42; config.py:218-278.
9	Expose protected paths in context pack	true	DONE	renderer.py:293-318; context tests cover protected section.
10	Implement git diff collection utility	true	DONE	git_state.py:91-157; tests cover temp git states.
11	Implement guard rule for generated/runtime edits	true	DONE	guard.py:306-338, 479-485; guard tests.
12	Implement guard rule for protected paths	true	PARTIAL	guard.py:269-303, 711-723; config loader exists.
13	Implement README generated-block guard	true	DONE	guard.py:341-380; run-post test catches fake OpenCode editing README.md.
14	Implement architecture-change handoff guard	true	DONE	guard.py:383-424; handoff.py:138-163.
15	Implement source/test mismatch guard warnings	true	DONE	guard.py:187-266; guard tests.
16	Add guard CLI command	true	DONE	cli.py:91-106, guard.py:668-763.
17	Add guard report JSON output	true	DONE	guard.py:171-184, 725-729; tests validate JSON.
18	Implement required checks schema validation	true	DONE	config.py:287-337; .vibecode/checks/required_checks.yaml:4-19.
19	Implement required checks runner	true	PARTIAL	check.py:95-149, 160-175; tests exist.
20	Add check command docs and context integration	true	DONE	README.md:82-86; renderer.py:263-290; Quickstart check docs.
21	Implement handoff placeholder detection	true	PARTIAL	handoff.py:43-83, 165-195.
22	Implement handoff architecture-change validation	true	DONE	handoff.py:138-163; tests exist.
23	Add handoff-check CLI command	true	DONE	cli.py:119-135; handoff.py:211-244.
24	Define history summary policy	true	PARTIAL	.vibecode/history/README.md:3-24.
25	Implement history summary template writer	true	PARTIAL	history.py:206-286; tests exist.
26	Integrate handoff/history requirements into context pack	true	DONE	renderer.py:360-378.
27	Add OpenCode availability detection	true	DONE	opencode.py:36-118; tests mock availability.
28	Add OpenCode permission profile templates	true	PARTIAL	.vibecode/agents/*.json; run.py:215-232; project.py:260-266.
29	Build OpenCode prompt/run plan assembly	true	PARTIAL	run_plan.py:51-287, 347-394; tests exist.
30	Implement OpenCode run preflight	true	PARTIAL	run.py:342-472; run_plan.py:84-248.
31	Implement OpenCode run adapter with fake runner tests	true	DONE	run.py:477-515; tests/test_vibecode_run.py; tests/test_vibecode_run_post.py.
32	Run post-OpenCode guard and check pipeline	true	PARTIAL	run.py:273-320, 533-543; post-agent tests pass.
33	Add OpenCode run diff summary	true	DONE	diff_summary.py; run.py:548-612; diff summary tests.
34	Document OpenCode run workflow	true	FLAGGED WRONG	README.md:7; docs/QUICKSTART.md:323-340; but docs/ARCHITECTURE_MAP_PRD.md:24, 37, 93 contradict this.
35	Keep canonical CLI command set small and consistent	true	PARTIAL	cli.py:23-306; CLI help all exists.
36	Implement project registry storage	true	DONE	registry.py:28-257; tests use temp registry/home.
37	Add project registry CLI commands	true	DONE	project_cli.py:16-111; duplicate add fails clearly.
38	Allow commands to use active project when repo is omitted	true	DONE	cli.py:309-342, 392-436; context fallback tests.
39	Update docs for project registry workflow	true	PARTIAL	README.md:130-177; docs/QUICKSTART.md:98-136.
40	Add end-to-end smoke for controlled agent preparation	true	DONE	tests/test_vibecode_full_workflow.py.
41	Add stale index detection	true	PARTIAL	indexer/__init__.py:60-109; run_plan.py:143-200; run.py:375-410.
42	Add context-pack quality regression test	true	DONE	tests/test_vibecode_context_pack.py:591-729.
43	Final control-layer audit report	false	DONE	This read-only audit report; tests passed.
5. Non-DONE task detail
Task 6 — Harden AGENTS export workflow safety
- Status: PARTIAL
- Problem: export-agents is safe against overwriting unmanaged manual AGENTS.md, but can downgrade this repo’s Vibecode-managed root block because render_agents_block() is less complete than committed AGENTS.md.
- Evidence: agents_export.py:14-42 omits PRD.json, .vibecode/agents/, .vibecode/runs/*, run-plan, and history; AGENTS.md:13-44 contains richer guidance.
- Step-by-step fix:
  1. Update vibecode/context/agents_export.py so generated block matches current root AGENTS.md doctrine.
  2. Add a regression test that exports over the committed-style managed block and verifies no loss of key lines.
  3. Run python -m pytest tests/test_vibecode_agents_export.py -p no:cacheprovider.
- Acceptance criteria: Exported managed block preserves all current source-truth/runtime/command guidance.
- Verification: python -m pytest tests/test_vibecode_agents_export.py -p no:cacheprovider.
Task 7 — Include AGENTS export workflow in context and docs
- Status: PARTIAL
- Problem: README/Quickstart explain lifecycle, but context/agent-facing guidance is incomplete and tied to a stale generated AGENTS block.
- Evidence: README.md:192-201; docs/QUICKSTART.md:381-393; agents_export.py:14-42.
- Step-by-step fix:
  1. Fix generated AGENTS block first.
  2. Add concise context-pack guidance that root AGENTS.md is stable and .vibecode/current/context_pack.md is per-task runtime.
  3. Add or adjust renderer tests for that guidance.
- Acceptance criteria: Agent-facing output consistently explains root AGENTS, current context pack, generated AGENTS output, and force behavior.
- Verification: python -m pytest tests/test_vibecode_context_pack.py tests/test_vibecode_agents_export.py -p no:cacheprovider.
Task 12 — Implement guard rule for protected paths
- Status: PARTIAL
- Problem: CLI guard applies project policy, but post-run vibecode run uses evaluate_guard() with only DEFAULT_PROTECTED_PATH_RULES.
- Evidence: evaluate_guard() uses defaults at guard.py:138-143; CLI adds project records at guard.py:711-723; run post-check calls only evaluate_guard() at run.py:291-294.
- Step-by-step fix:
  1. Add an optional protected_rules parameter to evaluate_guard() or create a shared helper that loads project policy.
  2. Use the loaded .vibecode/checks/protected_paths.yaml policy in _run_post_checks().
  3. Add a fake OpenCode test where a custom protected path is modified and post-run guard fails.
- Acceptance criteria: vibecode run and vibecode guard enforce the same project protected-path policy.
- Verification: python -m pytest tests/test_vibecode_guard.py tests/test_vibecode_run_post.py -p no:cacheprovider.
Task 19 — Implement required checks runner
- Status: PARTIAL
- Problem: The runner executes repo-defined command strings with shell=True.
- Evidence: check.py:95-105.
- Step-by-step fix:
  1. Decide whether required checks are trusted local shell commands or must be parsed/allowlisted.
  2. If hardening is desired, add explicit docs warning and/or support list-form commands.
  3. Add tests for shell metacharacter handling and timeout behavior.
- Acceptance criteria: Safety model is explicit and tested; untrusted config risk is documented or mitigated.
- Verification: python -m pytest tests/test_vibecode_check.py tests/test_vibecode_config.py -p no:cacheprovider.
Task 21 — Implement handoff placeholder detection
- Status: PARTIAL
- Problem: Placeholder and heading-only detection exists, but BLOCKERS.md semantic rule is not enforced.
- Evidence: Requirement is in handoff.py:115-119; implementation only checks placeholders/empty bullets/headings at handoff.py:165-195.
- Step-by-step fix:
  1. Add blocker-specific validation for “no blocker” wording or concrete blocker bullets.
  2. Reject arbitrary non-placeholder filler in BLOCKERS.md.
  3. Add tests for valid no-blocker, valid blocker list, and invalid vague text.
- Acceptance criteria: BLOCKERS.md cannot pass with meaningless non-placeholder body text.
- Verification: python -m pytest tests/test_vibecode_handoff.py tests/test_vibecode_handoff_cli.py -p no:cacheprovider.
Task 24 — Define history summary policy
- Status: PARTIAL
- Problem: Policy exists, but still says guard/check workflow is future.
- Evidence: .vibecode/history/README.md:57-59.
- Step-by-step fix:
  1. Update history README ownership text to say guard/handoff validation exists.
  2. Keep policy short and avoid raw log language.
  3. Add a docs regression if existing docs tests cover stale wording.
- Acceptance criteria: History policy no longer contradicts implemented guard/check/handoff behavior.
- Verification: python -m pytest tests/test_vibecode_history.py -p no:cacheprovider.
Task 25 — Implement history summary template writer
- Status: PARTIAL
- Problem: history new writes _Not yet filled._ for missing content, and validator does not reject it.
- Evidence: history.py:280-285; placeholder validator only checks TODO/TBD/PLACEHOLDER/comments at history.py:70-76.
- Step-by-step fix:
  1. Treat _Not yet filled._ as placeholder text.
  2. Require substantive body content before a summary passes validation, or document that history new creates drafts only.
  3. Add tests for empty generated summaries failing validation.
- Acceptance criteria: Empty generated summaries are not considered durable truth.
- Verification: python -m pytest tests/test_vibecode_history.py -p no:cacheprovider.
Task 28 — Add OpenCode permission profile templates
- Status: PARTIAL
- Problem: Profiles are committed and validated before launch, but Vibecode does not enforce them against the OpenCode process.
- Evidence: Profiles at .vibecode/agents/*.json; validation at run.py:215-232; command invocation at run.py:493-502 does not pass profile data.
- Step-by-step fix:
  1. Define whether profiles are advisory or must be translated into OpenCode flags/config.
  2. If enforceable, pass the selected profile to OpenCode in the supported way.
  3. Add fake OpenCode tests asserting profile-specific command/config is supplied.
- Acceptance criteria: “Permission profile enforced before launch” has concrete behavior, not only JSON existence validation.
- Verification: python -m pytest tests/test_vibecode_run.py tests/test_vibecode_opencode_adapter.py -p no:cacheprovider.
Task 29 — Build OpenCode prompt/run plan assembly
- Status: PARTIAL
- Problem: Implementation is present, but docs say run-plan checks preconditions “without making changes” while it writes .vibecode/current/run_plan.json.
- Evidence: run_plan.py:367-392; docs/QUICKSTART.md:312-320.
- Step-by-step fix:
  1. Reword docs to “without launching an agent or editing source.”
  2. Confirm run-plan output path is documented as generated/runtime.
  3. Add docs test if appropriate.
- Acceptance criteria: Docs match run-plan write behavior.
- Verification: python -m pytest tests/test_vibecode_run_plan.py tests/test_vibecode_quickstart.py -p no:cacheprovider.
Task 30 — Implement OpenCode run preflight
- Status: PARTIAL
- Problem: Preflight does not explicitly verify generated/runtime ignore rules, and stale-index detection is coarse.
- Evidence: run.py:342-472; run_plan.py:84-248; stale checks use age/root/commit in run_plan.py:143-200 and run.py:375-410.
- Step-by-step fix:
  1. Add an ignore-rule preflight check for .vibecode/current, .vibecode/generated, .vibecode/runs, .vibecode/logs, .vibecode/tmp, .vibecode/cache, and generated index outputs.
  2. Add tests where ignore rules are missing and preflight fails or warns.
  3. Extend stale detection to compare indexed path state where feasible.
- Acceptance criteria: run refuses or clearly warns when generated/runtime output would become tracked or unignored.
- Verification: python -m pytest tests/test_vibecode_run.py tests/test_vibecode_run_plan.py tests/test_vibecode_stale_index.py -p no:cacheprovider.
Task 32 — Run post-OpenCode guard and check pipeline
- Status: PARTIAL
- Problem: Post-run pipeline evaluates post-agent changes, but it does not enforce custom protected path records.
- Evidence: Post-agent baseline/delta exists at run.py:481-543; policy gap is run.py:291-294.
- Step-by-step fix:
  1. Share the same loaded-policy guard evaluation between guard CLI and run post-check.
  2. Add fake OpenCode test for custom protected path modification.
  3. Verify summary JSON records the custom policy failure.
- Acceptance criteria: Post-run guard/check/handoff behavior matches standalone commands.
- Verification: python -m pytest tests/test_vibecode_run_post.py tests/test_vibecode_guard_cli.py -p no:cacheprovider.
Task 34 — Document OpenCode run workflow
- Status: FLAGGED WRONG
- Problem: Docs directly contradict implemented vibecode run.
- Evidence: docs/ARCHITECTURE_MAP_PRD.md:24 says capability ends at prompt export; :37 says OpenCode run adapter is out of scope; :93 says no CLI command launches OpenCode. Current docs and code say otherwise: README.md:7, docs/QUICKSTART.md:323-340, run.py:1-11.
- Step-by-step fix:
  1. Rewrite docs/ARCHITECTURE_MAP_PRD.md as historical/core-boundary context or update it to include current run orchestration.
  2. Remove “no command launches OpenCode” claims.
  3. Keep non-goals: no custom coding agent, no GUI, no MCP, no LLM API calls by Vibecode.
- Acceptance criteria: No maintained doc falsely says OpenCode run is out of scope or unimplemented.
- Verification: python -m pytest tests/test_vibecode_quickstart.py -p no:cacheprovider plus grep for stale phrases.
Task 35 — Keep canonical CLI command set small and consistent
- Status: PARTIAL
- Problem: CLI is functional, but agent-facing command docs omit implemented commands and one help string has a typo.
- Evidence: CLI defines run-plan and history at cli.py:174-253; AGENTS.md:32-44 omits them; cli.py:168-172 says generation/refres.
- Step-by-step fix:
  1. Add run-plan and history to AGENTS command list or explicitly state they are secondary commands.
  2. Fix --no-index help typo.
  3. Audit README/Quickstart/AGENTS for command list drift.
- Acceptance criteria: CLI help and docs agree on command names and meanings.
- Verification: python -m pytest tests/test_vibecode_cli.py tests/test_vibecode_quickstart.py -p no:cacheprovider.
Task 39 — Update docs for project registry workflow
- Status: PARTIAL
- Problem: Docs overclaim fallback behavior.
- Evidence: docs/QUICKSTART.md:128-136 says repo-root resolution falls back to current directory generally; implementation’s generic resolver errors without active project at cli.py:332-340; run-plan defaults to cwd at cli.py:174-183, 438-443.
- Step-by-step fix:
  1. Document exact fallback behavior per command family.
  2. State run-plan defaults to current directory and does not use registry fallback.
  3. Keep explicit-path workflow examples.
- Acceptance criteria: Docs no longer imply all commands fall back to . after registry.
- Verification: python -m pytest tests/test_vibecode_active_project_fallback.py tests/test_vibecode_quickstart.py -p no:cacheprovider.
Task 41 — Add stale index detection
- Status: PARTIAL
- Problem: Stale detection exists but is not as strong as PRD requested.
- Evidence: indexer/__init__.py:60-109; run_plan.py:143-200; run.py:375-410.
- Step-by-step fix:
  1. Store indexed path fingerprint or tracked path set in index run metadata.
  2. Compare current tracked path set/status to last index metadata.
  3. Add tests for changed file set without commit change where context/run warns.
- Acceptance criteria: Stale detection catches file-state/path-set drift, not only age or HEAD changes.
- Verification: python -m pytest tests/test_vibecode_stale_index.py tests/test_vibecode_run_plan.py -p no:cacheprovider.
6. Repo hygiene findings
Critical
None found.
High
- Problem: Worktree is dirty before/after audit.
- Evidence: git status --short shows deleted tracked VibecodeApp_plan_dalsich_kroku.md and untracked audit markdown files.
- Why it matters: Autonomous runs should start from known state; dirty state can confuse guard/run baselines.
- Step-by-step fix: Decide whether the deleted plan file should be restored or committed as deletion; decide whether audit markdown files should be ignored, removed, or committed.
Medium
- Problem: Generated/runtime tracking is mostly correct, but internal write-rule prefixes omit some runtime dirs.
- Evidence: .gitignore:49-54 ignores runs/tmp/cache/logs/current/generated; write_rules.py:38-43 omits .vibecode/runs/, .vibecode/tmp/, .vibecode/cache/.
- Why it matters: Canonical generated/runtime doctrine is split across files and can drift.
- Step-by-step fix: Align write_rules.GENERATED_PATH_PREFIXES with .gitignore, guard, and .vibecode/README.md.
Low
- Problem: PRD.json is tracked and not ignored, which is good, but not mentioned consistently as truth in generated AGENTS export.
- Evidence: AGENTS.md:13 includes PRD.json; agents_export.py:26-29 omits it.
- Why it matters: Exported instructions could degrade future agent orientation.
- Step-by-step fix: Update render_agents_block().
7. Documentation hygiene findings
Critical
None found.
High
- Problem: docs/ARCHITECTURE_MAP_PRD.md falsely says OpenCode launch/run adapter is out of scope.
- Evidence: docs/ARCHITECTURE_MAP_PRD.md:24, 37, 93; implementation exists in run.py.
- Why it matters: Agents following docs may avoid or mis-audit implemented run behavior.
- Step-by-step fix: Update or clearly mark that PRD as historical core-boundary documentation.
Medium
- Problem: History README says guard/check workflow is future.
- Evidence: .vibecode/history/README.md:57-59.
- Why it matters: It contradicts guard/handoff validation now implemented.
- Step-by-step fix: Reword ownership section to current behavior.
- Problem: Generated index doctrine is inconsistent.
- Evidence: AGENTS.md:18 and .vibecode/architecture/STRUCTURE.md:36 emphasize only .vibecode/index/*.generated.*, while .gitignore:56-64 and .vibecode/index/README.md:15 treat legacy index outputs as generated too.
- Why it matters: Agents may treat non-*.generated.* index files as truth.
- Step-by-step fix: Use the same generated index list in AGENTS, architecture docs, Quickstart, and write rules.
- Problem: Registry fallback docs overclaim.
- Evidence: docs/QUICKSTART.md:128-136; implementation at cli.py:309-342, 438-443.
- Why it matters: Users may expect run-plan or all commands to use active registry fallback.
- Step-by-step fix: Document exact command behavior.
Low
- Problem: run-plan docs say “without making changes” but the command writes JSON.
- Evidence: docs/QUICKSTART.md:312-320; run_plan.py:367-392.
- Why it matters: It is a minor trust issue in preflight docs.
- Step-by-step fix: Say “without launching an agent or editing source.”
- Problem: Root AGENTS says not to update README outside generated blocks, while policy says README is manual-only until generated markers exist.
- Evidence: AGENTS.md:27; .vibecode/checks/protected_paths.yaml:20-22.
- Why it matters: Slightly confusing README edit policy.
- Step-by-step fix: Reword AGENTS to “Do not update README unless task explicitly scopes README/docs.”
8. Control-layer safety findings
- Post-run guard/check/handoff: The recent repair is real. run.py:481-543 captures pre-agent and post-agent state and evaluates agent delta, and tests cover fake OpenCode modifying README.md.
- Protected path enforcement: Standalone guard uses project policy, but post-run vibecode run does not load custom protected_paths.yaml.
- Permission profiles: Profiles are committed and selected profile JSON is checked before launch, but actual OpenCode process enforcement is not visible in run.py:493-502.
- Generated/runtime tracking: Git ignore and tracking state are good. No generated/runtime paths are tracked. Internal doctrine still drifts in write_rules.py and docs.
- Stale index/context: Detection exists and is tested, but it is age/commit/root based and does not fully compare path set or file state.
- Registry resolution: Core commands use active project fallback. run-plan intentionally defaults to cwd. Docs should say that.
- External process safety: vibecode run and vibecode check use shell=True; this is flexible for local Windows commands but should be explicitly treated as trusted-config execution.
9. Agent-readiness verdict
SAFE FOR NEXT NARROW IMPLEMENTATION TASK ONLY
The repo has passing tests and enough safety infrastructure to perform a narrow, well-specified repair. It is not ready for a broad autonomous implementation loop because documentation still contradicts implemented run behavior, permission profiles are advisory, and vibecode run does not enforce custom protected-path policy in post-run guard. Use manual prompt constraints until those are repaired.
10. Ordered repair plan
A. Must fix before more implementation
Step	Files	Action	What not to touch
1	vibecode/guard.py, vibecode/run.py, tests/test_vibecode_run_post.py	Make post-run guard load and enforce .vibecode/checks/protected_paths.yaml.	Do not change unrelated guard rules.
2	vibecode/run.py, vibecode/run_plan.py, tests	Add generated/runtime ignore preflight check.	Do not run real OpenCode.
3	docs/ARCHITECTURE_MAP_PRD.md, .vibecode/history/README.md, docs tests if present	Remove stale “OpenCode run out of scope/future guard” claims.	Do not add GUI/MCP/swarm roadmap.
B. Should fix soon
Step	Files	Action	What not to touch	Acceptance
1	vibecode/context/agents_export.py, AGENTS.md, tests	Align generated AGENTS block with committed root instructions.	Do not broaden agent philosophy.	Export no longer downgrades root AGENTS.md.
2	vibecode/write_rules.py, docs	Align generated/runtime path constants with .gitignore and guard.	Do not track generated files.	Runs/tmp/cache are consistently treated as generated/runtime.
3	vibecode/history.py, tests	Reject _Not yet filled._ as placeholder or mark generated summaries as drafts.	Do not create history files in repo.	Empty summaries cannot pass as durable truth.
4	docs/QUICKSTART.md, README.md, AGENTS.md, vibecode/cli.py	Fix registry fallback docs, command list omissions, and --no-index help typo.	Do not rename commands.	Docs and CLI help agree.
C. Can defer
Step	Files	Action	What not to touch
1	vibecode/indexer/run_record.py, vibecode/indexer/__init__.py, stale-index tests	Add path-set/file-state fingerprinting for stronger stale detection.	Do not regenerate committed artifacts.
2	vibecode/check.py, vibecode/run.py, docs	Clarify or harden shell=True safety model.	Do not break Windows command strings casually.
3	vibecode/run.py, .vibecode/agents/*.json, tests	Decide whether profiles are advisory or translated into OpenCode enforcement.	Do not claim enforcement without behavior.
11. Recommended next single task
Make vibecode run enforce the same project protected-path policy as vibecode guard, including a fake OpenCode regression test for a custom protected path modified after launch.
12. Final judgment
VibecodeApp is not a hollow PRD implementation: most control-layer pieces exist, the full suite passes, generated/runtime tracking is clean, and the repaired post-agent run evaluation is covered by tests. The repo is still not fully PRD-done because several completed flags hide safety and truth gaps, especially stale docs, advisory permission profiles, incomplete run preflight, and post-run guard policy drift. The next work should be narrow safety repair, not new features.