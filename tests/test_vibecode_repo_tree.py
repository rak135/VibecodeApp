"""Tests for the repo_tree.md renderer."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from vibecode.indexer.classifier import FileRecord, classify
from vibecode.indexer.repo_tree import render_repo_tree, write_repo_tree


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rec(path: str, size: int = 100) -> FileRecord:
    """Create a :class:`FileRecord` via the real classifier for *path*."""
    return classify(path, size)


def _make_fixture_records() -> list[FileRecord]:
    """Return a representative set of records for a mixed-role project."""
    return [
        _rec("api/routes.py"),          # backend_api – high risk
        _rec("api/utils.py"),           # backend_api – high risk
        _rec("engine/core.py"),         # backend_engine – high risk
        _rec("components/Button.tsx"),  # frontend_component – medium risk
        _rec("screens/Home.tsx"),       # frontend_screen – medium risk
        _rec("scripts/deploy.sh"),      # script – medium risk
        _rec("tests/test_api.py"),      # test – low risk
        _rec("tests/test_engine.py"),   # test – low risk
        _rec("docs/README.md"),         # doc – low risk
        _rec("pyproject.toml"),         # config – low risk
        _rec("README.md"),              # doc – low risk
    ]


_FIXED_TIME = datetime(2026, 5, 8, 12, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# render_repo_tree
# ---------------------------------------------------------------------------


class TestRenderRepoTree:
    def test_heading_present(self, tmp_path):
        output = render_repo_tree(tmp_path, [])
        assert output.startswith("# Repository Tree")

    def test_root_name_in_output(self, tmp_path):
        records = _make_fixture_records()
        output = render_repo_tree(tmp_path, records)
        assert tmp_path.name in output

    def test_generated_metadata_present(self, tmp_path):
        output = render_repo_tree(tmp_path, [])
        assert "Generated:" in output
        assert "Repo root:" in output
        assert "Git commit:" in output
        assert "## Tree" in output

    def test_high_risk_files_marked(self, tmp_path):
        records = _make_fixture_records()
        output = render_repo_tree(tmp_path, records)
        assert "`[HIGH RISK]`" in output

    def test_medium_risk_files_marked(self, tmp_path):
        records = _make_fixture_records()
        output = render_repo_tree(tmp_path, records)
        assert "`[MEDIUM RISK]`" in output

    def test_top_level_dirs_present(self, tmp_path):
        records = _make_fixture_records()
        output = render_repo_tree(tmp_path, records)
        # All top-level directories must appear
        for name in ("api/", "engine/", "components/", "screens/", "tests/", "docs/"):
            assert name in output, f"Expected '{name}' in tree"

    def test_top_level_files_present(self, tmp_path):
        records = _make_fixture_records()
        output = render_repo_tree(tmp_path, records)
        assert "pyproject.toml" in output
        assert "README.md" in output

    def test_role_note_for_api_dir(self, tmp_path):
        records = _make_fixture_records()
        output = render_repo_tree(tmp_path, records)
        assert "_API / routes_" in output

    def test_role_note_for_engine_dir(self, tmp_path):
        records = _make_fixture_records()
        output = render_repo_tree(tmp_path, records)
        assert "_core logic_" in output

    def test_role_note_for_tests_dir(self, tmp_path):
        records = _make_fixture_records()
        output = render_repo_tree(tmp_path, records)
        assert "_tests_" in output

    def test_role_note_for_docs_dir(self, tmp_path):
        records = _make_fixture_records()
        output = render_repo_tree(tmp_path, records)
        assert "_documentation_" in output

    def test_low_risk_deep_files_omitted(self, tmp_path):
        records = [
            _rec("tests/test_api.py"),      # low risk
            _rec("docs/guide/intro.md"),    # low risk
        ]
        output = render_repo_tree(tmp_path, records)
        # Low-risk files inside subdirs must NOT appear in the compact Tree section.
        # (They may appear in the Architecture Orientation section.)
        tree_section = output.split("## Tree")[-1]
        assert "test_api.py" not in tree_section
        assert "intro.md" not in tree_section

    def test_high_risk_deep_files_present(self, tmp_path):
        records = [
            _rec("api/routes.py"),   # backend_api – high risk
        ]
        output = render_repo_tree(tmp_path, records)
        assert "routes.py" in output
        assert "`[HIGH RISK]`" in output

    def test_excluded_generated_dir_hidden(self, tmp_path):
        records = [
            _rec("vibecode.egg-info/PKG-INFO"),
            _rec("src/main.py"),
        ]
        output = render_repo_tree(tmp_path, records)
        assert "vibecode.egg-info" not in output

    def test_excluded_runtime_and_cache_dirs_hidden(self, tmp_path):
        records = [
            _rec("__pycache__/module.pyc"),
            _rec("node_modules/pkg/index.js"),
            _rec(".venv/lib/site.py"),
            _rec("dist/bundle.js"),
            _rec("build/out.js"),
            _rec(".git/config"),
            _rec(".vibecode/current/context_pack.md"),
            _rec(".vibecode/cache/state.json"),
            _rec("src/main.py"),
        ]
        output = render_repo_tree(tmp_path, records)

        # These should never appear anywhere – they are noise, not architecture.
        for text in ("__pycache__", "node_modules", ".venv", "dist", "build", ".git"):
            assert text not in output

        # .vibecode/current and .vibecode/cache should NOT appear in the compact Tree.
        tree_section = output.split("## Tree")[-1]
        assert ".vibecode/current" not in tree_section
        assert ".vibecode/cache" not in tree_section

        # But they may appear in the Architecture Orientation section to warn agents,
        # clearly labelled as [runtime / ignored].
        arch_section = output.split("## Architecture Orientation")[1].split("## Tree")[0] \
            if "## Architecture Orientation" in output else ""
        if ".vibecode/current" in arch_section:
            assert "[runtime / ignored]" in arch_section

        assert "src/" in output

    def test_tree_connectors_present(self, tmp_path):
        records = _make_fixture_records()
        output = render_repo_tree(tmp_path, records)
        assert "├── " in output or "└── " in output

    def test_compact_for_large_repo(self, tmp_path):
        """A directory tree with 100 low-risk files should produce a small tree."""
        records = [_rec(f"src/module_{i}/helper.py") for i in range(100)]
        output = render_repo_tree(tmp_path, records)
        lines = [ln for ln in output.splitlines() if ln.strip()]
        # Compactness: should not exceed ~10 meaningful lines for 100 low-risk files
        # (only src/ dir with no expansion since all are low-risk "unknown")
        assert len(lines) < 20

    def test_empty_records_produces_valid_output(self, tmp_path):
        output = render_repo_tree(tmp_path, [])
        assert "# Repository Tree" in output
        assert tmp_path.name in output

    def test_max_depth_limits_expansion(self, tmp_path):
        records = [
            _rec("a/b/c/d/deep.py"),  # deep low-risk file
            _rec("api/v1/routes.py"), # deep high-risk file
        ]
        output = render_repo_tree(tmp_path, records, max_depth=2)
        # With max_depth=2 we only expand 2 levels deep
        assert "a/" in output
        # routes.py is at depth 3 but max_depth=2 stops before it
        assert "routes.py" not in output

    def test_node_modules_not_shown(self, tmp_path):
        """node_modules should never appear as a directory entry in the tree."""
        # Simulate records that don't include node_modules (as scanner would produce)
        records = [_rec("src/app.js"), _rec("README.md")]
        output = render_repo_tree(tmp_path, records)
        # Check no tree line introduces node_modules/ as an entry
        assert "node_modules/" not in output

    def test_output_ends_with_newline(self, tmp_path):
        output = render_repo_tree(tmp_path, _make_fixture_records())
        assert output.endswith("\n")

    def test_medium_risk_file_nested(self, tmp_path):
        records = [
            _rec("components/ui/Button.tsx"),  # frontend_component – medium
        ]
        output = render_repo_tree(tmp_path, records)
        assert "Button.tsx" in output
        assert "`[MEDIUM RISK]`" in output

    def test_script_role_note(self, tmp_path):
        records = [_rec("scripts/deploy.sh")]
        output = render_repo_tree(tmp_path, records)
        assert "_scripts_" in output

    def test_components_role_note(self, tmp_path):
        records = [_rec("components/Card.tsx")]
        output = render_repo_tree(tmp_path, records)
        assert "_UI components_" in output

    def test_screens_role_note(self, tmp_path):
        records = [_rec("screens/Dashboard.tsx")]
        output = render_repo_tree(tmp_path, records)
        assert "_UI screens_" in output

    def test_last_item_uses_corner_connector(self, tmp_path):
        records = [_rec("api/routes.py")]
        output = render_repo_tree(tmp_path, records)
        # The only top-level dir should use └──
        assert "└── api/" in output

    def test_multiple_top_level_uses_branch_connector(self, tmp_path):
        records = [
            _rec("api/routes.py"),
            _rec("tests/test_api.py"),
        ]
        output = render_repo_tree(tmp_path, records)
        # api/ is not the last item, so it uses ├──
        assert "├── api/" in output
        # tests/ is the last, uses └──
        assert "└── tests/" in output


# ---------------------------------------------------------------------------
# Architecture orientation section
# ---------------------------------------------------------------------------


def _make_vibecode_records() -> list[FileRecord]:
    """Return a representative set of records that mirrors the VibecodeApp layout."""
    return [
        # Source package
        _rec("vibecode/__init__.py"),
        _rec("vibecode/cli.py"),
        _rec("vibecode/config.py"),
        _rec("vibecode/project.py"),
        _rec("vibecode/paths.py"),
        _rec("vibecode/validation.py"),
        # Indexer sub-package
        _rec("vibecode/indexer/__init__.py"),
        _rec("vibecode/indexer/scanner.py"),
        _rec("vibecode/indexer/classifier.py"),
        _rec("vibecode/indexer/repo_tree.py"),
        _rec("vibecode/indexer/test_map.py"),   # should NOT be classified as tests
        _rec("vibecode/indexer/entrypoints.py"),
        # Context sub-package
        _rec("vibecode/context/__init__.py"),
        _rec("vibecode/context/renderer.py"),
        _rec("vibecode/context/scoring.py"),
        _rec("vibecode/context/agents_export.py"),
        # Test suite
        _rec("tests/__init__.py"),
        _rec("tests/test_vibecode_cli.py"),
        _rec("tests/test_vibecode_repo_tree.py"),
        _rec("tests/test_vibecode_context_pack.py"),
        # Docs
        _rec("docs/README.md"),
        # .vibecode project truth
        _rec(".vibecode/architecture/INVARIANTS.md"),
        _rec(".vibecode/handoff/NOW.md"),
        # .vibecode generated
        _rec(".vibecode/index/repo_tree.generated.md"),
        # Config
        _rec("pyproject.toml"),
        _rec("README.md"),
    ]


def _make_test_map_data() -> dict:
    """Return minimal test_map_data that links source to test files."""
    return {
        "tests": [
            {"path": "tests/test_vibecode_cli.py", "kind": "pytest"},
            {"path": "tests/test_vibecode_repo_tree.py", "kind": "pytest"},
            {"path": "tests/test_vibecode_context_pack.py", "kind": "pytest"},
        ],
        "rules": [
            {
                "path_pattern": "vibecode/cli.py",
                "required_checks": ["tests/test_vibecode_cli.py"],
                "reason": "import match",
            },
            {
                "path_pattern": "vibecode/indexer/repo_tree.py",
                "required_checks": ["tests/test_vibecode_repo_tree.py"],
                "reason": "import match",
            },
            {
                "path_pattern": "vibecode/context/renderer.py",
                "required_checks": ["tests/test_vibecode_context_pack.py"],
                "reason": "import match",
            },
        ],
    }


def _make_entrypoints_data() -> dict:
    return {
        "backend": [],
        "frontend": [],
        "cli_scripts": [
            {"name": "vibecode", "target": "vibecode.cli:main", "source": "pyproject.toml"},
        ],
        "runtime_config": [],
    }


class TestArchitectureOrientation:
    """Tests for the ## Architecture Orientation section of render_repo_tree."""

    def test_summary_section_present(self, tmp_path):
        records = _make_vibecode_records()
        output = render_repo_tree(tmp_path, records)
        assert "## Summary" in output

    def test_summary_source_count(self, tmp_path):
        records = _make_vibecode_records()
        output = render_repo_tree(tmp_path, records)
        assert "Source files:" in output

    def test_summary_test_count(self, tmp_path):
        records = _make_vibecode_records()
        output = render_repo_tree(tmp_path, records)
        assert "Test files:" in output

    def test_architecture_orientation_section_present(self, tmp_path):
        records = _make_vibecode_records()
        output = render_repo_tree(tmp_path, records)
        assert "## Architecture Orientation" in output

    def test_source_package_labeled_as_package_root(self, tmp_path):
        """vibecode/ must appear with [package root / source] label."""
        records = _make_vibecode_records()
        output = render_repo_tree(tmp_path, records)
        assert "[package root / source]" in output
        assert "vibecode/" in output

    def test_vibecode_not_classified_as_tests(self, tmp_path):
        """vibecode/ must NOT appear with a 'tests' label in the orientation section."""
        records = _make_vibecode_records()
        output = render_repo_tree(tmp_path, records)
        arch_section = output.split("## Architecture Orientation")[1].split("## Tree")[0]
        # The vibecode/ line should say [package root / source], not [test suite]
        for line in arch_section.splitlines():
            if "vibecode/" in line and "[" in line and not "indexer" in line and not "context" in line:
                assert "[test suite]" not in line, f"vibecode/ falsely labelled as test suite: {line!r}"

    def test_indexer_subfolder_labeled_as_indexing_core(self, tmp_path):
        """vibecode/indexer/ must appear as repository indexing core."""
        records = _make_vibecode_records()
        output = render_repo_tree(tmp_path, records)
        assert "[repository indexing core]" in output

    def test_context_subfolder_labeled_as_context_generation(self, tmp_path):
        """vibecode/context/ must appear as agent context generation."""
        records = _make_vibecode_records()
        output = render_repo_tree(tmp_path, records)
        assert "[agent context generation]" in output

    def test_cli_py_labeled_as_entrypoint(self, tmp_path):
        """cli.py must appear with [CLI entrypoint] label."""
        records = _make_vibecode_records()
        output = render_repo_tree(tmp_path, records)
        assert "[CLI entrypoint]" in output
        assert "cli.py" in output

    def test_test_suite_section_present(self, tmp_path):
        records = _make_vibecode_records()
        output = render_repo_tree(tmp_path, records)
        assert "### Test suite" in output
        assert "[test suite]" in output

    def test_test_files_grouped_in_test_section(self, tmp_path):
        """Top-level test files appear in the Test suite section."""
        records = _make_vibecode_records()
        output = render_repo_tree(tmp_path, records)
        assert "test_vibecode_cli.py" in output
        assert "test_vibecode_repo_tree.py" in output

    def test_test_source_links_shown(self, tmp_path):
        """Test files include → source links when test_map_data is provided."""
        records = _make_vibecode_records()
        test_map = _make_test_map_data()
        output = render_repo_tree(tmp_path, records, test_map_data=test_map)
        # Source → test link in the core package section
        assert "test_vibecode_cli.py" in output
        # Direct source file should mention its test
        assert "← tests:" in output or "→" in output

    def test_source_test_links_shown_in_orientation(self, tmp_path):
        """Source files in the core package show their test coverage."""
        records = _make_vibecode_records()
        test_map = _make_test_map_data()
        output = render_repo_tree(tmp_path, records, test_map_data=test_map)
        arch_section = output.split("## Architecture Orientation")[1].split("## Tree")[0]
        assert "test_vibecode_cli.py" in arch_section

    def test_entrypoints_section_shown(self, tmp_path):
        """Entrypoints section appears when entrypoints_data is provided."""
        records = _make_vibecode_records()
        entrypoints = _make_entrypoints_data()
        output = render_repo_tree(tmp_path, records, entrypoints_data=entrypoints)
        assert "### Entrypoints" in output
        assert "vibecode.cli:main" in output

    def test_entrypoints_count_in_summary(self, tmp_path):
        """Summary Entrypoints count reflects entrypoints_data."""
        records = _make_vibecode_records()
        entrypoints = _make_entrypoints_data()
        output = render_repo_tree(tmp_path, records, entrypoints_data=entrypoints)
        assert "Entrypoints: 1" in output

    def test_entrypoints_zero_without_data(self, tmp_path):
        records = _make_vibecode_records()
        output = render_repo_tree(tmp_path, records)
        assert "Entrypoints: 0" in output

    def test_docs_section_present(self, tmp_path):
        records = _make_vibecode_records()
        output = render_repo_tree(tmp_path, records)
        assert "[documentation]" in output

    def test_vibecode_architecture_labeled_as_truth(self, tmp_path):
        """`.vibecode/architecture/` appears with human-maintained label."""
        records = _make_vibecode_records()
        output = render_repo_tree(tmp_path, records)
        assert "[human-maintained architecture truth]" in output

    def test_vibecode_index_labeled_as_generated(self, tmp_path):
        """`.vibecode/index/` appears with generated / ignored label."""
        records = _make_vibecode_records()
        output = render_repo_tree(tmp_path, records)
        assert "[generated / ignored]" in output

    def test_generated_runtime_section_present(self, tmp_path):
        """Generated and runtime state section present when .vibecode/ files exist."""
        records = _make_vibecode_records()
        output = render_repo_tree(tmp_path, records)
        assert "### Generated and runtime state" in output
        assert "[runtime / ignored]" in output

    def test_test_map_py_not_in_test_suite_section(self, tmp_path):
        """vibecode/indexer/test_map.py must NOT appear in the Test suite section."""
        records = _make_vibecode_records()
        output = render_repo_tree(tmp_path, records)
        # Find the test suite section
        if "### Test suite" in output and "### Documentation" in output:
            test_section = output.split("### Test suite")[1].split("###")[0]
            # test_map.py lives in the source package, not in tests/
            assert "test_map.py" not in test_section

    def test_output_is_deterministic(self, tmp_path):
        """Same inputs always produce identical output."""
        records = _make_vibecode_records()
        test_map = _make_test_map_data()
        entrypoints = _make_entrypoints_data()
        out1 = render_repo_tree(
            tmp_path, records,
            generated_at=_FIXED_TIME,
            git_commit="abc123",
            entrypoints_data=entrypoints,
            test_map_data=test_map,
        )
        out2 = render_repo_tree(
            tmp_path, records,
            generated_at=_FIXED_TIME,
            git_commit="abc123",
            entrypoints_data=entrypoints,
            test_map_data=test_map,
        )
        assert out1 == out2

    def test_canonical_output_filename(self, tmp_path):
        """write_repo_tree uses repo_tree.generated.md as the canonical filename."""
        out = tmp_path / ".vibecode" / "index" / "repo_tree.generated.md"
        write_repo_tree(tmp_path, _make_vibecode_records(), out)
        assert out.exists()
        assert out.name == "repo_tree.generated.md"

    def test_second_level_indexer_files_listed(self, tmp_path):
        """Files inside vibecode/indexer/ appear in the orientation section."""
        records = _make_vibecode_records()
        output = render_repo_tree(tmp_path, records)
        arch_section = output.split("## Architecture Orientation")[1].split("## Tree")[0]
        assert "scanner.py" in arch_section
        assert "classifier.py" in arch_section
        assert "repo_tree.py" in arch_section

    def test_second_level_context_files_listed(self, tmp_path):
        """Files inside vibecode/context/ appear in the orientation section."""
        records = _make_vibecode_records()
        output = render_repo_tree(tmp_path, records)
        arch_section = output.split("## Architecture Orientation")[1].split("## Tree")[0]
        assert "renderer.py" in arch_section
        assert "scoring.py" in arch_section


