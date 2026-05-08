"""Command-line interface for vibecode."""

from __future__ import annotations

import argparse
import sys


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vibecode",
        description="Local repository architecture map and context-pack CLI.",
    )
    parser.add_argument("--version", action="version", version="vibecode 0.1.0")

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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "init":
        from vibecode.project import cmd_init
        return cmd_init(args)

    if args.command == "index":
        from vibecode.indexer import cmd_index
        return cmd_index(args)

    if args.command == "context":
        from vibecode.context import cmd_context
        return cmd_context(args)

    if args.command == "map":
        from vibecode.project import cmd_map
        return cmd_map(args)

    if args.command == "validate":
        from vibecode.validation import cmd_validate
        return cmd_validate(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
