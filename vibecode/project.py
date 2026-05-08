"""Project-level commands: init and map."""

from __future__ import annotations

import sys
from pathlib import Path


def cmd_init(args) -> int:
    repo_root = Path(args.repo_root).resolve()
    project_id = getattr(args, "project_id", None) or repo_root.name.lower().replace(" ", "_")
    project_name = getattr(args, "project_name", None) or repo_root.name
    print(
        f"Initializing vibecode project '{project_name}' (id={project_id}) in {repo_root}",
        file=sys.stderr,
    )
    # Full implementation in task 03.
    return 0


def cmd_map(args) -> int:
    repo_root = Path(args.repo_root).resolve()
    print(f"Repository map for {repo_root}", file=sys.stderr)
    # Full implementation in task 08.
    return 0
