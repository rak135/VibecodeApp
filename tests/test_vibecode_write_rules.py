"""Tests for vibecode write rules (human-maintained vs generated path enforcement)."""

from __future__ import annotations

from pathlib import Path

import pytest

from vibecode.cli import main
from vibecode.write_rules import (
    GENERATED_PATH_PREFIXES,
    HUMAN_MAINTAINED_PATHS,
    is_human_maintained,
    safe_write,
)


# ---------------------------------------------------------------------------
# HUMAN_MAINTAINED_PATHS contract
# ---------------------------------------------------------------------------


def test_human_maintained_paths_is_frozenset():
    assert isinstance(HUMAN_MAINTAINED_PATHS, frozenset)


def test_human_maintained_paths_contains_project_yaml():
    assert ".vibecode/project.yaml" in HUMAN_MAINTAINED_PATHS


def test_human_maintained_paths_contains_invariants():
    assert ".vibecode/architecture/INVARIANTS.md" in HUMAN_MAINTAINED_PATHS


def test_human_maintained_paths_contains_module_boundaries():
    assert ".vibecode/architecture/MODULE_BOUNDARIES.md" in HUMAN_MAINTAINED_PATHS


def test_human_maintained_paths_contains_protected_areas():
    assert ".vibecode/architecture/PROTECTED_AREAS.md" in HUMAN_MAINTAINED_PATHS


def test_human_maintained_paths_contains_handoff_files():
    assert ".vibecode/handoff/NOW.md" in HUMAN_MAINTAINED_PATHS
    assert ".vibecode/handoff/NEXT.md" in HUMAN_MAINTAINED_PATHS
    assert ".vibecode/handoff/BLOCKERS.md" in HUMAN_MAINTAINED_PATHS


def test_human_maintained_paths_contains_protected_paths_policy():
    assert ".vibecode/checks/protected_paths.yaml" in HUMAN_MAINTAINED_PATHS


def test_human_maintained_paths_contains_index_policy():
    assert ".vibecode/index/README.md" in HUMAN_MAINTAINED_PATHS
    assert ".vibecode/index/schema.json" in HUMAN_MAINTAINED_PATHS


def test_generated_path_prefixes_is_tuple():
    assert isinstance(GENERATED_PATH_PREFIXES, tuple)


def test_generated_path_prefixes_covers_index():
    assert any(p.startswith(".vibecode/index/") for p in GENERATED_PATH_PREFIXES)


def test_generated_path_prefixes_covers_current():
    assert any(p.startswith(".vibecode/current/") for p in GENERATED_PATH_PREFIXES)


def test_generated_path_prefixes_covers_logs():
    assert any(p.startswith(".vibecode/logs/") for p in GENERATED_PATH_PREFIXES)


def test_generated_path_prefixes_covers_runs():
    assert any(p.startswith(".vibecode/runs/") for p in GENERATED_PATH_PREFIXES)


def test_generated_path_prefixes_covers_tmp():
    assert any(p.startswith(".vibecode/tmp/") for p in GENERATED_PATH_PREFIXES)


def test_generated_path_prefixes_covers_cache():
    assert any(p.startswith(".vibecode/cache/") for p in GENERATED_PATH_PREFIXES)


def test_human_maintained_paths_not_in_generated_prefixes():
    """No human-maintained path may start with a generated prefix.

    Exception: committed policy files under .vibecode/index/ that are
    intentionally human-maintained (README.md, schema.json).
    """
    _COMMITTED_INDEX_EXCEPTIONS: frozenset[str] = frozenset({
        ".vibecode/index/README.md",
        ".vibecode/index/schema.json",
    })
    for rel in HUMAN_MAINTAINED_PATHS:
        if rel in _COMMITTED_INDEX_EXCEPTIONS:
            continue
        assert not rel.startswith(GENERATED_PATH_PREFIXES), (
            f"Human-maintained path '{rel}' lives under a generated prefix."
        )


# ---------------------------------------------------------------------------
# is_human_maintained
# ---------------------------------------------------------------------------


def test_is_human_maintained_true_for_invariants(tmp_path):
    path = tmp_path / ".vibecode" / "architecture" / "INVARIANTS.md"
    assert is_human_maintained(path, tmp_path) is True


def test_is_human_maintained_true_for_project_yaml(tmp_path):
    path = tmp_path / ".vibecode" / "project.yaml"
    assert is_human_maintained(path, tmp_path) is True


