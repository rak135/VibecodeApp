"""Tests for code intelligence providers (vibecode.indexer.code_intelligence)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecode.indexer.code_intelligence import (
    CodeIntelligenceProvider,
    DEFAULT_PROVIDER,
    SerenaProvider,
    SymbolMapProvider,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _symbol_map_json(files: list[dict]) -> str:
    return json.dumps({"$schema": "vibecode/symbol-map/v1", "files": files}, indent=2) + "\n"


def _index_path(root: Path) -> Path:
    return root / ".vibecode" / "index" / "symbol_map.json"


# ---------------------------------------------------------------------------
# DEFAULT_PROVIDER
# ---------------------------------------------------------------------------


def test_default_provider_is_symbol_map_provider():
    assert isinstance(DEFAULT_PROVIDER, SymbolMapProvider)


def test_default_provider_satisfies_protocol():
    assert isinstance(DEFAULT_PROVIDER, CodeIntelligenceProvider)


# ---------------------------------------------------------------------------
# SymbolMapProvider — missing / unreadable file
# ---------------------------------------------------------------------------


def test_symbol_map_provider_missing_file_returns_empty(tmp_path):
    provider = SymbolMapProvider()
    result = provider.get_symbol_map(tmp_path)
    assert result == {}


def test_symbol_map_provider_invalid_json_returns_empty(tmp_path):
    _write(_index_path(tmp_path), "not valid json {{")
    provider = SymbolMapProvider()
    assert provider.get_symbol_map(tmp_path) == {}


# ---------------------------------------------------------------------------
# SymbolMapProvider — valid data
# ---------------------------------------------------------------------------


def test_symbol_map_provider_returns_names_for_file(tmp_path):
    _write(
        _index_path(tmp_path),
        _symbol_map_json([
            {
                "path": "src/foo.py",
                "language": "python",
                "symbols": [
                    {"name": "Foo", "kind": "class", "line_start": 1},
                    {"name": "bar", "kind": "function", "line_start": 5},
                ],
            }
        ]),
    )
    provider = SymbolMapProvider()
    result = provider.get_symbol_map(tmp_path)
    assert "src/foo.py" in result
    assert result["src/foo.py"] == ["Foo", "bar"]


def test_symbol_map_provider_multiple_files(tmp_path):
    _write(
        _index_path(tmp_path),
        _symbol_map_json([
            {
                "path": "a.py",
                "language": "python",
                "symbols": [{"name": "A", "kind": "class", "line_start": 1}],
            },
            {
                "path": "b.ts",
                "language": "typescript",
                "symbols": [{"name": "B", "kind": "function", "line_start": 1}],
            },
        ]),
    )
    provider = SymbolMapProvider()
    result = provider.get_symbol_map(tmp_path)
    assert set(result) == {"a.py", "b.ts"}
    assert result["a.py"] == ["A"]
    assert result["b.ts"] == ["B"]


def test_symbol_map_provider_empty_symbols_omitted(tmp_path):
    _write(
        _index_path(tmp_path),
        _symbol_map_json([
            {"path": "empty.py", "language": "python", "symbols": []},
        ]),
    )
    provider = SymbolMapProvider()
    assert provider.get_symbol_map(tmp_path) == {}


def test_symbol_map_provider_skips_symbol_without_name(tmp_path):
    _write(
        _index_path(tmp_path),
        _symbol_map_json([
            {
                "path": "m.py",
                "language": "python",
                "symbols": [
                    {"name": "Good", "kind": "class", "line_start": 1},
                    {"kind": "function", "line_start": 3},  # no name key
                ],
            }
        ]),
    )
    provider = SymbolMapProvider()
    result = provider.get_symbol_map(tmp_path)
    assert result["m.py"] == ["Good"]


# ---------------------------------------------------------------------------
# SerenaProvider
# ---------------------------------------------------------------------------


def test_serena_provider_raises_not_implemented(tmp_path):
    provider = SerenaProvider()
    with pytest.raises(NotImplementedError):
        provider.get_symbol_map(tmp_path)


def test_serena_provider_satisfies_protocol():
    # SerenaProvider structurally satisfies the Protocol (has get_symbol_map)
    provider = SerenaProvider()
    assert hasattr(provider, "get_symbol_map")
    assert callable(provider.get_symbol_map)
