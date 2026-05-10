"""Tests for schema, ast_parser, risk_analyzer, risk_reporter, and context card generation."""

from __future__ import annotations

import json
from pathlib import Path

from vibecode.indexer.schema import ContextCard, Fact, Heuristic, RiskItem
from vibecode.indexer.ast_parser import parse_python_file
from vibecode.indexer.risk_analyzer import analyze_facts, analyze_heuristics
from vibecode.indexer.risk_reporter import build_risk_report, write_risk_report
from vibecode.indexer.inventory import build_inventory, write_inventory
from vibecode.indexer.scanner import FileStatus, IndexedFile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _make_indexed(path: str, size: int = 100, status: FileStatus = FileStatus.UNKNOWN) -> IndexedFile:
    return IndexedFile(path=path, status=status, size=size)


# ---------------------------------------------------------------------------
# schema – Fact
# ---------------------------------------------------------------------------


class TestFact:
    def test_fields(self):
        f = Fact(kind="todo", line=5, text="fix me")
        assert f.kind == "todo"
        assert f.line == 5
        assert f.text == "fix me"

    def test_zero_line_for_file_level(self):
        f = Fact(kind="unsafe_permission", line=0, text="world-writable file")
        assert f.line == 0


# ---------------------------------------------------------------------------
# schema – Heuristic
# ---------------------------------------------------------------------------


class TestHeuristic:
    def test_fields(self):
        h = Heuristic(kind="high_param_count", symbol="do_stuff", detail="6 parameters")
        assert h.kind == "high_param_count"
        assert h.symbol == "do_stuff"
        assert h.detail == "6 parameters"

    def test_severity_default(self):
        h = Heuristic(kind="high_param_count", symbol="f", detail="x")
        assert h.severity == "low"

    def test_severity_set(self):
        h = Heuristic(kind="suspicious_name", symbol="f", detail="x", severity="medium")
        assert h.severity == "medium"


# ---------------------------------------------------------------------------
# schema – RiskItem
# ---------------------------------------------------------------------------


class TestRiskItem:
    def test_defaults(self):
        ri = RiskItem(path="foo.py", risk_level="low")
        assert ri.facts == []
        assert ri.heuristics == []
        assert ri.reasons == []

    def test_with_facts(self):
        f = Fact("todo", 1, "do this")
        ri = RiskItem(path="foo.py", risk_level="high", facts=[f])
        assert len(ri.facts) == 1


# ---------------------------------------------------------------------------
# schema – ContextCard
# ---------------------------------------------------------------------------


class TestContextCard:
    def test_defaults(self):
        card = ContextCard(path="foo.py", language="python", purpose=None)
        assert card.symbols == []
        assert card.facts == []
        assert card.heuristics == []
        assert card.detail_level == "basic"
        assert card.content_snippet == ""


# ---------------------------------------------------------------------------
# ast_parser – parse_python_file
# ---------------------------------------------------------------------------


class TestParsePythonFile:
    def test_module_docstring(self, tmp_path):
        f = _write(tmp_path / "mod.py", '"""Module docstring."""\n\ndef foo(): pass\n')
        result = parse_python_file(f)
        assert result.module_docstring == "Module docstring."

    def test_no_docstring(self, tmp_path):
        f = _write(tmp_path / "mod.py", "def foo(): pass\n")
        result = parse_python_file(f)
        assert result.module_docstring is None

    def test_function_symbols(self, tmp_path):
        f = _write(tmp_path / "mod.py", "def foo(): pass\ndef bar(): pass\n")
        result = parse_python_file(f)
        assert "foo" in result.symbols
        assert "bar" in result.symbols

    def test_class_symbols(self, tmp_path):
        f = _write(tmp_path / "mod.py", "class MyClass: pass\n")
        result = parse_python_file(f)
        assert "MyClass" in result.symbols

    def test_function_param_count(self, tmp_path):
        f = _write(tmp_path / "mod.py", "def many(a, b, c, d, e, f): pass\n")
        result = parse_python_file(f)
        fn = next(fn for fn in result.functions if fn["name"] == "many")
        assert fn["param_count"] == 6

    def test_async_function(self, tmp_path):
        f = _write(tmp_path / "mod.py", "async def fetch(url): pass\n")
        result = parse_python_file(f)
        assert "fetch" in result.symbols

    def test_syntax_error_returns_empty(self, tmp_path):
        f = _write(tmp_path / "bad.py", "def !!(): pass\n")
        result = parse_python_file(f)
        assert result.module_docstring is None
        assert result.symbols == []

    def test_missing_file_returns_empty(self, tmp_path):
        result = parse_python_file(tmp_path / "nonexistent.py")
        assert result.module_docstring is None
        assert result.symbols == []

    def test_vararg_counted(self, tmp_path):
        f = _write(tmp_path / "mod.py", "def f(*args): pass\n")
        result = parse_python_file(f)
        fn = result.functions[0]
        assert fn["param_count"] == 1

    def test_kwarg_counted(self, tmp_path):
        f = _write(tmp_path / "mod.py", "def f(**kwargs): pass\n")
        result = parse_python_file(f)
        fn = result.functions[0]
        assert fn["param_count"] == 1


