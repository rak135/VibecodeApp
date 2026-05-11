# Observable Run Monitor P5 Advisory Guard Review

Generated: 2026-05-11

## Verdict

PASS WITH NOTES. The advisory guard change makes `vibecode run` advisory by default without hiding guard findings: error-severity findings still keep `guard.passed == false`, are serialized into the run summary and guard report, and surface the overall run as `needs_review`. Strict mode is explicit through `--guard-mode strict` and restores hard-failure behavior for guard errors.

This review did not modify implementation or test files. The task scope allowed only this review document.

## Findings

### PASS: advisory mode does not hide serious guard findings

`RunSummary.overall_status` maps guard errors to `needs_review` in advisory mode after preserving the original `GuardResult` object (`vibecode/run.py:116-134`). The serialized summary includes both `guard_mode` and the full guard payload (`vibecode/run.py:136-158`), and the per-session guard report writes `guard_result.as_dict(root=root)` unchanged (`vibecode/run.py:906-912`).

The focused tests prove the same behavior: advisory guard errors yield `needs_review`, keep `guard.passed == false`, and preserve the finding severity/rule id (`tests/test_vibecode_run_post.py:272-302`, `tests/test_vibecode_run_post.py:1428-1460`).

### PASS: run status language is honest

The user-visible status is not reported as success when a guard error exists. Advisory runs print `RUN NEEDS_REVIEW`, show guard error/warning counts, and add an explicit note that advisory findings are logged but do not block the run (`vibecode/run.py:969-982`). Strict runs report `failure` for guard errors (`vibecode/run.py:121-123`).

The status vocabulary is also persisted in `summary.json` as `overall_status`, so automation can distinguish `success` from `needs_review` even though both map to process exit code 0 in advisory mode (`vibecode/run.py:382-386`).

### PASS: agent exit code remains visible

The agent process exit code is captured from `run_streaming()`, assigned to the run summary, emitted in the finished agent event, written to metadata, and printed when non-zero (`vibecode/run.py:761-782`, `vibecode/run.py:943-958`). Advisory guard mode does not overwrite `exit_code`; a successful agent with guard errors remains `exit_code: 0` plus `overall_status: needs_review`.

Existing tests assert metadata and summary exit-code persistence for both zero and non-zero agent exits (`tests/test_vibecode_run.py:294-320`, `tests/test_vibecode_run_post.py:1222-1232`).

### PASS: strict behavior is explicit and documented at the CLI boundary

`vibecode run --guard-mode` is constrained to `{advisory, strict}`, defaults to `advisory`, and the help text documents both modes and their exit-code implications (`vibecode/cli.py:197-207`). `RunController` also documents `guard_mode` semantics in its constructor docstring (`vibecode/run.py:407-411`).

Note: direct `RunController` callers can still pass an arbitrary string because only the CLI parser enforces choices. A typo would behave like advisory mode rather than failing fast. That is not a CLI regression, but validating `guard_mode` inside `RunController.__init__` would reduce bypass risk for programmatic use.

### PASS: tests prove the new default

The test suite covers the default advisory value, advisory exit-code mapping, strict exit-code mapping, summary serialization of `guard_mode`, preserved guard finding severity, and required-check failures still blocking in advisory mode (`tests/test_vibecode_run_post.py:1373-1484`).

End-to-end run-post tests also cover real post-agent guard findings for README, custom protected paths, and generated/runtime files. The default mode returns rc 0 with `overall_status == "needs_review"`, while `--guard-mode strict` returns rc 1 with `overall_status == "failure"` (`tests/test_vibecode_run_post.py:1009-1105`, `tests/test_vibecode_run_post.py:1126-1168`).

### PASS: unrelated guard rules were not weakened

The standalone `vibecode guard` command still returns non-zero for error findings and only uses its existing `--strict` flag to promote warnings to failures (`vibecode/guard.py:638-716`). Guard finding severity is still computed by the existing `GuardResult.passed` property (`vibecode/guard.py:78-86`); advisory mode changes only how `vibecode run` interprets a populated guard result.

Regression tests continue to assert README protection, custom protected-path rules, generated/runtime edits, and source/test warning behavior in run-post coverage.

### PASS: checks and handoff reporting are not bypassed

Guard execution is still followed by required checks and handoff validation in `RunController.execute()` (`vibecode/run.py:797-904`). `RunSummary.overall_status` gives required-check failures precedence over advisory guard errors, so advisory mode does not soften required checks (`vibecode/run.py:121-127`, `tests/test_vibecode_run_post.py:1479-1484`).

Handoff issues still produce `incomplete` and exit code 2, and run-post tests cover missing handoff files independently of advisory guard behavior (`tests/test_vibecode_run_post.py:1187-1215`).

## Checks Run

- `python -m vibecode.cli context . --task "Review the advisory guard change"`
  - Result: passed; wrote the task context pack to `.vibecode/current/context_pack.md`.
- `python -m pytest tests/test_vibecode_run_post.py::TestRunSummaryOverallStatus tests/test_vibecode_run_post.py::TestRunSummaryStatusPriority tests/test_vibecode_run_post.py::TestAdvisoryGuardMode -p no:cacheprovider --basetemp C:\tmp\vibecode-p5-advisory-focused`
  - Result: passed; 28 tests passed.
- `python -m ruff check --no-cache vibecode\run.py vibecode\cli.py tests\test_vibecode_run_post.py`
  - Result: failed on existing lint in `tests/test_vibecode_run_post.py`: one unused `cmd_run` import and multiple unused local `plan` assignments.
- `python -m vibecode.cli guard .`
  - Result: passed; no guard violations found.
- `python -m vibecode.cli handoff-check .`
  - Result: failed on existing `.vibecode/handoff/NOW.md` placeholder-text issue.
- `python -m vibecode.cli check .`
  - Result: timed out after the unit-test step reported failure; CLI help, index help, and context help checks passed.
- `python -m pytest --maxfail=5 --tb=short -q`
  - Result: failed during pytest `tmp_path` setup with `PermissionError` scanning `C:\Users\Martin\AppData\Local\Temp\pytest-of-Martin`; stopped after five setup errors.

