"""Project registry for managing known projects by name instead of path.

Stores entries in ``~/.vibecode/projects.yaml`` so users can refer to
projects by name rather than typing the full repository path each time.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

from vibecode.paths import strip_to_posix

# ---------------------------------------------------------------------------
# Public data structures
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _default_projects_path() -> Path:
    """Return the default path for the projects registry file.

    The path is ``~/.vibecode/projects.yaml``.  The ``HOME`` / ``USERPROFILE``
    environment variable is used to locate the home directory so that tests
    can override it.
    """
    home = os.environ.get("HOME") or os.environ.get("USERPROFILE") or str(Path.home())
    return Path(home) / ".vibecode" / "projects.yaml"


# ---------------------------------------------------------------------------
# Registry entries
# ---------------------------------------------------------------------------


class ProjectEntry:
    """A single entry in the project registry."""

    __slots__ = ("name", "path", "project_id", "last_used")

    def __init__(
        self,
        *,
        name: str,
        path: str,
        project_id: str = "",
        last_used: str = "",
    ) -> None:
        self.name = name
        self.path = path
        self.project_id = project_id
        self.last_used = last_used

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "path": self.path,
        }
        if self.project_id:
            d["project_id"] = self.project_id
        if self.last_used:
            d["last_used"] = self.last_used
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectEntry":
        return cls(
            name=str(data.get("name", "")),
            path=str(data.get("path", "")),
            project_id=str(data.get("project_id", "")),
            last_used=str(data.get("last_used", "")),
        )

    def touch(self) -> None:
        """Update the last_used timestamp to now."""
        self.last_used = _now_iso()

    def normalised_path(self) -> Path:
        """Return the path with backslashes converted to forward slashes."""
        return Path(strip_to_posix(self.path))

    def __repr__(self) -> str:
        return (
            f"ProjectEntry(name={self.name!r}, path={self.path!r}, "
            f"project_id={self.project_id!r}, last_used={self.last_used!r})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ProjectEntry):
            return NotImplemented
        return (
            self.name == other.name
            and self.path == other.path
            and self.project_id == other.project_id
            and self.last_used == other.last_used
        )


# ---------------------------------------------------------------------------
# Registry file I/O
# ---------------------------------------------------------------------------


class ProjectRegistry:
    """Read/write registry of known projects backed by a YAML file.

    The default file location is ``~/.vibecode/projects.yaml``.  The
    *home_override* parameter (and the ``VIBECODE_HOME`` environment variable)
    let tests redirect the file to a temporary directory.
    """

    def __init__(self, path: Path | None = None) -> None:
        if path is not None:
            self._path = path
        else:
            override = os.environ.get("VIBECODE_HOME")
            if override:
                self._path = Path(override) / "projects.yaml"
            else:
                self._path = _default_projects_path()

    @property
    def path(self) -> Path:
        return self._path

    # -- CRUD ----------------------------------------------------------------

    def load(self) -> list[ProjectEntry]:
        """Return all entries.  Missing / deleted repos are included as-is."""
        raw = self._raw_load()
        return [ProjectEntry.from_dict(e) for e in raw.get("projects", [])]

    def save(self, entries: list[ProjectEntry]) -> None:
        """Write the full list of entries to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        doc = {"projects": [e.to_dict() for e in entries]}
        self._path.write_text(
            yaml.dump(doc, default_flow_style=False, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

    def add(self, entry: ProjectEntry) -> None:
        """Add or replace an entry with the same name."""
        entries = self.load()
        # Remove any existing entry with the same name.
        filtered = [e for e in entries if e.name != entry.name]
        filtered.append(entry)
        self.save(filtered)

    def remove(self, name: str) -> bool:
        """Remove the entry called *name*.  Returns True if it existed."""
        entries = self.load()
        original_len = len(entries)
        entries = [e for e in entries if e.name != name]
        if len(entries) == original_len:
            return False
        self.save(entries)
        return True

    def get(self, name: str) -> Optional[ProjectEntry]:
        """Look up an entry by name, or ``None``."""
        for entry in self.load():
            if entry.name == name:
                return entry
        return None

    def touch(self, name: str) -> bool:
        """Update the *last_used* timestamp for *name*.  Returns False if missing."""
        entry = self.get(name)
        if entry is None:
            return False
        entry.touch()
        self.add(entry)  # re-save (add replaces by name)
        return True

    def set_active(self, name: str) -> None:
        """Mark *name* as the currently active project."""
        entry = self.get(name)
        if entry is None:
            raise ValueError(f"Unknown project: {name!r}")
        self._set_active_name(name)
        entry.touch()
        self.add(entry)

    # -- Helpers -------------------------------------------------------------

    def list_names(self) -> list[str]:
        """Return all registered project names."""
        return [e.name for e in self.load()]

    def _raw_load(self) -> dict[str, Any]:
        """Load the raw YAML dict; return empty dict if the file is absent."""
        if not self._path.exists():
            return {}
        try:
            return yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            return {}

    def valid_entries(self, entries: list[ProjectEntry] | None = None) -> list[ProjectEntry]:
        """Return entries whose paths still exist on disk ("valid" repos).

        This lets the CLI gracefully skip repos that have been moved or deleted.
        """
        if entries is None:
            entries = self.load()
        return [e for e in entries if e.normalised_path().exists()]

    def pick(self, name: str | None) -> Path:
        """Resolve a project *name* (or *None* for the active one) to a Path.

        Raises ``FileNotFoundError`` when the name is not in the registry or
        when the stored path no longer exists.
        """
        if name is None:
            # Try the "active" project — stored as a tiny sidecar file.
            active = self._active_name()
            if active is None:
                raise FileNotFoundError("No active project; use a project name.")
            name = active
        entry = self.get(name)
        if entry is None:
            raise FileNotFoundError(f"Unknown project: {name!r}")
        resolved = entry.normalised_path()
        if not resolved.exists():
            raise FileNotFoundError(
                f"Project {name!r} path does not exist: {resolved}"
            )
        return resolved

    # -- Active-project sidecar ------------------------------------------------

    def _active_path(self) -> Path:
        return self._path.parent / ".active_project"

    def _active_name(self) -> str | None:
        p = self._active_path()
        if not p.exists():
            return None
        return p.read_text(encoding="utf-8").strip() or None

    def _set_active_name(self, name: str | None) -> None:
        p = self._active_path()
        if name is None:
            if p.exists():
                p.unlink()
            return
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(name, encoding="utf-8")