# ---------------------------------------------------------------------------
# risk_analyzer – analyze_facts
# ---------------------------------------------------------------------------


class TestAnalyzeFacts:
    def test_todo_detected(self, tmp_path):
        f = _write(tmp_path / "mod.py", "# TODO: fix this\n")
        facts = analyze_facts(f, f.read_text())
        assert any(fc.kind == "todo" for fc in facts)

    def test_fixme_detected(self, tmp_path):
        f = _write(tmp_path / "mod.py", "# FIXME: broken\n")
        facts = analyze_facts(f, f.read_text())
        assert any(fc.kind == "fixme" for fc in facts)

    def test_todo_case_insensitive(self, tmp_path):
        f = _write(tmp_path / "mod.py", "# todo: something\n")
        facts = analyze_facts(f, f.read_text())
        assert any(fc.kind == "todo" for fc in facts)

    def test_todo_line_number(self, tmp_path):
        content = "x = 1\n# TODO: fix\ny = 2\n"
        f = _write(tmp_path / "mod.py", content)
        facts = analyze_facts(f, content)
        todo = next(fc for fc in facts if fc.kind == "todo")
        assert todo.line == 2

    def test_no_todos_empty(self, tmp_path):
        f = _write(tmp_path / "mod.py", "x = 1\n")
        facts = analyze_facts(f, f.read_text())
        assert not any(fc.kind in ("todo", "fixme") for fc in facts)

    def test_multiple_todos(self, tmp_path):
        content = "# TODO: first\n# FIXME: second\n"
        f = _write(tmp_path / "mod.py", content)
        facts = analyze_facts(f, content)
        kinds = {fc.kind for fc in facts}
        assert "todo" in kinds
        assert "fixme" in kinds


# ---------------------------------------------------------------------------
# risk_analyzer – analyze_heuristics
# ---------------------------------------------------------------------------


class TestAnalyzeHeuristics:
    def test_high_param_count(self):
        fns = [{"name": "overloaded", "param_count": 8, "lineno": 1}]
        h = analyze_heuristics(fns)
        assert any(x.kind == "high_param_count" and x.symbol == "overloaded" for x in h)

    def test_high_param_count_severity_medium(self):
        fns = [{"name": "big", "param_count": 8, "lineno": 1}]
        h = analyze_heuristics(fns)
        item = next(x for x in h if x.kind == "high_param_count")
        assert item.severity == "medium"

    def test_suspicious_name_severity_low(self):
        fns = [{"name": "do_hack", "param_count": 1, "lineno": 1}]
        h = analyze_heuristics(fns)
        item = next(x for x in h if x.kind == "suspicious_name")
        assert item.severity == "low"

    def test_below_threshold_no_heuristic(self):
        fns = [{"name": "simple", "param_count": 3, "lineno": 1}]
        h = analyze_heuristics(fns)
        assert not any(x.kind == "high_param_count" for x in h)

    def test_threshold_exactly_five_no_flag(self):
        fns = [{"name": "fn", "param_count": 5, "lineno": 1}]
        h = analyze_heuristics(fns)
        assert not any(x.kind == "high_param_count" for x in h)

    def test_suspicious_name_hack(self):
        fns = [{"name": "do_hack", "param_count": 1, "lineno": 1}]
        h = analyze_heuristics(fns)
        assert any(x.kind == "suspicious_name" and "hack" in x.detail for x in h)

    def test_suspicious_name_evil(self):
        fns = [{"name": "evil_workaround", "param_count": 1, "lineno": 1}]
        h = analyze_heuristics(fns)
        assert any(x.kind == "suspicious_name" for x in h)

    def test_clean_name_no_suspicious(self):
        fns = [{"name": "process_data", "param_count": 2, "lineno": 1}]
        h = analyze_heuristics(fns)
        assert not any(x.kind == "suspicious_name" for x in h)

    def test_empty_functions(self):
        assert analyze_heuristics([]) == []


