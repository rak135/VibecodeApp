"""Tests for the agent provider abstraction.

Coverage:
- AgentProviderRegistry returns OpenCode by default.
- Provider availability can be tested/faked (dependency injection).
- TUI rendering functions accept and use provider_name.
- Context/run/external launch render functions use provider interface.
- Missing or unavailable provider reports clear status.
- VibecodeMainApp accepts a custom provider (DI).
- Existing OpenCode adapter behaviour is unaffected.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from vibecode.adapters.provider import (
    AgentProvider,
    AgentProviderRegistry,
    OpenCodeProvider,
    ProviderStatus,
    get_default_provider,
    get_provider,
    get_registry,
)


# ---------------------------------------------------------------------------
# ProviderStatus
# ---------------------------------------------------------------------------


class TestProviderStatus:
    def test_available_true_is_truthy(self):
        s = ProviderStatus(available=True, message="ok")
        assert bool(s) is True

    def test_available_false_is_falsy(self):
        s = ProviderStatus(available=False, message="missing")
        assert bool(s) is False

    def test_frozen(self):
        s = ProviderStatus(available=True, message="ok")
        with pytest.raises(Exception):
            s.available = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# AgentProviderRegistry
# ---------------------------------------------------------------------------


class TestAgentProviderRegistry:
    def test_opencode_registered_by_default(self):
        registry = get_registry()
        assert registry.get("opencode") is not None

    def test_opencode_is_opencode_provider(self):
        registry = get_registry()
        assert isinstance(registry.get("opencode"), OpenCodeProvider)

    def test_list_keys_includes_opencode(self):
        registry = get_registry()
        assert "opencode" in registry.list_keys()

    def test_list_keys_is_sorted(self):
        registry = get_registry()
        keys = registry.list_keys()
        assert keys == sorted(keys)

    def test_get_unknown_key_returns_none(self):
        registry = get_registry()
        assert registry.get("__nonexistent__") is None

    def test_register_and_retrieve(self):
        registry = AgentProviderRegistry()

        class _FakeProvider(AgentProvider):
            @property
            def display_name(self) -> str:
                return "Fake"

            def check_availability(self) -> ProviderStatus:
                return ProviderStatus(available=True, message="fake ok")

            @property
            def context_artifacts(self) -> list[str]:
                return []

            @property
            def supports_internal_run(self) -> bool:
                return False

            @property
            def supports_external_launch(self) -> bool:
                return False

        fake = _FakeProvider()
        registry.register("fake", fake)
        assert registry.get("fake") is fake

    def test_default_returns_opencode(self):
        registry = get_registry()
        assert isinstance(registry.default(), OpenCodeProvider)

    def test_default_returns_none_on_empty_registry(self):
        registry = AgentProviderRegistry()
        assert registry.default() is None

    def test_default_fallback_to_first_when_no_opencode(self):
        registry = AgentProviderRegistry()

        class _DummyProvider(AgentProvider):
            @property
            def display_name(self) -> str:
                return "Dummy"

            def check_availability(self) -> ProviderStatus:
                return ProviderStatus(available=True, message="dummy ok")

            @property
            def context_artifacts(self) -> list[str]:
                return []

            @property
            def supports_internal_run(self) -> bool:
                return False

            @property
            def supports_external_launch(self) -> bool:
                return False

        dummy = _DummyProvider()
        registry.register("zzz", dummy)
        assert registry.default() is dummy


# ---------------------------------------------------------------------------
# get_provider / get_default_provider convenience functions
# ---------------------------------------------------------------------------


class TestConvenienceFunctions:
    def test_get_provider_opencode(self):
        assert isinstance(get_provider("opencode"), OpenCodeProvider)

    def test_get_provider_missing_returns_none(self):
        assert get_provider("__missing__") is None

    def test_get_default_provider_returns_opencode(self):
        provider = get_default_provider()
        assert isinstance(provider, OpenCodeProvider)

    def test_get_default_provider_raises_when_empty(self):
        from vibecode.adapters import provider as _mod

        original_registry = _mod._registry
        empty_registry = AgentProviderRegistry()
        _mod._registry = empty_registry
        try:
            with pytest.raises(RuntimeError, match="No agent providers"):
                get_default_provider()
        finally:
            _mod._registry = original_registry


# ---------------------------------------------------------------------------
# OpenCodeProvider
# ---------------------------------------------------------------------------


class TestOpenCodeProvider:
    def test_display_name(self):
        p = OpenCodeProvider()
        assert p.display_name == "OpenCode"

    def test_context_artifacts_non_empty(self):
        p = OpenCodeProvider()
        assert len(p.context_artifacts) >= 1

    def test_supports_internal_run(self):
        p = OpenCodeProvider()
        assert p.supports_internal_run is True

    def test_supports_external_launch(self):
        p = OpenCodeProvider()
        assert p.supports_external_launch is True

    def test_limitations_non_empty(self):
        p = OpenCodeProvider()
        assert len(p.limitations) >= 1

    def test_check_availability_when_opencode_found(self):
        p = OpenCodeProvider()
        with (
            patch("vibecode.adapters.opencode.shutil.which", return_value="/usr/bin/opencode"),
            patch(
                "vibecode.adapters.opencode.subprocess.run",
                return_value=type("R", (), {"returncode": 0, "stdout": "v1.0\n", "stderr": ""})(),
            ),
        ):
            status = p.check_availability()
        assert status.available is True
        assert "v1.0" in status.message

    def test_check_availability_when_opencode_missing(self):
        p = OpenCodeProvider()
        with patch("vibecode.adapters.opencode.shutil.which", return_value=None):
            status = p.check_availability()
        assert status.available is False
        assert status.message

    def test_prepared_command_description_with_binary(self):
        p = OpenCodeProvider()
        with patch("vibecode.adapters.opencode.shutil.which", return_value="/usr/bin/opencode"):
            desc = p.prepared_command_description()
        assert desc  # non-empty

    def test_prepared_command_description_fallback_when_missing(self):
        p = OpenCodeProvider()
        with patch("vibecode.adapters.opencode.shutil.which", return_value=None):
            desc = p.prepared_command_description()
        assert "not found" in desc.lower() or "opencode" in desc.lower()


# ---------------------------------------------------------------------------
# Rendering functions honour provider_name
# ---------------------------------------------------------------------------


class TestRenderFunctionsWithProvider:
    def test_render_center_run_status_uses_provider_name(self):
        from vibecode.main_app import render_center_run_status

        text = render_center_run_status("task", "safe", "running...", provider_name="TestBot")
        assert "TestBot" in text
        assert "Provider: TestBot" in text

    def test_render_center_run_status_default_is_opencode(self):
        from vibecode.main_app import render_center_run_status

        text = render_center_run_status("task", "safe", "running...")
        assert "OpenCode" in text

    def test_render_center_context_status_uses_provider_name(self):
        from vibecode.main_app import render_center_context_status

        text = render_center_context_status("task", "/pack.md", "/prompt.md", provider_name="TestBot")
        assert "TestBot" in text
        assert "Provider: TestBot" in text

    def test_render_center_context_status_default_is_opencode(self):
        from vibecode.main_app import render_center_context_status

        text = render_center_context_status("task", "/pack.md", "/prompt.md")
        assert "OpenCode" in text

    def test_render_center_external_launch_status_uses_provider_name(self):
        from vibecode.main_app import render_center_external_launch_status

        result = {
            "launched": True,
            "terminal_kind": "windows-terminal",
            "pid": 1234,
            "task": "task",
            "profile": "safe",
            "prompt_path": "/path/prompt.md",
            "error_message": None,
        }
        text = render_center_external_launch_status(result, provider_name="TestBot")
        assert "TestBot" in text
        assert "Provider: TestBot" in text

    def test_render_center_external_launch_status_default_is_opencode(self):
        from vibecode.main_app import render_center_external_launch_status

        result = {
            "launched": True,
            "terminal_kind": "windows-terminal",
            "pid": 1234,
            "task": "task",
            "profile": "safe",
            "prompt_path": "/path/prompt.md",
            "error_message": None,
        }
        text = render_center_external_launch_status(result)
        assert "OpenCode" in text


# ---------------------------------------------------------------------------
# _make_center_placeholder
# ---------------------------------------------------------------------------


class TestMakeCenterPlaceholder:
    def test_uses_provider_name(self):
        from vibecode.main_app import _make_center_placeholder

        text = _make_center_placeholder("MyAgent")
        assert "MyAgent" in text

    def test_opencode_placeholder_mentions_opencode(self):
        from vibecode.main_app import _make_center_placeholder

        text = _make_center_placeholder("OpenCode")
        assert "OpenCode" in text

    def test_module_constant_uses_opencode(self):
        from vibecode.main_app import _CENTER_PLACEHOLDER

        assert "OpenCode" in _CENTER_PLACEHOLDER

    def test_module_constant_mentions_phase_1(self):
        from vibecode.main_app import _CENTER_PLACEHOLDER

        assert "Phase 1" in _CENTER_PLACEHOLDER


# ---------------------------------------------------------------------------
# VibecodeMainApp accepts a custom provider
# ---------------------------------------------------------------------------


class _StubProvider(AgentProvider):
    """Minimal stub provider for TUI injection tests."""

    @property
    def display_name(self) -> str:
        return "StubProvider"

    def check_availability(self) -> ProviderStatus:
        return ProviderStatus(available=True, message="stub ok")

    @property
    def context_artifacts(self) -> list[str]:
        return [".vibecode/current/context_pack.md"]

    @property
    def supports_internal_run(self) -> bool:
        return False

    @property
    def supports_external_launch(self) -> bool:
        return False


class TestVibecodeMainAppProvider:
    def test_app_accepts_custom_provider(self, tmp_path):
        from vibecode.main_app import VibecodeMainApp
        from vibecode.repo_status import RepoStatus

        status = RepoStatus(repo_path=tmp_path)
        stub = _StubProvider()
        app = VibecodeMainApp(repo_path=tmp_path, status=status, provider=stub)
        assert app._provider is stub  # type: ignore[attr-defined]

    def test_app_defaults_to_opencode_provider(self, tmp_path):
        from vibecode.main_app import VibecodeMainApp
        from vibecode.repo_status import RepoStatus

        status = RepoStatus(repo_path=tmp_path)
        app = VibecodeMainApp(repo_path=tmp_path, status=status)
        assert isinstance(app._provider, OpenCodeProvider)  # type: ignore[attr-defined]

    def test_app_uses_provider_display_name(self, tmp_path):
        from vibecode.main_app import VibecodeMainApp
        from vibecode.repo_status import RepoStatus

        status = RepoStatus(repo_path=tmp_path)
        stub = _StubProvider()
        app = VibecodeMainApp(repo_path=tmp_path, status=status, provider=stub)
        assert app._provider.display_name == "StubProvider"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Unavailable provider reports clear status
# ---------------------------------------------------------------------------


class TestUnavailableProvider:
    def test_unavailable_status_message_is_non_empty(self):
        p = OpenCodeProvider()
        with patch("vibecode.adapters.opencode.shutil.which", return_value=None):
            status = p.check_availability()
        assert not status.available
        assert len(status.message) > 10

    def test_unavailable_status_is_falsy(self):
        p = OpenCodeProvider()
        with patch("vibecode.adapters.opencode.shutil.which", return_value=None):
            status = p.check_availability()
        assert not status
