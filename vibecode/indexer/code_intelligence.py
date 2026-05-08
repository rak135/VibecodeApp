"""Code intelligence provider interface and built-in implementations.

A :class:`CodeIntelligenceProvider` returns a symbol map (path → symbol
names) for a given repository root.  The context builder depends on this
interface rather than on a specific index format or tool, so future providers
(e.g. a running Serena MCP server) can be plugged in without touching the
renderer.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class CodeIntelligenceProvider(Protocol):
    """Provide symbol information for files in a repository."""

    def get_symbol_map(self, repo_root: Path) -> dict[str, list[str]]:
        """Return ``{relative_path: [symbol_name, ...]}`` for *repo_root*.

        Returns an empty dict when no information is available.
        """
        ...


class SymbolMapProvider:
    """Built-in provider that reads from ``.vibecode/index/symbol_map.json``.

    Only symbol *names* are surfaced — never file content.  Returns an empty
    dict when the index file is absent or unreadable.
    """

    _INDEX_PATH = Path(".vibecode") / "index" / "symbol_map.json"

    def get_symbol_map(self, repo_root: Path) -> dict[str, list[str]]:
        symbol_map_path = repo_root / self._INDEX_PATH
        if not symbol_map_path.is_file():
            return {}
        try:
            data = json.loads(symbol_map_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        result: dict[str, list[str]] = {}
        for entry in data.get("files") or []:
            path = entry.get("path", "")
            names = [
                s["name"]
                for s in (entry.get("symbols") or [])
                if isinstance(s, dict) and s.get("name")
            ]
            if path and names:
                result[path] = names
        return result


class SerenaProvider:
    """Placeholder for future Serena-based code intelligence (MCP server).

    Not implemented yet.  Raises :exc:`NotImplementedError` until an MCP
    connection is wired up.
    """

    def get_symbol_map(self, repo_root: Path) -> dict[str, list[str]]:  # noqa: ARG002
        raise NotImplementedError(
            "SerenaProvider requires a running Serena MCP server and is not yet implemented."
        )


#: Default provider used by the context builder.
DEFAULT_PROVIDER: CodeIntelligenceProvider = SymbolMapProvider()
