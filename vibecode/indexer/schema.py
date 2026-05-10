"""Dataclasses for context cards and risk items."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Fact:
    """A deterministic, verifiable finding in a file."""

    kind: str  # "todo", "fixme", "unsafe_permission"
    line: int  # 0 means file-level (not line-specific)
    text: str


@dataclass
class Heuristic:
    """A code-smell heuristic finding in a file."""

    kind: str  # "high_param_count", "suspicious_name"
    symbol: str
    detail: str


@dataclass
class RiskItem:
    """Risk evaluation result with supporting facts and heuristics."""

    path: str
    risk_level: str
    reasons: list[str] = field(default_factory=list)
    facts: list[Fact] = field(default_factory=list)
    heuristics: list[Heuristic] = field(default_factory=list)


@dataclass
class ContextCard:
    """Parsed context information for a single file."""

    path: str
    language: str
    module_docstring: str | None
    symbols: list[str] = field(default_factory=list)
    facts: list[Fact] = field(default_factory=list)
    heuristics: list[Heuristic] = field(default_factory=list)
    detail_level: str = "basic"
