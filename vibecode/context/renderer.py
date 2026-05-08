"""Render task-scoped context packs for coding agents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import NamedTuple

from vibecode.context.scoring import score_relevant_files

ARCHITECTURE_DIR = Path(".vibecode") / "architecture"
CHECKS_PATH = Path(".vibecode") / "checks" / "required_checks.yaml"
CURRENT_CONTEXT_PACK = Path(".vibecode") / "current" / "context_pack.md"
HANDOFF_NOW_PATH = Path(".vibecode") / "handoff" / "NOW.md"
INDEX_DIR = Path(".vibecode") / "index"

# ~6 400 words at five chars/word; prevents unbounded context packs.
DEFAULT_CHAR_LIMIT = 32_000


class _Section(NamedTuple):
    name: str
    heading: str
    lines: list[str]
    priority: int  # lower = higher priority; kept longer when truncating


def write_context_pack(
    repo_root: Path, task: str, char_limit: int = DEFAULT_CHAR_LIMIT
) -> Path:
    """Write the derived context pack for *task* and return its path."""

    root = repo_root.resolve()
    output_path = root / CURRENT_CONTEXT_PACK
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_context_pack(root, task, char_limit=char_limit), encoding="utf-8"
    )
    return output_path


def render_context_pack(
    repo_root: Path, task: str, char_limit: int = DEFAULT_CHAR_LIMIT
) -> str:
    """Render a compact, agent-ready context pack within *char_limit* characters."""

    root = repo_root.resolve()

    header_lines = [
        "# Vibecode Context Pack",
        "",
        "This is a derived runtime artifact. Treat committed architecture docs and required checks as source of truth.",
        "",
    ]

    # Priority order: lower number = higher priority = removed last when truncating.
    # Highest: task (1), invariants (2), protected (3), relevant files (4), required checks (5)
    # Lower:   working rule (6), project (7), architecture (8), index status (9), handoff (10)
    sections: list[_Section] = [
        _Section("project", "## Project", _project_summary(root), priority=7),
        _Section("task", "## Current task", [task], priority=1),
        _Section("invariants", "## Must preserve / invariants", _project_invariants(root), priority=2),
        _Section("architecture", "## Relevant architecture", _architecture_summary(root), priority=8),
        _Section("relevant_files", "## Relevant files with reasons", _relevant_files(root, task), priority=4),
        _Section("index_status", "## Generated index status", _generated_index_status(root), priority=9),
        _Section("required_checks", "## Required checks", _required_checks(root), priority=5),
        _Section("protected", "## Risky/protected files not allowed or requiring confirmation", _do_not_touch(root), priority=3),
        _Section("handoff", "## Handoff required", _handoff_expectations(root), priority=10),
        _Section("working_rule", "## Working rule", [
            "- Make the smallest task-relevant change.",
            "- Do not refactor unrelated code.",
            "- Do not mark the task complete without listing evidence and checks run.",
        ], priority=6),
    ]

    return _apply_length_limit(header_lines, sections, char_limit)


def _apply_length_limit(
    header_lines: list[str],
    sections: list[_Section],
    char_limit: int,
) -> str:
    """Render sections, dropping lowest-priority ones until within *char_limit*.

    A notice is appended whenever sections are omitted so the reader knows
    what was shortened.
    """

    def _render(active: list[_Section], omitted: list[str]) -> str:
        parts = list(header_lines)
        for sec in active:
            parts.append("")
            parts.append(sec.heading)
            parts.append("")
            parts.extend(sec.lines)
        if omitted:
            parts.extend([
                "",
                "> **Context limit reached.** The following lower-priority sections were "
                "omitted to stay within the limit: " + ", ".join(omitted) + ".",
            ])
        return "\n".join(parts).rstrip() + "\n"

    active = list(sections)
    omitted: list[str] = []

    content = _render(active, omitted)

    while len(content) > char_limit and active:
        # Remove the lowest-priority section still present.
        worst = max(active, key=lambda s: s.priority)
        active.remove(worst)
        omitted.append(f"*{worst.heading.lstrip('#').strip()}*")
        content = _render(active, omitted)

    return content


def _project_summary(repo_root: Path) -> list[str]:
    project_yaml = repo_root / ".vibecode" / "project.yaml"
    if not project_yaml.is_file():
        return [f"- Root: `{repo_root.as_posix()}`", "- Project config missing."]

    try:
        from vibecode.config import load_config

        cfg = load_config(repo_root / ".vibecode")
    except Exception as exc:  # noqa: BLE001
        return [f"- Root: `{repo_root.as_posix()}`", f"- Project config could not be loaded: {exc}"]
    return [
        f"- Project: `{cfg.project_name}`",
        f"- Project id: `{cfg.project_id}`",
        f"- Root: `{cfg.root.as_posix()}`",
    ]


def _project_invariants(repo_root: Path) -> list[str]:
    invariants = repo_root / ARCHITECTURE_DIR / "INVARIANTS.md"
    if not invariants.is_file():
        return ["- Missing `.vibecode/architecture/INVARIANTS.md`; verify project truth before editing."]
    bullets = _markdown_bullets(invariants.read_text(encoding="utf-8", errors="replace"))
    return bullets or ["- `INVARIANTS.md` exists but has no bullet invariants."]


def _architecture_summary(repo_root: Path) -> list[str]:
    architecture_dir = repo_root / ARCHITECTURE_DIR
    if not architecture_dir.is_dir():
        return ["- Missing `.vibecode/architecture/`; generate or restore architecture docs first."]

    lines: list[str] = []
    for path in sorted(architecture_dir.glob("*.md")):
        rel = _rel(repo_root, path)
        if path.name == "INVARIANTS.md":
            continue
        title = _first_heading(path)
        bullets = _markdown_bullets(path.read_text(encoding="utf-8", errors="replace"))[:4]
        if bullets:
            lines.append(f"- `{rel}`: {title}.")
            lines.extend(f"  {bullet}" for bullet in bullets)
        else:
            lines.append(f"- `{rel}`: {title}.")
    return lines or ["- No architecture summary docs found beyond invariants."]


def _relevant_files(repo_root: Path, task: str) -> list[str]:
    scored = score_relevant_files(repo_root, task, limit=16)
    by_path = {item["path"]: item for item in scored}
    ordered_paths = [item["path"] for item in scored]

    for extra in _expected_context_paths(repo_root):
        if extra not in by_path and extra not in ordered_paths:
            ordered_paths.append(extra)

    if not ordered_paths:
        return ["- No relevant files scored. Run `vibecode index` and retry."]

    lines = ["Do not paste full source into follow-up prompts; use these paths as navigation targets."]
    for rel in ordered_paths[:24]:
        item = by_path.get(rel)
        if item:
            reason = "; ".join(item.get("reasons", [])[:3])
            risk = item.get("risk_level")
            risk_note = f", risk `{risk}`" if risk else ""
            confirm = ", requires confirmation" if item.get("requires_confirmation") else ""
            lines.append(f"- `{rel}` (score {item['score']}{risk_note}{confirm}): {reason}")
        else:
            lines.append(f"- `{rel}` (included for context-pack workflow coverage)")
    return lines


def _generated_index_status(repo_root: Path) -> list[str]:
    index_dir = repo_root / INDEX_DIR
    if not index_dir.is_dir():
        return ["- Missing `.vibecode/index/`; run `vibecode index` before relying on generated context."]

    files = sorted(path for path in index_dir.iterdir() if path.is_file())
    if not files:
        return ["- `.vibecode/index/` exists but contains no index files."]

    lines = ["Generated indexes are derived and must be regenerated when repository structure changes."]
    for path in files:
        rel = _rel(repo_root, path)
        generated = ".generated." in path.name
        kind = "generated" if generated else "existing index/status"
        lines.append(f"- `{rel}`: present, {kind}, {path.stat().st_size} bytes")
    return lines


def _required_checks(repo_root: Path) -> list[str]:
    checks_path = repo_root / CHECKS_PATH
    lines: list[str] = []
    if checks_path.is_file():
        for line in checks_path.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if stripped.startswith("- name:"):
                lines.append(f"- {stripped.removeprefix('- name:').strip()}")
            elif stripped.startswith("command:"):
                command = stripped.removeprefix("command:").strip()
                if lines:
                    lines[-1] = f"{lines[-1]}: `{command}`"

    test_map_checks = _required_checks_from_test_map(repo_root)
    for check in test_map_checks:
        if check not in lines:
            lines.append(check)

    if not lines:
        return ["- Missing `.vibecode/checks/required_checks.yaml`; ask before declaring work complete."]
    return lines or [f"- See `{CHECKS_PATH.as_posix()}`."]


def _do_not_touch(repo_root: Path) -> list[str]:
    lines = [
        "- Do not edit `.vibecode/current/*`; it is runtime/session output.",
        "- Do not treat `.vibecode/index/*` as source of truth; regenerate indexes instead.",
        "- Do not overwrite `.vibecode/architecture/*.md`, `.vibecode/checks/*.yaml`, or `.vibecode/handoff/*.md` unless the task explicitly asks for truth-doc changes.",
    ]
    protected = repo_root / ARCHITECTURE_DIR / "PROTECTED_AREAS.md"
    if protected.is_file():
        bullets = _markdown_bullets(protected.read_text(encoding="utf-8", errors="replace"))
        lines.extend(bullets)
    return lines


def _required_checks_from_test_map(repo_root: Path) -> list[str]:
    test_map = repo_root / INDEX_DIR / "test_map.json"
    if not test_map.is_file():
        return []
    try:
        data = json.loads(test_map.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    checks: list[str] = []
    for rule in data.get("rules") or []:
        if rule.get("path_pattern") != "**":
            continue
        for command in rule.get("required_checks") or []:
            checks.append(f"- test map required check: `{command}`")
    return checks


def _handoff_expectations(repo_root: Path) -> list[str]:
    lines = [
        "- Keep edits scoped to files relevant to the task.",
        "- Report changed files and checks run.",
        "- If architecture truth changes, update committed architecture docs in the same handoff.",
    ]
    now = repo_root / HANDOFF_NOW_PATH
    if now.is_file():
        content = _compact_markdown(now.read_text(encoding="utf-8", errors="replace"), max_lines=6)
        if content:
            lines.extend(["", f"Current handoff from `{HANDOFF_NOW_PATH.as_posix()}`:"])
            lines.extend(f"> {line}" for line in content)
    return lines


def _expected_context_paths(repo_root: Path) -> list[str]:
    candidates = [
        "vibecode/context/__init__.py",
        "vibecode/context/renderer.py",
        "vibecode/context/scoring.py",
        "vibecode/cli.py",
        "tests/test_vibecode_context_pack.py",
        "tests/test_vibecode_relevant_files.py",
    ]
    architecture = [
        _rel(repo_root, path)
        for path in sorted((repo_root / ARCHITECTURE_DIR).glob("*.md"))
        if path.is_file()
    ]
    return [path for path in [*candidates, *architecture] if (repo_root / path).is_file()]


def _markdown_bullets(content: str) -> list[str]:
    bullets = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            bullets.append(stripped)
    return bullets


def _first_heading(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                return stripped.lstrip("#").strip() or path.stem.replace("_", " ").title()
    except OSError:
        pass
    return path.stem.replace("_", " ").title()


def _compact_markdown(content: str, max_lines: int) -> list[str]:
    kept = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("<!--"):
            continue
        kept.append(stripped)
        if len(kept) >= max_lines:
            break
    return kept


def _rel(repo_root: Path, path: Path) -> str:
    return path.relative_to(repo_root).as_posix()
