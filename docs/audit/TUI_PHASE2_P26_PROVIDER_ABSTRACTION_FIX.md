# TUI Phase 2 P26 Provider Abstraction Fix

Applied: 2026-05-16

Source review: `docs/audit/TUI_PHASE2_P26_PROVIDER_ABSTRACTION_REVIEW.md`

## Verdict

**All concrete fixes from P26.2 review applied.** No scope expansion.

## Changes applied

### MEDIUM finding addressed: Provider abstraction broader than runtime usage

The review found that `check_availability`, `supports_internal_run`, and `supports_external_launch` were defined on the `AgentProvider` interface but never queried by the TUI before dispatching actions. This made them a "partly fake" seam.

**Fix:** Wired these provider capabilities into TUI action dispatch.

### Change 1: Provider availability checked in constructor and stored

`vibecode/main_app.py:1210` — `VibecodeMainApp.__init__` now calls `self._provider.check_availability()` and stores the result as `self._provider_status`.

### Change 2: Internal run actions gated on provider capabilities

`vibecode/main_app.py:1325-1337` — `action_cmd_audit` and `action_cmd_safe` now check:
1. `self._provider.supports_internal_run` — logs error and returns if `False`
2. `self._provider_status` (bool) — logs "Provider unavailable: ..." and returns if `False`

Only proceeds to `_start_run()` when both checks pass.

### Change 3: External launch action gated on provider capabilities

`vibecode/main_app.py:1339-1347` — `action_cmd_external` now checks:
1. `self._provider.supports_external_launch` — logs error and returns if `False`
2. `self._provider_status` (bool) — logs "Provider unavailable: ..." and returns if `False`

Only proceeds to `_start_external()` when both checks pass.

### Change 4: Compose placeholder shows provider availability

`vibecode/main_app.py:53-82` — `_make_center_placeholder` gained optional `available` and `status_msg` parameters. When provided, a `Status:   available` or `Status:   unavailable (<reason>)` line is included.

The `compose()` method now passes the stored provider status to this function.

## What was NOT changed (out of scope)

- No new abstract methods added to `AgentProvider`
- No refactoring of `AgentRunService` or `ExternalTerminalService` (these remain OpenCode-specific)
- No new providers added
- No embedded terminal
- No context generation architecture changes

## Tests added

`tests/test_vibecode_agent_provider.py` — 11 new tests:

| Test | What it covers |
|------|---------------|
| `test_shows_available_status` | Placeholder renders availability line for `available=True` |
| `test_shows_unavailable_status_with_message` | Placeholder renders `unavailable (msg)` for `available=False` |
| `test_backward_compatible_without_availability` | Placeholder omits status line when `available` not passed |
| `test_audit_blocked_when_no_internal_support` | `[A]` action blocked when `supports_internal_run=False` |
| `test_safe_blocked_when_no_internal_support` | `[S]` action blocked when `supports_internal_run=False` |
| `test_audit_blocked_when_provider_unavailable` | `[A]` action blocked when unavailable, message logged |
| `test_external_blocked_when_no_external_support` | `[E]` action blocked when `supports_external_launch=False` |
| `test_external_blocked_when_provider_unavailable` | `[E]` action blocked when unavailable, message logged |
| `test_audit_proceeds_when_supported_and_available` | `[A]` proceeds to `_start_run("audit")` when both pass |
| `test_external_proceeds_when_supported_and_available` | `[E]` proceeds to `_start_external("safe")` when both pass |
| `test_constructor_stores_provider_status` | Constructor stores availability result on `_provider_status` |

## Test results

```
python -m compileall vibecode -q       → PASS (no output)
python -m pytest -q tests/test_vibecode_agent_provider.py               → 51 passed
python -m pytest -q tests/test_vibecode_main_tui.py \
    tests/test_vibecode_external_terminal.py \
    tests/test_vibecode_run_action_tui.py \
    tests/test_vibecode_opencode_adapter.py \
    tests/test_vibecode_monitor.py                                      → 450 passed
python -m pytest -q tests/test_vibecode_run.py tests/test_vibecode_run_plan.py → 96 passed
```

## Changed files

- `vibecode/main_app.py` — action gating + availability display in compose
- `tests/test_vibecode_agent_provider.py` — 11 new gating/display tests
