# P13 Completion Audit

## Verdict

PASS

P13 is complete against the requested scope. The command resolution regression is covered in code and tests, the targeted and full validation suites pass, default fake OpenCode works without `OPENCODE_COMMAND`, and validation did not dirty the repository before this report was written.

`PRD.json` marks P13.1, P13.2, and P13.3 as completed, but this verdict does not rely on that flag.

## Command results

| Command | Result | Notes |
| --- | --- | --- |
| `git status --short` | PASS | Baseline before validation: no output, clean tree. |
| `python -m compileall vibecode -q` | PASS | Exit 0, no output. |
| `python -m pytest -p no:cacheprovider -q tests/test_vibecode_opencode_adapter.py` | PASS | `26 passed in 0.03s`. |
| `python -m pytest -p no:cacheprovider -q tests/test_vibecode_run_controller.py tests/test_vibecode_run.py::TestCmdRunEndToEnd tests/test_vibecode_run.py::TestCmdRunPreflight::test_safe_gitignore_allows_agent_launch` | PASS | `48 passed in 80.11s (0:01:20)`. |
| `python -m pytest -p no:cacheprovider -q` | PASS | `1769 passed, 35 warnings in 255.66s (0:04:15)`. Warnings were existing protected-path and syntax-error test warnings. |
| `python -m vibecode.cli --help` | PASS | Help rendered and listed `run`, `monitor`, and `runs`. |
| `python -m vibecode.cli run --help` | PASS | Help rendered; `--guard-mode {advisory,strict}` documents advisory default and strict blocking. |
| `python -m vibecode.cli monitor --help` | PASS | Help rendered; describes streaming monitor, not PTY. |
| `python -m vibecode.cli runs --help` | PASS | Help rendered; lists `list` and `show`. |
| `Get-Command opencode -ErrorAction SilentlyContinue` | PASS | Found local `opencode.ps1` as an ExternalScript under `C:\Users\Martin\AppData\Roaming\npm\...`. |
| `opencode --version` | PASS | Returned `1.14.48`. This is a version check only, not an agent session. |
| `git status --short` | PASS | After validation and before writing this report: no output, clean tree. |

## Code evidence

- `vibecode/adapters/opencode.py:34-36` defines the default command as `opencode run`.
- `vibecode/adapters/opencode.py:47-52` returns `OPENCODE_COMMAND` unchanged when set; otherwise it computes the default and calls `shutil.which(shlex.split(default_cmd)[0])`. For `opencode run`, the only lookup target is `opencode`.
- `vibecode/adapters/opencode.py:79-97` parses the configured command with `shlex.split(...)`, stores `parts[0]` as `binary`, stores remaining args separately as `extra_args`, and calls `shutil.which(binary)`.
- The focused search `rg -n "shutil\.which\(" vibecode/adapters/opencode.py` found only:
  - `vibecode/adapters/opencode.py:51`: `shutil.which(shlex.split(default_cmd)[0])`
  - `vibecode/adapters/opencode.py:97`: `shutil.which(binary)`
- No `shutil.which()` call is made with `"opencode run"` or any other compound command string. A focused search for `which(...opencode run` found no code hit.
- `vibecode/adapters/opencode.py:109-119` checks availability with `[binary_path, "--version"]`, so the availability check verifies the binary without launching `opencode run` as an agent session.
- `vibecode/run.py:703-724` resolves the OpenCode command, emits a clear missing-command error if it is absent, and calls `check_opencode(command)` before launching.
- `vibecode/run.py:790-798` passes the resolved command to `run_streaming(...)` with prompt stdin and per-session stdout/stderr logs.
- `vibecode/process_runner.py:123-133` uses `subprocess.Popen(..., shell=True)` for the trusted local command string, preserving Windows `.cmd` and compound command behavior. The fake-run regression test proves `opencode run` reaches the fake executable as argv `["run"]`.

## Test evidence

- Default fake OpenCode launch:
  - `tests/test_vibecode_run_controller.py::TestRunControllerSummaryWritten::test_fake_opencode_orchestration_writes_artifacts_and_preserves_advisory_guard`
  - `tests/test_vibecode_run.py::TestCmdRunEndToEnd::test_run_succeeds_with_fake_opencode`
  - Evidence: fake `opencode.cmd` is placed on PATH without `OPENCODE_COMMAND`; summary command is `opencode run`; captured argv is `["run"]`.

- Env override:
  - `tests/test_vibecode_opencode_adapter.py::TestResolveOpencodeCommand::test_env_override_simple_binary`
  - `tests/test_vibecode_opencode_adapter.py::TestResolveOpencodeCommand::test_env_override_compound_command`
  - `tests/test_vibecode_opencode_adapter.py::TestResolveOpencodeCommand::test_env_override_with_space_in_value`
  - `tests/test_vibecode_run.py::TestCmdRunPreflight::test_env_only_opencode_command_reaches_fake_runner`

- Compound command behavior:
  - `tests/test_vibecode_opencode_adapter.py::TestResolveOpencodeCommand::test_default_checks_only_executable_not_compound_string`
  - `tests/test_vibecode_opencode_adapter.py::TestCompoundCommandParsing::test_quoted_windows_path_parsed_correctly`
  - `tests/test_vibecode_opencode_adapter.py::TestCompoundCommandParsing::test_missing_local_script_detected`
  - `tests/test_vibecode_opencode_adapter.py::TestCompoundCommandParsing::test_missing_absolute_script_detected`

