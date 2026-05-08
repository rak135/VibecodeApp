"""Relevant-file scoring for context-pack generation."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path, PurePosixPath

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_-]*")
_PATH_RE = re.compile(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+")

_STOPWORDS: frozenset[str] = frozenset({
    "a",
    "an",
    "and",
    "are",
    "for",
    "in",
    "of",
    "on",
    "the",
    "to",
    "with",
})

_IGNORED_PARTS: frozenset[str] = frozenset({
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "cache",
    "coverage",
    "dist",
    "build",
    "node_modules",
    "vendor",
})

_GENERATED_SUFFIXES: tuple[str, ...] = (
    ".generated.json",
    ".generated.md",
    ".min.js",
    ".min.css",
)

_ENTRYPOINT_NAMES: frozenset[str] = frozenset({
    "app.py",
    "asgi.py",
    "cli.py",
    "docker-compose.yaml",
    "docker-compose.yml",
    "dockerfile",
    "main.py",
    "makefile",
    "manage.py",
    "package.json",
    "pyproject.toml",
    "vite.config.js",
    "vite.config.ts",
    "wsgi.py",
})

_DOMAIN_EXTENSIONS: dict[str, frozenset[str]] = {
    "api": frozenset({".py", ".ts", ".tsx", ".js", ".jsx"}),
    "architecture": frozenset({".md", ".yaml", ".yml"}),
    "cli": frozenset({".py"}),
    "config": frozenset({".toml", ".yaml", ".yml", ".json"}),
    "context": frozenset({".py", ".md", ".json"}),
    "doc": frozenset({".md"}),
    "docs": frozenset({".md"}),
    "frontend": frozenset({".ts", ".tsx", ".js", ".jsx", ".css"}),
    "index": frozenset({".py", ".json", ".md"}),
    "map": frozenset({".py", ".json", ".md"}),
    "pack": frozenset({".py", ".md", ".json"}),
    "test": frozenset({".py", ".ts", ".tsx", ".js", ".jsx"}),
    "tests": frozenset({".py", ".ts", ".tsx", ".js", ".jsx"}),
}


def score_relevant_files(
    repo_root: Path,
    task: str,
    inventory: dict | None = None,
    limit: int = 20,
) -> list[dict]:
    """Return the highest-scoring files for *task*.

    Results are JSON-serialisable dictionaries containing ``path``, ``score``,
    and ``reasons``.  When *inventory* is omitted, the function first reads
    ``.vibecode/index/file_inventory.json`` and falls back to a lightweight
    filesystem scan.
    """

    root = repo_root.resolve()
    records = _load_records(root, inventory)
    paths = [record["path"] for record in records]
    path_set = set(paths)
    task_keywords = _task_keywords(task)
    architecture_refs = _architecture_references(root)
    recent_paths = _recent_git_paths(root)
    source_to_tests = _source_test_pairs(root, path_set)
    paired_tests = {test for tests in source_to_tests.values() for test in tests}

    results: list[dict] = []
    for record in records:
        rel = record["path"]
        score = 0
        reasons: list[str] = []

        risk_level = str(record.get("risk_level") or "").lower()

        if _is_ignored(rel):
            score -= 20
            reasons.append("-20 ignored/generated/vendor/cache file")

        path_lower = rel.lower()
        filename = PurePosixPath(rel).name.lower()
        for keyword in task_keywords:
            if keyword in path_lower:
                score += 10
                reasons.append(f"+10 task keyword '{keyword}' in path")
            if keyword in filename:
                score += 8
                reasons.append(f"+8 task keyword '{keyword}' in filename")

        if rel in architecture_refs or _is_architecture_doc(rel):
            score += 6
            reasons.append("+6 file listed in architecture docs")

        if rel in source_to_tests:
            score += 5
            checks = ", ".join(source_to_tests[rel])
            reasons.append(f"+5 source file has matching test file ({checks})")
        elif rel in paired_tests:
            score += 5
            reasons.append("+5 test file matches a relevant source file")

        if rel in recent_paths:
            score += 4
            reasons.append("+4 recently changed file")

        if _is_config_or_entrypoint(rel, record):
            score += 3
            reasons.append("+3 config/entrypoint file")

        if _extension_matches_task(rel, task_keywords):
            score += 2
            reasons.append("+2 matching extension for task domain")

        if reasons and score > 0:
            result = {"path": rel, "score": score, "reasons": reasons}
            if risk_level:
                result["risk_level"] = risk_level
                if risk_level in {"high", "critical"}:
                    result["requires_confirmation"] = True
            results.append(result)

    results.sort(key=lambda item: (-item["score"], item["path"]))
    return results[: max(limit, 0)]


def write_relevant_files(
    repo_root: Path,
    task: str,
    inventory: dict | None = None,
    limit: int = 20,
    output_path: Path | None = None,
) -> list[dict]:
    """Score relevant files and write ``relevant_files.generated.json``."""

    root = repo_root.resolve()
    results = score_relevant_files(root, task, inventory=inventory, limit=limit)
    output = output_path or root / ".vibecode" / "index" / "relevant_files.generated.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "$schema": "vibecode/relevant-files/v1",
        "task": task,
        "files": results,
    }
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return results


def _load_records(repo_root: Path, inventory: dict | None) -> list[dict]:
    data = inventory
    if data is None:
        inventory_path = repo_root / ".vibecode" / "index" / "file_inventory.json"
        if inventory_path.is_file():
            try:
                data = json.loads(inventory_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = None

    if data is not None:
        records = []
        for item in data.get("files") or []:
            rel = _normalise_rel(item.get("path", ""))
            if rel:
                copied = dict(item)
                copied["path"] = rel
                records.append(copied)
        return records

    records = []
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(repo_root).as_posix()
        records.append({"path": rel})
    return records


def _normalise_rel(path: str) -> str:
    rel = path.replace("\\", "/").strip()
    while rel.startswith("./"):
        rel = rel[2:]
    return rel


def _task_keywords(task: str) -> list[str]:
    seen: set[str] = set()
    keywords: list[str] = []
    for raw in _TOKEN_RE.findall(task.lower()):
        token = raw.replace("_", "-")
        parts = [part for part in token.split("-") if part]
        candidates = [token, *parts] if len(parts) > 1 else [token]
        for candidate in candidates:
            if len(candidate) < 2 or candidate in _STOPWORDS or candidate in seen:
                continue
            seen.add(candidate)
            keywords.append(candidate)
    return keywords


def _architecture_references(repo_root: Path) -> set[str]:
    refs: set[str] = set()
    docs = [
        *(repo_root / ".vibecode" / "architecture").glob("*.md"),
        *(repo_root / "docs").glob("**/*.md"),
        *(repo_root / ".docs").glob("**/*.md"),
    ]
    for doc in docs:
        if not doc.is_file():
            continue
        rel_doc = doc.relative_to(repo_root).as_posix()
        if _is_architecture_doc(rel_doc):
            refs.add(rel_doc)
        try:
            content = doc.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in _PATH_RE.findall(content):
            rel = _normalise_rel(match.strip("`'\".,:)"))
            if rel:
                refs.add(rel)
    return refs


def _recent_git_paths(repo_root: Path) -> set[str]:
    paths: set[str] = set()
    commands = [
        ["git", "status", "--short"],
        ["git", "diff", "--name-only", "HEAD~5..HEAD"],
    ]
    for command in commands:
        try:
            result = subprocess.run(
                command,
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode != 0:
            continue
        for line in result.stdout.splitlines():
            rel = _parse_git_path(line)
            if rel:
                paths.add(rel)
    return paths


def _parse_git_path(line: str) -> str:
    cleaned = line.strip()
    if not cleaned:
        return ""
    if " -> " in cleaned:
        cleaned = cleaned.rsplit(" -> ", 1)[1]
    elif len(line) > 3 and line[2] == " ":
        cleaned = line[3:]
    return _normalise_rel(cleaned)


def _source_test_pairs(repo_root: Path, path_set: set[str]) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    test_map_path = repo_root / ".vibecode" / "index" / "test_map.json"
    if test_map_path.is_file():
        try:
            data = json.loads(test_map_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        for rule in data.get("rules") or []:
            source = _normalise_rel(rule.get("path_pattern", ""))
            if source == "**" or source not in path_set:
                continue
            checks = [
                _normalise_rel(check)
                for check in rule.get("required_checks") or []
                if _normalise_rel(check) in path_set
            ]
            if checks:
                mapping[source] = sorted(set(checks))

    if mapping:
        return mapping

    tests = [path for path in path_set if _looks_like_test(path)]
    for source in path_set:
        if _looks_like_test(source):
            continue
        matches = [test for test in tests if _test_matches_source(test, source)]
        if matches:
            mapping[source] = sorted(matches)
    return mapping


def _looks_like_test(path: str) -> bool:
    name = PurePosixPath(path).name.lower()
    parts = path.lower().split("/")
    return (
        "tests" in parts[:-1]
        or "__tests__" in parts[:-1]
        or name.startswith("test_")
        or name.endswith("_test.py")
        or ".test." in name
        or ".spec." in name
    )


def _test_matches_source(test_path: str, source_path: str) -> bool:
    test_name = PurePosixPath(test_path).name.lower()
    source = PurePosixPath(source_path)
    stem = source.stem.lower()
    return (
        test_name == f"test_{stem}.py"
        or test_name == f"{stem}_test.py"
        or test_name.startswith(f"{stem}.test.")
        or test_name.startswith(f"{stem}.spec.")
    )


def _is_config_or_entrypoint(path: str, record: dict) -> bool:
    name = PurePosixPath(path).name.lower()
    if record.get("is_config") is True:
        return True
    if name in _ENTRYPOINT_NAMES:
        return True
    return path.startswith("scripts/") and PurePosixPath(path).suffix in {".sh", ".ps1", ".py"}


def _extension_matches_task(path: str, keywords: list[str]) -> bool:
    suffix = PurePosixPath(path).suffix.lower()
    if not suffix:
        return False
    return any(suffix in _DOMAIN_EXTENSIONS.get(keyword, frozenset()) for keyword in keywords)


def _is_architecture_doc(path: str) -> bool:
    lower = path.lower()
    return (
        lower.startswith(".vibecode/architecture/")
        or "/architecture/" in lower
        or "architecture" in PurePosixPath(lower).name
    )


def _is_ignored(path: str) -> bool:
    lower = path.lower()
    parts = set(lower.split("/"))
    if parts & _IGNORED_PARTS:
        return True
    if lower.endswith(_GENERATED_SUFFIXES):
        return True
    return any(part.endswith(".egg-info") for part in parts)
