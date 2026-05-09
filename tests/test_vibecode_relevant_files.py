"""Tests for relevant-file scoring."""

from __future__ import annotations

import json
from pathlib import Path

from vibecode.context.scoring import score_relevant_files


def _write(path: Path, content: str = "# placeholder\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _inventory(*paths: str) -> dict:
    return {"files": [{"path": path} for path in paths]}


def _paths(results: list[dict]) -> list[str]:
    return [item["path"] for item in results]


def _reasons(results: list[dict], path: str) -> str:
    scored = {item["path"]: item for item in results}
    return " ".join(scored.get(path, {}).get("reasons", []))


# ---------------------------------------------------------------------------
# Existing tests (updated reason strings)
# ---------------------------------------------------------------------------


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
    paths = _paths(results)

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

    assert 'task keyword matched path token: "context"' in source_reasons
    assert 'task keyword matched filename token: "context"' in source_reasons
    assert "architecture" in source_reasons  # "referenced in task-relevant architecture doc ..."
    assert "paired test" in source_reasons
    assert "matching extension for task domain" in source_reasons
    assert "paired" in test_reasons


# ---------------------------------------------------------------------------
# Cleanup-pass tests — H and I
# ---------------------------------------------------------------------------


def test_generic_token_does_not_create_false_positive(tmp_path):
    """H: Generic task tokens like 'file' must not lift unrelated files into top results."""
    inventory = _inventory(
        "vibecode/context/scoring.py",
        "tests/test_vibecode_relevant_files.py",
        "vibecode/indexer/risky_files.py",   # should score low despite "file" in name
        "vibecode/context/renderer.py",
        "vibecode/indexer/file_scanner.py",  # should score low despite "file" in name
    )

    results = score_relevant_files(
        tmp_path, "Improve relevant-file scoring", inventory=inventory, limit=10
    )
    scored = {r["path"]: r["score"] for r in results}

    scoring_score = scored.get("vibecode/context/scoring.py", 0)
    relevant_score = scored.get("tests/test_vibecode_relevant_files.py", 0)
    risky_score = scored.get("vibecode/indexer/risky_files.py", 0)
    scanner_score = scored.get("vibecode/indexer/file_scanner.py", 0)

    # Domain-specific files must score significantly higher than generic-token files.
    assert scoring_score >= 18, f"scoring.py score too low: {scoring_score}"
    assert relevant_score >= 18, f"test_vibecode_relevant_files.py score too low: {relevant_score}"
    # Generic "file" token alone should not give risky_files.py or file_scanner.py a high score.
    assert risky_score < scoring_score // 3, (
        f"risky_files.py score {risky_score} too close to scoring.py {scoring_score}"
    )
    assert scanner_score < scoring_score // 3, (
        f"file_scanner.py score {scanner_score} too close to scoring.py {scoring_score}"
    )


def test_architecture_doc_does_not_overboost_generic_files(tmp_path):
    """I: Arch-doc listing a file must not push it above domain-specific scoring matches."""
    # MODULE_BOUNDARIES.md mentions "scoring" (task-specific) AND lists cli.py, config.py.
    _write(
        tmp_path / ".vibecode" / "architecture" / "MODULE_BOUNDARIES.md",
        "CLI code (`vibecode/cli.py`, `vibecode/config.py`) must not implement scoring.\n"
        "Scoring lives in `vibecode/context/scoring.py`.\n",
    )
    inventory = _inventory(
        "vibecode/context/scoring.py",
        "tests/test_vibecode_relevant_files.py",
        "vibecode/cli.py",
        "vibecode/config.py",
    )

    results = score_relevant_files(
        tmp_path, "Improve relevant-file scoring", inventory=inventory, limit=10
    )
    paths = _paths(results)

    # Scoring file must rank #1.
    assert paths[0] == "vibecode/context/scoring.py"
    # cli.py / config.py should not beat scoring.py just because arch doc lists them.
    scoring_score = next(r["score"] for r in results if r["path"] == "vibecode/context/scoring.py")
    cli_score = next((r["score"] for r in results if r["path"] == "vibecode/cli.py"), 0)
    config_score = next((r["score"] for r in results if r["path"] == "vibecode/config.py"), 0)
    assert scoring_score > cli_score
    assert scoring_score > config_score


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
    paths = _paths(results)

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


