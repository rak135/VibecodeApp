"""TypeScript/JavaScript symbol extractor using heuristic line scanning.

No compiler or AST required — uses regex patterns to extract top-level
symbols from ``.ts``, ``.tsx``, ``.js``, and ``.jsx`` files.
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path

from .symbols import Symbol

_TS_EXTS: frozenset[str] = frozenset({".ts", ".tsx", ".js", ".jsx"})
_REACT_EXTS: frozenset[str] = frozenset({".tsx", ".jsx"})

# Each entry: (compiled regex, base kind).
# Patterns are tried in order; the first match wins per line.
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # interface declarations
    (re.compile(r"^\s*(?:export\s+)?interface\s+(\w+)"), "interface"),
    # type alias declarations  (must come before const/function to avoid
    # matching `type` as a variable name in other constructs)
    (re.compile(r"^\s*(?:export\s+)?type\s+(\w+)\s"), "type"),
    # function declarations (regular, async, generator, default-exported)
    (re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*(\w+)"), "function"),
    # const declarations  (matches `const Name =` and `const Name:`)
    (re.compile(r"^\s*(?:export\s+)?const\s+(\w+)\s*[=:]"), "const"),
]

_PASCAL_RE: re.Pattern[str] = re.compile(r"^[A-Z][a-zA-Z0-9]*$")


def extract_ts_symbols(path: str | Path) -> list[Symbol]:
    """Return symbols extracted from a TypeScript or JavaScript file at *path*.

    Detected kinds:

    * ``function`` — regular and async function declarations
    * ``const`` — const variable declarations
    * ``interface`` — TypeScript interface declarations
    * ``type`` — TypeScript type alias declarations
    * ``component`` — PascalCase function/const in ``.tsx`` / ``.jsx`` files

    Returns an empty list for unsupported file extensions or on read errors.
    ``line_end`` is always ``None`` because block end cannot be determined
    reliably without a full parser.
    """
    p = Path(path)
    if p.suffix.lower() not in _TS_EXTS:
        return []

    try:
        source = p.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        warnings.warn(f"Skipping {posix}: cannot read file: {exc}", UserWarning, stacklevel=2)
        return []

    posix = p.as_posix()
    is_react = p.suffix.lower() in _REACT_EXTS
    symbols: list[Symbol] = []

    for lineno, line in enumerate(source.splitlines(), start=1):
        for pattern, base_kind in _PATTERNS:
            m = pattern.match(line)
            if m:
                name = m.group(1)
                kind = _classify_kind(name, base_kind, is_react)
                symbols.append(
                    Symbol(
                        path=posix,
                        name=name,
                        kind=kind,
                        line_start=lineno,
                        line_end=None,
                    )
                )
                break  # only the first matching pattern applies per line

    return symbols


def _classify_kind(name: str, base_kind: str, is_react: bool) -> str:
    """Promote PascalCase function/const declarations in React files to *component*."""
    if is_react and base_kind in {"function", "const"} and _PASCAL_RE.match(name):
        return "component"
    return base_kind
