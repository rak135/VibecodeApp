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
- README guard evaluation now treats root `README.md` as manual-only unless the task explicitly mentions README/docs; docs files such as `docs/QUICKSTART.md` are not blocked.
- Architecture truth guard evaluation now requires same-change handoff/history acknowledgement for `.vibecode/architecture/*.md` changes.
- Guard evaluation now warns when source and test changes are not paired, using test-map suggestions when available and allowing explicit test-only work.
- `vibecode run` orchestrates external OpenCode only when explicitly invoked, validates selected permission profiles before launch, and evaluates guard/check/handoff against the post-agent working tree.
- Default permission profiles live in committed `.vibecode/agents/{safe,fast,audit}.json`.
- Post-run guard evaluation now uses the same project-loaded protected path policy as standalone `vibecode guard`, with regression coverage for custom `.vibecode/checks/protected_paths.yaml` rules.
- AGENTS export now preserves the committed managed block content, including `PRD.json`, run metadata, and the current CLI command list.
- Root `AGENTS.md` now clarifies README is manual project documentation unless README/docs are explicitly scoped, and its generated command list follows top-level CLI help order.
- `docs/ARCHITECTURE_MAP_PRD.md` now carries a phase-boundary note at the top clarifying it describes the earlier Architecture Map Core phase; the OpenCode run adapter non-goal entry has been updated to reflect current implementation status (`vibecode run`).
- Stale-index detection now uses a disk-scan file-set fingerprint to detect added/removed tracked source files even without a new git commit; `check_index_freshness`, `cmd_run`, and `build_run_plan` all use the disk-scan fingerprint; generated/runtime paths (including `.vibecode/index/`) are excluded from the fingerprint.
- Context cards, AST parsing, and risk analysis are implemented: `schema.py` (ContextCard, RiskItem, Fact, Heuristic), `ast_parser.py` (module docstring + symbol extraction via `ast`), `risk_analyzer.py` (TODO/FIXME facts, unsafe-permission facts, high-param-count and suspicious-name heuristics), `risk_reporter.py` (writes `.vibecode/index/risk_report.json` with per-file `facts` and `heuristics` arrays). `inventory.py` now accepts `generate_cards=True/card_detail/compute_heuristics` and emits a `cards` list in `file_inventory.json`. `vibecode index` loads `.vibecode/config.yml` (`cards.detail_level`, `cards.compute_heuristics`) and writes both `file_inventory.json` (with cards) and `risk_report.json`. 50 new tests in `tests/test_vibecode_context_cards.py`; all 1310 tests pass.
- `vibecode inventory` command added: scans the repository, writes `.vibecode/index/file_inventory.json` with a `context_cards` key (one card per Python file) and `.vibecode/index/risk_report.json`. Each context card has `purpose` (module docstring), structured `symbols` list (`name`, `kind`, `line`), `content_snippet` (first 200 chars), `facts`, and `heuristics`. Heuristic items carry a `severity` field (`high_param_count` → "medium", `suspicious_name` → "low"). `risk_report.json` per-file entries have separated `facts` and `heuristics` lists, with severity included on each heuristic. `ast_parser.py` now also populates `symbol_records` (structured, used by inventory) while keeping `symbols: list[str]` for backward compat. 29 new tests in `tests/test_vibecode_inventory_cmd.py`; all 1339 tests pass.
- `vibecode serve` MCP server added: `vibecode/mcp_server.py` defines `VibecodeServer` (loads `file_inventory.json` and `risk_report.json` at startup, builds card/symbol/risk indexes), `build_mcp_server()` (returns a `FastMCP` instance with three tools), and `cmd_serve()`. Tools: `get_file_card(file_path)` returns a human-readable Markdown card; `find_symbol(symbol_name)` returns a JSON array of locations (with case-insensitive fallback); `list_high_risk()` returns files with `severity == "high"` heuristics. Missing files produce warnings to stderr rather than crashes. `vibecode serve` CLI subcommand prints a ready-to-paste OpenCode MCP JSON snippet to stderr before starting the stdio transport loop. 36 new tests in `tests/test_vibecode_mcp_server.py`; all 1375 tests pass.

