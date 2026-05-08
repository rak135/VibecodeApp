"""Symbol map builder: combines Python and TS/TSX extractors into symbol_map.json.

Strategy for files without symbols
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Files that yield no symbols (empty source, unsupported language, or a parse
error) are **omitted** from the ``files`` list.  This keeps the output compact
and avoids polluting context packs with noise entries.  Parse errors are
recorded in the *run_log* list instead of being hidden.
"""

from __future__ import annotations

import json
import warnings
from datetime import datetime, timezone
from pathlib import Path

from vibecode.indexer.classifier import detect_language
from vibecode.indexer.scanner import IndexedFile
from vibecode.indexer.symbols import Symbol, extract_python_symbols
from vibecode.indexer.ts_symbols import extract_ts_symbols

_SCHEMA = "vibecode/symbol-map/v1"

_PY_LANG = "python"
_TS_LANGS: frozenset[str] = frozenset({
    "typescript",
    "typescriptreact",
    "javascript",
    "javascriptreact",
})


def _symbols_to_dicts(symbols: list[Symbol]) -> list[dict]:
    result = []
    for s in symbols:
        entry: dict = {"name": s.name, "kind": s.kind, "line_start": s.line_start}
        if s.line_end is not None:
            entry["line_end"] = s.line_end
        result.append(entry)
    return result


def build_symbol_map(
    root: Path,
    indexed_files: list[IndexedFile],
    run_log: list[str] | None = None,
) -> dict:
    """Return the symbol map dict from a list of :class:`IndexedFile` objects.

    Files without symbols are omitted (see module docstring for rationale).
    Parsing errors are appended to *run_log* when provided.
    """
    files_out = []

    for f in indexed_files:
        language = detect_language(f.path)
        abs_path = root / Path(f.path)

        if language == _PY_LANG:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                symbols = extract_python_symbols(abs_path)
            for w in caught:
                if run_log is not None:
                    run_log.append(str(w.message))
        elif language in _TS_LANGS:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                symbols = extract_ts_symbols(abs_path)
            for w in caught:
                if run_log is not None:
                    run_log.append(str(w.message))
        else:
            continue  # unsupported language — omit

        if not symbols:
            continue  # no symbols found — omit

        files_out.append({
            "path": f.path,
            "language": language,
            "symbols": _symbols_to_dicts(symbols),
        })

    return {
        "$schema": _SCHEMA,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "files": files_out,
    }


def write_symbol_map(
    root: Path,
    indexed_files: list[IndexedFile],
    output_path: Path,
    run_log: list[str] | None = None,
) -> None:
    """Write the symbol map JSON to *output_path*, creating parent dirs as needed."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = build_symbol_map(root, indexed_files, run_log=run_log)
    output_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
