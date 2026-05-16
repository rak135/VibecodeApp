"""Tests for VibecodeMainApp — Phase 1 three-column TUI.

Coverage:
- Pure rendering helpers: render_status_lines, render_left_panel
- _ACTIONS_TEXT contains all required action keys
- _CENTER_PLACEHOLDER mentions OpenCode, Phase 1, and no LLM
- VibecodeMainApp can be constructed without running the event loop
- VibecodeMainApp accepts a custom refresh_service (dependency injection)
- _get_refresh_service creates a default VibecodeRefreshService when none injected
- cmd_tui does not call OpenCode or any LLM on startup
- cmd_tui returns 1 when Textual is unavailable
- Existing CLI entrypoint routing is unaffected
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vibecode.main_app import (
    _ACTIONS_TEXT,
    _CENTER_PLACEHOLDER,
    render_left_panel,
    render_status_lines,
)
from vibecode.repo_status import RepoStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_status(tmp_path: Path, **kwargs) -> RepoStatus:
    defaults: dict = dict(repo_path=tmp_path)
    defaults.update(kwargs)
    return RepoStatus(**defaults)


# ---------------------------------------------------------------------------
# render_status_lines — pure function
# ---------------------------------------------------------------------------


class TestRenderStatusLines:
    def test_vibecode_exists_yes(self, tmp_path):
        status = _make_status(tmp_path, vibecode_dir_exists=True)
        lines = render_status_lines(tmp_path, status, checks_str="not run")
        assert any(".vibecode exists: yes" in l for l in lines)

    def test_vibecode_exists_no(self, tmp_path):
        status = _make_status(tmp_path, vibecode_dir_exists=False)
        lines = render_status_lines(tmp_path, status, checks_str="not run")
        assert any(".vibecode exists: no" in l for l in lines)

    def test_manual_files_ok_when_all_present(self, tmp_path):
        truth = {
            ".vibecode/project.yaml": True,
            ".vibecode/architecture/OVERVIEW.md": True,
        }
        status = _make_status(tmp_path, manual_truth=truth)
        lines = render_status_lines(tmp_path, status, checks_str="not run")
        assert any("manual files: ok" in l for l in lines)

    def test_manual_files_warn_when_partial(self, tmp_path):
        truth = {
            ".vibecode/project.yaml": True,
            ".vibecode/architecture/OVERVIEW.md": False,
        }
        status = _make_status(tmp_path, manual_truth=truth)
        lines = render_status_lines(tmp_path, status, checks_str="not run")
        assert any("manual files: warn" in l for l in lines)

    def test_manual_files_missing_when_none_present(self, tmp_path):
        truth = {
            ".vibecode/project.yaml": False,
            ".vibecode/architecture/OVERVIEW.md": False,
        }
        status = _make_status(tmp_path, manual_truth=truth)
        lines = render_status_lines(tmp_path, status, checks_str="not run")
        assert any("manual files: missing" in l for l in lines)

    def test_manual_files_missing_when_empty_dict(self, tmp_path):
        status = _make_status(tmp_path, manual_truth={})
        lines = render_status_lines(tmp_path, status, checks_str="not run")
        assert any("manual files: missing" in l for l in lines)

    def test_index_freshness_fresh(self, tmp_path):
        status = _make_status(tmp_path, index_freshness="fresh")
        lines = render_status_lines(tmp_path, status, checks_str="not run")
        assert any("generated index: fresh" in l for l in lines)

    def test_index_freshness_stale(self, tmp_path):
        status = _make_status(tmp_path, index_freshness="stale")
        lines = render_status_lines(tmp_path, status, checks_str="not run")
        assert any("generated index: stale" in l for l in lines)

    def test_index_freshness_missing(self, tmp_path):
        status = _make_status(tmp_path, index_freshness="missing")
        lines = render_status_lines(tmp_path, status, checks_str="not run")
        assert any("generated index: missing" in l for l in lines)

    def test_context_ready(self, tmp_path):
        status = _make_status(tmp_path, context_pack_exists=True)
        lines = render_status_lines(tmp_path, status, checks_str="not run")
        assert any("current context: ready" in l for l in lines)

    def test_context_missing(self, tmp_path):
        status = _make_status(tmp_path, context_pack_exists=False)
        lines = render_status_lines(tmp_path, status, checks_str="not run")
        assert any("current context: missing" in l for l in lines)

    def test_checks_not_run_when_no_results(self, tmp_path):
        status = _make_status(tmp_path, check_results_exist=False)
        lines = render_status_lines(tmp_path, status, checks_str="not run")
        assert any("checks: not run" in l for l in lines)

    def test_checks_injected_pass(self, tmp_path):
        status = _make_status(tmp_path, check_results_exist=True)
        lines = render_status_lines(tmp_path, status, checks_str="pass")
        assert any("checks: pass" in l for l in lines)

    def test_checks_injected_fail(self, tmp_path):
        status = _make_status(tmp_path, check_results_exist=True)
        lines = render_status_lines(tmp_path, status, checks_str="fail")
        assert any("checks: fail" in l for l in lines)

    def test_git_state_clean(self, tmp_path):
        status = _make_status(tmp_path, git_state="clean")
        lines = render_status_lines(tmp_path, status, checks_str="not run")
        assert any("git state: clean" in l for l in lines)

    def test_git_state_dirty(self, tmp_path):
        status = _make_status(tmp_path, git_state="dirty")
        lines = render_status_lines(tmp_path, status, checks_str="not run")
        assert any("git state: dirty" in l for l in lines)

    def test_git_state_unknown(self, tmp_path):
        status = _make_status(tmp_path, git_state="unknown")
        lines = render_status_lines(tmp_path, status, checks_str="not run")
        assert any("git state: unknown" in l for l in lines)

    def test_returns_six_lines(self, tmp_path):
        status = _make_status(tmp_path)
        lines = render_status_lines(tmp_path, status, checks_str="not run")
        assert len(lines) == 6

    def test_check_results_not_run_when_file_absent(self, tmp_path):
        """When check_results_exist is False, auto-computed checks_str is 'not run'."""
        status = _make_status(tmp_path, check_results_exist=False)
        lines = render_status_lines(tmp_path, status)
        assert any("checks: not run" in l for l in lines)


# ---------------------------------------------------------------------------
# render_left_panel — pure function
# ---------------------------------------------------------------------------


class TestRenderLeftPanel:
    def test_contains_vibecodeapp_title(self, tmp_path):
        status = _make_status(tmp_path)
        text = render_left_panel(tmp_path, status, checks_str="not run")
        assert "VibecodeApp" in text

    def test_contains_active_repo_path(self, tmp_path):
        status = _make_status(tmp_path)
        text = render_left_panel(tmp_path, status, checks_str="not run")
        assert str(tmp_path) in text

    def test_contains_active_repo_label(self, tmp_path):
        status = _make_status(tmp_path)
        text = render_left_panel(tmp_path, status, checks_str="not run")
        assert "Active repo:" in text

    def test_contains_status_section(self, tmp_path):
        status = _make_status(tmp_path)
        text = render_left_panel(tmp_path, status, checks_str="not run")
        assert "Status:" in text

    def test_contains_actions_section(self, tmp_path):
        status = _make_status(tmp_path)
        text = render_left_panel(tmp_path, status, checks_str="not run")
        assert "Actions:" in text

    @pytest.mark.parametrize(
        "key",
        ["[R]", "[I]", "[C]", "[A]", "[S]", "[G]", "[T]", "[H]", "[Q]"],
    )
    def test_contains_all_action_keys(self, tmp_path, key):
        status = _make_status(tmp_path)
        text = render_left_panel(tmp_path, status, checks_str="not run")
        assert key in text, f"Action key {key!r} missing from left panel"

    def test_status_lines_embedded_in_output(self, tmp_path):
        status = _make_status(tmp_path, vibecode_dir_exists=True, git_state="clean")
        text = render_left_panel(tmp_path, status, checks_str="not run")
        assert ".vibecode exists: yes" in text
        assert "git state: clean" in text


# ---------------------------------------------------------------------------
# _ACTIONS_TEXT constant
# ---------------------------------------------------------------------------


class TestActionsText:
    @pytest.mark.parametrize(
        "key",
        ["[R]", "[I]", "[C]", "[A]", "[S]", "[G]", "[T]", "[H]", "[Q]"],
    )
    def test_all_action_keys_present(self, key):
        assert key in _ACTIONS_TEXT

    def test_refresh_label(self):
        assert "Refresh" in _ACTIONS_TEXT

    def test_inspect_label(self):
        assert "Inspect" in _ACTIONS_TEXT

    def test_quit_label(self):
        assert "Quit" in _ACTIONS_TEXT

    def test_context_label(self):
        assert "context" in _ACTIONS_TEXT.lower() or "Context" in _ACTIONS_TEXT

    def test_guard_label(self):
        assert "Guard" in _ACTIONS_TEXT or "guard" in _ACTIONS_TEXT.lower()

    def test_handoff_label(self):
        assert "Handoff" in _ACTIONS_TEXT or "handoff" in _ACTIONS_TEXT.lower()


# ---------------------------------------------------------------------------
# _CENTER_PLACEHOLDER constant
# ---------------------------------------------------------------------------


class TestCenterPlaceholder:
    def test_mentions_opencode(self):
        assert "OpenCode" in _CENTER_PLACEHOLDER

    def test_mentions_phase_1(self):
        assert "Phase 1" in _CENTER_PLACEHOLDER

    def test_not_a_terminal_disclaimer(self):
        text_lower = _CENTER_PLACEHOLDER.lower()
        assert "not" in text_lower and "implemented" in text_lower

    def test_no_llm_reference(self):
        text_lower = _CENTER_PLACEHOLDER.lower()
        assert "llm" not in text_lower
        assert "gpt" not in text_lower
        assert "claude" not in text_lower
        assert "openai" not in text_lower

    def test_does_not_pretend_to_be_terminal(self):
        assert "interactive terminal" in _CENTER_PLACEHOLDER.lower() or "pty" not in _CENTER_PLACEHOLDER.lower()


# ---------------------------------------------------------------------------
# TUI instantiation
# ---------------------------------------------------------------------------


class TestTuiInstantiation:
    def test_app_can_be_constructed_without_running(self, tmp_path):
        """VibecodeMainApp can be constructed without launching the event loop."""
        from vibecode.main_app import VibecodeMainApp

        status = RepoStatus(repo_path=tmp_path)
        app = VibecodeMainApp(repo_path=tmp_path, status=status)
        assert app is not None

    def test_app_stores_repo_path(self, tmp_path):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")
        status = RepoStatus(repo_path=tmp_path)
        app = VibecodeMainApp(repo_path=tmp_path, status=status)
        assert app._repo_path == tmp_path

    def test_app_stores_status(self, tmp_path):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")
        status = RepoStatus(repo_path=tmp_path)
        app = VibecodeMainApp(repo_path=tmp_path, status=status)
        assert app._status is status

    def test_app_accepts_custom_refresh_service(self, tmp_path):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")

        class FakeRefreshService:
            pass

        fake = FakeRefreshService()
        status = RepoStatus(repo_path=tmp_path)
        app = VibecodeMainApp(repo_path=tmp_path, status=status, refresh_service=fake)
        assert app._refresh_service is fake

    def test_refresh_service_none_by_default(self, tmp_path):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")
        status = RepoStatus(repo_path=tmp_path)
        app = VibecodeMainApp(repo_path=tmp_path, status=status)
        assert app._refresh_service is None


# ---------------------------------------------------------------------------
# _get_refresh_service — lazy default creation
# ---------------------------------------------------------------------------


class TestGetRefreshService:
    def test_creates_default_when_none(self, tmp_path):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp
        from vibecode.refresh import VibecodeRefreshService

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")
        status = RepoStatus(repo_path=tmp_path)
        app = VibecodeMainApp(repo_path=tmp_path, status=status)
        svc = app._get_refresh_service()
        assert isinstance(svc, VibecodeRefreshService)

    def test_returns_injected_service_unchanged(self, tmp_path):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")

        class FakeService:
            def refresh(self):
                pass

        fake = FakeService()
        status = RepoStatus(repo_path=tmp_path)
        app = VibecodeMainApp(repo_path=tmp_path, status=status, refresh_service=fake)
        assert app._get_refresh_service() is fake

    def test_same_instance_returned_on_repeated_calls(self, tmp_path):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")
        status = RepoStatus(repo_path=tmp_path)
        app = VibecodeMainApp(repo_path=tmp_path, status=status)
        svc1 = app._get_refresh_service()
        svc2 = app._get_refresh_service()
        assert svc1 is svc2


# ---------------------------------------------------------------------------
# Refresh service wiring
# ---------------------------------------------------------------------------


class TestRefreshServiceWiring:
    def test_injected_service_is_callable(self, tmp_path):
        """The injected refresh_service must expose a callable refresh() method."""
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp
        from vibecode.refresh import RefreshReport

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")

        calls = []

        class FakeRefreshService:
            def refresh(self):
                calls.append(1)
                return RefreshReport(repo_path=str(tmp_path), vibecode_existed=False)

        fake = FakeRefreshService()
        status = RepoStatus(repo_path=tmp_path)
        app = VibecodeMainApp(repo_path=tmp_path, status=status, refresh_service=fake)

        # Directly invoke the service to confirm it is the fake
        svc = app._get_refresh_service()
        report = svc.refresh()
        assert calls == [1]
        assert report.validation_status == "skipped"

    def test_default_service_type_is_vibecode_refresh(self, tmp_path):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp
        from vibecode.refresh import VibecodeRefreshService

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")
        status = RepoStatus(repo_path=tmp_path)
        app = VibecodeMainApp(repo_path=tmp_path, status=status)
        svc = app._get_refresh_service()
        assert isinstance(svc, VibecodeRefreshService)


# ---------------------------------------------------------------------------
# cmd_tui — no LLM / no OpenCode on startup
# ---------------------------------------------------------------------------


class TestCmdTuiNoOpenCodeOnStartup:
    def test_cmd_tui_runs_fake_app_not_opencode(self, tmp_path, monkeypatch):
        """cmd_tui must not invoke OpenCode or any LLM; only the TUI app runs."""
        import vibecode.main_app as ma

        monkeypatch.setattr(ma, "_TEXTUAL_AVAILABLE", True)

        run_called = []

        class FakeApp:
            def __init__(self, **kwargs):
                pass

            def run(self):
                run_called.append(True)

        monkeypatch.setattr(ma, "VibecodeMainApp", FakeApp)

        class FakeArgs:
            repo = str(tmp_path)

        rc = ma.cmd_tui(FakeArgs())
        assert rc == 0
        assert run_called == [True]

    def test_cmd_tui_no_opencode_import_on_startup(self, tmp_path, monkeypatch):
        """cmd_tui must not import opencode or call any external agent."""
        import vibecode.main_app as ma

        monkeypatch.setattr(ma, "_TEXTUAL_AVAILABLE", True)

        opencode_imported = []

        real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __import__

        def guarded_import(name, *args, **kwargs):
            if "opencode" in name.lower():
                opencode_imported.append(name)
            return real_import(name, *args, **kwargs)

        import builtins

        monkeypatch.setattr(builtins, "__import__", guarded_import)

        class FakeApp:
            def __init__(self, **kwargs):
                pass

            def run(self):
                pass

        monkeypatch.setattr(ma, "VibecodeMainApp", FakeApp)

        class FakeArgs:
            repo = str(tmp_path)

        ma.cmd_tui(FakeArgs())
        assert opencode_imported == [], f"OpenCode was imported: {opencode_imported}"

    def test_cmd_tui_returns_one_when_textual_unavailable(self, tmp_path, capsys):
        import vibecode.main_app as ma

        original = ma._TEXTUAL_AVAILABLE
        try:
            ma._TEXTUAL_AVAILABLE = False

            class FakeArgs:
                repo = str(tmp_path)

            rc = ma.cmd_tui(FakeArgs())
        finally:
            ma._TEXTUAL_AVAILABLE = original

        assert rc == 1
        err = capsys.readouterr().err
        assert "textual" in err.lower()

    def test_cmd_tui_prints_pip_install_hint(self, tmp_path, capsys):
        import vibecode.main_app as ma

        original = ma._TEXTUAL_AVAILABLE
        try:
            ma._TEXTUAL_AVAILABLE = False

            class FakeArgs:
                repo = str(tmp_path)

            ma.cmd_tui(FakeArgs())
        finally:
            ma._TEXTUAL_AVAILABLE = original

        err = capsys.readouterr().err
        assert "pip install" in err


# ---------------------------------------------------------------------------
# Existing CLI routing is unaffected
# ---------------------------------------------------------------------------


class TestExistingCliRoutingUnaffected:
    def test_no_args_still_dispatches_to_cmd_tui(self, monkeypatch):
        import vibecode.main_app as ma
        from vibecode.cli import main

        called = []
        monkeypatch.setattr(ma, "cmd_tui", lambda args: called.append(args) or 0)
        rc = main([])
        assert rc == 0
        assert len(called) == 1

    def test_tui_subcommand_still_dispatches_to_cmd_tui(self, monkeypatch):
        import vibecode.main_app as ma
        from vibecode.cli import main

        called = []
        monkeypatch.setattr(ma, "cmd_tui", lambda args: called.append(args) or 0)
        rc = main(["tui"])
        assert rc == 0
        assert len(called) == 1

    def test_init_help_still_exits_zero(self):
        from vibecode.cli import main

        with pytest.raises(SystemExit) as exc_info:
            main(["init", "--help"])
        assert exc_info.value.code == 0

    def test_index_help_still_exits_zero(self):
        from vibecode.cli import main

        with pytest.raises(SystemExit) as exc_info:
            main(["index", "--help"])
        assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# Refresh action / key-binding / widget-tree coverage (P21.2)
# ---------------------------------------------------------------------------


class TestActionRefreshRepo:
    """Test the _on_refresh_done callback directly — the key path for logging."""

    def test_on_refresh_done_logs_artifact_paths(self, tmp_path):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp
        from vibecode.repo_status import RepoStatus

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")

        report = type(
            "FakeReport",
            (),
            dict(
                generated_artifacts=[
                    ".vibecode/index/file_inventory.json",
                    ".vibecode/index/symbol_map.json",
                ],
                validation_status="ok",
                warnings=[],
                errors=[],
                next_recommended_action="Ready.",
            ),
        )

        log_messages: list[str] = []

        class _FakeEventLog:
            def write(self, msg):
                log_messages.append(msg)

        status = RepoStatus(repo_path=tmp_path)
        app = VibecodeMainApp(repo_path=tmp_path, status=status)

        # Patch query_one and _log_event on the app
        original_log_event = app._log_event
        try:
            app.query_one = lambda selector, *_: _FakeEventLog()
            app._on_refresh_done(report)
        finally:
            app._log_event = original_log_event

        has_count = any("artifacts: 2 written" in m for m in log_messages)
        has_path_1 = any("file_inventory.json" in m for m in log_messages)
        has_path_2 = any("symbol_map.json" in m for m in log_messages)
        assert has_count, f"Expected artifact count log, got: {log_messages}"
        assert has_path_1, f"Expected artifact path file_inventory.json in log, got: {log_messages}"
        assert has_path_2, f"Expected artifact path symbol_map.json in log, got: {log_messages}"

    def test_on_refresh_done_logs_completion_status(self, tmp_path):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp
        from vibecode.repo_status import RepoStatus

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")

        report = type(
            "FakeReport",
            (),
            dict(
                generated_artifacts=[],
                validation_status="ok",
                warnings=[],
                errors=[],
                next_recommended_action="Ready.",
            ),
        )

        log_messages: list[str] = []

        class _FakeEventLog:
            def write(self, msg):
                log_messages.append(msg)

        status = RepoStatus(repo_path=tmp_path)
        app = VibecodeMainApp(repo_path=tmp_path, status=status)
        app.query_one = lambda selector, *_: _FakeEventLog()
        app._on_refresh_done(report)

        assert any("Refresh complete" in m for m in log_messages)

    def test_on_refresh_error_logs_failure(self, tmp_path):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp
        from vibecode.repo_status import RepoStatus

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")

        log_messages: list[str] = []

        class _FakeEventLog:
            def write(self, msg):
                log_messages.append(msg)

        status = RepoStatus(repo_path=tmp_path)
        app = VibecodeMainApp(repo_path=tmp_path, status=status)
        app.query_one = lambda selector, *_: _FakeEventLog()
        app._on_refresh_error("disk full")

        assert any("Refresh failed" in m for m in log_messages)
        assert any("disk full" in m for m in log_messages)


class TestRefreshBindingsTable:
    def test_bindings_include_r_mapping(self):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")

        bindings = getattr(VibecodeMainApp, "BINDINGS", [])
        refresh_binding = None
        for b in bindings:
            if hasattr(b, "key") and b.key == "r":
                refresh_binding = b
                break
        assert refresh_binding is not None, "No binding for key 'r' found"
        assert refresh_binding.action == "refresh_repo", (
            f"Expected 'refresh_repo' action, got {refresh_binding.action!r}"
        )

    def test_bindings_count_matches_actions_text(self):
        from vibecode.main_app import _ACTIONS_TEXT, _TEXTUAL_AVAILABLE, VibecodeMainApp

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")

        bindings = getattr(VibecodeMainApp, "BINDINGS", [])
        action_keys_in_text = [
            k for k in ["[R]", "[I]", "[C]", "[A]", "[S]", "[G]", "[T]", "[H]", "[Q]"]
            if k in _ACTIONS_TEXT
        ]
        binding_keys = [getattr(b, "key", None) for b in bindings]
        expected_lower = [k.strip("[]").lower() for k in action_keys_in_text]
        assert all(k in binding_keys for k in expected_lower), (
            f"Action keys in text: {expected_lower}, binding keys: {binding_keys}"
        )


class TestComposeThreeColumnLayout:
    def test_bindings_and_action_methods_aligned(self, tmp_path):
        from vibecode.main_app import _ACTIONS_TEXT, _TEXTUAL_AVAILABLE, VibecodeMainApp
        from vibecode.repo_status import RepoStatus

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")

        bindings = getattr(VibecodeMainApp, "BINDINGS", [])
        binding_actions = {getattr(b, "action", None) for b in bindings}

        app = VibecodeMainApp(repo_path=tmp_path, status=RepoStatus(repo_path=tmp_path))
        action_methods = {n for n in dir(app) if n.startswith("action_")}
        for act in binding_actions:
            if act and act != "app.exit":  # textal built-in
                method_name = f"action_{act}"
                assert method_name in action_methods, f"Binding action '{act}' has no method {method_name!r} on app"

    def test_on_mount_logs_ready_and_repo(self, tmp_path):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp
        from vibecode.repo_status import RepoStatus

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")

        log_messages: list[str] = []

        class _FakeEventLog:
            def write(self, msg):
                log_messages.append(msg)

        status = RepoStatus(repo_path=tmp_path)
        app = VibecodeMainApp(repo_path=tmp_path, status=status)
        app.query_one = lambda selector, *_: _FakeEventLog()
        app.on_mount()

        assert any("ready" in m.lower() for m in log_messages)
        assert any(str(tmp_path) in m for m in log_messages)

    def test_title_and_css_path_set(self, tmp_path):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp
        from vibecode.repo_status import RepoStatus

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")

        assert VibecodeMainApp.TITLE == "VibecodeApp"
        css = getattr(VibecodeMainApp, "CSS_PATH", None)
        assert css is not None
        assert css.name == "tui_theme.tcss"
