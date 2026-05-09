"""Tests for the project registry (vibecode.registry).

All tests use a temporary ``VIBECODE_HOME`` so they never touch the real
``~/.vibecode`` directory.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from vibecode.registry import (
    ProjectEntry,
    ProjectRegistry,
)


@pytest.fixture
def tmp_registry(tmp_path):
    """Return a ProjectRegistry that stores its file under *tmp_path*."""
    home = tmp_path / "home"
    os.environ["VIBECODE_HOME"] = str(home)
    try:
        yield ProjectRegistry()
    finally:
        os.environ.pop("VIBECODE_HOME", None)


# ---------------------------------------------------------------------------
# ProjectEntry
# ---------------------------------------------------------------------------


class TestProjectEntry:
    def test_basic_construction(self):
        e = ProjectEntry(name="myproj", path="/home/user/myproj")
        assert e.name == "myproj"
        assert e.path == "/home/user/myproj"
        assert e.project_id == ""
        assert e.last_used == ""

    def test_optional_fields(self):
        e = ProjectEntry(
            name="demo",
            path="/opt/demo",
            project_id="abc-123",
            last_used="2025-01-01T00:00:00+00:00",
        )
        assert e.project_id == "abc-123"
        assert e.last_used == "2025-01-01T00:00:00+00:00"

    def test_to_dict_minimal(self):
        e = ProjectEntry(name="x", path="/x")
        d = e.to_dict()
        assert d == {"name": "x", "path": "/x"}

    def test_to_dict_full(self):
        e = ProjectEntry(
            name="x", path="/x", project_id="id1", last_used="2025-01-01T00:00:00+00:00"
        )
        d = e.to_dict()
        assert d["name"] == "x"
        assert d["path"] == "/x"
        assert d["project_id"] == "id1"
        assert d["last_used"] == "2025-01-01T00:00:00+00:00"

    def test_from_dict(self):
        raw = {
            "name": "foo",
            "path": "/repos/foo",
            "project_id": "fid",
            "last_used": "2025-06-01T12:00:00+00:00",
        }
        e = ProjectEntry.from_dict(raw)
        assert e.name == "foo"
        assert e.path == "/repos/foo"
        assert e.project_id == "fid"
        assert e.last_used == "2025-06-01T12:00:00+00:00"

    def test_from_dict_missing_optional(self):
        raw = {"name": "bar", "path": "/repos/bar"}
        e = ProjectEntry.from_dict(raw)
        assert e.project_id == ""
        assert e.last_used == ""

    def test_touch_sets_last_used(self):
        e = ProjectEntry(name="x", path="/x")
        e.touch()
        assert e.last_used != ""
        # Verify it looks like an ISO timestamp.
        assert "T" in e.last_used

    def test_normalised_path(self):
        e = ProjectEntry(name="win", path=r"C:\Users\foo\repo")
        p = e.normalised_path()
        assert p.as_posix().startswith("C:/")
        assert "\\" not in p.as_posix()

    def test_equality(self):
        a = ProjectEntry(name="x", path="/x", project_id="1", last_used="t1")
        b = ProjectEntry(name="x", path="/x", project_id="1", last_used="t1")
        c = ProjectEntry(name="y", path="/x")
        assert a == b
        assert a != c
        assert a != "not-an-entry"

    def test_repr(self):
        e = ProjectEntry(name="x", path="/x")
        r = repr(e)
        assert "ProjectEntry" in r
        assert "x" in r


# ---------------------------------------------------------------------------
# ProjectRegistry — empty / missing file
# ---------------------------------------------------------------------------


class TestEmptyRegistry:
    def test_load_empty(self, tmp_registry):
        assert tmp_registry.load() == []

    def test_get_missing(self, tmp_registry):
        assert tmp_registry.get("nope") is None

    def test_remove_missing(self, tmp_registry):
        assert tmp_registry.remove("nope") is False

    def test_list_names_empty(self, tmp_registry):
        assert tmp_registry.list_names() == []

    def test_valid_entries_empty(self, tmp_registry):
        assert tmp_registry.valid_entries() == []

    def test_pick_no_active_raises(self, tmp_registry):
        with pytest.raises(FileNotFoundError, match="No active project"):
            tmp_registry.pick(None)

    def test_pick_unknown_raises(self, tmp_registry):
        with pytest.raises(FileNotFoundError, match="Unknown project"):
            tmp_registry.pick("ghost")


# ---------------------------------------------------------------------------
# ProjectRegistry — CRUD
# ---------------------------------------------------------------------------


class TestCRUD:
    def test_add_and_get(self, tmp_registry):
        entry = ProjectEntry(name="alpha", path="/repos/alpha")
        tmp_registry.add(entry)
        fetched = tmp_registry.get("alpha")
        assert fetched is not None
        assert fetched.name == "alpha"
        assert fetched.path == "/repos/alpha"

    def test_add_overwrites_same_name(self, tmp_registry):
        a = ProjectEntry(name="proj", path="/old")
        b = ProjectEntry(name="proj", path="/new", project_id="42")
        tmp_registry.add(a)
        tmp_registry.add(b)
        fetched = tmp_registry.get("proj")
        assert fetched is not None
        assert fetched.path == "/new"
        assert fetched.project_id == "42"

    def test_load_returns_all(self, tmp_registry):
        tmp_registry.add(ProjectEntry(name="a", path="/a"))
        tmp_registry.add(ProjectEntry(name="b", path="/b"))
        entries = tmp_registry.load()
        names = {e.name for e in entries}
        assert names == {"a", "b"}

    def test_remove_existing(self, tmp_registry):
        tmp_registry.add(ProjectEntry(name="x", path="/x"))
        assert tmp_registry.remove("x") is True
        assert tmp_registry.get("x") is None

    def test_remove_nonexistent(self, tmp_registry):
        tmp_registry.add(ProjectEntry(name="x", path="/x"))
        assert tmp_registry.remove("y") is False

    def test_list_names(self, tmp_registry):
        tmp_registry.add(ProjectEntry(name="a", path="/a"))
        tmp_registry.add(ProjectEntry(name="b", path="/b"))
        assert sorted(tmp_registry.list_names()) == ["a", "b"]

    def test_touch_updates_timestamp(self, tmp_registry):
        entry = ProjectEntry(name="p", path="/p")
        tmp_registry.add(entry)
        before = tmp_registry.get("p").last_used
        tmp_registry.touch("p")
        after = tmp_registry.get("p").last_used
        assert after != before
        assert "T" in after

    def test_touch_missing_returns_false(self, tmp_registry):
        assert tmp_registry.touch("nope") is False


# ---------------------------------------------------------------------------
# Valid repos / missing paths
# ---------------------------------------------------------------------------


class TestValidEntries:
    def test_only_existing_paths(self, tmp_registry, tmp_path):
        real_dir = tmp_path / "exists"
        real_dir.mkdir()
        fake_dir = tmp_path / "deleted"

        tmp_registry.add(ProjectEntry(name="real", path=str(real_dir)))
        tmp_registry.add(ProjectEntry(name="gone", path=str(fake_dir)))

        valid = tmp_registry.valid_entries()
        names = {e.name for e in valid}
        assert names == {"real"}

    def test_pick_missing_path_raises(self, tmp_registry, tmp_path):
        deleted = tmp_path / "deleted"
        tmp_registry.add(ProjectEntry(name="lost", path=str(deleted)))
        with pytest.raises(FileNotFoundError, match="path does not exist"):
            tmp_registry.pick("lost")


# ---------------------------------------------------------------------------
# Windows path handling
# ---------------------------------------------------------------------------


class TestWindowsPaths:
    def test_backslash_path_stored_and_normalised(self, tmp_registry):
        entry = ProjectEntry(name="win", path=r"C:\Users\dev\repo")
        tmp_registry.add(entry)
        fetched = tmp_registry.get("win")
        assert fetched is not None
        # Normalised path should be a Path with forward slashes.
        p = fetched.normalised_path()
        assert p.as_posix().startswith("C:/")
        assert "\\" not in p.as_posix()

    def test_pick_windows_path_resolves(self, tmp_registry, tmp_path):
        """If a Windows-style path points to an existing location, pick() works."""
        win_path = str(tmp_path).replace("/", "\\")
        entry = ProjectEntry(name="here", path=win_path)
        tmp_registry.add(entry)
        resolved = tmp_registry.pick("here")
        assert resolved.exists()


# ---------------------------------------------------------------------------
# Active project
# ---------------------------------------------------------------------------


class TestActiveProject:
    def test_set_and_pick_active(self, tmp_registry, tmp_path):
        target = tmp_path / "myrepo"
        target.mkdir()
        tmp_registry.add(ProjectEntry(name="myrepo", path=str(target)))
        tmp_registry._set_active_name("myrepo")
        result = tmp_registry.pick(None)
        assert result == target.resolve()

    def test_no_active_file_means_none(self, tmp_registry):
        assert tmp_registry._active_name() is None

    def test_set_active_none_clears(self, tmp_registry, tmp_path):
        target = tmp_path / "repo"
        target.mkdir()
        tmp_registry.add(ProjectEntry(name="repo", path=str(target)))
        tmp_registry._set_active_name("repo")
        assert tmp_registry._active_name() == "repo"
        tmp_registry._set_active_name(None)
        assert tmp_registry._active_name() is None

    def test_pick_unknown_active_raises(self, tmp_registry):
        """If the active file references a non-existent entry, pick raises."""
        tmp_registry._set_active_name("missing")
        with pytest.raises(FileNotFoundError, match="Unknown project"):
            tmp_registry.pick(None)


# ---------------------------------------------------------------------------
# Registry file format / round-trip
# ---------------------------------------------------------------------------


class TestFileFormat:
    def test_saved_yaml_is_valid(self, tmp_registry):
        tmp_registry.add(ProjectEntry(name="a", path="/a", project_id="id-a"))
        tmp_registry.add(ProjectEntry(name="b", path="/b"))
        content = tmp_registry.path.read_text(encoding="utf-8")
        assert "a" in content
        assert "b" in content
        assert "id-a" in content

    def test_round_trip(self, tmp_registry):
        entries = [
            ProjectEntry(name="x", path="/x", project_id="xid", last_used="2025-01-01T00:00:00+00:00"),
            ProjectEntry(name="y", path="/y"),
        ]
        tmp_registry.save(entries)
        reloaded = ProjectRegistry(tmp_registry.path)
        fetched = reloaded.load()
        assert len(fetched) == 2
        # Order is preserved.
        assert fetched[0].name == "x"
        assert fetched[1].name == "y"

    def test_corrupt_yaml_loads_empty(self, tmp_registry):
        """A malformed YAML file should not crash — treat as empty."""
        tmp_registry._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_registry._path.write_text("!!invalid yaml %%\n", encoding="utf-8")
        assert tmp_registry.load() == []

    def test_empty_yaml_file(self, tmp_registry):
        tmp_registry._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_registry._path.write_text("", encoding="utf-8")
        assert tmp_registry.load() == []