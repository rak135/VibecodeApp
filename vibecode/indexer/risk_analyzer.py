"""Deterministic fact extraction and heuristic analysis for source files."""

from __future__ import annotations

import re
import stat
from pathlib import Path

from vibecode.indexer.schema import Fact, Heuristic

# ---------------------------------------------------------------------------
# Facts
# ---------------------------------------------------------------------------

_TODO_RE = re.compile(r"\b(TODO|FIXME)\b[:\s]*(.*)", re.IGNORECASE)

_HIGH_PARAM_COUNT_THRESHOLD = 5

_SUSPICIOUS_NAMES: frozenset[str] = frozenset({
    "hack",
    "kludge",
    "workaround",
    "bandaid",
    "dirty",
    "evil",
})


def analyze_facts(abs_path: Path, content: str) -> list[Fact]:
    """Return deterministic :class:`~vibecode.indexer.schema.Fact` objects for *content*.

    Detects:
    * ``TODO`` / ``FIXME`` comments (any case).
    * World-writable file permission (``S_IWOTH``), when the OS supports it.
    """
    facts: list[Fact] = []

    for lineno, line in enumerate(content.splitlines(), start=1):
        m = _TODO_RE.search(line)
        if m:
            kind = m.group(1).lower()
            text = m.group(2).strip() or line.strip()
            facts.append(Fact(kind=kind, line=lineno, text=text))

    try:
        mode = abs_path.stat().st_mode
        if mode & stat.S_IWOTH:
            facts.append(Fact(kind="unsafe_permission", line=0, text="world-writable file"))
    except OSError:
        pass

    return facts


# ---------------------------------------------------------------------------
# Heuristics
# ---------------------------------------------------------------------------


def analyze_heuristics(functions: list[dict]) -> list[Heuristic]:
    """Return :class:`~vibecode.indexer.schema.Heuristic` objects for *functions*.

    *functions* is the list produced by :func:`~vibecode.indexer.ast_parser.parse_python_file`
    (each item has ``name``, ``param_count``, ``lineno``).

    Detects:
    * Functions with more than :data:`_HIGH_PARAM_COUNT_THRESHOLD` parameters.
    * Functions whose name contains a known suspicious word.
    """
    heuristics: list[Heuristic] = []
    for fn in functions:
        if fn["param_count"] > _HIGH_PARAM_COUNT_THRESHOLD:
            heuristics.append(Heuristic(
                kind="high_param_count",
                symbol=fn["name"],
                detail=f"{fn['param_count']} parameters",
                severity="medium",
            ))
        name_lower = fn["name"].lower()
        for sus in _SUSPICIOUS_NAMES:
            if sus in name_lower:
                heuristics.append(Heuristic(
                    kind="suspicious_name",
                    symbol=fn["name"],
                    detail=f"name contains '{sus}'",
                    severity="low",
                ))
                break
    return heuristics
