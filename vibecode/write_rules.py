"""Write rules: canonical definitions for human-maintained vs generated paths.

Rules enforced by this module:
- ``vibecode index`` must never write to human-maintained paths.
- ``vibecode init`` must never overwrite human-maintained paths without ``--force``.
- ``vibecode export-agents`` uses marker blocks; skips unmanaged files without ``--force``.
- Paths under GENERATED_PATH_PREFIXES are always safe to overwrite.
"""

from __future__ import annotations

from pathlib import Path

# Relative POSIX paths of every human-maintained vibecode file.
# These are created by ``vibecode init`` and are intended to be edited by humans.
# No generated command (index, export-agents, …) may write to these paths unless
# an explicit ``--force`` flag is passed by the user.
HUMAN_MAINTAINED_PATHS: frozenset[str] = frozenset({
    ".vibecode/project.yaml",
    ".vibecode/checks/required_checks.yaml",
    ".vibecode/architecture/OVERVIEW.md",
    ".vibecode/architecture/INVARIANTS.md",
    ".vibecode/architecture/STRUCTURE.md",
    ".vibecode/architecture/MODULE_BOUNDARIES.md",
    ".vibecode/architecture/PROTECTED_AREAS.md",
    ".vibecode/architecture/DATA_FLOW.md",
    ".vibecode/handoff/NOW.md",
    ".vibecode/handoff/NEXT.md",
    ".vibecode/handoff/BLOCKERS.md",
    ".vibecode/history/README.md",
    ".vibecode/agents/safe.json",
    ".vibecode/agents/fast.json",
    ".vibecode/agents/audit.json",
})

# Path prefixes (POSIX, relative to repo root) whose contents are entirely generated.
# Writes to paths under these prefixes are always safe to overwrite.
GENERATED_PATH_PREFIXES: tuple[str, ...] = (
    ".vibecode/index/",
    ".vibecode/current/",
    ".vibecode/logs/",
    ".vibecode/runs/",
    ".vibecode/tmp/",
    ".vibecode/cache/",
    ".vibecode/generated/",
)


def is_human_maintained(path: Path, repo_root: Path) -> bool:
    """Return True if *path* resolves to a human-maintained vibecode file."""
    try:
        rel = path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return False
    return rel.as_posix() in HUMAN_MAINTAINED_PATHS


def safe_write(path: Path, content: str, *, repo_root: Path, force: bool = False) -> None:
    """Write *content* to *path*, refusing if it is a human-maintained file.

    Raises PermissionError when writing to a human-maintained path without
    ``force=True``. Creates parent directories automatically.
    """
    if is_human_maintained(path, repo_root) and not force:
        rel = path.resolve().relative_to(repo_root.resolve()).as_posix()
        raise PermissionError(
            f"Refusing to overwrite human-maintained file '{rel}'. "
            "Pass force=True or use --force to override."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
