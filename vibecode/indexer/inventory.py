"""File inventory JSON writer for vibecode."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from vibecode.indexer.classifier import classify
from vibecode.indexer.scanner import FileStatus, IndexedFile

_SCHEMA = "vibecode/file-inventory/v1"


def _build_card_dict(
    card_rec: dict,
    root: Path,
    detail_level: str,
    compute_heuristics: bool,
) -> dict | None:
    """Return a context card dict for a Python file, or None on failure."""
    from vibecode.indexer.ast_parser import parse_python_file
    from vibecode.indexer.risk_analyzer import analyze_facts, analyze_heuristics

    abs_path = root / Path(card_rec["path"].replace("/", "\\"))
    if not abs_path.is_file():
        # Try with POSIX path join (cross-platform)
        abs_path = root / card_rec["path"]
    if not abs_path.is_file():
        return None

    parsed = parse_python_file(abs_path)

    try:
        content = abs_path.read_text(encoding="utf-8")
    except OSError:
        content = ""

    facts = analyze_facts(abs_path, content)
    heuristics = analyze_heuristics(parsed.functions) if compute_heuristics else []

    card: dict = {
        "path": card_rec["path"],
        "language": "python",
        "module_docstring": parsed.module_docstring,
        "symbols": parsed.symbols,
        "detail_level": detail_level,
        "facts": [{"kind": f.kind, "line": f.line, "text": f.text} for f in facts],
        "heuristics": [
            {"kind": h.kind, "symbol": h.symbol, "detail": h.detail} for h in heuristics
        ],
    }
    return card


def build_inventory(
    project_id: str,
    root: Path,
    indexed_files: list[IndexedFile],
    risk_index: dict | None = None,
    generate_cards: bool = False,
    card_detail: str = "basic",
    compute_heuristics: bool = True,
) -> dict:
    """Return the inventory dict from a list of scanned :class:`IndexedFile` objects.

    When *risk_index* (a mapping of path → :class:`~vibecode.indexer.risk_engine.RiskResult`)
    is provided, the ``risk_level`` field for each file is taken from the risk engine
    result rather than the base classifier value.

    When *generate_cards* is True, each Python file is also parsed via
    :mod:`~vibecode.indexer.ast_parser` and a ``cards`` list is included in the
    output, with one :class:`~vibecode.indexer.schema.ContextCard`-shaped dict per
    Python file.  *card_detail* (``"basic"`` or ``"full"``) and *compute_heuristics*
    control the card content.
    """
    records = []
    for f in indexed_files:
        rec = classify(f.path, f.size)
        risk_level = rec.risk_level
        if risk_index and rec.path in risk_index:
            risk_level = risk_index[rec.path].risk_level
        entry: dict = {
            "path": rec.path,
            "language": rec.language,
            "size_bytes": rec.size_bytes,
            "role_guess": rec.role_guess,
            "is_test": rec.is_test,
            "is_config": rec.is_config,
            "is_doc": rec.is_doc,
            "risk_level": risk_level,
        }
        if f.status != FileStatus.UNKNOWN:
            entry["tracked"] = f.status.value
        records.append(entry)

    result: dict = {
        "$schema": _SCHEMA,
        "project_id": project_id,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "root": root.as_posix(),
        "files": records,
    }

    if generate_cards:
        cards = []
        for rec in records:
            if rec.get("language") == "python":
                card = _build_card_dict(rec, root, card_detail, compute_heuristics)
                if card is not None:
                    cards.append(card)
        result["cards"] = cards

    return result


def write_inventory(
    project_id: str,
    root: Path,
    indexed_files: list[IndexedFile],
    output_path: Path,
    risk_index: dict | None = None,
    generate_cards: bool = False,
    card_detail: str = "basic",
    compute_heuristics: bool = True,
) -> None:
    """Write the inventory JSON to *output_path*, creating parent dirs as needed."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    inventory = build_inventory(
        project_id,
        root,
        indexed_files,
        risk_index=risk_index,
        generate_cards=generate_cards,
        card_detail=card_detail,
        compute_heuristics=compute_heuristics,
    )
    output_path.write_text(
        json.dumps(inventory, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
