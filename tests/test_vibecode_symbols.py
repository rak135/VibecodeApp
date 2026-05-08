"""Tests for Python symbol extraction (vibecode.indexer.symbols)."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from vibecode.indexer.symbols import Symbol, extract_python_symbols


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _symbols_by_name(symbols: list[Symbol]) -> dict[str, Symbol]:
    return {s.name: s for s in symbols}


# ---------------------------------------------------------------------------
# Basic symbol detection
# ---------------------------------------------------------------------------


class TestClassDetection:
    def test_class_found(self, tmp_path):
        f = _write(tmp_path / "m.py", "class Foo:\n    pass\n")
        syms = extract_python_symbols(f)
        names = {s.name for s in syms}
        assert "Foo" in names

    def test_class_kind(self, tmp_path):
        f = _write(tmp_path / "m.py", "class Bar:\n    pass\n")
        syms = _symbols_by_name(extract_python_symbols(f))
        assert syms["Bar"].kind == "class"

    def test_class_line_numbers(self, tmp_path):
        f = _write(tmp_path / "m.py", "class Baz:\n    x = 1\n    y = 2\n")
        syms = _symbols_by_name(extract_python_symbols(f))
        s = syms["Baz"]
        assert s.line_start == 1
        assert s.line_end is not None
        assert s.line_end >= s.line_start

    def test_path_stored(self, tmp_path):
        f = _write(tmp_path / "m.py", "class A:\n    pass\n")
        syms = extract_python_symbols(f)
        assert all(s.path == f.as_posix() for s in syms)


class TestFunctionDetection:
    def test_function_found(self, tmp_path):
        f = _write(tmp_path / "m.py", "def greet(): pass\n")
        syms = extract_python_symbols(f)
        assert any(s.name == "greet" and s.kind == "function" for s in syms)

    def test_async_function_found(self, tmp_path):
        f = _write(tmp_path / "m.py", "async def fetch(): pass\n")
        syms = extract_python_symbols(f)
        assert any(s.name == "fetch" and s.kind == "async_function" for s in syms)

    def test_function_line_numbers(self, tmp_path):
        f = _write(tmp_path / "m.py", "def foo():\n    x = 1\n    return x\n")
        syms = _symbols_by_name(extract_python_symbols(f))
        s = syms["foo"]
        assert s.line_start == 1
        assert s.line_end is not None
        assert s.line_end >= 3


class TestMethodDetection:
    def test_method_kind(self, tmp_path):
        src = "class MyClass:\n    def do_thing(self):\n        pass\n"
        f = _write(tmp_path / "m.py", src)
        syms = extract_python_symbols(f)
        assert any(s.name == "do_thing" and s.kind == "method" for s in syms)

    def test_async_method_kind(self, tmp_path):
        src = "class MyClass:\n    async def fetch(self):\n        pass\n"
        f = _write(tmp_path / "m.py", src)
        syms = extract_python_symbols(f)
        assert any(s.name == "fetch" and s.kind == "async_method" for s in syms)

    def test_nested_function_in_method_is_not_method(self, tmp_path):
        src = (
            "class Outer:\n"
            "    def method(self):\n"
            "        def inner(): pass\n"
        )
        f = _write(tmp_path / "m.py", src)
        syms = _symbols_by_name(extract_python_symbols(f))
        assert syms["inner"].kind == "function"

    def test_multiple_methods_all_detected(self, tmp_path):
        src = (
            "class Svc:\n"
            "    def alpha(self): pass\n"
            "    def beta(self): pass\n"
            "    async def gamma(self): pass\n"
        )
        f = _write(tmp_path / "m.py", src)
        syms = _symbols_by_name(extract_python_symbols(f))
        assert syms["alpha"].kind == "method"
        assert syms["beta"].kind == "method"
        assert syms["gamma"].kind == "async_method"


# ---------------------------------------------------------------------------
# FastAPI / route decorators
# ---------------------------------------------------------------------------


class TestRouteDecorators:
    def test_app_get_is_api_route(self, tmp_path):
        src = '@app.get("/")\ndef index(): pass\n'
        f = _write(tmp_path / "routes.py", src)
        syms = extract_python_symbols(f)
        assert any(s.name == "index" and s.kind == "api_route" for s in syms)

    def test_router_post_is_api_route(self, tmp_path):
        src = '@router.post("/items")\ndef create_item(): pass\n'
        f = _write(tmp_path / "routes.py", src)
        syms = extract_python_symbols(f)
        assert any(s.name == "create_item" and s.kind == "api_route" for s in syms)

    def test_router_put_is_api_route(self, tmp_path):
        src = '@router.put("/items/{id}")\ndef update_item(): pass\n'
        f = _write(tmp_path / "routes.py", src)
        syms = extract_python_symbols(f)
        assert any(s.name == "update_item" and s.kind == "api_route" for s in syms)

    def test_router_delete_is_api_route(self, tmp_path):
        src = '@router.delete("/items/{id}")\ndef remove_item(): pass\n'
        f = _write(tmp_path / "routes.py", src)
        syms = extract_python_symbols(f)
        assert any(s.name == "remove_item" and s.kind == "api_route" for s in syms)

    def test_router_patch_is_api_route(self, tmp_path):
        src = '@router.patch("/items/{id}")\ndef patch_item(): pass\n'
        f = _write(tmp_path / "routes.py", src)
        syms = extract_python_symbols(f)
        assert any(s.name == "patch_item" and s.kind == "api_route" for s in syms)

    def test_all_http_verbs_in_one_file(self, tmp_path):
        src = (
            '@app.get("/a")\ndef get_a(): pass\n'
            '@router.post("/b")\ndef post_b(): pass\n'
            '@router.put("/c")\ndef put_c(): pass\n'
            '@router.delete("/d")\ndef del_d(): pass\n'
            '@router.patch("/e")\ndef patch_e(): pass\n'
        )
        f = _write(tmp_path / "routes.py", src)
        syms = extract_python_symbols(f)
        api_names = {s.name for s in syms if s.kind == "api_route"}
        assert api_names == {"get_a", "post_b", "put_c", "del_d", "patch_e"}

    def test_route_decorator_with_extra_kwargs(self, tmp_path):
        src = '@router.get("/path", response_model=str)\ndef handler(): pass\n'
        f = _write(tmp_path / "routes.py", src)
        syms = extract_python_symbols(f)
        assert any(s.name == "handler" and s.kind == "api_route" for s in syms)

    def test_non_route_decorator_not_api_route(self, tmp_path):
        src = "@staticmethod\ndef helper(): pass\n"
        f = _write(tmp_path / "m.py", src)
        syms = extract_python_symbols(f)
        assert any(s.name == "helper" and s.kind == "function" for s in syms)


# ---------------------------------------------------------------------------
# Syntax error handling
# ---------------------------------------------------------------------------


class TestSyntaxErrorHandling:
    def test_syntax_error_returns_empty_list(self, tmp_path):
        f = _write(tmp_path / "broken.py", "def foo(:\n    pass\n")
        result = extract_python_symbols(f)
        assert result == []

    def test_syntax_error_emits_user_warning(self, tmp_path):
        f = _write(tmp_path / "broken.py", "def foo(:\n    pass\n")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            extract_python_symbols(f)
        assert len(caught) == 1
        assert issubclass(caught[0].category, UserWarning)

    def test_syntax_error_warning_mentions_file(self, tmp_path):
        f = _write(tmp_path / "broken.py", "class Foo(:\n    pass\n")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            extract_python_symbols(f)
        assert len(caught) == 1
        assert "broken.py" in str(caught[0].message)

    def test_broken_file_does_not_stop_good_file(self, tmp_path):
        broken = _write(tmp_path / "broken.py", "def foo(:\n")
        good = _write(tmp_path / "good.py", "def ok(): pass\n")
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            extract_python_symbols(broken)
        syms = extract_python_symbols(good)
        assert any(s.name == "ok" for s in syms)

    def test_empty_file_returns_empty_list(self, tmp_path):
        f = _write(tmp_path / "empty.py", "")
        result = extract_python_symbols(f)
        assert result == []
