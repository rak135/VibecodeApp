"""Path normalization utilities for cross-platform (Windows/POSIX) compatibility."""

from __future__ import annotations

from pathlib import Path


def normalise_root(raw: str) -> Path:
    """Resolve a raw path string to an absolute :class:`~pathlib.Path`.

    Converts Windows-style backslash separators to forward slashes before
    passing to :class:`~pathlib.Path`, then calls :meth:`~pathlib.Path.resolve`.
    This means ``C:\\path\\to\\repo`` is accepted on Windows without treating
    the drive-letter colon as a special character.

    Parameters
    ----------
    raw:
        A path string, possibly using Windows backslash separators or starting
        with a drive letter (e.g. ``C:\\Users\\foo\\project``).

    Returns
    -------
    Path
        An absolute, resolved :class:`~pathlib.Path`.
    """
    return Path(strip_to_posix(raw)).resolve()


def strip_to_posix(raw: str) -> str:
    """Return *raw* with every backslash replaced by a forward slash.

    This is a pure string operation — no filesystem access, no path resolution.
    Drive-letter colons (``C:``) are left unchanged so that Windows absolute
    paths remain valid after the conversion.

    Use this when normalising path strings from YAML/JSON configuration or
    from user input that may originate on a Windows machine.
    """
    return raw.replace("\\", "/")


def to_posix_str(path: Path) -> str:
    """Return a forward-slash string representation of *path*.

    Wraps :meth:`~pathlib.Path.as_posix` and is safe to embed in JSON values
    and Markdown text on all platforms — no backslashes will appear in the
    output even on Windows.
    """
    return path.as_posix()