# ---------------------------------------------------------------------------
# risk_reporter – build_risk_report
# ---------------------------------------------------------------------------


class TestBuildRiskReport:
    def test_schema_present(self, tmp_path):
        report = build_risk_report("proj", tmp_path, [])
        assert report["$schema"] == "vibecode/risk-report/v1"

    def test_project_id(self, tmp_path):
        report = build_risk_report("myproj", tmp_path, [])
        assert report["project_id"] == "myproj"

    def test_root_posix(self, tmp_path):
        report = build_risk_report("proj", tmp_path, [])
        assert "\\" not in report["root"]

    def test_empty_files_list(self, tmp_path):
        report = build_risk_report("proj", tmp_path, [])
        assert report["files"] == []

    def test_file_entry_structure(self, tmp_path):
        item = RiskItem(
            path="src/auth.py",
            risk_level="high",
            reasons=["keyword"],
            facts=[Fact("todo", 1, "fix")],
            heuristics=[Heuristic("high_param_count", "do_auth", "6 parameters", "medium")],
        )
        report = build_risk_report("proj", tmp_path, [item])
        entry = report["files"][0]
        assert entry["path"] == "src/auth.py"
        assert entry["risk_level"] == "high"
        assert "keyword" in entry["reasons"]
        assert entry["facts"][0]["kind"] == "todo"
        h = entry["heuristics"][0]
        assert h["kind"] == "high_param_count"
        assert h["severity"] == "medium"

    def test_separate_facts_and_heuristics_keys(self, tmp_path):
        item = RiskItem(path="x.py", risk_level="low")
        report = build_risk_report("proj", tmp_path, [item])
        entry = report["files"][0]
        assert "facts" in entry
        assert "heuristics" in entry


# ---------------------------------------------------------------------------
# risk_reporter – write_risk_report
# ---------------------------------------------------------------------------


