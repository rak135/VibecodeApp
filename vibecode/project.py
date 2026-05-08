"""Project-level commands: init and map."""

from __future__ import annotations

import sys
from pathlib import Path

# Directories created as empty generated artifacts (always safe to re-create).
_GENERATED_DIRS = [
    ".vibecode/index",
    ".vibecode/current",
    ".vibecode/logs/index_runs",
]


def _project_yaml(project_id: str, project_name: str) -> str:
    return (
        "# vibecode project configuration\n"
        "# schema: vibecode/project/v1\n"
        "\n"
        "project:\n"
        f"  id: {project_id}\n"
        f"  name: {project_name}\n"
        "  root: .\n"
        "\n"
        "indexing:\n"
        "  include:\n"
        '    - "**/*.py"\n'
        '    - "**/*.md"\n'
        '    - "**/*.yaml"\n'
        '    - "**/*.json"\n'
        "  exclude:\n"
        '    - ".git/**"\n'
        '    - "__pycache__/**"\n'
        '    - "*.pyc"\n'
        '    - ".vibecode/index/**"\n'
        '    - ".vibecode/current/**"\n'
        '    - ".vibecode/logs/**"\n'
        "\n"
        "protected_paths:\n"
        '  - ".vibecode/architecture/**"\n'
        '  - ".vibecode/handoff/**"\n'
        '  - ".vibecode/history/**"\n'
        "\n"
        "risk_rules: []\n"
        "\n"
        "required_checks:\n"
        "  - lint\n"
        "  - tests\n"
    )


def _file_templates(project_id: str, project_name: str) -> dict[str, str]:
    return {
        ".vibecode/project.yaml": _project_yaml(project_id, project_name),
        ".vibecode/architecture/INVARIANTS.md": (
            f"# {project_name} \u2013 Architectural Invariants\n\n"
            "<!-- Document non-negotiable constraints here. -->\n"
        ),
        ".vibecode/architecture/STRUCTURE.md": (
            f"# {project_name} \u2013 Repository Structure\n\n"
            "<!-- Document the top-level directory layout and conventions here. -->\n"
        ),
        ".vibecode/architecture/MODULE_BOUNDARIES.md": (
            f"# {project_name} \u2013 Module Boundaries\n\n"
            "<!-- Define module ownership and allowed dependencies here. -->\n"
        ),
        ".vibecode/architecture/PROTECTED_AREAS.md": (
            f"# {project_name} \u2013 Protected Areas\n\n"
            "<!-- List paths that require extra review before modification. -->\n"
        ),
        ".vibecode/handoff/NOW.md": (
            "# Now\n\n<!-- What is being worked on right now. -->\n"
        ),
        ".vibecode/handoff/NEXT.md": (
            "# Next\n\n<!-- What should be tackled next. -->\n"
        ),
        ".vibecode/handoff/BLOCKERS.md": (
            "# Blockers\n\n<!-- Current blockers preventing progress. -->\n"
        ),
        ".vibecode/history/README.md": (
            f"# {project_name} \u2013 Change History\n\n"
            "<!-- Index of significant changes and decisions. -->\n"
        ),
    }


def cmd_init(args) -> int:
    repo_root = Path(args.repo_root).resolve()
    force: bool = getattr(args, "force", False)
    project_id = getattr(args, "project_id", None) or repo_root.name.lower().replace(" ", "_")
    project_name = getattr(args, "project_name", None) or repo_root.name

    print(
        f"Initializing vibecode project '{project_name}' (id={project_id}) in {repo_root}",
        file=sys.stderr,
    )

    for rel_dir in _GENERATED_DIRS:
        (repo_root / Path(rel_dir)).mkdir(parents=True, exist_ok=True)

    templates = _file_templates(project_id, project_name)
    skipped: list[str] = []

    for rel_path, content in templates.items():
        target = repo_root / Path(rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and not force:
            skipped.append(rel_path)
            continue
        target.write_text(content, encoding="utf-8")
        print(f"  created {rel_path}", file=sys.stderr)

    if skipped:
        print(
            f"  skipped {len(skipped)} existing file(s) (use --force to overwrite): "
            + ", ".join(skipped),
            file=sys.stderr,
        )

    return 0


def cmd_map(args) -> int:
    repo_root = Path(args.repo_root).resolve()
    print(f"Repository map for {repo_root}", file=sys.stderr)

    include: list[str] = []
    exclude: list[str] = []
    vibecode_dir = repo_root / ".vibecode"

    if (vibecode_dir / "project.yaml").exists():
        try:
            from vibecode.config import load_config

            cfg = load_config(vibecode_dir)
            include = cfg.include
            exclude = cfg.exclude
        except Exception as exc:  # noqa: BLE001
            print(f"Warning: could not load project.yaml: {exc}", file=sys.stderr)

    from vibecode.indexer import scan
    from vibecode.indexer.classifier import classify
    from vibecode.indexer.repo_tree import write_repo_tree

    files = scan(repo_root, include=include, exclude=exclude)
    records = [classify(f.path, f.size) for f in files]

    output_path = vibecode_dir / "current" / "repo_tree.md"
    write_repo_tree(repo_root, records, output_path)

    tree_content = output_path.read_text(encoding="utf-8")
    print(tree_content)
    print(
        f"  repo_tree.md written to {output_path.relative_to(repo_root).as_posix()}",
        file=sys.stderr,
    )
    return 0