# ---------------------------------------------------------------------------
# New tests — A through G
# ---------------------------------------------------------------------------


def test_repo_tree_task_selects_source_and_paired_test(tmp_path):
    """A: 'Improve repo tree rendering' surfaces repo_tree.py and its test."""
    _write(
        tmp_path / ".vibecode" / "architecture" / "STRUCTURE.md",
        "Repo tree rendering: `vibecode/indexer/repo_tree.py`.\n",
    )
    inventory = _inventory(
        "vibecode/indexer/repo_tree.py",
        "tests/test_vibecode_repo_tree.py",
        ".vibecode/architecture/STRUCTURE.md",
        "vibecode/context/renderer.py",
    )

    results = score_relevant_files(
        tmp_path, "Improve repo tree rendering", inventory=inventory, limit=10
    )
    paths = _paths(results)

    assert "vibecode/indexer/repo_tree.py" in paths[:3]
    assert "tests/test_vibecode_repo_tree.py" in paths
    assert ".vibecode/architecture/STRUCTURE.md" in paths


def test_context_pack_task_selects_renderer_scoring_and_test(tmp_path):
    """B: 'Improve context pack rendering' surfaces renderer, scoring, and test."""
    _write(
        tmp_path / ".vibecode" / "architecture" / "MODULE_BOUNDARIES.md",
        "Context pack renderer: `vibecode/context/renderer.py`.\n"
        "Scoring: `vibecode/context/scoring.py`.\n",
    )
    inventory = _inventory(
        "vibecode/context/renderer.py",
        "vibecode/context/scoring.py",
        "tests/test_vibecode_context_pack.py",
        "tests/test_vibecode_relevant_files.py",
        ".vibecode/architecture/MODULE_BOUNDARIES.md",
    )

    results = score_relevant_files(
        tmp_path, "Improve context pack rendering", inventory=inventory, limit=10
    )
    paths = _paths(results)

    assert "vibecode/context/renderer.py" in paths
    assert "tests/test_vibecode_context_pack.py" in paths
    assert "vibecode/context/scoring.py" in paths


def test_opencode_task_selects_platform_export_and_registry(tmp_path):
    """C: 'Add OpenCode prompt export behavior' surfaces export and registry files."""
    inventory = _inventory(
        "vibecode/context/platform_export.py",
        "vibecode/context/platform_registry.py",
        "tests/test_vibecode_platform_export.py",
        "tests/test_vibecode_platform_registry.py",
        "vibecode/context/renderer.py",
    )

    results = score_relevant_files(
        tmp_path, "Add OpenCode prompt export behavior", inventory=inventory, limit=10
    )
    paths = _paths(results)

    assert "vibecode/context/platform_export.py" in paths
    assert "tests/test_vibecode_platform_export.py" in paths
    assert "vibecode/context/platform_registry.py" in paths


def test_handoff_signal_boosts_scoring_files_for_scoring_task(tmp_path):
    """D: Handoff mentioning 'scoring' boosts scoring.py for a scoring task."""
    _write(
        tmp_path / ".vibecode" / "handoff" / "NEXT.md",
        "- Address relevant-file scoring gaps.\n",
    )
    inventory = _inventory(
        "vibecode/context/scoring.py",
        "tests/test_vibecode_relevant_files.py",
        "vibecode/context/renderer.py",
    )

    results = score_relevant_files(
        tmp_path, "Improve relevant-file scoring", inventory=inventory, limit=10
    )
    paths = _paths(results)

    assert "vibecode/context/scoring.py" in paths[:3]
    scoring_r = _reasons(results, "vibecode/context/scoring.py")
    assert "handoff" in scoring_r.lower()


