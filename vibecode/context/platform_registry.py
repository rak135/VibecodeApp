"""Platform export registry for vibecode context packs.

Each registered exporter is a callable that accepts a repo root
:class:`~pathlib.Path` and the context-pack content string, writes a
platform-specific file, and returns the path that was written.

Adding a new platform
---------------------
Create a module under ``vibecode/context/`` (or elsewhere), implement the
export function, then call :func:`register` — no changes to the core
context builder are needed::

    from vibecode.context.platform_registry import register

    def write_my_platform(repo_root: Path, context_pack_content: str) -> Path:
        ...

    register("my-platform", write_my_platform)

Looking up an exporter
----------------------
::

    exporter = get_exporter("opencode")
    if exporter is not None:
        path = exporter(repo_root, context_pack_content)
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

# (repo_root: Path, context_pack_content: str) -> written_path: Path
PlatformExporter = Callable[[Path, str], Path]

_registry: dict[str, PlatformExporter] = {}


def register(name: str, exporter: PlatformExporter) -> None:
    """Register *exporter* under platform *name*."""
    _registry[name] = exporter


def get_exporter(name: str) -> PlatformExporter | None:
    """Return the exporter for *name*, or ``None`` if not registered."""
    return _registry.get(name)


def list_platforms() -> list[str]:
    """Return a sorted list of registered platform names."""
    return sorted(_registry)


# ---------------------------------------------------------------------------
# Built-in platform registrations
# ---------------------------------------------------------------------------

from vibecode.context.platform_export import write_opencode_prompt  # noqa: E402

register("opencode", write_opencode_prompt)
