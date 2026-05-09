"""Context pack generation for vibecode."""

from __future__ import annotations

import sys

from vibecode.context.renderer import write_context_pack
from vibecode.paths import normalise_root
from vibecode.registry import ProjectRegistry


def cmd_context(args) -> int:
    task_option = getattr(args, "task_option", None)
    context_arg = getattr(args, "context_arg", None)
    legacy_task = getattr(args, "task", None)
    repo_arg = getattr(args, "repo", None)
    platform = getattr(args, "platform", None)

    if task_option:
        repo = _resolve_repo(repo_arg or context_arg)
        task = task_option
    else:
        repo = _resolve_repo(repo_arg)
        task = legacy_task or context_arg or "(no task specified)"

    if not repo.is_dir():
        print(f"Error: Repository root does not exist: {repo}", file=sys.stderr)
        return 1

    vibecode_dir = repo / ".vibecode"
    if not (vibecode_dir / "project.yaml").exists():
        print(
            f"Error: No project.yaml found in {vibecode_dir}.\n"
            "       Run 'vibecode init' to initialize the project.",
            file=sys.stderr,
        )
        return 1

    print(f"Generating context pack for: {task}", file=sys.stderr)
    print(f"Repository: {repo}", file=sys.stderr)

    risky_files_path = repo / ".vibecode" / "index" / "risky_files.md"
    if risky_files_path.exists():
        content = risky_files_path.read_text(encoding="utf-8")
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

    if platform:
        from vibecode.context.platform_registry import get_exporter

        exporter = get_exporter(platform)
        if exporter is not None:
            context_pack_content = output_path.read_text(encoding="utf-8")
            prompt_path = exporter(repo, context_pack_content)
            print(f"Platform export written ({platform}): {prompt_path}", file=sys.stderr)
        else:
            print(f"Warning: unknown platform '{platform}'; no export written.", file=sys.stderr)

    return 0


def _resolve_repo(repo_arg):
    """Resolve the repository root, with fallback to the active project registry.

    Priority:
    1. Explicit --repo / positional argument (non-".").
    2. Active project from the registry.
    3. Current working directory (".").
    """
    if repo_arg is not None and repo_arg != ".":
        return normalise_root(repo_arg)
    if repo_arg is not None:
        return normalise_root(".")
    try:
        reg = ProjectRegistry()
        resolved = reg.pick(None)
        return normalise_root(str(resolved))
    except FileNotFoundError:
        return normalise_root(".")