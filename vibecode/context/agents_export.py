"""Agent instructions export for vibecode."""

from __future__ import annotations

import sys
from pathlib import Path

AGENTS_MARKER_START = "<!-- vibecode:agents:start -->"
AGENTS_MARKER_END = "<!-- vibecode:agents:end -->"
AGENTS_GENERATED_PATH = Path(".vibecode") / "generated" / "AGENTS.generated.md"
AGENTS_ROOT_PATH = Path("AGENTS.md")


def render_agents_block() -> str:
    """Return the vibecode agent instructions block (without markers)."""
    return (
        "# Agent Instructions\n\n"
        "## Before you start\n\n"
        '1. Run `python -m vibecode.cli context . --task "<task>"`'
        " to generate a task-specific context pack;"
        " start from `Relevant files with reasons`.\n"
        "2. Read `.vibecode/architecture/INVARIANTS.md`"
        " and `.vibecode/architecture/STRUCTURE.md` when present.\n"
        "3. Read `.vibecode/handoff/NOW.md` for current scope.\n"
        "4. Check `.vibecode/checks/required_checks.yaml` for required checks.\n\n"
        "## Source of truth\n\n"
        "Treat source code, tests, `PRD.json`, and human-maintained docs"
        " (`.vibecode/architecture/`, `.vibecode/handoff/`,"
        " `.vibecode/checks/`, `.vibecode/history/`, `.vibecode/agents/`)"
        " as truth.\n\n"
        "## Do not manually edit\n\n"
        "- `.vibecode/current/*` \u2014 session state\n"
        "- `.vibecode/index/*.generated.*` \u2014 generated index\n"
        "- `.vibecode/generated/*` \u2014 export artifacts\n"
        "- `.vibecode/logs/*` \u2014 runtime logs\n"
        "- `.vibecode/runs/*` \u2014 run metadata\n\n"
        "## Rules\n\n"
        "- Do not perform unrelated refactors.\n"
        "- Do not modify protected files without an explicit task.\n"
        "- Do not edit README unless the task explicitly scopes README/docs;"
        " only edit generated blocks if future markers exist.\n"
        "- Run required checks before finalizing changes.\n"
        "- Report changed files and checks run before marking work complete.\n"
        "- Update the handoff document when done.\n"
        "\n"
        "## Available commands\n\n"
        "- `vibecode init` \u2014 initialize `.vibecode/` project layer\n"
        "- `vibecode index` \u2014 scan and generate architecture maps\n"
        "- `vibecode context` \u2014 generate task-scoped context pack\n"
        "- `vibecode map` \u2014 print one-page project summary\n"
        "- `vibecode validate` \u2014 check artifact consistency (run this first)\n"
        "- `vibecode guard` \u2014 check diff against protected/generated paths\n"
        "- `vibecode check` — run required checks from"
        " `.vibecode/checks/required_checks.yaml`\n"
        "- `vibecode handoff-check` \u2014 validate handoff file quality\n"
        "- `vibecode run` \u2014 explicitly orchestrate an external OpenCode run"
        " and then run guard/check/handoff\n"
        "- `vibecode run-plan` \u2014 assemble an agent run plan without launching it\n"
        "- `vibecode history` \u2014 manage durable history summaries\n"
        "- `vibecode project` \u2014 manage the local project registry outside the repo\n"
        "- `vibecode export-agents` \u2014 write/update root AGENTS.md\n"
    )


def render_agents_file() -> str:
    """Return AGENTS.md content wrapped in vibecode marker blocks."""
    block = render_agents_block()
    return f"{AGENTS_MARKER_START}\n{block}{AGENTS_MARKER_END}\n"


def _is_vibecode_managed(content: str) -> bool:
    """Return True if the file contains vibecode agent marker blocks."""
    return AGENTS_MARKER_START in content and AGENTS_MARKER_END in content


def _update_marker_block(existing: str, new_block: str) -> str:
    """Replace the vibecode marker block in *existing* with updated *new_block*."""
    start_idx = existing.index(AGENTS_MARKER_START)
    end_idx = existing.index(AGENTS_MARKER_END) + len(AGENTS_MARKER_END)
    replacement = f"{AGENTS_MARKER_START}\n{new_block}{AGENTS_MARKER_END}"
    return existing[:start_idx] + replacement + existing[end_idx:]


def write_agents_export(repo_root: Path, force: bool = False) -> tuple[Path, Path | None]:
    """Write agent instructions; return (generated_path, agents_md_path | None).

    Always writes to .vibecode/generated/AGENTS.generated.md.
    Also writes AGENTS.md in the repo root, unless it already exists and is
    not Vibecode-managed (in which case it is skipped unless *force* is True).
    """
    root = repo_root.resolve()

    generated_path = root / AGENTS_GENERATED_PATH
    generated_path.parent.mkdir(parents=True, exist_ok=True)
    block = render_agents_block()
    generated_path.write_text(block, encoding="utf-8")

    agents_md = root / AGENTS_ROOT_PATH
    agents_md_written: Path | None = None
    wrapped = render_agents_file()

    if not agents_md.exists():
        agents_md.write_text(wrapped, encoding="utf-8")
        agents_md_written = agents_md
    else:
        existing = agents_md.read_text(encoding="utf-8")
        if _is_vibecode_managed(existing):
            agents_md.write_text(_update_marker_block(existing, block), encoding="utf-8")
            agents_md_written = agents_md
        elif force:
            agents_md.write_text(wrapped, encoding="utf-8")
            agents_md_written = agents_md

    return generated_path, agents_md_written


def cmd_export_agents(args) -> int:
    repo_root = Path(args.repo_root).resolve()
    force: bool = getattr(args, "force", False)

    generated_path, agents_md_path = write_agents_export(repo_root, force=force)
    print(f"Agents export written: {generated_path}", file=sys.stderr)

    if agents_md_path:
        print(f"AGENTS.md written: {agents_md_path}", file=sys.stderr)
        return 0

    agents_md = repo_root / AGENTS_ROOT_PATH
    if agents_md.exists():
        print(
            "AGENTS.md exists and is not Vibecode-managed; skipped"
            " (use --force to overwrite).",
            file=sys.stderr,
        )
        return 1

    return 0