- Missing command behavior:
  - `tests/test_vibecode_opencode_adapter.py::TestBinaryNotFound::test_missing_command`
  - `tests/test_vibecode_opencode_adapter.py::TestResolveOpencodeCommand::test_default_returns_none_when_binary_missing`
  - `tests/test_vibecode_run.py::TestCmdRunEndToEnd::test_run_missing_opencode_command`
  - `tests/test_vibecode_run_controller.py::TestRunControllerFailureEvents::test_no_opencode_command_emits_error_events`
  - `tests/test_vibecode_run.py::TestCmdRunPreflight::test_invalid_env_opencode_command_fails_before_launch`

- Stdout/stderr logs and streaming events:
  - `tests/test_vibecode_process_runner.py::TestRunStreamingStdoutOnly::test_stdout_captured`
  - `tests/test_vibecode_process_runner.py::TestRunStreamingStdoutOnly::test_stdout_events_emitted`
  - `tests/test_vibecode_process_runner.py::TestRunStreamingStderrOnly::test_stderr_captured`
  - `tests/test_vibecode_process_runner.py::TestRunStreamingStderrOnly::test_stderr_events_emitted`
  - `tests/test_vibecode_process_runner.py::TestRunStreamingMixed::test_both_streams_captured`
  - `tests/test_vibecode_process_runner.py::TestRunStreamingMixed::test_both_log_files_written`
  - `tests/test_vibecode_process_runner.py::TestRunStreamingMixed::test_both_event_types_emitted`
  - `tests/test_vibecode_run_controller.py::TestRunControllerSummaryWritten::test_fake_opencode_orchestration_writes_artifacts_and_preserves_advisory_guard`

- Prompt/context snapshots:
  - `tests/test_vibecode_run_controller.py::TestContextAndPromptSnapshotEvents::test_context_event_has_snapshot_path`
  - `tests/test_vibecode_run_controller.py::TestContextAndPromptSnapshotEvents::test_context_snapshot_file_exists_on_disk`
  - `tests/test_vibecode_run_controller.py::TestContextAndPromptSnapshotEvents::test_prompt_event_has_snapshot_path`
  - `tests/test_vibecode_run_controller.py::TestContextAndPromptSnapshotEvents::test_fake_opencode_stdin_matches_prompt_snapshot`

- Summary/events:
  - `tests/test_vibecode_run_controller.py::TestRunControllerSummaryWritten::test_summary_json_exists_after_successful_run`
  - `tests/test_vibecode_run_controller.py::TestRunControllerSummaryWritten::test_summary_event_has_correct_path`
  - `tests/test_vibecode_run_controller.py::TestRunControllerSummaryWritten::test_returned_summary_matches_written_file`
  - `tests/test_vibecode_run_controller.py::TestRunControllerEventSequence::test_agent_started_before_agent_finished`
  - `tests/test_vibecode_run_controller.py::TestRunControllerEventSequence::test_summary_written_before_run_finished`

- Advisory guard default:
  - `tests/test_vibecode_run_controller.py::TestRunControllerSummaryWritten::test_fake_opencode_orchestration_writes_artifacts_and_preserves_advisory_guard`
  - `tests/test_vibecode_run_post.py::TestRunSummaryOverallStatus::test_guard_with_error_causes_needs_review_in_advisory_mode`
  - `tests/test_vibecode_run_post.py::TestRunSummaryOverallStatus::test_guard_failure_overrides_agent_success_advisory`
  - `tests/test_vibecode_run_post.py::TestGuardModeSemantics::test_advisory_is_default`
  - `tests/test_vibecode_run_post.py::TestGuardModeSemantics::test_advisory_exit_code_zero`
  - `tests/test_vibecode_run_post.py::TestGuardModeSemantics::test_advisory_guard_findings_fully_preserved`

- Strict guard mode:
  - `tests/test_vibecode_run_post.py::TestRunSummaryOverallStatus::test_guard_with_error_causes_failure_in_strict_mode`
  - `tests/test_vibecode_run_post.py::TestRunSummaryOverallStatus::test_guard_failure_overrides_agent_success_strict`
  - `tests/test_vibecode_run_post.py::TestGuardModeSemantics::test_strict_guard_error_yields_failure`
  - `tests/test_vibecode_run_post.py::TestGuardModeSemantics::test_strict_exit_code_one`
  - `tests/test_vibecode_run_post.py::TestRunPostIntegration::test_run_guard_catches_readme_modified_by_agent_strict`
  - `tests/test_vibecode_monitor.py::TestCmdMonitor::test_cmd_monitor_guard_mode_defaults_to_advisory`
  - `tests/test_vibecode_monitor.py::TestCmdMonitor::test_cmd_monitor_passes_repo_root`

## Repo hygiene

- Before validation, `git status --short` produced no output.
- After validation and before writing this report, `git status --short` produced no output.
- `.gitignore:6` ignores `.pytest-tmp/`.
- `.gitignore:58` ignores `.vibecode/tmp/`.
- `git ls-files -- .pytest-tmp .vibecode/tmp tmp` produced no output, so there are no tracked temp artifacts in those paths.
- Validation did not create tracked `.pytest-tmp` or generated temp-state churn.
- This report file is the only intended repository mutation made after the clean post-validation status check.

## Remaining risks

- A real `opencode run` agent session was not launched during this audit. This was intentional: the P13 requirement is that availability checks do not launch an agent session, and fake default OpenCode launch is covered by tests.
- Runtime execution still uses `shell=True` for trusted local command strings to support Windows `.cmd` wrappers and compound `OPENCODE_COMMAND` values. Unusual user-provided quoting remains a command configuration risk, though the covered default and documented compound paths pass.
