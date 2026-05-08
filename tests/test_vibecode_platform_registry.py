"""Tests for the platform export registry."""

from __future__ import annotations

from pathlib import Path

import pytest

from vibecode.context.platform_registry import (
    get_exporter,
    list_platforms,
    register,
)


# ---------------------------------------------------------------------------
# Built-in registrations
# ---------------------------------------------------------------------------


def test_opencode_is_registered():
    assert get_exporter("opencode") is not None


def test_opencode_exporter_is_callable():
    exporter = get_exporter("opencode")
    assert callable(exporter)


def test_list_platforms_includes_opencode():
    assert "opencode" in list_platforms()


def test_list_platforms_is_sorted():
    platforms = list_platforms()
    assert platforms == sorted(platforms)


# ---------------------------------------------------------------------------
# Unknown platform
# ---------------------------------------------------------------------------


def test_get_exporter_unknown_returns_none():
    assert get_exporter("__nonexistent_platform__") is None


# ---------------------------------------------------------------------------
# Custom registration
# ---------------------------------------------------------------------------


def test_register_custom_exporter(tmp_path):
    written: list[Path] = []

    def _custom_exporter(repo_root: Path, content: str) -> Path:
        out = repo_root / "custom_export.md"
        out.write_text(content, encoding="utf-8")
        written.append(out)
        return out

    register("__test_custom__", _custom_exporter)
    try:
        exporter = get_exporter("__test_custom__")
        assert exporter is not None
        assert "__test_custom__" in list_platforms()

        result = exporter(tmp_path, "hello")
        assert written == [tmp_path / "custom_export.md"]
        assert result == tmp_path / "custom_export.md"
    finally:
        # Clean up: remove test registration from the shared registry
        from vibecode.context import platform_registry as _reg

        _reg._registry.pop("__test_custom__", None)


def test_register_overrides_existing():
    original = get_exporter("opencode")

    def _override(repo_root: Path, content: str) -> Path:
        return repo_root / "override.md"

    register("opencode", _override)
    assert get_exporter("opencode") is _override

    # Restore
    register("opencode", original)
    assert get_exporter("opencode") is original


# ---------------------------------------------------------------------------
# Integration: opencode exporter writes the prompt file
# ---------------------------------------------------------------------------


def test_opencode_exporter_writes_file(tmp_path):
    exporter = get_exporter("opencode")
    out = exporter(tmp_path, "# Context Pack\n\nsome content\n")
    assert out.exists()
    assert "some content" in out.read_text(encoding="utf-8")