class TestWriteRiskReport:
    def test_creates_file(self, tmp_path):
        out = tmp_path / ".vibecode" / "index" / "risk_report.json"
        write_risk_report("proj", tmp_path, [], out)
        assert out.exists()

    def test_creates_parent_dirs(self, tmp_path):
        out = tmp_path / "deep" / "nested" / "risk_report.json"
        write_risk_report("proj", tmp_path, [], out)
        assert out.exists()

    def test_valid_json(self, tmp_path):
        out = tmp_path / "risk_report.json"
        write_risk_report("proj", tmp_path, [], out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_overwrite(self, tmp_path):
        out = tmp_path / "risk_report.json"
        write_risk_report("proj", tmp_path, [RiskItem("a.py", "low")], out)
        write_risk_report("proj", tmp_path, [], out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["files"] == []


# ---------------------------------------------------------------------------
# inventory – generate_cards=True
# ---------------------------------------------------------------------------


class TestInventoryWithCards:
    def test_cards_absent_by_default(self, tmp_path):
        files = [_make_indexed("mod.py")]
        inv = build_inventory("proj", tmp_path, files)
        assert "context_cards" not in inv

    def test_cards_present_when_enabled(self, tmp_path):
        _write(tmp_path / "mod.py", '"""Docstring."""\ndef foo(): pass\n')
        files = [_make_indexed("mod.py")]
        inv = build_inventory("proj", tmp_path, files, generate_cards=True)
        assert "context_cards" in inv

    def test_non_python_files_excluded_from_cards(self, tmp_path):
        _write(tmp_path / "README.md", "# readme")
        files = [_make_indexed("README.md")]
        inv = build_inventory("proj", tmp_path, files, generate_cards=True)
        assert inv["context_cards"] == []

    def test_card_has_required_fields(self, tmp_path):
        _write(tmp_path / "mod.py", '"""Docstring."""\ndef foo(): pass\n')
        files = [_make_indexed("mod.py")]
        inv = build_inventory("proj", tmp_path, files, generate_cards=True)
        card = inv["context_cards"][0]
        assert card["path"] == "mod.py"
        assert card["language"] == "python"
        assert "purpose" in card
        assert "symbols" in card
        assert "content_snippet" in card
        assert "facts" in card
        assert "heuristics" in card
        assert "detail_level" in card

    def test_card_purpose_extracted(self, tmp_path):
        _write(tmp_path / "mod.py", '"""My module."""\n')
        files = [_make_indexed("mod.py")]
        inv = build_inventory("proj", tmp_path, files, generate_cards=True)
        assert inv["context_cards"][0]["purpose"] == "My module."

    def test_card_purpose_none_when_no_docstring(self, tmp_path):
        _write(tmp_path / "mod.py", "x = 1\n")
        files = [_make_indexed("mod.py")]
        inv = build_inventory("proj", tmp_path, files, generate_cards=True)
        assert inv["context_cards"][0]["purpose"] is None

    def test_card_content_snippet_200_chars(self, tmp_path):
        content = "x = 1\n" * 100  # more than 200 chars
        _write(tmp_path / "mod.py", content)
        files = [_make_indexed("mod.py")]
        inv = build_inventory("proj", tmp_path, files, generate_cards=True)
        snippet = inv["context_cards"][0]["content_snippet"]
        assert snippet == content[:200]
        assert len(snippet) == 200

    def test_card_content_snippet_short_file(self, tmp_path):
        content = "x = 1\n"
        _write(tmp_path / "mod.py", content)
        files = [_make_indexed("mod.py")]
        inv = build_inventory("proj", tmp_path, files, generate_cards=True)
        assert inv["context_cards"][0]["content_snippet"] == content

    def test_card_symbols_structured(self, tmp_path):
        _write(tmp_path / "mod.py", "class Foo: pass\ndef bar(): pass\n")
        files = [_make_indexed("mod.py")]
        inv = build_inventory("proj", tmp_path, files, generate_cards=True)
        symbols = inv["context_cards"][0]["symbols"]
        names = {s["name"] for s in symbols}
        assert "Foo" in names
        assert "bar" in names

    def test_card_symbols_have_name_kind_line(self, tmp_path):
        _write(tmp_path / "mod.py", "class Foo:\n    pass\ndef bar():\n    pass\n")
        files = [_make_indexed("mod.py")]
        inv = build_inventory("proj", tmp_path, files, generate_cards=True)
        symbols = inv["context_cards"][0]["symbols"]
        for s in symbols:
            assert "name" in s
            assert "kind" in s
            assert "line" in s
        kinds = {s["kind"] for s in symbols}
        assert "class" in kinds
        assert "function" in kinds

    def test_card_detail_level_passed(self, tmp_path):
        _write(tmp_path / "mod.py", "def foo(): pass\n")
        files = [_make_indexed("mod.py")]
        inv = build_inventory("proj", tmp_path, files, generate_cards=True, card_detail="full")
        assert inv["context_cards"][0]["detail_level"] == "full"

    def test_card_heuristics_disabled(self, tmp_path):
        _write(tmp_path / "mod.py", "def evil_hack(a,b,c,d,e,f,g): pass\n")
        files = [_make_indexed("mod.py")]
        inv = build_inventory(
            "proj", tmp_path, files, generate_cards=True, compute_heuristics=False
        )
        assert inv["context_cards"][0]["heuristics"] == []

    def test_card_facts_detected(self, tmp_path):
        _write(tmp_path / "mod.py", "# TODO: fix this\ndef foo(): pass\n")
        files = [_make_indexed("mod.py")]
        inv = build_inventory("proj", tmp_path, files, generate_cards=True)
        facts = inv["context_cards"][0]["facts"]
        assert any(f["kind"] == "todo" for f in facts)

    def test_card_heuristic_detected(self, tmp_path):
        _write(tmp_path / "mod.py", "def big(a, b, c, d, e, f, g): pass\n")
        files = [_make_indexed("mod.py")]
        inv = build_inventory("proj", tmp_path, files, generate_cards=True)
        heuristics = inv["context_cards"][0]["heuristics"]
        assert any(h["kind"] == "high_param_count" for h in heuristics)

    def test_card_heuristic_has_severity(self, tmp_path):
        _write(tmp_path / "mod.py", "def big(a, b, c, d, e, f, g): pass\n")
        files = [_make_indexed("mod.py")]
        inv = build_inventory("proj", tmp_path, files, generate_cards=True)
        heuristics = inv["context_cards"][0]["heuristics"]
        item = next(h for h in heuristics if h["kind"] == "high_param_count")
        assert item["severity"] == "medium"

    def test_write_inventory_with_cards(self, tmp_path):
        _write(tmp_path / "mod.py", '"""Doc."""\ndef foo(): pass\n')
        out = tmp_path / "inv.json"
        files = [_make_indexed("mod.py")]
        write_inventory("proj", tmp_path, files, out, generate_cards=True)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "context_cards" in data
        assert len(data["context_cards"]) == 1
