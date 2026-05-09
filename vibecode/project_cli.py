"""CLI handlers for ``vibecode project`` subcommands."""

from __future__ import annotations

import sys
from pathlib import Path

from vibecode.registry import ProjectEntry, ProjectRegistry


def _registry() -> ProjectRegistry:
    """Return a ProjectRegistry using the VIBECODE_HOME or default path."""
    return ProjectRegistry()


def cmd_project(args) -> int:
    """Dispatch project subcommands: add, use, list, remove, current."""
    sub = getattr(args, "project_subcommand", None)

    if sub == "add":
        return _cmd_project_add(args)
    if sub == "use":
        return _cmd_project_use(args)
    if sub == "list":
        return _cmd_project_list(args)
    if sub == "remove":
        return _cmd_project_remove(args)
    if sub == "current":
        return _cmd_project_current(args)

    return 1


def _cmd_project_add(args) -> int:
    name = args.name
    path = str(Path(args.path).resolve())

    reg = _registry()
    existing = reg.get(name)
    if existing is not None:
        print(
            f"Error: project {name!r} already exists (path={existing.path}). "
            "Remove it first or use a different name.",
            file=sys.stderr,
        )
        return 1

    entry = ProjectEntry(name=name, path=path)
    reg.add(entry)
    print(f"Added project {name!r} at {path}")
    return 0


def _cmd_project_use(args) -> int:
    name = args.name
    reg = _registry()

    try:
        reg.set_active(name)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Active project set to {name!r}")
    return 0


def _cmd_project_list(args) -> int:
    reg = _registry()
    entries = reg.load()
    if not entries:
        print("No projects registered.")
        return 0

    active = reg._active_name()
    for e in entries:
        marker = " (*)" if e.name == active else ""
        print(f"  {e.name}{marker}  {e.path}")
    return 0


def _cmd_project_remove(args) -> int:
    name = args.name
    reg = _registry()

    active = reg._active_name()
    if active == name:
        reg._set_active_name(None)

    if reg.remove(name):
        print(f"Removed project {name!r}")
        return 0
    else:
        print(f"Error: project {name!r} not found", file=sys.stderr)
        return 1


def _cmd_project_current(args) -> int:
    reg = _registry()
    active = reg._active_name()
    if active is None:
        print("No active project.")
        return 0

    entry = reg.get(active)
    if entry is None:
        print(f"Active project {active!r} is not in registry.", file=sys.stderr)
        return 1

    print(f"{active}  {entry.path}")
    return 0