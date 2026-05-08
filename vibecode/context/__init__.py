"""Context pack generation for vibecode."""

from __future__ import annotations

import sys
from pathlib import Path

from vibecode.context.renderer import write_context_pack


def cmd_context(args) -> int:
    task_option = getattr(args, "task_option", None)
    context_arg = getattr(args, "context_arg", None)
    legacy_task = getattr(args, "task", None)
    repo_arg = getattr(args, "repo", None)

    if task_option:
        repo = Path(repo_arg or context_arg or ".").resolve()
        task = task_option
    else:
        repo = Path(repo_arg or ".").resolve()
        task = legacy_task or context_arg or "(no task specified)"

    print(f"Generating context pack for: {task}", file=sys.stderr)
    print(f"Repository: {repo}", file=sys.stderr)

    risky_files_path = repo / ".vibecode" / "index" / "risky_files.md"
    if risky_files_path.exists():
        content = risky_files_path.read_text(encoding="utf-8")
        # Surface high-risk / protected files so the agent is aware of them.
        if "## High Risk" in content:
            print("\n--- Protected / High-Risk Files ---", file=sys.stderr)
            in_high = False
            for line in content.splitlines():
                if line.startswith("## High Risk"):
                    in_high = True
                    continue
                if in_high and line.startswith("## "):
                    break
                if in_high and line.startswith("- `"):
                    path_part = line.strip()[3:].rstrip("`")
                    print(f"  [PROTECTED/RISKY] {path_part}", file=sys.stderr)
            print("-----------------------------------", file=sys.stderr)

    output_path = write_context_pack(repo, task)
    print(f"Context pack written: {output_path}", file=sys.stderr)
    return 0
