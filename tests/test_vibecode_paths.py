"""Tests for the path normalizer utilities (vibecode.paths).

The pure-string helpers (strip_to_posix, to_posix_str) are OS-independent and
can be exercised with Windows-like strings on any CI platform.  normalise_root
tests that only require a relative path use tmp_path and monkeypatch.chdir to
avoid touching real filesystem paths.
"""

from __future__ import annotations

import json
from pathlib import Path

from vibecode.paths import normalise_root, strip_to_posix, to_posix_str


class TestStripToPosix:
    """Pure string normalisation — fully OS-independent."""

    def test_windows_backslashes(self):
        assert strip_to_posix(r"C:\path\to\repo") == "C:/path/to/repo"

    def test_mixed_slashes(self):
        assert strip_to_posix("C:/path\\to/repo") == "C:/path/to/repo"

    def test_already_posix(self):
        assert strip_to_posix("/home/user/repo") == "/home/user/repo"

    def test_relative_posix(self):
        assert strip_to_posix("./src/foo") == "./src/foo"

    def test_drive_colon_preserved(self):
        result = strip_to_posix(r"C:\Users\foo")
        assert result.startswith("C:")

    def test_no_backslash_in_output(self):
        result = strip_to_posix(r"a\b\c\d")
        assert "\\" not in result

    def test_deep_windows_path(self):
        result = strip_to_posix(r"C:\Users\user\projects\my-repo")
        assert result == "C:/Users/user/projects/my-repo"

    def test_empty_string(self):
        assert strip_to_posix("") == ""

    def test_dot(self):
        assert strip_to_posix(".") == "."

    def test_windows_unc_path(self):
        result = strip_to_posix(r"\\server\share\folder")
        assert "\\" not in result
        assert result == "//server/share/folder"

    def test_no_colon_issue_with_drive_letter(self):
        """Drive-letter colon must not be treated as a YAML/path parse error.

        This is a pure normalisation check: the colon survives intact after
        backslash-to-forward-slash conversion.
        """
        raw = r"C:\path\to\example-repo"
        normalised = strip_to_posix(raw)
        assert normalised == "C:/path/to/example-repo"
        assert ":" in normalised  # colon preserved


class TestToPosixStr:
    """to_posix_str must never produce backslashes."""

    def test_no_backslashes(self, tmp_path):
        assert "\\" not in to_posix_str(tmp_path)

    def test_nested_path_no_backslashes(self, tmp_path):
        p = tmp_path / "a" / "b" / "c"
        result = to_posix_str(p)
        assert "\\" not in result
        assert "a/b/c" in result

    def test_json_round_trip(self, tmp_path):
        """to_posix_str output must survive a JSON round-trip without escaping issues."""
        s = to_posix_str(tmp_path)
        encoded = json.dumps({"root": s})
        decoded = json.loads(encoded)
        assert decoded["root"] == s

    def test_is_string(self, tmp_path):
        assert isinstance(to_posix_str(tmp_path), str)

    def test_valid_json_no_escaped_backslash(self, tmp_path):
        """Serialised JSON must not contain '\\\\' (escaped backslash)."""
        s = to_posix_str(tmp_path)
        serialized = json.dumps(s)
        # A forward-slash path produces no backslash escapes in JSON.
        assert "\\\\" not in serialized


class TestNormaliseRoot:
    """normalise_root must resolve to an absolute path."""

    def test_dot_resolves_to_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = normalise_root(".")
        assert result == tmp_path.resolve()

    def test_result_is_absolute(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = normalise_root(".")
        assert result.is_absolute()

    def test_no_backslash_in_posix_output(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = normalise_root(".")
        assert "\\" not in to_posix_str(result)

    def test_backslash_input_normalised(self, tmp_path):
        """Backslashes in the raw string are converted before Path() is called."""
        sub = tmp_path / "sub"
        sub.mkdir()
        # Replace forward slashes with backslashes to simulate Windows input.
        windows_like = str(sub).replace("/", "\\")
        result = normalise_root(windows_like)
        assert result == sub.resolve()

    def test_windows_style_string_normalisation(self):
        """Verify Windows-style string normalisation (pure string check, no resolve)."""
        raw = r"C:\path\to\example-repo"
        normalised = strip_to_posix(raw)
        assert normalised == "C:/path/to/example-repo"
        assert "\\" not in normalised

    def test_returns_path_object(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = normalise_root(".")
        assert isinstance(result, Path)


class TestJsonOutputIntegrity:
    """Validate that path values in JSON outputs contain no broken backslash escaping."""

    def test_root_field_no_backslashes(self, tmp_path):
        record = {"root": to_posix_str(tmp_path)}
        serialized = json.dumps(record)
        assert "\\\\" not in serialized

    def test_relative_file_path_in_json(self, tmp_path):
        rel = tmp_path / "src" / "main.py"
        rel.parent.mkdir(parents=True, exist_ok=True)
        posix = strip_to_posix(str(rel.relative_to(tmp_path)))
        record = {"path": posix}
        serialized = json.dumps(record)
        assert "\\\\" not in serialized

    def test_windows_path_string_survives_json(self):
        """A Windows path normalised by strip_to_posix must encode cleanly in JSON."""
        windows_raw = r"C:\Users\user\projects\my-repo"
        posix = strip_to_posix(windows_raw)
        encoded = json.dumps({"root": posix})
        decoded = json.loads(encoded)
        assert decoded["root"] == "C:/Users/user/projects/my-repo"
        assert "\\" not in decoded["root"]
