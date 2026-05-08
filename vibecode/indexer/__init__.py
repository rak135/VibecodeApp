"""File indexer for vibecode."""

from __future__ import annotations

import sys
from pathlib import Path


def cmd_index(args) -> int:
    repo_root = Path(args.repo_root).resolve()
    print(f"Indexing {repo_root}", file=sys.stderr)
    # Full implementation in tasks 05–07.
    return 0