# ---------------------------------------------------------------------------
# Tree section: source package expansion
# ---------------------------------------------------------------------------


def _tree_section(output: str) -> str:
    """Return just the ## Tree section content from render_repo_tree output."""
    return output.split("## Tree")[-1]


class TestTreeSourcePackageExpansion:
    """Tests that the ## Tree section expands Python source packages."""

    def test_vibecode_not_bare_in_tree(self, tmp_path):
        """vibecode/ must NOT appear as a collapsed bare directory in ## Tree."""
        records = _make_vibecode_records()
        tree = _tree_section(render_repo_tree(tmp_path, records))
        # The tree must show content inside vibecode/ — at minimum cli.py.
        assert "cli.py" in tree, "vibecode/ appears collapsed; cli.py missing from ## Tree"

    def test_vibecode_context_in_tree(self, tmp_path):
        """vibecode/context/ must appear inside the ## Tree section."""
        records = _make_vibecode_records()
        tree = _tree_section(render_repo_tree(tmp_path, records))
        assert "context/" in tree

    def test_vibecode_indexer_in_tree(self, tmp_path):
        """vibecode/indexer/ must appear inside the ## Tree section."""
        records = _make_vibecode_records()
        tree = _tree_section(render_repo_tree(tmp_path, records))
        assert "indexer/" in tree

    def test_vibecode_cli_py_in_tree(self, tmp_path):
        """vibecode/cli.py must appear inside the ## Tree section."""
        records = _make_vibecode_records()
        tree = _tree_section(render_repo_tree(tmp_path, records))
        assert "cli.py" in tree

    def test_context_files_in_tree(self, tmp_path):
        """Key files in vibecode/context/ appear in ## Tree."""
        records = _make_vibecode_records()
        tree = _tree_section(render_repo_tree(tmp_path, records))
        assert "renderer.py" in tree
        assert "scoring.py" in tree
        assert "agents_export.py" in tree

    def test_indexer_files_in_tree(self, tmp_path):
        """Key files in vibecode/indexer/ appear in ## Tree."""
        records = _make_vibecode_records()
        tree = _tree_section(render_repo_tree(tmp_path, records))
        assert "scanner.py" in tree
        assert "classifier.py" in tree
        assert "repo_tree.py" in tree

    def test_init_py_omitted_from_tree_expansion(self, tmp_path):
        """__init__.py files should not clutter the tree output."""
        records = _make_vibecode_records()
        tree = _tree_section(render_repo_tree(tmp_path, records))
        assert "__init__.py" not in tree

    def test_tests_not_expanded_more_than_source(self, tmp_path):
        """tests/ must not be expanded to show individual test files in ## Tree."""
        records = _make_vibecode_records()
        tree = _tree_section(render_repo_tree(tmp_path, records))
        # The test suite section should NOT list individual test files inline in the tree
        # (those live in the Architecture Orientation section, not in the Tree).
        # At minimum, test files from tests/ should not appear as file entries in the Tree.
        assert "test_vibecode_cli.py" not in tree

    def test_dir_without_init_not_expanded_as_source(self, tmp_path):
        """A directory without __init__.py must not be expanded as a source package."""
        records = [_rec(f"src/module_{i}/helper.py") for i in range(5)]
        tree = _tree_section(render_repo_tree(tmp_path, records))
        # src/ has no __init__.py, so helper.py files must not appear in the tree
        assert "helper.py" not in tree

    def test_source_package_expansion_deterministic(self, tmp_path):
        """Source package expansion must be deterministic (same input → same output)."""
        records = _make_vibecode_records()
        out1 = _tree_section(render_repo_tree(tmp_path, records, generated_at=_FIXED_TIME))
        out2 = _tree_section(render_repo_tree(tmp_path, records, generated_at=_FIXED_TIME))
        assert out1 == out2



    def test_creates_file(self, tmp_path):
        out = tmp_path / ".vibecode" / "index" / "repo_tree.generated.md"
        write_repo_tree(tmp_path, _make_fixture_records(), out)
        assert out.exists()

    def test_creates_parent_dirs(self, tmp_path):
        deep = tmp_path / "a" / "b" / "c" / "repo_tree.md"
        write_repo_tree(tmp_path, [], deep)
        assert deep.exists()

    def test_file_content_matches_render(self, tmp_path):
        out = tmp_path / "repo_tree.md"
        records = _make_fixture_records()
        write_repo_tree(tmp_path, records, out, generated_at=_FIXED_TIME, git_commit="abc123")
        expected = render_repo_tree(tmp_path, records, generated_at=_FIXED_TIME, git_commit="abc123")
        assert out.read_text(encoding="utf-8") == expected

    def test_repeated_write_overwrites(self, tmp_path):
        out = tmp_path / "repo_tree.md"
        write_repo_tree(tmp_path, [_rec("api/routes.py")], out)
        size1 = out.stat().st_size

        write_repo_tree(tmp_path, [], out)
        size2 = out.stat().st_size

        assert size2 < size1

    def test_human_files_untouched(self, tmp_path):
        human = tmp_path / ".vibecode" / "architecture" / "INVARIANTS.md"
        human.parent.mkdir(parents=True, exist_ok=True)
        human.write_text("# Custom\n", encoding="utf-8")
        mtime = human.stat().st_mtime

        out = tmp_path / ".vibecode" / "index" / "repo_tree.generated.md"
        write_repo_tree(tmp_path, _make_fixture_records(), out)

        assert human.stat().st_mtime == mtime
        assert human.read_text(encoding="utf-8") == "# Custom\n"
