# Now

- Phase 1+2 TUI implementation is technically validated in this repository.
- The main command is `vibecode` and it now serves as a TUI-first control surface.
- Phase 1 scope is the three-column TUI workflow (control/status on the left, operator/output surface in the center, debug/event surface on the right).
- Phase 2 scope is external terminal/OpenCode launch support; this is not a fully embedded PTY terminal inside Textual.
- Vibecode itself does not make LLM calls. Model calls happen only through external providers (for example OpenCode) when explicitly launched.
- P28 validation passed broad automated checks, including targeted TUI/refresh/context coverage and fake OpenCode execution coverage.
- Non-interactive validation did not run live interactive TUI smoke or real OpenCode smoke; those remain manual local checks.
- Immediate next step: supervised Windows dogfood with a real `vibecode` launch and optional real OpenCode launch.
