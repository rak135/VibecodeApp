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