def test_is_human_maintained_true_for_all_human_maintained_paths(tmp_path):
    for rel in HUMAN_MAINTAINED_PATHS:
        path = tmp_path / Path(rel)
        assert is_human_maintained(path, tmp_path) is True, f"Expected True for {rel}"


def test_is_human_maintained_false_for_generated_inventory(tmp_path):
    path = tmp_path / ".vibecode" / "index" / "file_inventory.json"
    assert is_human_maintained(path, tmp_path) is False


def test_generated_index_outputs_are_not_human_maintained(tmp_path):
    generated_outputs = (
        "file_inventory.json",
        "symbol_map.json",
        "dependency_map.json",
        "test_map.json",
        "entrypoints.md",
        "risky_files.md",
        "repo_tree.generated.md",
    )
    for name in generated_outputs:
        path = tmp_path / ".vibecode" / "index" / name
        assert is_human_maintained(path, tmp_path) is False, name


def test_is_human_maintained_false_for_generated_context_pack(tmp_path):
    path = tmp_path / ".vibecode" / "current" / "context_pack.md"
    assert is_human_maintained(path, tmp_path) is False


def test_is_human_maintained_false_for_log_file(tmp_path):
    path = tmp_path / ".vibecode" / "logs" / "index_runs" / "20240101T000000Z.json"
    assert is_human_maintained(path, tmp_path) is False


def test_is_human_maintained_false_for_runs_file(tmp_path):
    path = tmp_path / ".vibecode" / "runs" / "20240101T000000Z.json"
    assert is_human_maintained(path, tmp_path) is False


def test_is_human_maintained_false_for_tmp_file(tmp_path):
    path = tmp_path / ".vibecode" / "tmp" / "scratch.txt"
    assert is_human_maintained(path, tmp_path) is False


def test_is_human_maintained_false_for_cache_file(tmp_path):
    path = tmp_path / ".vibecode" / "cache" / "context_digest.json"
    assert is_human_maintained(path, tmp_path) is False


def test_is_human_maintained_false_for_generated_export(tmp_path):
    path = tmp_path / ".vibecode" / "generated" / "AGENTS.generated.md"
    assert is_human_maintained(path, tmp_path) is False


def test_is_human_maintained_false_for_unrelated_path(tmp_path):
    path = tmp_path / "src" / "main.py"
    assert is_human_maintained(path, tmp_path) is False


def test_is_human_maintained_false_for_path_outside_repo_root(tmp_path):
    other = tmp_path.parent
    path = other / ".vibecode" / "architecture" / "INVARIANTS.md"
    assert is_human_maintained(path, tmp_path) is False


# ---------------------------------------------------------------------------
# safe_write
# ---------------------------------------------------------------------------


def test_safe_write_raises_for_human_maintained_without_force(tmp_path):
    path = tmp_path / ".vibecode" / "architecture" / "INVARIANTS.md"
    with pytest.raises(PermissionError, match="human-maintained"):
        safe_write(path, "content", repo_root=tmp_path)


def test_safe_write_raises_for_project_yaml_without_force(tmp_path):
    path = tmp_path / ".vibecode" / "project.yaml"
    with pytest.raises(PermissionError):
        safe_write(path, "content", repo_root=tmp_path)


def test_safe_write_succeeds_for_generated_path(tmp_path):
    path = tmp_path / ".vibecode" / "index" / "file_inventory.json"
    safe_write(path, '{"files": []}', repo_root=tmp_path)
    assert path.read_text(encoding="utf-8") == '{"files": []}'


def test_safe_write_succeeds_for_runs_path(tmp_path):
    path = tmp_path / ".vibecode" / "runs" / "metadata.json"
    safe_write(path, "{}", repo_root=tmp_path)
    assert path.exists()


def test_safe_write_succeeds_for_tmp_path(tmp_path):
    path = tmp_path / ".vibecode" / "tmp" / "scratch.txt"
    safe_write(path, "scratch", repo_root=tmp_path)
    assert path.exists()


def test_safe_write_succeeds_for_cache_path(tmp_path):
    path = tmp_path / ".vibecode" / "cache" / "digest.json"
    safe_write(path, "{}", repo_root=tmp_path)
    assert path.exists()


def test_safe_write_succeeds_for_generated_export_path(tmp_path):
    path = tmp_path / ".vibecode" / "generated" / "output.md"
    safe_write(path, "# output\n", repo_root=tmp_path)
    assert path.exists()


