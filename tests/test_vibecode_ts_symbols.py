"""Tests for TypeScript/JavaScript symbol extraction (vibecode.indexer.ts_symbols)."""

from __future__ import annotations

from pathlib import Path

from vibecode.indexer.symbols import Symbol
from vibecode.indexer.ts_symbols import extract_ts_symbols


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _by_name(symbols: list[Symbol]) -> dict[str, Symbol]:
    return {s.name: s for s in symbols}


# ---------------------------------------------------------------------------
# TSX component detection
# ---------------------------------------------------------------------------


class TestTsxComponent:
    def test_export_function_component_detected(self, tmp_path):
        src = "export function MyButton(): JSX.Element {\n  return <button />;\n}\n"
        f = _write(tmp_path / "MyButton.tsx", src)
        syms = extract_ts_symbols(f)
        assert any(s.name == "MyButton" and s.kind == "component" for s in syms)

    def test_export_const_arrow_component_detected(self, tmp_path):
        src = "export const MyCard = (): JSX.Element => {\n  return <div />;\n};\n"
        f = _write(tmp_path / "MyCard.tsx", src)
        syms = extract_ts_symbols(f)
        assert any(s.name == "MyCard" and s.kind == "component" for s in syms)

    def test_jsx_file_component_detected(self, tmp_path):
        src = "export function Banner() {\n  return <div>hi</div>;\n}\n"
        f = _write(tmp_path / "Banner.jsx", src)
        syms = extract_ts_symbols(f)
        assert any(s.name == "Banner" and s.kind == "component" for s in syms)

    def test_ts_file_pascal_not_promoted_to_component(self, tmp_path):
        """PascalCase in a plain .ts file must NOT be promoted to component."""
        src = "export function MyService() {}\n"
        f = _write(tmp_path / "service.ts", src)
        syms = _by_name(extract_ts_symbols(f))
        assert syms["MyService"].kind == "function"

    def test_line_start_recorded(self, tmp_path):
        src = "// header\nexport function Widget() {\n  return null;\n}\n"
        f = _write(tmp_path / "Widget.tsx", src)
        syms = _by_name(extract_ts_symbols(f))
        assert syms["Widget"].line_start == 2

    def test_line_end_is_none(self, tmp_path):
        src = "export function Thing() {\n  return null;\n}\n"
        f = _write(tmp_path / "Thing.tsx", src)
        syms = _by_name(extract_ts_symbols(f))
        assert syms["Thing"].line_end is None

    def test_does_not_crash_on_jsx_syntax(self, tmp_path):
        src = (
            "import React from 'react';\n"
            "export const Comp = () => (\n"
            "  <div className=\"x\">{value && <span />}</div>\n"
            ");\n"
        )
        f = _write(tmp_path / "Comp.tsx", src)
        syms = extract_ts_symbols(f)  # must not raise
        assert any(s.name == "Comp" for s in syms)


# ---------------------------------------------------------------------------
# Hook detection
# ---------------------------------------------------------------------------


class TestHook:
    def test_const_hook_detected(self, tmp_path):
        src = "export const useCounter = (initial: number) => {\n  return initial;\n};\n"
        f = _write(tmp_path / "hooks.ts", src)
        syms = extract_ts_symbols(f)
        assert any(s.name == "useCounter" and s.kind == "const" for s in syms)

    def test_function_hook_detected(self, tmp_path):
        src = "export function useTheme() {\n  return {};\n}\n"
        f = _write(tmp_path / "hooks.ts", src)
        syms = extract_ts_symbols(f)
        assert any(s.name == "useTheme" and s.kind == "function" for s in syms)

    def test_hook_not_promoted_to_component_in_tsx(self, tmp_path):
        """Hooks start with lowercase 'use', so they must NOT become component."""
        src = "export const useSomething = () => {};\n"
        f = _write(tmp_path / "hooks.tsx", src)
        syms = extract_ts_symbols(f)
        assert any(s.name == "useSomething" and s.kind == "const" for s in syms)

    def test_hook_line_start(self, tmp_path):
        src = "// top\nexport const useData = () => {};\n"
        f = _write(tmp_path / "hooks.ts", src)
        syms = _by_name(extract_ts_symbols(f))
        assert syms["useData"].line_start == 2


