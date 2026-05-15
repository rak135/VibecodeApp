"""Repository resolution service for the TUI entrypoint.

Resolves a concrete repository path using the standard priority chain:
  1. Explicit path argument (if provided)
  2. Active project from the project registry
  3. Current working directory
"""

from __future__ import annotations

from pathlib import Path

from vibecode.paths import normalise_root


class RepoResolutionService:
    """Resolve a repository path using the standard priority chain."""

    def resolve(self, explicit_path: str | None = None) -> Path:
        """Return an absolute, resolved repository path.

        Parameters
        ----------
        explicit_path:
            If provided, this path is returned directly (after normalisation).
            Pass ``None`` to use the fallback chain.
        """
        if explicit_path is not None:
            return normalise_root(explicit_path)

        # Try the active project from the registry.
        try:
            from vibecode.registry import ProjectRegistry

            reg = ProjectRegistry()
            resolved = reg.pick(None)
            return normalise_root(str(resolved))
        except FileNotFoundError:
            pass

        # Fall back to the current working directory.
        return normalise_root(".")