def test_safe_write_creates_parent_directories(tmp_path):
    path = tmp_path / ".vibecode" / "index" / "subdir" / "output.json"
    safe_write(path, "{}", repo_root=tmp_path)
    assert path.exists()


def test_safe_write_with_force_writes_human_maintained(tmp_path):
    path = tmp_path / ".vibecode" / "architecture" / "INVARIANTS.md"
    safe_write(path, "# Overwritten\n", repo_root=tmp_path, force=True)
    assert path.read_text(encoding="utf-8") == "# Overwritten\n"


def test_safe_write_error_message_includes_path(tmp_path):
    path = tmp_path / ".vibecode" / "handoff" / "NOW.md"
    with pytest.raises(PermissionError, match=r"\.vibecode/handoff/NOW\.md"):
        safe_write(path, "content", repo_root=tmp_path)


# ---------------------------------------------------------------------------
# Integration: index does not overwrite human-maintained files
# ---------------------------------------------------------------------------


def test_index_does_not_overwrite_invariants(tmp_path):
    """INVARIANTS.md must remain unchanged after a full ``vibecode index`` run."""
    assert main(["init", str(tmp_path), "--id", "proj", "--name", "Proj"]) == 0

    invariants = tmp_path / ".vibecode" / "architecture" / "INVARIANTS.md"
    custom = "# Custom Invariants\n\n- No circular imports.\n- All public APIs typed.\n"
    invariants.write_text(custom, encoding="utf-8")

    (tmp_path / "app.py").write_text("def main(): pass\n", encoding="utf-8")

    rc = main(["index", str(tmp_path)])
    assert rc == 0
    assert invariants.read_text(encoding="utf-8") == custom


def test_index_does_not_overwrite_any_human_maintained_file(tmp_path):
    """All human-maintained files must remain unchanged after ``vibecode index``."""
    assert main(["init", str(tmp_path), "--id", "proj", "--name", "Proj"]) == 0

    snapshots: dict[str, str] = {}
    for rel in HUMAN_MAINTAINED_PATHS:
        p = tmp_path / Path(rel)
        if p.exists():
            snapshots[rel] = p.read_text(encoding="utf-8")

    (tmp_path / "app.py").write_text("def main(): pass\n", encoding="utf-8")
    assert main(["index", str(tmp_path)]) == 0

    for rel, original in snapshots.items():
        current = (tmp_path / Path(rel)).read_text(encoding="utf-8")
        assert current == original, f"index modified human-maintained file: {rel}"


# ---------------------------------------------------------------------------
# Drift detection: init-created files must be in HUMAN_MAINTAINED_PATHS
# ---------------------------------------------------------------------------


def test_init_created_files_covered_by_write_rules(tmp_path):
    """Every file created by ``vibecode init`` that should be human-maintained
    must be listed in HUMAN_MAINTAINED_PATHS.  This test catches drift when
    new template files are added without updating the allowlist."""
    assert main(["init", str(tmp_path), "--id", "proj", "--name", "Proj"]) == 0

    # Files that vibecode init creates.
    files_created_by_init = {
        ".vibecode/project.yaml",
        ".vibecode/checks/required_checks.yaml",
        ".vibecode/checks/protected_paths.yaml",
        ".vibecode/architecture/OVERVIEW.md",
        ".vibecode/architecture/INVARIANTS.md",
        ".vibecode/architecture/STRUCTURE.md",
        ".vibecode/architecture/MODULE_BOUNDARIES.md",
        ".vibecode/architecture/PROTECTED_AREAS.md",
        ".vibecode/architecture/DATA_FLOW.md",
        ".vibecode/handoff/NOW.md",
        ".vibecode/handoff/NEXT.md",
        ".vibecode/handoff/BLOCKERS.md",
        ".vibecode/history/README.md",
        ".vibecode/agents/safe.json",
        ".vibecode/agents/fast.json",
        ".vibecode/agents/audit.json",
    }

    missing = files_created_by_init - HUMAN_MAINTAINED_PATHS
    assert not missing, (
        f"Files created by init but missing from HUMAN_MAINTAINED_PATHS: {missing}"
    )

    # Also verify they exist on disk and are recognised.
    for rel in files_created_by_init:
        path = tmp_path / Path(rel)
        assert path.exists(), f"init did not create {rel}"
        assert is_human_maintained(path, tmp_path) is True, (
            f"is_human_maintained returned False for {rel}"
        )
