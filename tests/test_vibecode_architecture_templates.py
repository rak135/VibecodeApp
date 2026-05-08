"""Tests for human-maintained architecture template creation and preservation."""

from __future__ import annotations

import argparse
from pathlib import Path

from vibecode.cli import main
from vibecode.project import ARCHITECTURE_FILES, TEMPLATE_UNFILLED_MARKER


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init(tmp_path: Path, **kwargs) -> int:
    argv = ["init", str(tmp_path), "--id", "testproj", "--name", "Test Project"]
    for k, v in kwargs.items():
        argv += [f"--{k}", v]
    return main(argv)


def _index(tmp_path: Path) -> tuple[int, list[str]]:
    """Run index and return (rc, stderr_lines)."""
    import io
    import sys

    buf = io.StringIO()
    old_stderr = sys.stderr
    sys.stderr = buf
    try:
        rc = main(["index", str(tmp_path)])
    finally:
        sys.stderr = old_stderr
    return rc, buf.getvalue().splitlines()


# ---------------------------------------------------------------------------
# Template creation
# ---------------------------------------------------------------------------


class TestArchitectureTemplatesCreated:
    def test_all_four_files_created(self, tmp_path):
        _init(tmp_path)
        for rel in ARCHITECTURE_FILES:
            assert (tmp_path / Path(rel)).is_file(), f"Missing: {rel}"

    def test_templates_contain_unfilled_marker(self, tmp_path):
        _init(tmp_path)
        for rel in ARCHITECTURE_FILES:
            content = (tmp_path / Path(rel)).read_text(encoding="utf-8")
            assert TEMPLATE_UNFILLED_MARKER in content, (
                f"{rel} does not contain the unfilled marker"
            )

    def test_templates_contain_todo_instructions(self, tmp_path):
        _init(tmp_path)
        for rel in ARCHITECTURE_FILES:
            content = (tmp_path / Path(rel)).read_text(encoding="utf-8")
            assert "TODO" in content, f"{rel} has no TODO fill-in instruction"

    def test_templates_do_not_contain_fictional_rules(self, tmp_path):
        """Templates must not hallucinate domain rules the user did not provide."""
        _init(tmp_path)
        forbidden_phrases = [
            "Django",
            "Flask",
            "REST",
            "GraphQL",
            "PostgreSQL",
            "Docker",
        ]
        for rel in ARCHITECTURE_FILES:
            content = (tmp_path / Path(rel)).read_text(encoding="utf-8")
            for phrase in forbidden_phrases:
                assert phrase not in content, (
                    f"{rel} hallucinated domain rule containing '{phrase}'"
                )

    def test_templates_include_section_headers(self, tmp_path):
        _init(tmp_path)
        for rel in ARCHITECTURE_FILES:
            content = (tmp_path / Path(rel)).read_text(encoding="utf-8")
            assert "##" in content, f"{rel} has no section headers"


# ---------------------------------------------------------------------------
# Idempotency – templates survive repeated init
# ---------------------------------------------------------------------------


class TestTemplatesSurviveRepeatedInit:
    def test_manually_edited_invariants_survives_init(self, tmp_path):
        _init(tmp_path)
        invariants = tmp_path / ".vibecode" / "architecture" / "INVARIANTS.md"
        custom = "# My invariants\n\n- No circular imports.\n"
        invariants.write_text(custom, encoding="utf-8")

        _init(tmp_path)

        assert invariants.read_text(encoding="utf-8") == custom

    def test_all_architecture_files_survive_repeated_init(self, tmp_path):
        _init(tmp_path)
        contents: dict[str, str] = {}
        for rel in ARCHITECTURE_FILES:
            p = tmp_path / Path(rel)
            p.write_text(f"# Custom content for {rel}\n", encoding="utf-8")
            contents[rel] = p.read_text(encoding="utf-8")

        _init(tmp_path)

        for rel, expected in contents.items():
            actual = (tmp_path / Path(rel)).read_text(encoding="utf-8")
            assert actual == expected, f"File was changed by second init: {rel}"

    def test_force_flag_overwrites_architecture_files(self, tmp_path):
        _init(tmp_path)
        invariants = tmp_path / ".vibecode" / "architecture" / "INVARIANTS.md"
        invariants.write_text("# Custom\n", encoding="utf-8")

        main(["init", str(tmp_path), "--id", "testproj", "--name", "Test Project", "--force"])

        content = invariants.read_text(encoding="utf-8")
        assert "Custom" not in content
        assert TEMPLATE_UNFILLED_MARKER in content


