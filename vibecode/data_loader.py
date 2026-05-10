"""Single source of truth for loading project inventory and risk data."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ProjectData:
    """Parsed inventory and risk data, ready for the MCP server and TUI."""

    inventory: dict = field(default_factory=dict)
    risk_report: dict = field(default_factory=dict)
    cards: list[dict] = field(default_factory=list)
    total_files: int = 0
    high_risk_count: int = 0
    inventory_missing: bool = False
    risk_report_missing: bool = False


def _load_json(path: Path) -> tuple[dict, bool]:
    """Load JSON from *path*.

    Returns ``(data, is_missing)`` where *is_missing* is ``True`` when the
    file does not exist.  Parse/IO errors are printed to stderr and treated
    as empty data (not missing).
    """
    if not path.exists():
        return {}, True
    try:
        return json.loads(path.read_text(encoding="utf-8")), False
    except (json.JSONDecodeError, OSError) as exc:
        print(f"Warning: failed to load {path.name}: {exc}", file=sys.stderr)
        return {}, False


def load_project_data(repo_root: Path) -> ProjectData:
    """Load ``file_inventory.json`` and ``risk_report.json`` from *.vibecode/index/*.

    Normalises ``None`` list fields on each card (``symbols``, ``facts``,
    ``heuristics``) to ``[]`` so callers never have to guard against ``None``.
    Missing files are recorded in the returned :class:`ProjectData` so callers
    can prompt the user to run ``vibecode inventory``.
    """
    index_dir = repo_root / ".vibecode" / "index"

    inventory, inv_missing = _load_json(index_dir / "file_inventory.json")
    risk_report, risk_missing = _load_json(index_dir / "risk_report.json")

    cards: list[dict] = list(inventory.get("context_cards", []))
    for card in cards:
        for key in ("symbols", "facts", "heuristics"):
            if card.get(key) is None:
                card[key] = []

    total_files = len(inventory.get("files", []))

    high_risk_count = 0
    for entry in risk_report.get("files", []):
        if entry.get("risk_level") == "high":
            high_risk_count += 1
        elif any(h.get("severity") == "high" for h in entry.get("heuristics", [])):
            high_risk_count += 1

    return ProjectData(
        inventory=inventory,
        risk_report=risk_report,
        cards=cards,
        total_files=total_files,
        high_risk_count=high_risk_count,
        inventory_missing=inv_missing,
        risk_report_missing=risk_missing,
    )