def test_generated_and_runtime_files_excluded(tmp_path):
    """E: Generated/runtime paths do not appear in top results."""
    inventory = _inventory(
        "vibecode/context/scoring.py",
        ".vibecode/current/context_pack.md",
        ".vibecode/index/relevant_files.generated.json",
        ".vibecode/logs/run.log",
        ".ralphy/state.json",
        "__pycache__/scoring.cpython-312.pyc",
    )

    results = score_relevant_files(tmp_path, "Improve scoring", inventory=inventory, limit=10)
    paths = _paths(results)

    assert "vibecode/context/scoring.py" in paths
    assert ".vibecode/current/context_pack.md" not in paths
    assert ".vibecode/index/relevant_files.generated.json" not in paths
    assert ".vibecode/logs/run.log" not in paths
    assert ".ralphy/state.json" not in paths
    assert "__pycache__/scoring.cpython-312.pyc" not in paths


def test_source_test_pairing_surfaces_both_sides(tmp_path):
    """F: A matching source/test pair both appear, with pairing reasons."""
    inventory = _inventory(
        "vibecode/indexer/repo_tree.py",
        "tests/test_vibecode_repo_tree.py",
        "vibecode/cli.py",
    )

    results = score_relevant_files(tmp_path, "repo tree", inventory=inventory, limit=10)
    scored = {item["path"]: item for item in results}

    assert "vibecode/indexer/repo_tree.py" in scored
    assert "tests/test_vibecode_repo_tree.py" in scored

    source_r = " ".join(scored["vibecode/indexer/repo_tree.py"]["reasons"])
    test_r = " ".join(scored["tests/test_vibecode_repo_tree.py"]["reasons"])

    assert "paired test" in source_r
    assert "paired" in test_r


def test_dependency_signal_boosts_connected_files(tmp_path):
    """G: Files connected via the dependency map receive a small boost."""
    dep_map = {
        "$schema": "vibecode/dependency-map/v1",
        "edges": [
            {
                "from": "vibecode/context/renderer.py",
                "import_target": "vibecode.context.scoring",
                "type": "python",
                "status": "resolved",
                "resolved_path": "vibecode/context/scoring.py",
            }
        ],
    }
    dep_path = tmp_path / ".vibecode" / "index" / "dependency_map.json"
    dep_path.parent.mkdir(parents=True, exist_ok=True)
    dep_path.write_text(json.dumps(dep_map), encoding="utf-8")

    inventory = _inventory(
        "vibecode/context/renderer.py",
        "vibecode/context/scoring.py",
        "vibecode/cli.py",
    )

    results = score_relevant_files(
        tmp_path, "context pack rendering", inventory=inventory, limit=10
    )
    scored = {item["path"]: item for item in results}

    # renderer.py scores on "context" keyword → dep boost reaches scoring.py
    assert "vibecode/context/scoring.py" in scored
    scoring_r = " ".join(scored["vibecode/context/scoring.py"]["reasons"])
    assert "dependency connection" in scoring_r


# ---------------------------------------------------------------------------
# Hub/dependency fan-out tests — J, K, L
# ---------------------------------------------------------------------------


def test_hub_file_not_in_top_3_for_scoring_task(tmp_path):
    """J: cli.py must not rank near the top for a non-CLI implementation task."""
    inventory = _inventory(
        "vibecode/context/scoring.py",
        "tests/test_vibecode_relevant_files.py",
        "vibecode/context/renderer.py",
        "vibecode/cli.py",
        "vibecode/config.py",
    )

    results = score_relevant_files(
        tmp_path, "Improve relevant-file scoring", inventory=inventory, limit=10
    )
    paths = _paths(results)
    scored = {r["path"]: r["score"] for r in results}

    assert "vibecode/context/scoring.py" in paths[:2]
    assert "tests/test_vibecode_relevant_files.py" in paths[:2]
    # cli.py must score significantly lower than the direct implementation matches.
    scoring_score = scored.get("vibecode/context/scoring.py", 0)
    cli_score = scored.get("vibecode/cli.py", 0)
    assert cli_score < scoring_score // 3, (
        f"cli.py score {cli_score} too close to scoring.py {scoring_score}"
    )


def test_cli_task_still_ranks_hub_file_high(tmp_path):
    """K: A task explicitly about CLI commands should rank cli.py high."""
    inventory = _inventory(
        "vibecode/cli.py",
        "vibecode/context/scoring.py",
        "tests/test_vibecode_cli.py",
    )

    results = score_relevant_files(
        tmp_path, "Improve context command help", inventory=inventory, limit=10
    )
    paths = _paths(results)

    assert "vibecode/cli.py" in paths[:3]


