"""Relevant-file scoring for context-pack generation."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path, PurePosixPath

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_-]*")
_PATH_RE = re.compile(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+")
# Used to split a file path into component tokens for word-boundary keyword matching.
_PATH_SPLIT_RE = re.compile(r"[/._\-]")
# Splits CamelCase words at lower→upper and UPPER→Upper transitions so that
# "ContextPanel" yields "Context" and "Panel" as separate tokens.
_CAMEL_SPLIT_RE = re.compile(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
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

# Tokens that are too generic to justify a strong path/filename or arch-doc boost.
# They may still contribute a tiny (+1) path signal to break ties, but emit no reason string.
# They are also excluded from handoff/history reinforcement and arch-doc keyword matching.
_LOW_VALUE_TOKENS: frozenset[str] = frozenset({
    "add",
    "change",
    "current",
    "file",
    "files",
    "fix",
    "generated",
    "improve",
    "new",
    "project",
    "render",
    "source",
    "task",
    "test",
    "tests",
    "update",
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

# Path prefixes that indicate generated/runtime/session locations.
_IGNORED_PATH_PREFIXES: tuple[str, ...] = (
    ".vibecode/current/",
    ".vibecode/logs/",
    ".vibecode/runs/",
    ".vibecode/tmp/",
    ".vibecode/cache/",
    ".vibecode/generated/",
    ".ralphy/",
    ".ralph/",
)

_GENERATED_SUFFIXES: tuple[str, ...] = (
    ".generated.json",
    ".generated.md",
    ".min.js",
    ".min.css",
    ".pyc",
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
    "agent": frozenset({".py", ".md"}),
    "agents": frozenset({".py", ".md"}),
    "api": frozenset({".py", ".ts", ".tsx", ".js", ".jsx"}),
    "architecture": frozenset({".md", ".yaml", ".yml"}),
    "check": frozenset({".py", ".yaml", ".yml"}),
    "checks": frozenset({".py", ".yaml", ".yml"}),
    "cli": frozenset({".py"}),
    "config": frozenset({".toml", ".yaml", ".yml", ".json"}),
    "context": frozenset({".py", ".md", ".json"}),
    "dependency": frozenset({".py", ".json"}),
    "doc": frozenset({".md"}),
    "docs": frozenset({".md"}),
    "export": frozenset({".py"}),
    "frontend": frozenset({".ts", ".tsx", ".js", ".jsx", ".css"}),
    "handoff": frozenset({".md"}),
    "index": frozenset({".py", ".json", ".md"}),
    "map": frozenset({".py", ".json", ".md"}),
    "pack": frozenset({".py", ".md", ".json"}),
    "render": frozenset({".py", ".ts", ".tsx"}),
    "renderer": frozenset({".py", ".ts", ".tsx"}),
    "rendering": frozenset({".py", ".ts", ".tsx"}),
    "scan": frozenset({".py"}),
    "scanner": frozenset({".py"}),
    "score": frozenset({".py"}),
    "scoring": frozenset({".py"}),
    "symbol": frozenset({".py", ".json"}),
    "symbols": frozenset({".py", ".json"}),
    "test": frozenset({".py", ".ts", ".tsx", ".js", ".jsx"}),
    "tests": frozenset({".py", ".ts", ".tsx", ".js", ".jsx"}),
    "tree": frozenset({".py", ".md", ".json"}),
    "validation": frozenset({".py"}),
}

# A file must score at least this much to trigger dependency boosts on neighbours.
# Set high enough that only files with a real task-keyword match (≥10 path signal)
# can propagate boosts; this prevents mutual source/test dep-boost cycles from
# flooding the top results with unrelated pairs.
_DEP_BOOST_THRESHOLD = 12
# Score added per unique high-scoring dependency connection, capped per file.
_DEP_BOOST = 3
_DEP_BOOST_CAP = 3

# Minimum pass-1 score a source file must reach (without pairing boost) for its
# paired tests to receive the pairing boost in pass 1.5.  This prevents unrelated
# tests from entering the long tail simply because they happen to be paired with a
# low-scoring source.
_TEST_BOOST_SOURCE_THRESHOLD = 8

# Hub files: modules that broadly import/dispatch many project modules.  They
# should only receive full scoring boosts (pairing, entrypoint, dep fan-out)
# when the task explicitly targets CLI or command-dispatch topics.
_HUB_FILES: frozenset[str] = frozenset({
    "vibecode/cli.py",
    "vibecode/config.py",
    "vibecode/project.py",
    "vibecode/__init__.py",
    "vibecode/context/__init__.py",
    "vibecode/indexer/__init__.py",
})

# Task keyword fragments indicating the task targets CLI or entrypoint behaviour.
_HUB_KEYWORDS: frozenset[str] = frozenset({
    "cli",
    "command",
    "commands",
    "parser",
    "entrypoint",
    "dispatch",
})


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
    task_is_hub_relevant = _task_has_hub_keyword(task_keywords)

    # Load all project signals once.
    arch_keyword_reasons = _architecture_signal(root, task_keywords)
    recent_paths = _recent_git_paths(root)
    source_to_tests = _source_test_pairs(root, path_set)
    # Suppress hub-file pairings when the task is not CLI/command-related.
    # Hub files (e.g. cli.py) connect to many tests; without this suppression
    # those tests flood directly_relevant_tests and trigger dep fan-out.
    if not task_is_hub_relevant:
        source_to_tests = {
            k: v for k, v in source_to_tests.items() if not _is_hub_file(k)
        }
    handoff_tok = _handoff_tokens(root)
    history_tok = _history_tokens(root)
    dep_connections = _dependency_connections(root)

    # Exclude low-value tokens from reinforcement sets so generic words in handoff/history
    # docs (e.g. "file", "improve") don't create false-positive boosts.
    handoff_reinforced = {
        kw for kw in task_keywords if kw in handoff_tok and kw not in _LOW_VALUE_TOKENS
    }
    history_reinforced = {
        kw for kw in task_keywords if kw in history_tok and kw not in _LOW_VALUE_TOKENS
    }

    # Pass 1: score each file independently.
    raw: dict[str, tuple[int, list[str], dict]] = {}
    for record in records:
        rel = record["path"]
        score = 0
        reasons: list[str] = []
        risk_level = str(record.get("risk_level") or "").lower()

        if _is_ignored(rel):
            score -= 20
            reasons.append("generated/vendor/cache penalty")

        path_lower = rel.lower()
        filename_orig = PurePosixPath(rel).name
        filename = filename_orig.lower()
        # Pre-compute path and filename token sets for word-boundary keyword matching.
        # This prevents "pack" from matching "package.json" via substring.
        # CamelCase segments (e.g. "ContextPanel") are split into constituent words
        # so that "context" and "panel" are each recognised as separate tokens.
        path_tokens = _split_path_tokens(path_lower, path_orig=rel)
        filename_tokens = _split_path_tokens(filename, path_orig=filename_orig)

        # Task keyword matching.
        # Low-value tokens (generic words) give only +1 for path presence with no reason string.
        # Domain-specific tokens get the full +10/+8 boost with a reason.
        # Token-set matching (not substring) avoids false positives like "pack" in "package.json".
        for keyword in task_keywords:
            if keyword in _LOW_VALUE_TOKENS:
                if keyword in path_tokens:
                    score += 1
            else:
                if keyword in path_tokens:
                    score += 10
                    reasons.append(f'task keyword matched path token: "{keyword}"')
                if keyword in filename_tokens:
                    score += 8
                    reasons.append(f'task keyword matched filename token: "{keyword}"')

        # Architecture doc signal: the doc files themselves get a small boost.
        if _is_architecture_doc(rel):
            score += 4
            reasons.append("architecture doc")

        # Architecture keyword signal: files in task-relevant docs get a boost.
        if rel in arch_keyword_reasons:
            score += 3
            reasons.extend(arch_keyword_reasons[rel][:2])

        # Handoff signal: extra boost when handoff docs also mention this task keyword.
        for keyword in handoff_reinforced:
            if keyword in path_tokens:
                score += 3
                reasons.append(f'handoff mentions: "{keyword}"')
                break  # one handoff reason per file

        # History signal (weak).
        for keyword in history_reinforced:
            if keyword in path_tokens:
                score += 2
                reasons.append(f'history mentions: "{keyword}"')
                break  # one history reason per file

        # Recent git changes: only boost if the file also matches a task keyword.
        if rel in recent_paths and any(kw in path_tokens for kw in task_keywords):
            score += 3
            reasons.append("recently changed and task-matching")

        if _is_config_or_entrypoint(rel, record):
            # Hub files (cli.py, config.py, etc.) get the entrypoint boost only
            # when the task is explicitly CLI/command-related.
            if not _is_hub_file(rel) or task_is_hub_relevant:
                score += 3
                reasons.append("config/entrypoint file")

        if _extension_matches_task(rel, task_keywords):
            score += 2
            reasons.append("matching extension for task domain")

        extra: dict = {}
        if risk_level:
            extra["risk_level"] = risk_level
            if risk_level in {"high", "critical"}:
                extra["requires_confirmation"] = True

        raw[rel] = (score, reasons, extra)

    # Pass 1.5: pairing boost — only tests whose paired source scored at least
    # _TEST_BOOST_SOURCE_THRESHOLD in pass 1 receive the boost.  This prevents
    # unrelated tests from flooding the long tail via free +5 pairing points.
    directly_relevant_sources = {
        src for src in source_to_tests
        if raw.get(src, (0,))[0] >= _TEST_BOOST_SOURCE_THRESHOLD
    }
    directly_relevant_tests: set[str] = {
        test
        for src in directly_relevant_sources
        for test in source_to_tests[src]
    }
    for src in directly_relevant_sources:
        if src in raw:
            s, r, e = raw[src]
            tests_str = ", ".join(f"`{t}`" for t in source_to_tests[src][:2])
            raw[src] = (s + 5, r + [f"source file: paired test {tests_str}"], e)
    for test in directly_relevant_tests:
        if test in raw:
            s, r, e = raw[test]
            raw[test] = (s + 5, r + ["paired test for a relevant source file"], e)

    # Pass 2: dependency boost — files connected to high-scoring files get a small lift.
    dep_boosts: dict[str, list[str]] = {}
    for rel, (score, _reasons, _extra) in raw.items():
        if score < _DEP_BOOST_THRESHOLD:
            continue
        # Hub files must not spread dependency boosts when the task does not
        # target CLI/command topics; they import too many modules and cause
        # fan-out that lifts unrelated files.
        if _is_hub_file(rel) and not task_is_hub_relevant:
            continue
        for connected in dep_connections.get(rel, set()):
            if connected in path_set and connected != rel:
                dep_boosts.setdefault(connected, []).append(
                    f"dependency connection from `{rel}`"
                )

    # Assemble final results.
    results: list[dict] = []
    for record in records:
        rel = record["path"]
        score, reasons, extra = raw[rel]
        reasons = list(reasons)

        if rel in dep_boosts:
            # Deduplicate and cap the dep boost.
            unique = list(dict.fromkeys(dep_boosts[rel]))[:2]
            boost = min(_DEP_BOOST * len(unique), _DEP_BOOST_CAP)
            score += boost
            reasons.extend(unique)

        if reasons and score > 0:
            result = {"path": rel, "score": score, "reasons": reasons}
            result.update(extra)
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


def _architecture_signal(
    repo_root: Path,
    task_keywords: list[str],
) -> dict[str, list[str]]:
    """Return ``keyword_reasons``: a mapping from path to extra reason strings.

    A file appears in *keyword_reasons* only when it is referenced in an
    architecture/docs file that also mentions at least one *domain-specific*
    task keyword.  Low-value tokens (e.g. "file", "improve") are excluded
    from this check so that generic words in docs don't lift unrelated files.
    """
    keyword_reasons: dict[str, list[str]] = {}

    docs = [
        *(repo_root / ".vibecode" / "architecture").glob("*.md"),
        *(repo_root / "docs").glob("**/*.md"),
        *(repo_root / ".docs").glob("**/*.md"),
    ]
    for doc in docs:
        if not doc.is_file():
            continue
        rel_doc = doc.relative_to(repo_root).as_posix()
        try:
            content = doc.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        content_lower = content.lower()

        # Collect file-path references from the doc.
        doc_file_refs: list[str] = []
        for match in _PATH_RE.findall(content):
            rel = _normalise_rel(match.strip("`'\".,):"))
            if rel:
                doc_file_refs.append(rel)

        # Only fire when a non-low-value task keyword appears in the doc.
        # This prevents generic words ("file", "improve") from creating false boosts.
        mentioned = [
            kw for kw in task_keywords
            if kw in content_lower and kw not in _LOW_VALUE_TOKENS
        ]
        if mentioned:
            kw_str = ", ".join(f'"{k}"' for k in mentioned[:2])
            doc_reason = f'architecture docs mention task keyword: {kw_str}'
            keyword_reasons.setdefault(rel_doc, []).append(doc_reason)
            for ref in doc_file_refs:
                if ref != rel_doc:
                    keyword_reasons.setdefault(ref, []).append(
                        f'referenced in task-relevant architecture doc `{rel_doc}`'
                    )

    return keyword_reasons


def _handoff_tokens(repo_root: Path) -> set[str]:
    """Return normalised keyword tokens from handoff docs."""
    tokens: set[str] = set()
    handoff_dir = repo_root / ".vibecode" / "handoff"
    for name in ("NOW.md", "NEXT.md", "BLOCKERS.md"):
        path = handoff_dir / name
        if path.is_file():
            try:
                content = path.read_text(encoding="utf-8", errors="replace").lower()
            except OSError:
                continue
            for raw in _TOKEN_RE.findall(content):
                token = raw.replace("_", "-")
                for part in token.split("-"):
                    if len(part) >= 4 and part not in _STOPWORDS:
                        tokens.add(part)
                if len(token) >= 4 and token not in _STOPWORDS:
                    tokens.add(token)
    return tokens


def _history_tokens(repo_root: Path) -> set[str]:
    """Return normalised keyword tokens from history docs (weak signal)."""
    tokens: set[str] = set()
    history_dir = repo_root / ".vibecode" / "history"
    for path in history_dir.glob("*.md"):
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace").lower()
        except OSError:
            continue
        for raw in _TOKEN_RE.findall(content):
            if len(raw) >= 4 and raw not in _STOPWORDS:
                tokens.add(raw)
    return tokens


def _dependency_connections(repo_root: Path) -> dict[str, set[str]]:
    """Return bidirectional adjacency from the generated dependency map."""
    dep_map_path = repo_root / ".vibecode" / "index" / "dependency_map.json"
    connections: dict[str, set[str]] = {}
    if not dep_map_path.is_file():
        return connections
    try:
        data = json.loads(dep_map_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return connections
    for edge in data.get("edges", []):
        if edge.get("status") != "resolved":
            continue
        frm = _normalise_rel(edge.get("from", ""))
        to = _normalise_rel(edge.get("resolved_path", ""))
        if frm and to and frm != to:
            connections.setdefault(frm, set()).add(to)
            connections.setdefault(to, set()).add(frm)
    return connections


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

    # Direct stem match (strongest).
    if (
        test_name == f"test_{stem}.py"
        or test_name == f"{stem}_test.py"
        or test_name.startswith(f"{stem}.test.")
        or test_name.startswith(f"{stem}.spec.")
    ):
        return True

    # Project convention: test_vibecode_{stem}.py
    if test_name == f"test_vibecode_{stem}.py":
        return True

    # Token-level overlap: match if a significant, domain-specific stem token appears in
    # the test name.  Low-value tokens (e.g. "file", "files") are excluded to prevent
    # false pairings like risky_files.py ↔ test_vibecode_relevant_files.py.
    stem_tokens = [
        t for t in re.split(r"[_\-]", stem)
        if len(t) >= 4 and t not in _LOW_VALUE_TOKENS
    ]
    if stem_tokens and any(
        f"_{t}" in test_name or test_name.startswith(f"test_{t}")
        for t in stem_tokens
    ):
        return True

    return False


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
    name = PurePosixPath(lower).name
    return (
        lower.startswith(".vibecode/architecture/")
        or "/architecture/" in lower
        or (lower.startswith("docs/") and "architecture" in name and name.endswith(".md"))
    )


def _is_ignored(path: str) -> bool:
    lower = path.lower()
    if any(lower.startswith(prefix) for prefix in _IGNORED_PATH_PREFIXES):
        return True
    parts = set(lower.split("/"))
    if parts & _IGNORED_PARTS:
        return True
    if lower.endswith(_GENERATED_SUFFIXES):
        return True
    return any(part.endswith(".egg-info") for part in parts)


def _split_path_tokens(path_lower: str, path_orig: str | None = None) -> frozenset[str]:
    """Return path component tokens split on /._- boundaries.

    Used for word-boundary keyword matching so that e.g. ``"pack"`` does not
    accidentally match ``"package.json"``.

    When *path_orig* (the original non-lowercased path or filename) is provided,
    CamelCase segments are additionally split at case-transition boundaries so
    that e.g. ``"ContextPanel.tsx"`` contributes both ``"context"`` and
    ``"panel"`` as individual tokens alongside ``"contextpanel"``.
    """
    tokens: set[str] = {t for t in _PATH_SPLIT_RE.split(path_lower) if t}
    if path_orig is not None:
        for part in _PATH_SPLIT_RE.split(path_orig):
            subs = _CAMEL_SPLIT_RE.split(part)
            if len(subs) > 1:
                tokens.update(s.lower() for s in subs if s)
    return frozenset(tokens)


def _is_hub_file(rel: str) -> bool:
    """Return True if *rel* is a known hub/entrypoint-style file."""
    return rel in _HUB_FILES or PurePosixPath(rel).name == "__init__.py"


def _task_has_hub_keyword(task_keywords: list[str]) -> bool:
    """Return True when the task explicitly targets CLI/command topics."""
    return any(kw in _HUB_KEYWORDS for kw in task_keywords)
