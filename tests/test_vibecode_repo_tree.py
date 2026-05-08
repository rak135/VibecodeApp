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
        # Low-risk files inside subdirs should not appear
        assert "test_api.py" not in output
        assert "intro.md" not in output

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

        forbidden = [
            "__pycache__",
            "node_modules",
            ".venv",
            "dist",
            "build",
            ".git",
            ".vibecode/current",
            ".vibecode/cache",
        ]
        for text in forbidden:
            assert text not in output
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
# write_repo_tree
# ---------------------------------------------------------------------------


class TestWriteRepoTree:
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
