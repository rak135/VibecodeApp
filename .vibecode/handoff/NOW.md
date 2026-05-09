# Now

- Repo hygiene cleanup is complete; generated/runtime artifacts are ignored/untracked.
- Repo tree source package expansion is complete.
- Relevant-file scoring has been improved and cleaned up:
  - Task keywords, source/test pairing, arch-doc references, handoff/history/dependency/git signals, generated-file penalties all active.
  - Generic tokens (e.g. "file", "improve") no longer produce strong false-positive boosts.
  - Architecture-doc overboosting reduced; only domain-specific keyword matches fire.
  - Required checks deduplicated by command string in context_pack.md.
  - Hub/entrypoint files (cli.py, config.py, project.py) suppressed for non-CLI tasks.
  - Dependency boost threshold raised (12) to block generic dep fan-out.
  - Token-based path matching implemented; "pack" no longer matches "package.json".
- Context-pack relevance verified for "Improve relevant-file scoring": scoring.py and test_relevant_files.py rank #1/#2; cli.py is absent from scored results.
- Phrase routing implemented in scoring.py:
  - `context` added to `_LOW_VALUE_TOKENS`; broad directory-level token no longer gives +10 to every file under vibecode/context/.
  - `_PHRASE_ROUTES` constant maps compound task phrases (e.g. "context pack", "repo tree", "platform export", "agents export", "required checks", "guard") to specific file-path patterns.
  - `_active_phrase_patterns()` helper computes active patterns from task keywords each run.
  - Matched files receive `_PHRASE_BOOST` (+12), producing a "phrase route match" reason.
  - `platform_registry.py` no longer outranks `renderer.py` for context-pack rendering tasks.
  - 8 new phrase-routing tests (O–V) added to test_vibecode_relevant_files.py; 715 total tests pass.
