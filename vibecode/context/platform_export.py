"""Platform-specific prompt export for vibecode context."""

from __future__ import annotations

from pathlib import Path

OPENCODE_PROMPT_PATH = Path(".vibecode") / "current" / "opencode_prompt.md"

_PRE_EDIT_INSTRUCTIONS = """\
## Pre-edit instructions

- Read the task carefully before making any changes.
- Read the relevant files listed in the context pack before editing.
- Confirm which files are protected or require confirmation before touching them.
- Prefer narrow, focused edits scoped to the task.\
"""

_POST_EDIT_INSTRUCTIONS = """\
## Post-edit instructions

- Summarize each file you changed and explain why.
- List every test or check you ran and its result.
- Update the handoff document when explicitly instructed to do so.\
"""


def render_opencode_prompt(context_pack_content: str) -> str:
    """Return the OpenCode wrapper with *context_pack_content* embedded."""
    parts = [
        "You are working inside a Vibecode-controlled repository.",
        "",
        _PRE_EDIT_INSTRUCTIONS,
        "",
        _POST_EDIT_INSTRUCTIONS,
        "",
        "---",
        "",
        context_pack_content.rstrip(),
    ]
    return "\n".join(parts) + "\n"


def write_opencode_prompt(repo_root: Path, context_pack_content: str) -> Path:
    """Write opencode_prompt.md alongside the context pack and return its path."""
    root = repo_root.resolve()
    output_path = root / OPENCODE_PROMPT_PATH
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_opencode_prompt(context_pack_content), encoding="utf-8")
    return output_path
