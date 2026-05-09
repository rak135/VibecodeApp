"""Command-line interface for vibecode."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vibecode",
        description="Local repository architecture map and context-pack CLI.",
    )
    parser.add_argument("--version", action="version", version="vibecode 0.1.0")
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Show full traceback on error.",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    # init
    init_parser = subparsers.add_parser(
        "init", help="Initialize .vibecode structure in a repository."
    )
    init_parser.add_argument(
        "repo_root",
        nargs="?",
        default=".",
        help="Repository root directory (default: current directory).",
    )
    init_parser.add_argument("--id", dest="project_id", default=None, help="Project identifier.")
    init_parser.add_argument("--name", dest="project_name", default=None, help="Project name.")
    init_parser.add_argument(
        "--force", action="store_true", help="Overwrite existing human-maintained files."
    )

    # index
    index_parser = subparsers.add_parser("index", help="Scan and index repository files.")
    index_parser.add_argument(
        "repo_root",
        nargs="?",
        default=".",
        help="Repository root directory (default: current directory).",
    )

    # context
    context_parser = subparsers.add_parser("context", help="Generate a context pack for a task.")
    context_parser.add_argument(
        "context_arg",
        nargs="?",
        default=None,
        help="Task description, or repository root when --task is used.",
    )
    context_parser.add_argument("--task", dest="task_option", default=None, help="Task description.")
    context_parser.add_argument(
        "--repo",
        default=None,
        help="Repository root directory (default: current directory).",
    )
    context_parser.add_argument(
        "--platform",
        default=None,
        choices=["opencode"],
        help="Export a platform-specific prompt file (e.g. opencode).",
    )

    # map
    map_parser = subparsers.add_parser("map", help="Print the repository architecture map.")
    map_parser.add_argument(
        "repo_root",
        nargs="?",
        default=".",
        help="Repository root directory (default: current directory).",
    )

    # validate
    validate_parser = subparsers.add_parser(
        "validate", help="Validate .vibecode project artifacts."
    )
    validate_parser.add_argument(
        "repo_root",
        nargs="?",
        default=".",
        help="Repository root directory (default: current directory).",
    )

    # guard
    guard_parser = subparsers.add_parser(
        "guard", help="Check git diff against guard rules."
    )
    guard_parser.add_argument(
        "repo_root",
        nargs="?",
        default=".",
        help="Repository root directory (default: current directory).",
    )
    guard_parser.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help="Treat warnings as hard failures (non-zero exit).",
    )

    # check
    check_parser = subparsers.add_parser(
        "check", help="Run required checks from .vibecode/checks/required_checks.yaml."
    )
    check_parser.add_argument(
        "repo_root",
        nargs="?",
        default=".",
        help="Repository root directory (default: current directory).",
    )

    # handoff-check
    handoff_parser = subparsers.add_parser(
        "handoff-check",
        help="Validate handoff files (NOW/NEXT/BLOCKERS) and check architecture-change recording.",
    )
    handoff_parser.add_argument(
        "repo_root",
        nargs="?",
        default=".",
        help="Repository root directory (default: current directory).",
    )
    handoff_parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Write a JSON report to .vibecode/current/handoff_check.json.",
    )

    # run
    run_parser = subparsers.add_parser(
        "run", help="Run an agent session (e.g. OpenCode) against a repository."
    )
    run_parser.add_argument(
        "repo_root",
        nargs="?",
        default=".",
        help="Repository root directory (default: current directory).",
    )
    run_parser.add_argument(
        "--task", default="", help="Task description for the context pack."
    )
    run_parser.add_argument(
        "--platform",
        default="opencode",
        choices=["opencode"],
        help="Target platform (default: opencode).",
    )
    run_parser.add_argument(
        "--profile",
        default=None,
        help="Permission profile name (default: safe).",
    )
    run_parser.add_argument(
        "--allow-dirty",
        action="store_true",
        default=False,
        help="Allow running even with uncommitted changes (warn only, no error).",
    )
    run_parser.add_argument(
        "--no-index",
        action="store_true",
        default=False,
        help="Skip automatic index generation/refres.",
    )

    # run-plan
    run_plan_parser = subparsers.add_parser(
        "run-plan",
        help="Assemble a run plan for an agent without launching it.",
    )
    run_plan_parser.add_argument(
        "repo_root",
        nargs="?",
        default=".",
        help="Repository root directory (default: current directory).",
    )
    run_plan_parser.add_argument(
        "--task", default="", help="Task description for the context pack."
    )
    run_plan_parser.add_argument(
        "--platform",
        default="opencode",
        choices=["opencode"],
        help="Target platform (default: opencode).",
    )
    run_plan_parser.add_argument(
        "--profile",
        default=None,
        help="Permission profile name (default: safe).",
    )
    run_plan_parser.add_argument(
        "--allow-dirty",
        action="store_true",
        default=False,
        help="Allow running even with uncommitted changes (warn only, no error).",
    )

    # history
    history_parser = subparsers.add_parser(
        "history", help="Manage durable history summaries."
    )
    history_sub = history_parser.add_subparsers(
        dest="history_subcommand", metavar="SUBCOMMAND"
    )

    # history new
    history_new_parser = history_sub.add_parser(
        "new", help="Create a new history summary for a task."
    )
    history_new_parser.add_argument(
        "--repo",
        default=None,
        help="Repository root directory (default: current directory).",
    )
    history_new_parser.add_argument(
        "--task", default="", help="Short description of the task or change."
    )
    history_new_parser.add_argument(
        "--author", default="", help="Author name or email."
    )
    history_new_parser.add_argument(
        "--changed-files",
        default="",
        help="Markdown list of changed files and why.",
    )
    history_new_parser.add_argument(
        "--behavior-changed",
        default="",
        help="Description of behavioural impact.",
    )
    history_new_parser.add_argument(
        "--tests-run",
        default="",
        help="Test results summary.",
    )
    history_new_parser.add_argument(
        "--decisions",
        default="",
        help="Key architectural or design choices.",
    )
    history_new_parser.add_argument(
        "--follow-up",
        default="",
        help="Open items or next steps.",
    )

    # export-agents
    export_agents_parser = subparsers.add_parser(
        "export-agents", help="Export agent instructions to AGENTS.md."
    )
    export_agents_parser.add_argument(
        "repo_root",
        nargs="?",
        default=".",
        help="Repository root directory (default: current directory).",
    )
    export_agents_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite AGENTS.md even if it is not Vibecode-managed.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)
    debug: bool = getattr(args, "debug", False)

    if args.command is None:
        parser.print_help()
        return 0

    try:
        return _dispatch(args, parser)
    except PermissionError as exc:
        print(f"Error: Permission denied – {exc}", file=sys.stderr)
        if debug:
            import traceback
            traceback.print_exc()
        return 1
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        if debug:
            import traceback
            traceback.print_exc()
        return 1
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        if debug:
            import traceback
            traceback.print_exc()
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        if debug:
            import traceback
            traceback.print_exc()
        else:
            print("Hint: rerun with --debug for full details.", file=sys.stderr)
        return 1


def _dispatch(args, parser) -> int:
    from vibecode.paths import normalise_root

    if args.command == "init":
        args.repo_root = normalise_root(args.repo_root)
        from vibecode.project import cmd_init
        return cmd_init(args)

    if args.command == "index":
        args.repo_root = normalise_root(args.repo_root)
        _require_root_exists(args.repo_root)
        from vibecode.indexer import cmd_index
        return cmd_index(args)

    if args.command == "context":
        from vibecode.context import cmd_context
        return cmd_context(args)

    if args.command == "map":
        args.repo_root = normalise_root(args.repo_root)
        _require_root_exists(args.repo_root)
        from vibecode.project import cmd_map
        return cmd_map(args)

    if args.command == "validate":
        args.repo_root = normalise_root(args.repo_root)
        _require_root_exists(args.repo_root)
        from vibecode.validation import cmd_validate
        return cmd_validate(args)

    if args.command == "guard":
        args.repo_root = normalise_root(args.repo_root)
        _require_root_exists(args.repo_root)
        from vibecode.guard import cmd_guard
        return cmd_guard(args)

    if args.command == "check":
        args.repo_root = normalise_root(args.repo_root)
        _require_root_exists(args.repo_root)
        from vibecode.check import cmd_check
        return cmd_check(args)

    if args.command == "handoff-check":
        args.repo_root = normalise_root(args.repo_root)
        _require_root_exists(args.repo_root)
        from vibecode.handoff import cmd_handoff_check
        return cmd_handoff_check(args)

    if args.command == "run":
        args.repo_root = normalise_root(args.repo_root)
        _require_root_exists(args.repo_root)
        from vibecode.run import cmd_run
        return cmd_run(args)

    if args.command == "run-plan":
        args.repo_root = normalise_root(args.repo_root)
        _require_root_exists(args.repo_root)
        from vibecode.run_plan import cmd_run_plan
        return cmd_run_plan(args)

    if args.command == "history":
        from vibecode.history import cmd_history
        return cmd_history(args)

    if args.command == "export-agents":
        args.repo_root = normalise_root(args.repo_root)
        _require_root_exists(args.repo_root)
        from vibecode.context.agents_export import cmd_export_agents
        return cmd_export_agents(args)

    parser.print_help()
    return 1


def _require_root_exists(root: Path) -> None:
    if not root.is_dir():
        raise FileNotFoundError(f"Repository root does not exist: {root}")


if __name__ == "__main__":
    sys.exit(main())