# ---------------------------------------------------------------------------
# Idempotency – templates survive index
# ---------------------------------------------------------------------------


class TestTemplatesSurviveIndex:
    def test_manually_edited_invariants_survives_index(self, tmp_path):
        _init(tmp_path)
        invariants = tmp_path / ".vibecode" / "architecture" / "INVARIANTS.md"
        custom = "# My invariants\n\n- No circular imports.\n"
        invariants.write_text(custom, encoding="utf-8")

        rc, _ = _index(tmp_path)

        assert rc == 0
        assert invariants.read_text(encoding="utf-8") == custom

    def test_all_architecture_files_survive_index(self, tmp_path):
        _init(tmp_path)
        contents: dict[str, str] = {}
        for rel in ARCHITECTURE_FILES:
            p = tmp_path / Path(rel)
            p.write_text(f"# Custom content for {rel}\n", encoding="utf-8")
            contents[rel] = p.read_text(encoding="utf-8")

        rc, _ = _index(tmp_path)

        assert rc == 0
        for rel, expected in contents.items():
            actual = (tmp_path / Path(rel)).read_text(encoding="utf-8")
            assert actual == expected, f"Index modified human file: {rel}"


# ---------------------------------------------------------------------------
# Validation warnings for unfilled templates
# ---------------------------------------------------------------------------


class TestUnfilledTemplateWarnings:
    def test_unfilled_templates_produce_warnings(self, tmp_path):
        _init(tmp_path)
        rc, stderr_lines = _index(tmp_path)

        assert rc == 0
        warnings = [l for l in stderr_lines if "unfilled template" in l.lower()]
        assert len(warnings) == len(ARCHITECTURE_FILES), (
            f"Expected {len(ARCHITECTURE_FILES)} unfilled-template warnings, got {len(warnings)}"
        )

    def test_filled_template_produces_no_warning(self, tmp_path):
        _init(tmp_path)
        # Fill in all architecture files (remove unfilled marker)
        for rel in ARCHITECTURE_FILES:
            p = tmp_path / Path(rel)
            content = p.read_text(encoding="utf-8").replace(TEMPLATE_UNFILLED_MARKER, "")
            p.write_text(content, encoding="utf-8")

        rc, stderr_lines = _index(tmp_path)

        assert rc == 0
        warnings = [l for l in stderr_lines if "unfilled template" in l.lower()]
        assert warnings == [], f"Unexpected unfilled-template warnings: {warnings}"

    def test_partially_filled_produces_partial_warnings(self, tmp_path):
        _init(tmp_path)
        # Fill in only INVARIANTS.md
        invariants_rel = ".vibecode/architecture/INVARIANTS.md"
        p = tmp_path / Path(invariants_rel)
        content = p.read_text(encoding="utf-8").replace(TEMPLATE_UNFILLED_MARKER, "")
        p.write_text(content, encoding="utf-8")

        rc, stderr_lines = _index(tmp_path)

        assert rc == 0
        warnings = [l for l in stderr_lines if "unfilled template" in l.lower()]
        assert len(warnings) == len(ARCHITECTURE_FILES) - 1
        assert not any(invariants_rel in w for w in warnings)

    def test_unfilled_warnings_appear_in_log_file(self, tmp_path):
        _init(tmp_path)
        _index(tmp_path)

        log_dir = tmp_path / ".vibecode" / "logs" / "index_runs"
        logs = sorted(log_dir.glob("*.log"))
        assert logs, "No log file was written"
        log_content = logs[-1].read_text(encoding="utf-8")
        assert "unfilled template" in log_content.lower()
