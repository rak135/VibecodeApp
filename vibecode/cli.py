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

    # inventory
    inventory_parser = subparsers.add_parser(
        "inventory",
        help="Scan repository and write context cards and risk report.",
        description=(
            "Scan the repository and write two index files under .vibecode/index/:\n"
            "  file_inventory.json — every Python file with a context card (purpose,\n"
            "    symbols, snippet, facts, heuristics) and basic metadata for all files.\n"
            "  risk_report.json — per-file risk level, reasons, and heuristics.\n\n"
            "Run this before 'vibecode dashboard' or 'vibecode serve'."
        ),
    )
    inventory_parser.add_argument(
        "repo_root",
        nargs="?",
        default=None,
        help="Repository root directory (default: active project from registry).",
    )

    # index
    index_parser = subparsers.add_parser("index", help="Scan and index repository files.")
    index_parser.add_argument(
        "repo_root",
        nargs="?",
        default=None,
        help="Repository root directory (default: active project from registry).",
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
        help="Repository root directory (default: active project from registry).",
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
        default=None,
        help="Repository root directory (default: active project from registry).",
    )

    # validate
    validate_parser = subparsers.add_parser(
        "validate", help="Validate .vibecode project artifacts."
    )
    validate_parser.add_argument(
        "repo_root",
        nargs="?",
        default=None,
        help="Repository root directory (default: active project from registry).",
    )

    # guard
    guard_parser = subparsers.add_parser(
        "guard", help="Check git diff against guard rules."
    )
    guard_parser.add_argument(
        "repo_root",
        nargs="?",
        default=None,
        help="Repository root directory (default: active project from registry).",
    )
    guard_parser.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help="Treat warnings as hard failures (non-zero exit).",
    )
    guard_parser.add_argument(
        "--task",
        default="",
        help="Task description for contextualizing guard findings.",
    )

    # check
    check_parser = subparsers.add_parser(
        "check", help="Run required checks from .vibecode/checks/required_checks.yaml."
    )
    check_parser.add_argument(
        "repo_root",
        nargs="?",
        default=None,
        help="Repository root directory (default: active project from registry).",
    )

    # handoff-check
    handoff_parser = subparsers.add_parser(
        "handoff-check",
        help="Validate handoff files (NOW/NEXT/BLOCKERS) and check architecture-change recording.",
    )
    handoff_parser.add_argument(
        "repo_root",
        nargs="?",
        default=None,
        help="Repository root directory (default: active project from registry).",
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
        default=None,
        help="Repository root directory (default: active project from registry).",
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
        help="Advisory permission profile name (validated + recorded; does not constrain OpenCode). Default: safe.",
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
        help="Skip automatic index generation/refresh.",
    )
    run_parser.add_argument(
        "--guard-mode",
        default="advisory",
        choices=["advisory", "strict"],
        dest="guard_mode",
        help=(
            "Guard enforcement mode (default: advisory). "
            "advisory: guard findings are logged with full severity as 'needs_review' "
            "but do not block the run. "
            "strict: guard errors cause run failure and a non-zero exit code."
        ),
    )

    # run-plan -- keeps "." default (no registry fallback)
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
        help="Advisory permission profile name (validated + recorded; does not constrain OpenCode). Default: safe.",
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

    # project
    project_parser = subparsers.add_parser(
        "project", help="Manage registered projects by name."
    )
    project_sub = project_parser.add_subparsers(
        dest="project_subcommand", metavar="SUBCOMMAND"
    )

    # project add
    project_add_parser = project_sub.add_parser(
        "add", help="Register a project by name and path."
    )
    project_add_parser.add_argument("name", help="Project name.")
    project_add_parser.add_argument(
        "path", help="Repository root directory for the project."
    )

    # project use
    project_use_parser = project_sub.add_parser(
        "use", help="Set the active project by name."
    )
    project_use_parser.add_argument("name", help="Project name to activate.")

    # project list
    project_sub.add_parser("list", help="List all registered projects.")

    # project remove
    project_remove_parser = project_sub.add_parser(
        "remove", help="Remove a registered project by name."
    )
    project_remove_parser.add_argument("name", help="Project name to remove.")

    # project current
    project_sub.add_parser("current", help="Show the currently active project.")

    # serve
    serve_parser = subparsers.add_parser(
        "serve",
        help="Start the vibecode MCP server (stdio transport) for use with OpenCode.",
        description=(
            "Start a Model Context Protocol (MCP) server over stdio that exposes three tools\n"
            "for coding agents such as OpenCode:\n\n"
            "  get_file_card <file_path>   — purpose, symbols, snippet, facts, and heuristics\n"
            "                                for a single file\n"
            "  find_symbol <symbol_name>   — locations of a function/class across all files\n"
            "  list_high_risk              — all files flagged as high-risk or containing\n"
            "                                high-severity heuristics\n\n"
            "The server reads .vibecode/index/file_inventory.json and risk_report.json.\n"
            "Run 'vibecode inventory' first to generate those files.\n\n"
            "When the server starts, it prints a ready-to-paste JSON snippet to stderr\n"
            "showing how to add it to your OpenCode MCP configuration.\n\n"
            "MCP tool events are written to the path set by VIBECODE_MCP_EVENTS_LOG,\n"
            "falling back to .vibecode/logs/mcp_events.jsonl. Set the\n"
            "VIBECODE_SESSION_ID environment variable to correlate events with an\n"
            "enclosing vibecode run session. Without it, the session defaults to\n"
            "\"mcp-server\".\n"
            "vibecode run and vibecode monitor set both environment variables\n"
            "automatically for per-run MCP correlation.\n\n"
            "Example OpenCode setup (~/.config/opencode/config.json or opencode.json):\n"
            '  { "mcpServers": { "vibecode": { "command": "vibecode",\n'
            '      "args": ["serve", "/path/to/repo"] } } }'
        ),
    )
    serve_parser.add_argument(
        "repo_root",
        nargs="?",
        default=None,
        help="Repository root directory (default: active project from registry).",
    )

    # dashboard
    dashboard_parser = subparsers.add_parser(
        "dashboard",
        help="Launch the interactive TUI context-card dashboard.",
        description=(
            "Launch a terminal-based interactive dashboard showing context cards for all\n"
            "indexed Python files in the repository.\n\n"
            "The main view is a table of files with their purpose and symbol count.\n"
            "Press Enter on any row to open a detail panel showing:\n"
            "  - Purpose (module docstring)\n"
            "  - Symbols list (functions and classes with kind and line number)\n"
            "  - Facts (TODO/FIXME comments, unsafe permission patterns)\n"
            "  - Heuristics (high-param-count, suspicious-name warnings)\n"
            "  - Content snippet\n\n"
            "The footer shows total file count, card count, and number of high-risk items.\n\n"
            "Key bindings: Enter — open detail view  |  Escape / Q — go back or quit\n\n"
            "Requires 'vibecode inventory' to have been run first."
        ),
    )
    dashboard_parser.add_argument(
        "repo_root",
        nargs="?",
        default=None,
        help="Repository root directory (default: active project from registry).",
    )

    # monitor
    monitor_parser = subparsers.add_parser(
        "monitor",
        help="Run an agent session with a live TUI showing agent output and Vibecode events.",
        description=(
            "Launch a split-pane terminal monitor that runs an OpenCode session and\n"
            "streams output live:\n\n"
            "  Left pane:  agent stdout/stderr (raw OpenCode output).\n"
            "  Right pane: Vibecode event spine (lifecycle, guard, checks, handoff).\n"
            "  Status bar: agent status, guard status, checks status, run artifact path.\n\n"
            "Note: this is a streaming-output monitor (text mode), not a PTY.  For\n"
            "full interactive terminal control, run OpenCode directly.\n\n"
            "Press Q to close the monitor (running agent process behavior is not managed)."
        ),
    )
    monitor_parser.add_argument(
        "repo_root",
        nargs="?",
        default=None,
        help="Repository root directory (default: active project from registry).",
    )
    monitor_parser.add_argument(
        "--task", default="", help="Task description for the context pack."
    )
    monitor_parser.add_argument(
        "--platform",
        default="opencode",
        choices=["opencode"],
        help="Target platform (default: opencode).",
    )
    monitor_parser.add_argument(
        "--profile",
        default=None,
        help="Advisory permission profile name (default: safe).",
    )
    monitor_parser.add_argument(
        "--allow-dirty",
        action="store_true",
        default=False,
        help="Allow running even with uncommitted changes (warn only, no error).",
    )
    monitor_parser.add_argument(
        "--no-index",
        action="store_true",
        default=False,
        help="Skip automatic index generation/refresh.",
    )
    monitor_parser.add_argument(
        "--guard-mode",
        default="advisory",
        choices=["advisory", "strict"],
        dest="guard_mode",
        help="Guard enforcement mode (default: advisory).",
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

    # runs
    runs_parser = subparsers.add_parser(
        "runs",
        help="Inspect previous observable run sessions.",
        description=(
            "Inspect run sessions recorded under .vibecode/runs/.\n\n"
            "Sub-commands:\n"
            "  list [--repo REPO]                    — list recent run session IDs\n"
            "  show <session_id> [--repo REPO]        — show summary for a run\n"
            "                   [--events]            — also replay events in order\n\n"
            "Each run directory contains: summary.json, events.jsonl, guard_report.*,\n"
            "checks_report.json, handoff_report.*, agent_stdout.log, agent_stderr.log."
        ),
    )
    runs_sub = runs_parser.add_subparsers(dest="runs_subcommand", metavar="SUBCOMMAND")

    # runs list
    runs_list_parser = runs_sub.add_parser("list", help="List recent run session IDs.")
    runs_list_parser.add_argument(
        "--repo",
        default=None,
        help="Repository root directory (default: active project from registry).",
    )

    # runs show
    runs_show_parser = runs_sub.add_parser(
        "show", help="Show summary for a specific run session."
    )
    runs_show_parser.add_argument("session_id", help="Run session ID to inspect.")
    runs_show_parser.add_argument(
        "--repo",
        default=None,
        help="Repository root directory (default: active project from registry).",
    )
    runs_show_parser.add_argument(
        "--events",
        action="store_true",
        default=False,
        help="Replay events from events.jsonl in chronological order.",
    )

    return parser


def _resolve_repo_root(args, allow_fallback: bool = True) -> Path:
    """Resolve the repo root from args, falling back to the active project in the registry.

    Priority:
    1. Explicit ``repo_root`` argument from CLI, including ``"."``.
    2. Active project from the registry (if *allow_fallback* is True).

    Raises ``FileNotFoundError`` with a clear message if no repo can be resolved.

    Returns an absolute, resolved, forward-slash :class:`~pathlib.Path`.
    """
    from vibecode.paths import normalise_root
    from vibecode.registry import ProjectRegistry

    raw = getattr(args, "repo_root", None)
    if raw is not None:
        return normalise_root(raw)

    # The user did not explicitly pass a repo root.
    if not allow_fallback:
        # Commands whose semantics already default to cwd (".").
        return normalise_root(".")

    # Try the registry's active project.
    reg = ProjectRegistry()
    try:
        resolved = reg.pick(None)  # None -> active project
    except FileNotFoundError:
        raise FileNotFoundError(
            "No repository root given and no active project. "
            "Either pass a repo path or run 'vibecode project use <name>'."
        ) from None

    return normalise_root(str(resolved))


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
        print(f"Error: Permission denied - {exc}", file=sys.stderr)
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

    if args.command == "inventory":
        args.repo_root = _resolve_repo_root(args)
        _require_root_exists(args.repo_root)
        from vibecode.indexer import cmd_inventory
        return cmd_inventory(args)

    if args.command == "index":
        args.repo_root = _resolve_repo_root(args)
        _require_root_exists(args.repo_root)
        from vibecode.indexer import cmd_index
        return cmd_index(args)

    if args.command == "context":
        from vibecode.context import cmd_context
        return cmd_context(args)

    if args.command == "map":
        args.repo_root = _resolve_repo_root(args)
        _require_root_exists(args.repo_root)
        from vibecode.project import cmd_map
        return cmd_map(args)

    if args.command == "validate":
        args.repo_root = _resolve_repo_root(args)
        _require_root_exists(args.repo_root)
        from vibecode.validation import cmd_validate
        return cmd_validate(args)

    if args.command == "guard":
        args.repo_root = _resolve_repo_root(args)
        _require_root_exists(args.repo_root)
        from vibecode.guard import cmd_guard
        return cmd_guard(args)

    if args.command == "check":
        args.repo_root = _resolve_repo_root(args)
        _require_root_exists(args.repo_root)
        from vibecode.check import cmd_check
        return cmd_check(args)

    if args.command == "handoff-check":
        args.repo_root = _resolve_repo_root(args)
        _require_root_exists(args.repo_root)
        from vibecode.handoff import cmd_handoff_check
        return cmd_handoff_check(args)

    if args.command == "run":
        args.repo_root = _resolve_repo_root(args)
        _require_root_exists(args.repo_root)
        from vibecode.run import cmd_run
        return cmd_run(args)

    if args.command == "run-plan":
        # run-plan keeps its original "." default (no registry fallback).
        args.repo_root = normalise_root(args.repo_root)
        _require_root_exists(args.repo_root)
        from vibecode.run_plan import cmd_run_plan
        return cmd_run_plan(args)

    if args.command == "history":
        from vibecode.history import cmd_history
        return cmd_history(args)

    if args.command == "serve":
        args.repo_root = _resolve_repo_root(args)
        _require_root_exists(args.repo_root)
        from vibecode.mcp_server import cmd_serve
        return cmd_serve(args)

    if args.command == "dashboard":
        args.repo_root = _resolve_repo_root(args)
        _require_root_exists(args.repo_root)
        from vibecode.data_loader import load_project_data
        project = load_project_data(args.repo_root)
        if project.inventory_missing or project.risk_report_missing:
            print(
                "Hint: index files are missing. Run 'vibecode inventory' to generate them.",
                file=sys.stderr,
            )
        from vibecode.tui_app import VibecodeTUI
        VibecodeTUI(repo_root=args.repo_root).run()
        return 0

    if args.command == "monitor":
        args.repo_root = _resolve_repo_root(args)
        _require_root_exists(args.repo_root)
        from vibecode.monitor_app import cmd_monitor
        return cmd_monitor(args)

    if args.command == "export-agents":
        args.repo_root = normalise_root(args.repo_root)
        _require_root_exists(args.repo_root)
        from vibecode.context.agents_export import cmd_export_agents
        return cmd_export_agents(args)

    if args.command == "runs":
        from vibecode.show_run import cmd_runs
        return cmd_runs(args)

    if args.command == "project":
        from vibecode.project_cli import cmd_project
        return cmd_project(args)

    parser.print_help()
    return 1


def _require_root_exists(root: Path) -> None:
    if not root.is_dir():
        raise FileNotFoundError(f"Repository root does not exist: {root}")


if __name__ == "__main__":
    sys.exit(main())
