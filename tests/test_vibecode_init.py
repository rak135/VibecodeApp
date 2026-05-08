"""Tests for vibecode init command."""

from __future__ import annotations

from pathlib import Path

from vibecode.cli import main


def test_init_creates_all_required_paths(tmp_path):
    rc = main(["init", str(tmp_path), "--id", "testproj", "--name", "Test Project"])
    assert rc == 0

    # Generated directories
    assert (tmp_path / ".vibecode" / "index").is_dir()
    assert (tmp_path / ".vibecode" / "current").is_dir()
    assert (tmp_path / ".vibecode" / "logs" / "index_runs").is_dir()

    # Human-maintained files
    assert (tmp_path / ".vibecode" / "project.yaml").is_file()
    assert (tmp_path / ".vibecode" / "architecture" / "INVARIANTS.md").is_file()
    assert (tmp_path / ".vibecode" / "architecture" / "STRUCTURE.md").is_file()
    assert (tmp_path / ".vibecode" / "architecture" / "MODULE_BOUNDARIES.md").is_file()
    assert (tmp_path / ".vibecode" / "architecture" / "PROTECTED_AREAS.md").is_file()
    assert (tmp_path / ".vibecode" / "handoff" / "NOW.md").is_file()
    assert (tmp_path / ".vibecode" / "handoff" / "NEXT.md").is_file()
    assert (tmp_path / ".vibecode" / "handoff" / "BLOCKERS.md").is_file()
    assert (tmp_path / ".vibecode" / "history" / "README.md").is_file()


def test_init_project_yaml_contains_required_fields(tmp_path):
    main(["init", str(tmp_path), "--id", "myapp", "--name", "My App"])
    content = (tmp_path / ".vibecode" / "project.yaml").read_text(encoding="utf-8")
    assert "schema: vibecode/project/v1" in content
    assert "id: myapp" in content
    assert "name: My App" in content
    assert "root:" in content
    assert "indexing:" in content
    assert "include:" in content
    assert "exclude:" in content
    assert "protected_paths:" in content
    assert "risk_rules:" in content
    assert "required_checks:" in content


def test_init_idempotent_does_not_overwrite_human_files(tmp_path):
    main(["init", str(tmp_path), "--id", "proj", "--name", "Proj"])

    invariants = tmp_path / ".vibecode" / "architecture" / "INVARIANTS.md"
    custom_text = "# Custom invariants\n\nDo not overwrite me.\n"
    invariants.write_text(custom_text, encoding="utf-8")

    rc = main(["init", str(tmp_path), "--id", "proj", "--name", "Proj"])
    assert rc == 0
    assert invariants.read_text(encoding="utf-8") == custom_text


def test_init_idempotent_preserves_all_human_files(tmp_path):
    main(["init", str(tmp_path), "--id", "proj", "--name", "Proj"])

    human_files = [
        ".vibecode/project.yaml",
        ".vibecode/architecture/INVARIANTS.md",
        ".vibecode/architecture/STRUCTURE.md",
        ".vibecode/architecture/MODULE_BOUNDARIES.md",
        ".vibecode/architecture/PROTECTED_AREAS.md",
        ".vibecode/handoff/NOW.md",
        ".vibecode/handoff/NEXT.md",
        ".vibecode/handoff/BLOCKERS.md",
        ".vibecode/history/README.md",
    ]
    original = {p: (tmp_path / Path(p)).read_text(encoding="utf-8") for p in human_files}

    # Second run
    main(["init", str(tmp_path), "--id", "proj", "--name", "Proj"])

    for rel, text in original.items():
        assert (tmp_path / Path(rel)).read_text(encoding="utf-8") == text, f"File was changed: {rel}"


def test_init_force_overwrites_existing_files(tmp_path):
    main(["init", str(tmp_path), "--id", "proj", "--name", "Proj"])

    invariants = tmp_path / ".vibecode" / "architecture" / "INVARIANTS.md"
    invariants.write_text("# Custom invariants\n\nDo not overwrite me.\n", encoding="utf-8")

    rc = main(["init", str(tmp_path), "--id", "proj", "--name", "Proj", "--force"])
    assert rc == 0
    content = invariants.read_text(encoding="utf-8")
    assert "Do not overwrite me" not in content


def test_init_default_id_derived_from_dirname(tmp_path):
    rc = main(["init", str(tmp_path)])
    assert rc == 0
    content = (tmp_path / ".vibecode" / "project.yaml").read_text(encoding="utf-8")
    expected_id = tmp_path.name.lower().replace(" ", "_")
    assert f"id: {expected_id}" in content


def test_init_second_run_leaves_generated_dirs_intact(tmp_path):
    main(["init", str(tmp_path), "--id", "proj", "--name", "Proj"])

    # Simulate a file dropped into a generated directory
    snapshot = tmp_path / ".vibecode" / "index" / "snapshot.json"
    snapshot.write_text("{}", encoding="utf-8")

    main(["init", str(tmp_path), "--id", "proj", "--name", "Proj"])
    assert snapshot.exists()


def test_init_returns_zero_on_success(tmp_path):
    assert main(["init", str(tmp_path), "--id", "x", "--name", "X"]) == 0
