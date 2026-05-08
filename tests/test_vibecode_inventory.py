"""Tests for file_inventory.json generation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from vibecode.indexer.inventory import build_inventory, write_inventory
from vibecode.indexer.scanner import FileStatus, IndexedFile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, content: str = "# placeholder\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _make_indexed(path: str, size: int, status: FileStatus = FileStatus.UNKNOWN) -> IndexedFile:
    return IndexedFile(path=path, status=status, size=size)


# ---------------------------------------------------------------------------
# build_inventory
# ---------------------------------------------------------------------------


class TestBuildInventory:
    def test_schema_marker_present(self, tmp_path):
        inv = build_inventory("myproject", tmp_path, [])
        assert inv["$schema"] == "vibecode/file-inventory/v1"

    def test_project_id(self, tmp_path):
        inv = build_inventory("testproject", tmp_path, [])
        assert inv["project_id"] == "testproject"

    def test_generated_at_is_utc_iso(self, tmp_path):
        inv = build_inventory("proj", tmp_path, [])
        ts = inv["generated_at"]
        # Must be a timezone-aware ISO string containing offset info
        assert "+" in ts or ts.endswith("Z") or "+00:00" in ts

    def test_root_is_posix(self, tmp_path):
        inv = build_inventory("proj", tmp_path, [])
        assert "\\" not in inv["root"]

    def test_files_list_present(self, tmp_path):
        inv = build_inventory("proj", tmp_path, [])
        assert isinstance(inv["files"], list)

    def test_python_file_record_fields(self, tmp_path):
        files = [_make_indexed("vibecode/cli.py", 512)]
        inv = build_inventory("proj", tmp_path, files)
        assert len(inv["files"]) == 1
        rec = inv["files"][0]
        assert rec["path"] == "vibecode/cli.py"
        assert rec["language"] == "python"
        assert rec["size_bytes"] == 512
        assert isinstance(rec["role_guess"], str)
        assert isinstance(rec["is_test"], bool)
        assert isinstance(rec["is_config"], bool)
        assert isinstance(rec["is_doc"], bool)
        assert isinstance(rec["risk_level"], str)

    def test_markdown_file_different_type(self, tmp_path):
        files = [
            _make_indexed("vibecode/cli.py", 512),
            _make_indexed("README.md", 1024),
        ]
        inv = build_inventory("proj", tmp_path, files)
        assert len(inv["files"]) == 2
        py_rec = next(r for r in inv["files"] if r["path"] == "vibecode/cli.py")
        md_rec = next(r for r in inv["files"] if r["path"] == "README.md")
        assert py_rec["language"] == "python"
        assert md_rec["language"] == "markdown"
        assert md_rec["is_doc"] is True
        assert py_rec["is_doc"] is False

    def test_tracked_field_present_when_tracked(self, tmp_path):
        files = [_make_indexed("main.py", 100, FileStatus.TRACKED)]
        inv = build_inventory("proj", tmp_path, files)
        assert inv["files"][0]["tracked"] == "tracked"

    def test_tracked_field_present_when_untracked(self, tmp_path):
        files = [_make_indexed("new.py", 100, FileStatus.UNTRACKED)]
        inv = build_inventory("proj", tmp_path, files)
        assert inv["files"][0]["tracked"] == "untracked"

    def test_tracked_field_absent_when_unknown(self, tmp_path):
        files = [_make_indexed("main.py", 100, FileStatus.UNKNOWN)]
        inv = build_inventory("proj", tmp_path, files)
        assert "tracked" not in inv["files"][0]

    def test_test_file_flagged(self, tmp_path):
        files = [_make_indexed("tests/test_cli.py", 200)]
        inv = build_inventory("proj", tmp_path, files)
        assert inv["files"][0]["is_test"] is True

    def test_config_file_flagged(self, tmp_path):
        files = [_make_indexed("pyproject.toml", 300)]
        inv = build_inventory("proj", tmp_path, files)
        rec = inv["files"][0]
        assert rec["is_config"] is True
        assert rec["language"] == "toml"

    def test_two_files_different_risk(self, tmp_path):
        files = [
            _make_indexed("api/views.py", 400),
            _make_indexed("README.md", 200),
        ]
        inv = build_inventory("proj", tmp_path, files)
        api_rec = next(r for r in inv["files"] if r["path"] == "api/views.py")
        doc_rec = next(r for r in inv["files"] if r["path"] == "README.md")
        assert api_rec["risk_level"] == "high"
        assert doc_rec["risk_level"] == "low"


# ---------------------------------------------------------------------------
# write_inventory
# ---------------------------------------------------------------------------


class TestWriteInventory:
    def test_creates_file(self, tmp_path):
        output = tmp_path / ".vibecode" / "index" / "file_inventory.json"
        files = [_make_indexed("main.py", 50)]
        write_inventory("proj", tmp_path, files, output)
        assert output.exists()

    def test_creates_parent_dirs(self, tmp_path):
        deep = tmp_path / "a" / "b" / "c" / "file_inventory.json"
        write_inventory("proj", tmp_path, [], deep)
        assert deep.exists()

    def test_output_is_valid_json(self, tmp_path):
        output = tmp_path / "file_inventory.json"
        files = [_make_indexed("vibecode/cli.py", 512), _make_indexed("README.md", 256)]
        write_inventory("proj", tmp_path, files, output)
        parsed = json.loads(output.read_text(encoding="utf-8"))
        assert isinstance(parsed, dict)
        assert isinstance(parsed["files"], list)

    def test_json_tool_validates(self, tmp_path):
        """Verify `python -m json.tool` succeeds on the generated file."""
        output = tmp_path / "file_inventory.json"
        files = [_make_indexed("src/app.py", 128), _make_indexed("README.md", 64)]
        write_inventory("myproject", tmp_path, files, output)
        result = subprocess.run(
            [sys.executable, "-m", "json.tool", str(output)],
            capture_output=True,
        )
        assert result.returncode == 0, result.stderr.decode()

    def test_repeated_write_updates_not_appends(self, tmp_path):
        output = tmp_path / "file_inventory.json"
        files_v1 = [_make_indexed("main.py", 10)]
        write_inventory("proj", tmp_path, files_v1, output)
        first_size = output.stat().st_size

        files_v2 = [_make_indexed("main.py", 10), _make_indexed("utils.py", 20)]
        write_inventory("proj", tmp_path, files_v2, output)
        second_size = output.stat().st_size

        parsed = json.loads(output.read_text(encoding="utf-8"))
        assert len(parsed["files"]) == 2
        assert second_size > first_size  # more content, not doubled

    def test_human_maintained_file_untouched(self, tmp_path):
        human_file = tmp_path / ".vibecode" / "architecture" / "INVARIANTS.md"
        human_file.parent.mkdir(parents=True, exist_ok=True)
        human_file.write_text("# Custom invariants\n", encoding="utf-8")
        original_mtime = human_file.stat().st_mtime

        output = tmp_path / ".vibecode" / "index" / "file_inventory.json"
        write_inventory("proj", tmp_path, [], output)

        assert human_file.stat().st_mtime == original_mtime
        assert human_file.read_text(encoding="utf-8") == "# Custom invariants\n"
