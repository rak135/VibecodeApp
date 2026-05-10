"""Tests for vibecode init command."""

from __future__ import annotations

from pathlib import Path

from vibecode.cli import main
from vibecode.config import (
    DEFAULT_PROTECTED_PATH_RULES,
    load_config,
    load_protected_path_records,
)


def test_init_creates_all_required_paths(tmp_path):
    rc = main(["init", str(tmp_path), "--id", "testproj", "--name", "Test Project"])
    assert rc == 0

    # Generated directories
    assert (tmp_path / ".vibecode" / "index").is_dir()
    assert (tmp_path / ".vibecode" / "current").is_dir()
    assert (tmp_path / ".vibecode" / "logs" / "index_runs").is_dir()
    assert (tmp_path / ".vibecode" / "checks").is_dir()

    # Human-maintained files
    assert (tmp_path / ".vibecode" / "project.yaml").is_file()
    assert (tmp_path / ".vibecode" / "checks" / "required_checks.yaml").is_file()
    assert (tmp_path / ".vibecode" / "checks" / "protected_paths.yaml").is_file()
    assert (tmp_path / ".vibecode" / "architecture" / "OVERVIEW.md").is_file()
    assert (tmp_path / ".vibecode" / "architecture" / "INVARIANTS.md").is_file()
    assert (tmp_path / ".vibecode" / "architecture" / "STRUCTURE.md").is_file()
    assert (tmp_path / ".vibecode" / "architecture" / "MODULE_BOUNDARIES.md").is_file()
    assert (tmp_path / ".vibecode" / "architecture" / "PROTECTED_AREAS.md").is_file()
    assert (tmp_path / ".vibecode" / "architecture" / "DATA_FLOW.md").is_file()
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
    assert "required_checks:" not in content
    checks = (tmp_path / ".vibecode" / "checks" / "required_checks.yaml").read_text(
        encoding="utf-8"
    )
    assert "checks:" in checks
    assert "required:" in checks


def test_init_protected_paths_yaml_contains_default_policy(tmp_path):
    main(["init", str(tmp_path), "--id", "myapp", "--name", "My App"])

    records = load_protected_path_records(tmp_path / ".vibecode")

    assert records == list(DEFAULT_PROTECTED_PATH_RULES)


def test_init_project_yaml_default_indexing_covers_python_js_ts_and_config(tmp_path):
    main(["init", str(tmp_path), "--id", "myapp", "--name", "My App"])

    cfg = load_config(tmp_path / ".vibecode")

    assert cfg.include == [
        "*.py",
        "*.js",
        "*.jsx",
        "*.ts",
        "*.tsx",
        "*.json",
        "*.toml",
        "*.yaml",
        "*.yml",
        "*.md",
        "*.mdx",
        "*.ini",
        "*.cfg",
        "*.env.example",
        "Dockerfile",
        "docker-compose.yml",
        "Makefile",
        "README*",
        "AGENTS.md",
        "package.json",
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "bun.lockb",
        "pyproject.toml",
        "requirements*.txt",
        "setup.cfg",
        "setup.py",
        "tsconfig*.json",
        "vite.config.*",
        "next.config.*",
        "tailwind.config.*",
        "postcss.config.*",
        "eslint.config.*",
        "prettier.config.*",
    ]
    assert cfg.exclude == [
        ".git/**",
        "node_modules/**",
        ".venv/**",
        "venv/**",
        "__pycache__/**",
        "dist/**",
        "build/**",
        "coverage/**",
        ".pytest_cache/**",
        ".mypy_cache/**",
        ".ruff_cache/**",
        ".vibecode/current/**",
        ".vibecode/runs/**",
        ".vibecode/tmp/**",
        ".vibecode/cache/**",
        ".vibecode/logs/**",
    ]


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


def test_init_external_repo_no_vibecode_specific_checks(tmp_path):
    """Init on an external non-VibecodeApp repo must not include vibecode.cli checks."""
    main(["init", str(tmp_path), "--id", "extproj", "--name", "External Project"])
    checks_content = (tmp_path / ".vibecode" / "checks" / "required_checks.yaml").read_text(
        encoding="utf-8"
    )
    assert "python -m vibecode.cli" not in checks_content
    assert "vibecode.cli --help" not in checks_content
    assert "vibecode.cli index" not in checks_content
    assert "vibecode.cli context" not in checks_content


def test_init_python_repo_gets_pytest_check(tmp_path):
    """Init on a Python repo should produce a pytest check."""
    (tmp_path / "app.py").write_text("print('hello')\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\nminversion = \"6.0\"\n", encoding="utf-8"
    )
    main(["init", str(tmp_path), "--id", "pyproj", "--name", "Python Project"])
    checks = (tmp_path / ".vibecode" / "checks" / "required_checks.yaml").read_text(
        encoding="utf-8"
    )
    assert "python -m pytest" in checks
    assert "python -m vibecode.cli" not in checks


def test_init_unknown_repo_gets_placeholder(tmp_path):
    """Init on a repo with no detectable tech stack should get a clear placeholder."""
    main(["init", str(tmp_path), "--id", "unk", "--name", "Unknown"])
    checks = (tmp_path / ".vibecode" / "checks" / "required_checks.yaml").read_text(
        encoding="utf-8"
    )
    assert "TODO" in checks
    assert "replace" in checks.lower()
    assert "python -m vibecode.cli" not in checks
