"""Project-level commands: init and map."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from vibecode.config import render_protected_paths_yaml
from vibecode.permissions import PROFILES, profile_path, write_profile

# Directories created as empty generated artifacts (always safe to re-create).
_GENERATED_DIRS = [
    ".vibecode/index",
    ".vibecode/current",
    ".vibecode/logs/index_runs",
    ".vibecode/checks",
    ".vibecode/agents",
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


def _required_checks_yaml(repo_root: Path | None = None) -> str:
    """Generate required_checks.yaml with checks appropriate for the target repo."""
    if repo_root is not None:
        checks = _detect_default_checks(repo_root)
    else:
        checks = _detect_default_checks(None)

    lines = [
        "# vibecode required checks",
        "# schema: vibecode/required-checks/v1",
        "",
        "# Generated during `vibecode init`. Replace with your real checks.",
        "# Each check must have: name, command, and required (true/false).",
        "",
        "checks:",
    ]
    for check in checks:
        name = check['name']
        command = check['command']
        required = str(check.get('required', True)).lower()
        if ":" in name or "#" in name or name.startswith("'"):
            name = f"\"{name}\""
        if ":" in command or "#" in command:
            command = f"\"{command}\""
        lines.append(f"  - name: {name}")
        lines.append(f"    command: {command}")
        lines.append(f"    required: {required}")
        lines.append("")
    return "\n".join(lines) + "\n"


def _detect_default_checks(repo_root: Path | None) -> list[dict]:
    """Detect appropriate default required checks for the target repository.

    Returns a list of check dicts with keys: name, command, required.
    """
    if repo_root is None:
        return _vibecode_app_default_checks()

    root = repo_root.resolve()

    # Is this the VibecodeApp repo itself?
    if (root / "vibecode" / "__init__.py").exists() or (root / "vibecode" / "cli.py").exists():
        return _vibecode_app_default_checks()

    checks: list[dict] = []

    # Python / pytest detection
    has_python = any(root.glob("*.py")) or any(root.glob("**/*.py"))
    has_pyproject = (root / "pyproject.toml").exists()
    has_pytest = False
    if has_pyproject:
        try:
            content = (root / "pyproject.toml").read_text(encoding="utf-8")
            has_pytest = "pytest" in content or "[tool.pytest" in content
        except OSError:
            pass
    if has_python and (has_pyproject or has_pytest or (root / "tests").is_dir()):
        checks.append({"name": "unit tests", "command": "python -m pytest", "required": True})

    # Node.js / npm detection
    has_package_json = (root / "package.json").exists()
    if has_package_json:
        try:
            pkg = json.loads((root / "package.json").read_text(encoding="utf-8"))
            if isinstance(pkg, dict):
                scripts = pkg.get("scripts", {})
                if isinstance(scripts, dict) and "test" in scripts:
                    checks.append({"name": "npm test", "command": "npm test", "required": True})
                elif "lint" in scripts:
                    checks.append({"name": "lint", "command": "npm run lint", "required": True})
        except (OSError, ValueError):
            pass

    # If we found checks, return them
    if checks:
        return checks

    # Fallback: placeholder that tells user to fill in
    return [
        {
            "name": "TODO: replace with your tests",
            "command": "echo 'TODO: add real test command'",
            "required": True,
        },
    ]


def _vibecode_app_default_checks() -> list[dict]:
    """Return VibecodeApp-specific default checks (for self-dogfood)."""
    return [
        {"name": "unit tests", "command": "python -m pytest", "required": True},
        {"name": "cli help", "command": "python -m vibecode.cli --help", "required": True},
        {"name": "index command help", "command": "python -m vibecode.cli index --help", "required": True},
        {"name": "context command help", "command": "python -m vibecode.cli context --help", "required": True},
    ]


def _file_templates(project_id: str, project_name: str, repo_root: Path | None = None) -> dict[str, str]:  # noqa: ARG001
    marker = TEMPLATE_UNFILLED_MARKER
    return {
        ".vibecode/project.yaml": _project_yaml(project_id, project_name),
        ".vibecode/checks/required_checks.yaml": _required_checks_yaml(repo_root),
        ".vibecode/checks/protected_paths.yaml": render_protected_paths_yaml(),
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
            "<!-- This file records significant changes with full context.\n"
            "     Every committed summary must include: Task, Changed files,\n"
            "     Behavior changed, Tests run, Decisions, Follow-up. -->\n"
        ),
        ".vibecode/index/README.md": (
            f"# {project_name} \u2013 Vibecode Index Policy\n\n"
            "This directory contains Vibecode index metadata.\n\n"
            "Human-maintained files:\n"
            "- README.md\n"
            "- schema.json\n\n"
            "Generated files are derived runtime artifacts and should be "
            "regenerated with `vibecode index` instead of edited by hand.\n"
        ),
        ".vibecode/index/schema.json": (
            json.dumps(
                {
                    "$schema": "vibecode/index-source-truth/v1",
                    "description": (
                        "Human-maintained marker for Vibecode index source-truth "
                        "files. Generated index outputs are not source truth."
                    ),
                    "human_maintained": ["README.md", "schema.json"],
                    "generated_outputs": [
                        "file_inventory.json",
                        "symbol_map.json",
                        "dependency_map.json",
                        "test_map.json",
                        "entrypoints.md",
                        "risky_files.md",
                        "repo_tree.generated.md",
                    ],
                },
                indent=2,
            )
            + "\n"
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

    templates = _file_templates(project_id, project_name, repo_root)
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

    # Create agent permission profiles (never overwrite human-edited profiles).
    profile_force = getattr(args, "force", False)
    for profile_name, profile_data in PROFILES.items():
        if write_profile(repo_root, profile_name, profile_data, force=profile_force):
            print(f"  created {profile_path(profile_name)}", file=sys.stderr)
        else:
            skipped.append(profile_path(profile_name))

    return 0


def cmd_map(args) -> int:
    repo_root = Path(args.repo_root).resolve()
    vibecode_dir = repo_root / ".vibecode"
    last_index_path = vibecode_dir / "current" / "last_index.json"

    if not last_index_path.exists():
        print(
            "No index found. Run `vibecode index` first.",
            file=sys.stderr,
        )
        return 1

    try:
        record = json.loads(last_index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"Error reading index: {exc}", file=sys.stderr)
        return 1

    counts = record.get("counts", {})
    warnings = record.get("warnings", [])
    project_id = record.get("project_id", repo_root.name)
    root = record.get("root", str(repo_root))
    started_at = record.get("started_at", "")

    project_name = project_id
    project_yaml = vibecode_dir / "project.yaml"
    if project_yaml.exists():
        try:
            from vibecode.config import load_config
            cfg = load_config(vibecode_dir)
            project_name = cfg.project_name
        except Exception:  # noqa: BLE001
            pass

    languages: list[str] = []
    high_risk_count = 0
    inventory_path = vibecode_dir / "index" / "file_inventory.json"
    if inventory_path.exists():
        try:
            inv = json.loads(inventory_path.read_text(encoding="utf-8"))
            lang_set: set[str] = set()
            for f in inv.get("files", []):
                lang = f.get("language", "unknown")
                if lang not in ("unknown", ""):
                    lang_set.add(lang)
                if f.get("risk_level") == "high":
                    high_risk_count += 1
            languages = sorted(lang_set)
        except (json.JSONDecodeError, OSError):
            pass

    entrypoint_count = 0
    try:
        from vibecode.indexer.entrypoints import detect_entrypoints
        ep = detect_entrypoints(repo_root)
        entrypoint_count = sum(
            len(ep.get(k, []))
            for k in ("backend", "frontend", "cli_scripts", "runtime_config")
        )
    except Exception:  # noqa: BLE001
        pass

    ts = started_at[:19].replace("T", " ") if started_at else "unknown"

    print(f"Project:     {project_name}  (id: {project_id})")
    print(f"Root:        {root}")
    print(f"Languages:   {', '.join(languages) or 'none detected'}")
    print(f"Files:       {counts.get('files', 0)}")
    print(f"Symbols:     {counts.get('symbols', 0)}")
    print(f"Tests:       {counts.get('tests', 0)}")
    print(f"High-risk:   {high_risk_count}")
    print(f"Entrypoints: {entrypoint_count}")
    print(f"Indexed:     {ts} UTC")
    if warnings:
        print(f"Warnings ({len(warnings)}):")
        for w in warnings:
            print(f"  ! {w}")
    else:
        print("Warnings:    none")

    return 0
