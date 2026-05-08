"""Entrypoint detection and entrypoints.md generator for vibecode."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class _Entry:
    path: str
    description: str


@dataclass
class _Script:
    name: str
    target: str
    source: str


# ---------------------------------------------------------------------------
# Candidate tables
# ---------------------------------------------------------------------------

_PY_BACKEND_CANDIDATES: list[tuple[str, str]] = [
    ("main.py", "Python application entry point"),
    ("app.py", "Python application / WSGI entry point"),
    ("wsgi.py", "WSGI server entry point"),
    ("asgi.py", "ASGI server entry point"),
    ("manage.py", "Django management entry point"),
]

_FE_CANDIDATES: list[tuple[str, str]] = [
    ("src/main.tsx", "React/TypeScript Vite entry point"),
    ("src/main.jsx", "React/JavaScript Vite entry point"),
    ("src/main.ts", "TypeScript entry point"),
    ("src/main.js", "JavaScript entry point"),
    ("src/index.tsx", "React/TypeScript entry point"),
    ("src/index.jsx", "React/JavaScript entry point"),
    ("src/App.tsx", "React root component"),
    ("src/App.jsx", "React root component"),
    ("vite.config.ts", "Vite build configuration"),
    ("vite.config.js", "Vite build configuration"),
    ("next.config.js", "Next.js configuration"),
    ("next.config.ts", "Next.js configuration"),
    ("webpack.config.js", "Webpack build configuration"),
    ("webpack.config.ts", "Webpack build configuration"),
]

_RUNTIME_CANDIDATES: list[tuple[str, str]] = [
    ("Dockerfile", "Docker container definition"),
    ("docker-compose.yml", "Docker Compose orchestration"),
    ("docker-compose.yaml", "Docker Compose orchestration"),
    ("Makefile", "Make build / task runner"),
]

_FASTAPI_RE = re.compile(r"=\s*FastAPI\s*\(")
_FLASK_RE = re.compile(r"=\s*Flask\s*\(")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _probe_python_framework(path: Path) -> str | None:
    """Return a short framework label if *path* bootstraps a FastAPI or Flask app."""
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if _FASTAPI_RE.search(src):
        return "FastAPI"
    if _FLASK_RE.search(src):
        return "Flask"
    return None


def _detect_backend(root: Path) -> list[_Entry]:
    entries: list[_Entry] = []
    seen: set[str] = set()

    for rel, desc in _PY_BACKEND_CANDIDATES:
        p = root / rel
        if p.is_file():
            fw = _probe_python_framework(p)
            full_desc = f"{desc} ({fw} bootstrap)" if fw else desc
            entries.append(_Entry(path=rel, description=full_desc))
            seen.add(rel)

    # Scan common sub-directories for an app.py / main.py with framework usage
    for subdir in ("src", "backend", "api", "server"):
        for name in ("main.py", "app.py"):
            rel = f"{subdir}/{name}"
            if rel in seen:
                continue
            p = root / subdir / name
            if p.is_file():
                fw = _probe_python_framework(p)
                desc = f"Python entry point in {subdir}/"
                if fw:
                    desc = f"{fw} bootstrap in {subdir}/"
                entries.append(_Entry(path=rel, description=desc))
                seen.add(rel)

    return entries


def _detect_frontend(root: Path) -> list[_Entry]:
    entries: list[_Entry] = []
    seen: set[str] = set()
    for rel, desc in _FE_CANDIDATES:
        if rel in seen:
            continue
        if (root / rel).is_file():
            entries.append(_Entry(path=rel, description=desc))
            seen.add(rel)
    return entries


def _detect_cli_scripts(root: Path) -> list[_Script]:
    scripts: list[_Script] = []

    # cli.py at root or in src/
    for rel in ("cli.py", "src/cli.py"):
        if (root / rel).is_file():
            scripts.append(_Script(name=rel, target=rel, source="file"))

    # pyproject.toml [project.scripts]
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            # Simple TOML parsing without a TOML library – read the
            # [project.scripts] section lines.
            _parse_pyproject_scripts(pyproject, scripts)
        except Exception:  # noqa: BLE001
            pass

    # package.json scripts
    pkg_json = root / "package.json"
    if pkg_json.is_file():
        try:
            data = json.loads(pkg_json.read_text(encoding="utf-8"))
            for name, cmd in (data.get("scripts") or {}).items():
                scripts.append(_Script(name=name, target=str(cmd), source="package.json"))
        except Exception:  # noqa: BLE001
            pass

    # Shell scripts in a scripts/ directory
    scripts_dir = root / "scripts"
    if scripts_dir.is_dir():
        for p in sorted(scripts_dir.iterdir()):
            if p.is_file() and p.suffix in (".sh", ".bash", ".zsh", ""):
                rel = f"scripts/{p.name}"
                scripts.append(_Script(name=p.name, target=rel, source="scripts/"))

    return scripts


def _parse_pyproject_scripts(path: Path, out: list[_Script]) -> None:
    """Extract [project.scripts] entries without a TOML parser dependency."""
    src = path.read_text(encoding="utf-8", errors="replace")
    in_section = False
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_section = stripped in ("[project.scripts]", "[project.gui-scripts]")
            continue
        if in_section and "=" in stripped and not stripped.startswith("#"):
            name, _, target = stripped.partition("=")
            name = name.strip().strip('"').strip("'")
            target = target.strip().strip('"').strip("'")
            if name and target:
                out.append(_Script(name=name, target=target, source="pyproject.toml"))


def _detect_runtime_config(root: Path) -> list[_Entry]:
    entries: list[_Entry] = []
    for rel, desc in _RUNTIME_CANDIDATES:
        if (root / rel).is_file():
            entries.append(_Entry(path=rel, description=desc))
    return entries


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_entrypoints(root: Path) -> dict:
    """Return a structured dict describing all detected entry points under *root*."""
    return {
        "backend": [{"path": e.path, "description": e.description} for e in _detect_backend(root)],
        "frontend": [{"path": e.path, "description": e.description} for e in _detect_frontend(root)],
        "cli_scripts": [
            {"name": s.name, "target": s.target, "source": s.source}
            for s in _detect_cli_scripts(root)
        ],
        "runtime_config": [
            {"path": e.path, "description": e.description} for e in _detect_runtime_config(root)
        ],
    }


def render_entrypoints(root: Path, data: dict) -> str:
    """Render *data* (from :func:`detect_entrypoints`) as a Markdown string."""
    lines: list[str] = [
        "# Entrypoints",
        "",
        f"Root: `{root.name}`",
        "",
    ]

    # Backend
    lines.append("## Backend")
    lines.append("")
    backend = data.get("backend") or []
    if backend:
        for item in backend:
            lines.append(f"- `{item['path']}` – {item['description']}")
    else:
        lines.append("not detected")
    lines.append("")

    # Frontend
    lines.append("## Frontend")
    lines.append("")
    frontend = data.get("frontend") or []
    if frontend:
        for item in frontend:
            lines.append(f"- `{item['path']}` – {item['description']}")
    else:
        lines.append("not detected")
    lines.append("")

    # CLI / Scripts
    lines.append("## CLI/Scripts")
    lines.append("")
    cli_scripts = data.get("cli_scripts") or []
    if cli_scripts:
        for item in cli_scripts:
            lines.append(f"- `{item['name']}` → `{item['target']}` _(source: {item['source']})_")
    else:
        lines.append("not detected")
    lines.append("")

    # Runtime / Config
    lines.append("## Runtime/Config")
    lines.append("")
    runtime = data.get("runtime_config") or []
    if runtime:
        for item in runtime:
            lines.append(f"- `{item['path']}` – {item['description']}")
    else:
        lines.append("not detected")
    lines.append("")

    return "\n".join(lines)


def write_entrypoints(root: Path, output_path: Path) -> None:
    """Detect entry points under *root* and write ``entrypoints.md`` to *output_path*."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = detect_entrypoints(root)
    content = render_entrypoints(root, data)
    output_path.write_text(content, encoding="utf-8")
