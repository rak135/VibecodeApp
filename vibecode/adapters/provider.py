"""Agent provider abstraction for the Vibecode TUI Agent Console.

Defines the minimal interface between the TUI and provider backends.
OpenCode is the only real provider; future providers can be added by
implementing :class:`AgentProvider` and registering with the shared
:data:`_registry`.

Usage::

    from vibecode.adapters.provider import get_default_provider, get_provider

    provider = get_default_provider()
    print(provider.display_name)      # "OpenCode"
    print(provider.check_availability())
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Availability result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProviderStatus:
    """Result of a provider availability check."""

    available: bool
    message: str

    def __bool__(self) -> bool:
        return self.available


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------


class AgentProvider(ABC):
    """Abstract interface for agent providers.

    Subclass this to add a new backend. At minimum, implement the five
    abstract members. The remaining properties have sensible defaults.
    """

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name shown in the TUI (e.g. ``"OpenCode"``)."""

    @abstractmethod
    def check_availability(self) -> ProviderStatus:
        """Check whether this provider is available on the current machine."""

    @property
    @abstractmethod
    def context_artifacts(self) -> list[str]:
        """Relative paths of context/prompt artifacts this provider expects."""

    @property
    @abstractmethod
    def supports_internal_run(self) -> bool:
        """True when Vibecode can orchestrate a streaming internal run."""

    @property
    @abstractmethod
    def supports_external_launch(self) -> bool:
        """True when this provider can be launched in an external terminal."""

    def prepared_command_description(self) -> str:
        """Return a one-line description of the command that will be executed."""
        return self.display_name

    @property
    def limitations(self) -> list[str]:
        """Known limitations in the TUI context."""
        return []


# ---------------------------------------------------------------------------
# OpenCode implementation
# ---------------------------------------------------------------------------


class OpenCodeProvider(AgentProvider):
    """Provider implementation for OpenCode."""

    @property
    def display_name(self) -> str:
        return "OpenCode"

    def check_availability(self) -> ProviderStatus:
        from vibecode.adapters.opencode import check_opencode

        status = check_opencode()
        return ProviderStatus(available=status.available, message=status.message)

    @property
    def context_artifacts(self) -> list[str]:
        return [
            ".vibecode/current/context_pack.md",
            ".vibecode/current/opencode_prompt.md",
        ]

    @property
    def supports_internal_run(self) -> bool:
        return True

    @property
    def supports_external_launch(self) -> bool:
        return True

    def prepared_command_description(self) -> str:
        from vibecode.adapters.opencode import resolve_opencode_command

        cmd = resolve_opencode_command()
        return cmd if cmd else "opencode (not found on PATH)"

    @property
    def limitations(self) -> list[str]:
        return [
            "No embedded PTY in TUI — use [E] for interactive sessions"
            " or 'vibecode monitor' for streaming output.",
        ]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class AgentProviderRegistry:
    """Registry of agent providers keyed by a short identifier.

    The default provider is ``'opencode'`` when registered, otherwise
    the first registered provider.
    """

    def __init__(self) -> None:
        self._providers: dict[str, AgentProvider] = {}

    def register(self, key: str, provider: AgentProvider) -> None:
        """Register *provider* under *key*."""
        self._providers[key] = provider

    def get(self, key: str) -> AgentProvider | None:
        """Return the provider for *key*, or ``None`` if not registered."""
        return self._providers.get(key)

    def list_keys(self) -> list[str]:
        """Return a sorted list of registered provider keys."""
        return sorted(self._providers)

    def default(self) -> AgentProvider | None:
        """Return the default provider.

        Prefers the ``'opencode'`` key; falls back to the first
        registered provider; returns ``None`` if the registry is empty.
        """
        if "opencode" in self._providers:
            return self._providers["opencode"]
        if self._providers:
            return next(iter(self._providers.values()))
        return None


# ---------------------------------------------------------------------------
# Shared module-level registry
# ---------------------------------------------------------------------------

_registry = AgentProviderRegistry()
_registry.register("opencode", OpenCodeProvider())


def get_registry() -> AgentProviderRegistry:
    """Return the shared provider registry."""
    return _registry


def get_provider(key: str) -> AgentProvider | None:
    """Return the provider registered under *key*, or ``None``."""
    return _registry.get(key)


def get_default_provider() -> AgentProvider:
    """Return the default provider.

    Raises
    ------
    RuntimeError
        When the registry is empty (should not happen in normal usage).
    """
    provider = _registry.default()
    if provider is None:
        raise RuntimeError("No agent providers are registered.")
    return provider
