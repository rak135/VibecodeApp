"""AST-based parser for Python files.

Extracts module docstrings and function/class symbol names for context cards.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ParseResult:
    """Result of parsing a single Python file."""

    module_docstring: str | None
    symbols: list[str] = field(default_factory=list)
    functions: list[dict] = field(default_factory=list)


_EMPTY = ParseResult(module_docstring=None)


def parse_python_file(path: Path) -> ParseResult:
    """Return parsed symbols and docstring from *path*.

    Returns an empty :class:`ParseResult` when the file cannot be read or
    contains a syntax error.
    """
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return _EMPTY

    try:
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, ValueError):
        return _EMPTY

    docstring = ast.get_docstring(tree)
    symbols: list[str] = []
    functions: list[dict] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(node.name)
            args = node.args
            param_count = (
                len(getattr(args, "posonlyargs", []))
                + len(args.args)
                + len(args.kwonlyargs)
                + (1 if args.vararg else 0)
                + (1 if args.kwarg else 0)
            )
            functions.append({
                "name": node.name,
                "param_count": param_count,
                "lineno": node.lineno,
            })
        elif isinstance(node, ast.ClassDef):
            symbols.append(node.name)

    return ParseResult(
        module_docstring=docstring,
        symbols=symbols,
        functions=functions,
    )
