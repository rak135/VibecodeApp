"""Tests for relevant-file scoring."""

from __future__ import annotations

from pathlib import Path

from vibecode.context.scoring import score_relevant_files


def _write(path: Path, content: str = "# placeholder\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _inventory(*paths: str) -> dict:
    return {"files": [{"path": path} for path in paths]}


def test_context_pack_scores_context_tests_and_architecture_docs(tmp_path):
    _write(
        tmp_path / ".vibecode" / "architecture" / "STRUCTURE.md",
        "Context pack renderer lives in `vibecode/context/__init__.py`.\n",
    )
    inventory = _inventory(
        "vibecode/context/__init__.py",
        "vibecode/cli.py",
        "tests/test_context.py",
        ".vibecode/architecture/STRUCTURE.md",
        ".pytest_cache/v/cache/nodeids",
    )

    results = score_relevant_files(tmp_path, "context pack", inventory=inventory, limit=5)
    paths = [item["path"] for item in results]

    assert "vibecode/context/__init__.py" in paths
    assert "tests/test_context.py" in paths
    assert ".vibecode/architecture/STRUCTURE.md" in paths
    assert ".pytest_cache/v/cache/nodeids" not in paths


def test_ignored_generated_vendor_and_cache_files_do_not_reach_top(tmp_path):
    inventory = _inventory(
        "src/context.py",
        "vendor/context.py",
        "build/context.generated.json",
        ".pytest_cache/context.py",
    )

    results = score_relevant_files(tmp_path, "context", inventory=inventory, limit=10)

    assert results[0]["path"] == "src/context.py"
    ignored = {item["path"]: item for item in results if item["path"] != "src/context.py"}
    assert ignored == {}


def test_reasons_include_task_architecture_test_pair_and_domain_extension(tmp_path):
    _write(
        tmp_path / ".vibecode" / "architecture" / "MODULE_BOUNDARIES.md",
        "Scoring code is maintained in `src/context.py`.\n",
    )
    inventory = _inventory("src/context.py", "tests/test_context.py")

    results = score_relevant_files(tmp_path, "context pack", inventory=inventory, limit=2)
    scored = {item["path"]: item for item in results}
    source_reasons = " ".join(scored["src/context.py"]["reasons"])
    test_reasons = " ".join(scored["tests/test_context.py"]["reasons"])

    assert "+10 task keyword 'context' in path" in source_reasons
    assert "+8 task keyword 'context' in filename" in source_reasons
    assert "+6 file listed in architecture docs" in source_reasons
    assert "+5 source file has matching test file" in source_reasons
    assert "+2 matching extension for task domain" in source_reasons
    assert "+5 test file matches a relevant source file" in test_reasons


def test_context_panel_task_selects_ui_test_and_architecture(tmp_path):
    _write(
        tmp_path / ".vibecode" / "architecture" / "STRUCTURE.md",
        "Context panel UI is in `ui/frontend/src/screens/context-panel.tsx`.\n",
    )
    inventory = _inventory(
        "ui/frontend/src/screens/context-panel.tsx",
        "ui/frontend/src/screens/context-panel.test.tsx",
        "vibecode/context/renderer.py",
        ".vibecode/architecture/STRUCTURE.md",
        ".vibecode/index/symbol_map.generated.json",
    )

    results = score_relevant_files(tmp_path, "context panel copy", inventory=inventory, limit=5)
    paths = [item["path"] for item in results]

    assert "ui/frontend/src/screens/context-panel.tsx" in paths[:3]
    assert "ui/frontend/src/screens/context-panel.test.tsx" in paths
    assert ".vibecode/architecture/STRUCTURE.md" in paths
    assert ".vibecode/index/symbol_map.generated.json" not in paths


def test_matching_algorithm_task_marks_matching_py_high_risk(tmp_path):
    inventory = {
        "files": [
            {
                "path": "vibecode/indexer/matching.py",
                "risk_level": "high",
            },
            {
                "path": "tests/test_matching.py",
                "risk_level": "low",
            },
        ]
    }

    results = score_relevant_files(tmp_path, "matching algorithm", inventory=inventory, limit=2)
    matching = next(item for item in results if item["path"] == "vibecode/indexer/matching.py")

    assert matching["risk_level"] == "high"
    assert matching["requires_confirmation"] is True
    assert any("matching" in reason for reason in matching["reasons"])
