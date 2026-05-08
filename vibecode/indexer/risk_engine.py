"""Risk engine: project config and filename heuristic risk classification."""

from __future__ import annotations

import fnmatch
import warnings
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_HEURISTIC_KEYWORDS: frozenset[str] = frozenset({
    "matching",
    "policy",
    "state",
    "migration",
    "auth",
    "security",
    "tax",
    "fx",
    "payments",
    "permissions",
})

_SENSITIVE_DIR_SEGMENTS: frozenset[str] = frozenset({"docs", "audit", "architecture"})

_SEVERITY_ORDER: dict[str, int] = {"low": 0, "medium": 1, "high": 2}
_VALID_SEVERITIES: frozenset[str] = frozenset(_SEVERITY_ORDER)


def _severity_cmp(level: str) -> int:
    return _SEVERITY_ORDER.get(level, 0)


# ---------------------------------------------------------------------------
# Glob matching
# ---------------------------------------------------------------------------


def _matches_glob(path: str, pattern: str) -> bool:
    """Return True if *path* matches *pattern*.

    Supports standard fnmatch patterns and ``dir/**`` directory globs.
    """
    if fnmatch.fnmatch(path, pattern):
        return True
    # "some/dir/**" → match "some/dir" itself and everything below it
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        if path == prefix or path.startswith(prefix + "/"):
            return True
    return False


# ---------------------------------------------------------------------------
# Heuristics
# ---------------------------------------------------------------------------


def _find_keyword(path: str) -> Optional[str]:
    """Return the first sensitive keyword found in the filename stem, or None."""
    stem = PurePosixPath(path).stem.lower()
    # Split on common separators to check individual words
    word_parts = stem.replace("-", "_").split("_")
    for word in word_parts:
        if word in _HEURISTIC_KEYWORDS:
            return word
    # Substring check for compound identifiers like "payment_matching"
    for kw in sorted(_HEURISTIC_KEYWORDS):
        if kw in stem:
            return kw
    return None


def _is_sensitive_dir(path: str) -> bool:
    """Return True if *path* lives under docs/, audit/, or architecture/."""
    dir_parts = path.split("/")[:-1]
    return any(p in _SENSITIVE_DIR_SEGMENTS for p in dir_parts)


# ---------------------------------------------------------------------------
# RiskResult
# ---------------------------------------------------------------------------


@dataclass
class RiskResult:
    """Risk evaluation result for a single file."""

    path: str
    risk_level: str
    reasons: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------


def evaluate_risk(
    path: str,
    base_risk: str,
    protected_paths: list[str],
    risk_rules: list[dict],
) -> RiskResult:
    """Return a :class:`RiskResult` for *path*.

    Priority (highest first):
    1. explicit ``protected_paths`` → always ``"high"``
    2. ``risk_rules`` entries → configured severity
    3. filename heuristics → ``"high"``
    4. docs / audit / architecture directory → at least ``"medium"``
    5. ``base_risk`` from the classifier

    The final risk level is the maximum severity across all matching rules.
    """
    risk_level = base_risk
    reasons: list[str] = []

    # 4. sensitive directory → floor at medium
    if _is_sensitive_dir(path) and _severity_cmp(risk_level) < _severity_cmp("medium"):
        risk_level = "medium"
        reasons.append("file is in a docs/audit/architecture directory (minimum medium risk)")

    # 3. filename heuristics
    kw = _find_keyword(path)
    if kw:
        if _severity_cmp("high") > _severity_cmp(risk_level):
            risk_level = "high"
        reasons.append(f"filename contains sensitive keyword '{kw}'")

    # 2. risk_rules
    for rule in risk_rules:
        if not isinstance(rule, dict):
            continue
        pattern = str(rule.get("pattern") or "")
        severity = str(rule.get("severity") or "high")
        if severity not in _VALID_SEVERITIES:
            severity = "high"
        reason_text = str(
            rule.get("reason") or f"matches risk rule pattern '{pattern}'"
        )
        if pattern and _matches_glob(path, pattern):
            if _severity_cmp(severity) > _severity_cmp(risk_level):
                risk_level = severity
            reasons.append(f"risk rule: {reason_text}")

    # 1. explicit protected_paths (highest priority)
    for pattern in protected_paths:
        if _matches_glob(path, pattern):
            risk_level = "high"
            reasons.append(f"explicitly protected path (pattern: '{pattern}')")
            break

    if not reasons:
        reasons.append(f"base role classification ({base_risk})")

    return RiskResult(path=path, risk_level=risk_level, reasons=reasons)


# ---------------------------------------------------------------------------
# Batch helper
# ---------------------------------------------------------------------------


def build_risk_index(
    file_records: list,
    protected_paths: list[str],
    risk_rules: list[dict],
    run_log: list[str] | None = None,
) -> dict[str, RiskResult]:
    """Return a mapping of path → :class:`RiskResult` for all *file_records*.

    Emits a :class:`UserWarning` (and logs to *run_log*) when *protected_paths*
    is empty.

    *file_records* must be objects with ``path`` and ``risk_level`` attributes
    (e.g. :class:`~vibecode.indexer.classifier.FileRecord`).
    """
    if not protected_paths:
        msg = "protected_paths is empty; no paths are explicitly protected"
        warnings.warn(msg, UserWarning, stacklevel=2)
        if run_log is not None:
            run_log.append(f"WARNING: {msg}")

    index: dict[str, RiskResult] = {}
    for rec in file_records:
        result = evaluate_risk(rec.path, rec.risk_level, protected_paths, risk_rules)
        index[rec.path] = result
    return index
