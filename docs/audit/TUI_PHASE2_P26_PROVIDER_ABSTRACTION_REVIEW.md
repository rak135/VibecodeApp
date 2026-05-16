# TUI Phase 2 P26 Provider Abstraction Review

Generated: 2026-05-16

## Verdict

**PASS WITH CORRECTIONS.**  
P26.1 introduces a real provider seam (`AgentProvider`, `OpenCodeProvider`, `AgentProviderRegistry`) and wires provider display metadata into the TUI shell, while keeping OpenCode as the only real provider and preserving existing OpenCode run/monitor behavior. There is no broad plugin-system overreach.

The main issue is that the new provider interface is only partially connected to runtime behavior: non-display provider capabilities are not used by the run/external launch flows yet, and OpenCode-specific logic remains hardcoded in services.

## Findings

### PASS: OpenCode is the only real provider, and future providers are not falsely advertised as working

- Registry is explicit and minimal: only `opencode` is registered (`vibecode/adapters/provider.py:176-177`).
- No fake “working” provider options are surfaced in the TUI; provider selection is not exposed as a misleading UI choice.
- The abstraction stays lightweight (single module, no plugin loading/reflection framework).

### PASS: TUI uses provider metadata instead of hardcoded provider labels in key center-panel render paths

Provider display label is read from the provider instance and threaded through rendering:

- Provider injected/defaulted in app constructor (`vibecode/main_app.py:1205-1209`).
- Compose placeholder uses `self._provider.display_name` (`vibecode/main_app.py:1262-1270`).
- Context/run/external center renderers receive provider name (`vibecode/main_app.py:1480`, `1518`, `1582`, `1653-1656`).
- Coverage exists for provider-driven labels (`tests/test_vibecode_agent_provider.py:233-289`, `298-374`).

### PASS: Existing OpenCode run/monitor behavior remains stable

OpenCode-oriented run flow still works via existing services and adapters:

- Internal run path still executes via `RunController(platform="opencode", ...)` (`vibecode/main_app.py:711-721`).
- External launch still generates context/prompt, resolves OpenCode command, and calls terminal adapter (`vibecode/main_app.py:928-956`).
- Targeted tests for run action, OpenCode adapter, monitor, provider, and external terminal all pass (see Evidence).

### PASS: No direct LLM call introduced

- The provider module itself only delegates availability/command info to OpenCode adapter helpers.
- Existing no-LLM guard tests remain in place and pass (`tests/test_vibecode_main_tui.py:435-467`, `tests/test_vibecode_external_terminal.py:689-698`, `tests/test_vibecode_run_action_tui.py:428-432`).

### MEDIUM: Provider abstraction is currently broader than its runtime usage (partly “fake” seam)

`AgentProvider` exposes:
- availability,
- context artifact expectations,
- internal/external support flags,
- prepared command description,
- limitations.

But in production code those members are effectively unused outside the provider module itself. Search evidence:

- `check_availability`, `supports_internal_run`, `supports_external_launch`, `context_artifacts`, `prepared_command_description`, `limitations` appear only in `vibecode/adapters/provider.py` (plus tests), not in TUI/runtime behavior.
- TUI behavior still hardcodes OpenCode-specific execution details:
  - internal run platform fixed to `"opencode"` (`vibecode/main_app.py:714`);
  - external path hardcodes `write_opencode_prompt` and `resolve_opencode_command` (`vibecode/main_app.py:930`, `944`, `946`).

**Impact:** the interface shape is larger than what the app currently consumes, so future-provider extensibility is only partially realized.

## Required evidence

### Test output

```text
python -m pytest -q tests/test_vibecode_agent_provider.py tests/test_vibecode_main_tui.py tests/test_vibecode_external_terminal.py tests/test_vibecode_run_action_tui.py tests/test_vibecode_opencode_adapter.py tests/test_vibecode_monitor.py
-> 490 passed in 17.02s

python -m pytest -q tests/test_vibecode_run.py tests/test_vibecode_run_plan.py
-> 96 passed in 89.83s (0:01:29)

python -m compileall vibecode -q; python -m vibecode.cli check .
-> PASS: unit tests (exit code 0, 325.734s)
-> PASS: cli help (exit code 0, 0.063s)
-> PASS: index command help (exit code 0, 0.078s)
-> PASS: context command help (exit code 0, 0.062s)
```

### Example provider status display

Captured from runtime call to `get_default_provider()` + `check_availability()`:

```text
=== Provider status ===
Provider: OpenCode
Available: True
Status: OpenCode found: 1.15.3 (at C:\Users\Martin\AppData\Roaming\npm\opencode.CMD)
Prepared command: opencode run
Context artifacts: ['.vibecode/current/context_pack.md', '.vibecode/current/opencode_prompt.md']
Supports internal run: True
Supports external launch: True
```

### How OpenCode run and external terminal launch connect to the provider

Current connection is **UI metadata-first**, not full behavior delegation:

1. `VibecodeMainApp` stores a provider (default: registry OpenCode provider) and uses `display_name` in center/status text.
2. Internal run action (`[A]/[S]`) still delegates to `AgentRunService`, which calls `RunController(... platform="opencode" ...)` directly.
3. External action (`[E]`) still delegates to `ExternalTerminalService`, which directly calls OpenCode-specific helpers (`write_opencode_prompt`, `resolve_opencode_command`) and then terminal adapter launch.

So the provider abstraction currently labels the UX correctly, but execution plumbing remains OpenCode-specific.

## Recommended corrections for P26.3

1. Either reduce `AgentProvider` to what is actually used now (display/status only), **or** wire current methods into runtime decisions.
2. Gate actions with provider capabilities (`supports_internal_run`, `supports_external_launch`) and availability (`check_availability`) before launch.
3. Move OpenCode-specific prompt/command preparation behind provider-facing methods so run/external actions consume provider behavior, not hardcoded OpenCode helpers.

## Changed files

- `docs/audit/TUI_PHASE2_P26_PROVIDER_ABSTRACTION_REVIEW.md`
