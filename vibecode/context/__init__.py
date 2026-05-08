"""Context pack generation for vibecode."""

from __future__ import annotations

import sys
from pathlib import Path


def cmd_context(args) -> int:
    repo = Path(args.repo).resolve()
    task = args.task or "(no task specified)"
    print(f"Generating context pack for: {task}", file=sys.stderr)
    print(f"Repository: {repo}", file=sys.stderr)
    # Full implementation in later tasks.
    return 0