# ---------------------------------------------------------------------------
# Interface and type declarations
# ---------------------------------------------------------------------------


class TestInterfaceAndType:
    def test_exported_interface_detected(self, tmp_path):
        src = "export interface UserProfile {\n  name: string;\n}\n"
        f = _write(tmp_path / "types.ts", src)
        syms = extract_ts_symbols(f)
        assert any(s.name == "UserProfile" and s.kind == "interface" for s in syms)

    def test_unexported_interface_detected(self, tmp_path):
        src = "interface InternalConfig {\n  debug: boolean;\n}\n"
        f = _write(tmp_path / "config.ts", src)
        syms = extract_ts_symbols(f)
        assert any(s.name == "InternalConfig" and s.kind == "interface" for s in syms)

    def test_exported_type_alias_detected(self, tmp_path):
        src = "export type ApiResponse = {\n  data: unknown;\n};\n"
        f = _write(tmp_path / "types.ts", src)
        syms = extract_ts_symbols(f)
        assert any(s.name == "ApiResponse" and s.kind == "type" for s in syms)

    def test_unexported_type_alias_detected(self, tmp_path):
        src = "type Status = 'active' | 'inactive';\n"
        f = _write(tmp_path / "status.ts", src)
        syms = extract_ts_symbols(f)
        assert any(s.name == "Status" and s.kind == "type" for s in syms)

    def test_multiple_types_in_one_file(self, tmp_path):
        src = (
            "export interface Req {\n  id: number;\n}\n"
            "export interface Res {\n  ok: boolean;\n}\n"
            "export type Handler = (r: Req) => Res;\n"
        )
        f = _write(tmp_path / "api.ts", src)
        syms = _by_name(extract_ts_symbols(f))
        assert syms["Req"].kind == "interface"
        assert syms["Res"].kind == "interface"
        assert syms["Handler"].kind == "type"


# ---------------------------------------------------------------------------
# Non-TS/JS files return empty list
# ---------------------------------------------------------------------------


class TestNonTsFiles:
    def test_css_returns_empty(self, tmp_path):
        src = ".button { color: red; }\nfunction fakeTs() {}\n"
        f = _write(tmp_path / "styles.css", src)
        assert extract_ts_symbols(f) == []

    def test_json_returns_empty(self, tmp_path):
        src = '{"type": "object", "const": "foo", "interface": "bar"}\n'
        f = _write(tmp_path / "data.json", src)
        assert extract_ts_symbols(f) == []

    def test_py_returns_empty(self, tmp_path):
        src = "def foo(): pass\n"
        f = _write(tmp_path / "script.py", src)
        assert extract_ts_symbols(f) == []

    def test_txt_returns_empty(self, tmp_path):
        src = "const x = 1;\nfunction y() {}\n"
        f = _write(tmp_path / "notes.txt", src)
        assert extract_ts_symbols(f) == []


# ---------------------------------------------------------------------------
# Miscellaneous
# ---------------------------------------------------------------------------


class TestMiscellaneous:
    def test_path_stored_as_posix(self, tmp_path):
        src = "function greet() {}\n"
        f = _write(tmp_path / "greet.ts", src)
        syms = extract_ts_symbols(f)
        assert all(s.path == f.as_posix() for s in syms)

    def test_empty_file_returns_empty(self, tmp_path):
        f = _write(tmp_path / "empty.ts", "")
        assert extract_ts_symbols(f) == []

    def test_async_function_detected(self, tmp_path):
        src = "export async function fetchData() {\n  return await api();\n}\n"
        f = _write(tmp_path / "fetch.ts", src)
        syms = extract_ts_symbols(f)
        assert any(s.name == "fetchData" and s.kind == "function" for s in syms)

    def test_unexported_function_detected(self, tmp_path):
        src = "function helper() { return 1; }\n"
        f = _write(tmp_path / "util.ts", src)
        syms = extract_ts_symbols(f)
        assert any(s.name == "helper" and s.kind == "function" for s in syms)

    def test_unexported_const_detected(self, tmp_path):
        src = "const MAX_RETRIES = 3;\n"
        f = _write(tmp_path / "config.ts", src)
        syms = extract_ts_symbols(f)
        assert any(s.name == "MAX_RETRIES" and s.kind == "const" for s in syms)
