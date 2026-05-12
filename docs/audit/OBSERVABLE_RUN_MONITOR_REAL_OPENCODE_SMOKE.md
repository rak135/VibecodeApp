# Observable Run Monitor - Real OpenCode Smoke

**Date:** 2026-05-12  
**Repo:** `C:\DATA\PROJECTS\VibecodeApp`  
**HEAD at start:** `5f09910` (`master`)  
**Environment:** Windows, PowerShell, Python 3.12, OpenCode 1.14.48

## Required Availability Checks

`Get-Command opencode -ErrorAction SilentlyContinue`

Result: OpenCode is present as an external PowerShell script:

```text
Name        : opencode.ps1
CommandType : ExternalScript
Path        : C:\Users\Martin\AppData\Roaming\npm\opencode.ps1
Source      : C:\Users\Martin\AppData\Roaming\npm\opencode.ps1
```

`opencode --version`

```text
1.14.48
```

CLI help checks all returned exit code 0:

```text
python -m vibecode.cli --help
python -m vibecode.cli run --help
python -m vibecode.cli monitor --help
python -m vibecode.cli runs --help
```

Initial `git status --short`: clean.

## Real OpenCode Smoke

The current OpenCode non-interactive command is `opencode run`; plain
`opencode` starts the TUI. The first successful smoke used Vibecode's existing
command override:

```powershell
$env:OPENCODE_COMMAND='opencode run'
python -m vibecode.cli run . --platform opencode --guard-mode advisory --allow-dirty --task "REAL OPENCODE SMOKE TEST ONLY. Do not modify any files. Inspect the VibecodeApp observable run prompt/context and print a concise confirmation that the agent process executed. Include the marker VIBECODE_REAL_OPENCODE_SMOKE_OK in your final output."
```

Resulting session: `20260512T051751673320Z`

Run status:

- Agent exit code: `0`
- Agent status: `success`
- Overall Vibecode status: `incomplete`
- Reason for incomplete status: handoff validation reported one pre-existing
  issue in `.vibecode/handoff/NOW.md` because the old placeholder detector
  treated a historical `TODO/FIXME` mention as placeholder text.
- Marker in agent output: yes, `VIBECODE_REAL_OPENCODE_SMOKE_OK` appeared in
  `agent_stdout.log`, `summary.json`, and `events.jsonl`.

After fixing the default command construction to use `opencode run`, a second
real default-path smoke was attempted without `OPENCODE_COMMAND`:

```powershell
python -m vibecode.cli run . --platform opencode --guard-mode advisory --allow-dirty --task "REAL OPENCODE SMOKE TEST ONLY. Do not modify any files. Inspect the VibecodeApp observable run prompt/context and print a concise confirmation that the agent process executed. Include the marker VIBECODE_REAL_OPENCODE_SMOKE_OK in your final output."
```

Resulting session: `20260512T052734396950Z`

Run status:

- Agent exit code: `-1`
- Agent status: `failure`
- Overall Vibecode status: `failure`
- Failure mode: OpenCode launched and produced output, but the agent process
  exceeded Vibecode's 300 second timeout after doing additional inspection and
  test commands. The marker appeared later in the live event stream, but not in
  `agent_stdout.log`/`summary.json` because the process timed out before normal
  result collection completed.
- The timed-out OpenCode process also attempted unrelated PRD follow-up edits
  despite the no-modification smoke prompt. Those smoke-fallout edits were
  removed from the working tree and this failure mode is recorded here.
- Post-run guard/check/handoff artifacts were still written.

## Artifact Checklist

Session `20260512T051751673320Z`:

| Artifact | Status |
|---|---:|
| `events.jsonl` | present, 7744 bytes |
| `summary.json` | present, 13585 bytes |
| `opencode_prompt.md` | present, 14748 bytes |
| `context_pack.md` | present, 14189 bytes |
| `agent_stdout.log` | present, 33 bytes |
| `agent_stderr.log` | present, 53 bytes |
| `guard_report.json` | present, 275 bytes |
| `guard_report.md` | present, 306 bytes |
| `handoff_report.json` | present, 291 bytes |
| `handoff_report.md` | not produced by current implementation |

Session `20260512T052734396950Z`:

| Artifact | Status |
|---|---:|
| `events.jsonl` | present, 97111 bytes |
| `summary.json` | present, 24302 bytes |
| `opencode_prompt.md` | present, 14856 bytes |
| `context_pack.md` | present, 14297 bytes |
| `agent_stdout.log` | present, 400 bytes |
| `agent_stderr.log` | present, 10010 bytes |
| `guard_report.json` | present, 275 bytes |
| `guard_report.md` | present, 306 bytes |
| `handoff_report.json` | present, 132 bytes |
| `handoff_report.md` | not produced by current implementation |

## Event Checklist

The successful real smoke session contains 22 events:

- run start: `run.lifecycle` phase `started`
- git/preflight: `run.git_preflight` phases `started`, `completed`
- index check: `run.index_check` phases `started`, `completed`
- context pack written: `run.context` phase `written`
- prompt written: `run.prompt` phase `written`
- agent started: `run.agent_process` phase `started`
- agent stdout/stderr: `run.agent_process` phases `stdout`, `stderr`
- agent finished: `run.agent_process` phase `finished`, exit code 0
- guard started/completed: `run.guard`
- checks started/completed: `run.check`
- handoff started/completed: `run.handoff`
- summary written: `run.summary`
- run finished: `run.lifecycle` phase `finished`

No required lifecycle event was missing. `handoff_report.md` is simply not a
current output; JSON handoff reporting is produced.

## Fixes Made From This Smoke

- Default OpenCode command changed from `opencode` to `opencode run` so normal
  `vibecode run` uses the non-interactive OpenCode path.
- `vibecode runs show --events` output was made safe for legacy Windows console
  encodings.
- `JsonlEventSink` writes are now locked so stdout/stderr reader threads cannot
  interleave JSONL fragments.
- Timeout process termination now uses a best-effort process-tree kill on
  Windows.
- Handoff placeholder detection no longer treats descriptive `TODO/FIXME`
  wording as an unfinished placeholder.
- `.pytest-tmp/` tracked runtime artifacts were removed from version control
  and temp directories were added to ignore/index exclusions.
- Optional runtime dependencies were moved into packaging extras: `tui`, `mcp`,
  and `all`.

## Validation After Fixes

```text
python -m compileall vibecode -q
PASS

python -m ruff check vibecode/
PASS - All checks passed!

python -m vibecode.cli validate .
PASS - 16 OK, 0 WARN, 0 ERROR

python -m pytest -p no:cacheprovider -q
PASS - 1757 passed, 35 warnings in 257.76s

python -m vibecode.cli check .
PASS - unit tests, cli help, index help, and context help all passed
```

Final `git status --short` remains intentionally dirty with the source/docs/test
fixes above and staged deletions for the formerly tracked `.pytest-tmp/`
runtime fixtures.
