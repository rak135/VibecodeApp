"""Python symbol extractor using the standard ``ast`` module."""

from __future__ import annotations

import ast
import warnings
from dataclasses import dataclass
from pathlib import Path

_ROUTE_ATTRS: frozenset[str] = frozenset({"get", "post", "put", "delete", "patch"})


@dataclass
class Symbol:
    """A single symbol extracted from a Python source file."""

    path: str
    name: str
    kind: str
    line_start: int
    line_end: int | None


def extract_python_symbols(path: str | Path) -> list[Symbol]:
    """Return symbols defined in the Python file at *path*.

    Detected kinds: ``class``, ``function``, ``async_function``, ``method``,
    ``async_method``, and ``api_route`` (for FastAPI-style route decorators).

    Syntax errors are emitted as :class:`UserWarning` and result in an empty
    list rather than raising an exception.
    """
    p = Path(path)
    posix = p.as_posix()
    try:
        source = p.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(p))
    except SyntaxError as exc:
        warnings.warn(f"Skipping {posix}: syntax error: {exc}", UserWarning, stacklevel=2)
        return []
    except OSError as exc:
        warnings.warn(f"Skipping {posix}: cannot read file: {exc}", UserWarning, stacklevel=2)
        return []

    visitor = _SymbolVisitor(posix)
    visitor.visit(tree)
    return visitor.symbols


# ---------------------------------------------------------------------------
# AST visitor
# ---------------------------------------------------------------------------


class _SymbolVisitor(ast.NodeVisitor):
    def __init__(self, path: str) -> None:
        self._path = path
        # Tracks the names of enclosing class scopes.  Cleared on function
        # entry so that nested functions inside methods are not mis-labelled.
        self._class_stack: list[str] = []
        self.symbols: list[Symbol] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.symbols.append(
            Symbol(
                path=self._path,
                name=node.name,
                kind="class",
                line_start=node.lineno,
                line_end=getattr(node, "end_lineno", None),
            )
        )
        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_func(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_func(node, is_async=True)

    # ------------------------------------------------------------------

    def _visit_func(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, *, is_async: bool
    ) -> None:
        kind = self._classify_func(node, is_async=is_async)
        self.symbols.append(
            Symbol(
                path=self._path,
                name=node.name,
                kind=kind,
                line_start=node.lineno,
                line_end=getattr(node, "end_lineno", None),
            )
        )
        # Clear class context so nested functions/classes inside this
        # function body are not treated as class members.
        saved = self._class_stack[:]
        self._class_stack.clear()
        self.generic_visit(node)
        self._class_stack[:] = saved

    def _classify_func(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, *, is_async: bool
    ) -> str:
        for dec in node.decorator_list:
            if _is_route_decorator(dec):
                return "api_route"
        if self._class_stack:
            return "async_method" if is_async else "method"
        return "async_function" if is_async else "function"


# ---------------------------------------------------------------------------
# Decorator helpers
# ---------------------------------------------------------------------------


def _is_route_decorator(dec: ast.expr) -> bool:
    """Return True if *dec* looks like a FastAPI/Starlette route decorator.

    Matches patterns such as ``@app.get(...)``, ``@router.post(...)``, etc.
    """
    node = dec.func if isinstance(dec, ast.Call) else dec
    return isinstance(node, ast.Attribute) and node.attr in _ROUTE_ATTRS
