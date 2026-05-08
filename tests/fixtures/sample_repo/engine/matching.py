"""Matching engine for the sample application.

High-risk module: contains core scoring and matching logic.
"""

from __future__ import annotations


def match_candidates(query: str, candidates: list[str]) -> list[str]:
    """Return candidates that contain the query string (case-insensitive)."""
    q = query.lower()
    return [c for c in candidates if q in c.lower()]


class MatchingEngine:
    """Core engine for candidate matching."""

    def rank(self, query: str, candidates: list[str]) -> list[tuple[str, float]]:
        """Return (candidate, score) pairs sorted by descending score."""
        matches = match_candidates(query, candidates)
        return [(m, 1.0) for m in matches]
