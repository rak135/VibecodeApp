"""Project-level commands: init and map."""

from __future__ import annotations

import sys
from pathlib import Path

# Directories created as empty generated artifacts (always safe to re-create).
_GENERATED_DIRS = [
    ".vibecode/index",
    ".vibecode/current",
    ".vibecode/logs/index_runs",
    ".vibecode/checks",
]

# Sentinel embedded in unfilled architecture templates.
# The indexer checks for this marker to emit a validation warning.
# Users should remove this line once they have filled in the file.
TEMPLATE_UNFILLED_MARKER = "<!-- vibecode:unfilled -->"

# Human-maintained architecture files (relative to repo root).
ARCHITECTURE_FILES = [
    ".vibecode/architecture/OVERVIEW.md",
    ".vibecode/architecture/INVARIANTS.md",
    ".vibecode/architecture/STRUCTURE.md",
    ".vibecode/architecture/MODULE_BOUNDARIES.md",
    ".vibecode/architecture/PROTECTED_AREAS.md",
    ".vibecode/architecture/DATA_FLOW.md",
]

DEFAULT_INCLUDE_PATTERNS = [
    "*.py",
    "*.js",
    "*.jsx",
    "*.ts",
    "*.tsx",
    "*.json",
    "*.toml",
    "*.yaml",
    "*.yml",
    "*.md",
    "*.mdx",
    "*.ini",
    "*.cfg",
    "*.env.example",
    "Dockerfile",
    "docker-compose.yml",
    "Makefile",
    "README*",
    "AGENTS.md",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "bun.lockb",
    "pyproject.toml",
    "requirements*.txt",
    "setup.cfg",
    "setup.py",
    "tsconfig*.json",
    "vite.config.*",
    "next.config.*",
    "tailwind.config.*",
    "postcss.config.*",
    "eslint.config.*",
    "prettier.config.*",
]

DEFAULT_EXCLUDE_PATTERNS = [
    ".git/**",
    "node_modules/**",
    ".venv/**",
    "venv/**",
    "__pycache__/**",
    "dist/**",
    "build/**",
    "coverage/**",
    ".pytest_cache/**",
    ".mypy_cache/**",
    ".ruff_cache/**",
    ".vibecode/current/**",
    ".vibecode/runs/**",
    ".vibecode/tmp/**",
    ".vibecode/cache/**",
    ".vibecode/logs/**",
]


def _project_yaml(project_id: str, project_name: str) -> str:
    include = "\n".join(f'    - "{pattern}"' for pattern in DEFAULT_INCLUDE_PATTERNS)
    exclude = "\n".join(f'    - "{pattern}"' for pattern in DEFAULT_EXCLUDE_PATTERNS)
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
        f"{include}\n"
        "  exclude:\n"
        f"{exclude}\n"
        "\n"
        "protected_paths:\n"
        '  - ".vibecode/architecture/**"\n'
        '  - ".vibecode/handoff/**"\n'
        '  - ".vibecode/history/**"\n'
        "\n"
        "risk_rules: []\n"
    )


def _required_checks_yaml() -> str:
    return (
        "# vibecode required checks\n"
        "# schema: vibecode/required-checks/v1\n"
        "\n"
        "checks:\n"
        "  - name: unit tests\n"
        "    command: python -m pytest\n"
        "    required: true\n"
        "\n"
        "  - name: cli help\n"
        "    command: python -m vibecode.cli --help\n"
        "    required: true\n"
        "\n"
        "  - name: index command help\n"
        "    command: python -m vibecode.cli index --help\n"
        "    required: true\n"
        "\n"
        "  - name: context command help\n"
        "    command: python -m vibecode.cli context --help\n"
        "    required: true\n"
    )


def _file_templates(project_id: str, project_name: str) -> dict[str, str]:  # noqa: ARG001
    marker = TEMPLATE_UNFILLED_MARKER
    return {
        ".vibecode/project.yaml": _project_yaml(project_id, project_name),
        ".vibecode/checks/required_checks.yaml": _required_checks_yaml(),
        ".vibecode/architecture/OVERVIEW.md": (
            f"# {project_name} Architecture Overview\n\n"
            f"{marker}\n\n"
            "> **TODO:** Replace this template with project-specific architecture facts.\n"
            "> Remove the unfilled marker when the overview contains project-specific facts.\n\n"
            "## Control layer role\n\n"
            "- Define what this project is and what Vibecode controls.\n"
        ),
        ".vibecode/architecture/INVARIANTS.md": (
            f"# {project_name} \u2013 Architectural Invariants\n\n"
            f"{marker}\n\n"
            "> **TODO:** Replace this template with the non-negotiable rules for this\n"
            "> project. Remove the `<!-- vibecode:unfilled -->` line above when done.\n\n"
            "## Invariants\n\n"
            "<!-- Add one rule per bullet. Each rule should be verifiable.\n"
            "     Example: '- No package may import from a sibling package.' -->\n\n"
            "- \n"
        ),
        ".vibecode/architecture/STRUCTURE.md": (
            f"# {project_name} \u2013 Repository Structure\n\n"
            f"{marker}\n\n"
            "> **TODO:** Document the top-level layout and directory conventions.\n"
            "> Remove the `<!-- vibecode:unfilled -->` line above when done.\n\n"
            "## Top-Level Directories\n\n"
            "<!-- Describe each top-level directory and its purpose.\n"
            "     Example: '- `src/` – Application source code.' -->\n\n"
            "## Conventions\n\n"
            "<!-- Describe naming, file-placement, and structural conventions. -->\n"
        ),
        ".vibecode/architecture/MODULE_BOUNDARIES.md": (
            f"# {project_name} \u2013 Module Boundaries\n\n"
            f"{marker}\n\n"
            "> **TODO:** Define each module's responsibility and the allowed dependency\n"
            "> directions between them. Remove the `<!-- vibecode:unfilled -->` line above when done.\n\n"
            "## Modules\n\n"
            "<!-- List each module/package and its single responsibility.\n"
            "     Example: '- `auth` – Handles authentication and token management.' -->\n\n"
            "## Allowed Dependencies\n\n"
            "<!-- Describe which modules may depend on which others.\n"
            "     Example: '- `api` may import from `auth` and `db`.' -->\n"
        ),
        ".vibecode/architecture/PROTECTED_AREAS.md": (
            f"# {project_name} \u2013 Protected Areas\n\n"
            f"{marker}\n\n"
            "> **TODO:** List concrete files and directories that require extra review\n"
            "> before modification. Remove the `<!-- vibecode:unfilled -->` line above when done.\n\n"
            "## Protected Paths\n\n"
            "<!-- Add project-specific protected paths and why each one is sensitive. -->\n"
        ),
        ".vibecode/architecture/DATA_FLOW.md": (
            f"# {project_name} \u2013 Data Flow\n\n"
            f"{marker}\n\n"
            "> **TODO:** Document how data moves between source code, generated indexes,\n"
            "> context packs, and runtime state.\n"
            "> Remove the `<!-- vibecode:unfilled -->` line above when done.\n\n"
            "## Flows\n\n"
            "<!-- List concrete flows. Example: 'index reads source files and writes generated indexes.' -->\n"
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

    vibecode_dir = repo_root / ".vibecode"
    output_path = vibecode_dir / "index" / "repo_tree.generated.md"

    if not output_path.exists():
        print(
            "No generated repo tree found. Run `vibecode index` first.",
            file=sys.stderr,
        )
        return 1

    tree_content = output_path.read_text(encoding="utf-8")
    print(tree_content)
    return 0
