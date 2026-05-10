"""Write .vibecode/index/risk_report.json with per-file facts and heuristics."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from vibecode.indexer.schema import Fact, Heuristic, RiskItem

_SCHEMA = "vibecode/risk-report/v1"


def _fact_to_dict(fact: Fact) -> dict:
    return {"kind": fact.kind, "line": fact.line, "text": fact.text}


def _heuristic_to_dict(h: Heuristic) -> dict:
    return {"kind": h.kind, "symbol": h.symbol, "detail": h.detail, "severity": h.severity}


def build_risk_report(
    project_id: str,
    root: Path,
    risk_items: list[RiskItem],
) -> dict:
    """Return the risk report dict from a list of :class:`~vibecode.indexer.schema.RiskItem` objects."""
    records = []
    for item in risk_items:
        records.append({
            "path": item.path,
            "risk_level": item.risk_level,
            "reasons": item.reasons,
            "facts": [_fact_to_dict(f) for f in item.facts],
            "heuristics": [_heuristic_to_dict(h) for h in item.heuristics],
        })
    return {
        "$schema": _SCHEMA,
        "project_id": project_id,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "root": root.as_posix(),
        "files": records,
    }


def write_risk_report(
    project_id: str,
    root: Path,
    risk_items: list[RiskItem],
    output_path: Path,
) -> None:
    """Write the risk report JSON to *output_path*, creating parent dirs as needed."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report = build_risk_report(project_id, root, risk_items)
    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