def test_hub_dep_fanout_does_not_flood_results(tmp_path):
    """L: Dependency boost through cli.py (hub) must not elevate unrelated files."""
    dep_map = {
        "$schema": "vibecode/dependency-map/v1",
        "edges": [
            {
                "from": "tests/test_vibecode_agents_export.py",
                "import_target": "vibecode.cli",
                "type": "python",
                "status": "resolved",
                "resolved_path": "vibecode/cli.py",
            }
        ],
    }
    dep_path = tmp_path / ".vibecode" / "index" / "dependency_map.json"
    dep_path.parent.mkdir(parents=True, exist_ok=True)
    dep_path.write_text(json.dumps(dep_map), encoding="utf-8")

    inventory = _inventory(
        "vibecode/context/scoring.py",
        "tests/test_vibecode_relevant_files.py",
        "vibecode/cli.py",
        "tests/test_vibecode_agents_export.py",
    )

    results = score_relevant_files(
        tmp_path, "Improve relevant-file scoring", inventory=inventory, limit=10
    )
    paths = _paths(results)

    # Direct matches must dominate.
    assert paths[0] in {
        "vibecode/context/scoring.py",
        "tests/test_vibecode_relevant_files.py",
    }
    # CLI hub must not appear in top 2 via dep fan-out alone.
    assert "vibecode/cli.py" not in paths[:2]
    # Unrelated test boosted only through cli.py hub must rank below direct matches.
    if "tests/test_vibecode_agents_export.py" in paths:
        agents_idx = paths.index("tests/test_vibecode_agents_export.py")
        scoring_idx = paths.index("vibecode/context/scoring.py")
        assert scoring_idx < agents_idx


# ---------------------------------------------------------------------------
# Two-pass behavior tests — M and N
# ---------------------------------------------------------------------------


def test_unrelated_test_not_boosted_when_source_is_irrelevant(tmp_path):
    """M: A test paired with a low-scoring source must NOT receive a pairing boost."""
    # "widget.py" contains no task-relevant keywords → scores below threshold in pass 1.
    # Its paired test must not receive the +5 pairing boost and must not appear with
    # a "paired" reason.
    inventory = _inventory(
        "vibecode/context/scoring.py",       # directly relevant to task
        "vibecode/context/widget.py",         # not relevant to task
        "tests/test_vibecode_scoring.py",    # paired with relevant source
        "tests/test_vibecode_widget.py",     # paired with irrelevant source
    )

    results = score_relevant_files(
        tmp_path, "Improve relevant-file scoring", inventory=inventory, limit=10
    )
    scored = {r["path"]: r for r in results}

    scoring_test_score = scored.get("tests/test_vibecode_scoring.py", {}).get("score", 0)
    widget_test_score = scored.get("tests/test_vibecode_widget.py", {}).get("score", 0)

    # Relevant test must outscore unrelated test by a significant margin.
    assert scoring_test_score > widget_test_score, (
        f"test_vibecode_scoring.py ({scoring_test_score}) should score > "
        f"test_vibecode_widget.py ({widget_test_score})"
    )
    # Unrelated test must not carry a pairing reason.
    widget_reasons = " ".join(scored.get("tests/test_vibecode_widget.py", {}).get("reasons", []))
    assert "paired" not in widget_reasons


def test_relevant_source_propagates_boost_to_paired_test(tmp_path):
    """N: A test paired with a high-scoring source DOES receive a pairing boost."""
    inventory = _inventory(
        "vibecode/context/scoring.py",      # directly relevant to task
        "tests/test_vibecode_scoring.py",   # paired with relevant source
    )

    results = score_relevant_files(
        tmp_path, "Improve relevant-file scoring", inventory=inventory, limit=10
    )
    scored = {r["path"]: r for r in results}

    assert "tests/test_vibecode_scoring.py" in scored, "paired test must appear in results"
    reasons = " ".join(scored["tests/test_vibecode_scoring.py"]["reasons"])
    assert "paired" in reasons, "paired test must carry a pairing reason"
