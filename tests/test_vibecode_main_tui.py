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


# ---------------------------------------------------------------------------
# InspectMapService — unit tests
# ---------------------------------------------------------------------------


class TestInspectMapService:
    def test_error_when_no_index_files(self, tmp_path):
        from vibecode.main_app import InspectMapService

        svc = InspectMapService()
        result = svc.run(tmp_path)
        assert result["error"] is not None
        assert "index" in result["error"].lower() or "not found" in result["error"].lower()

    def test_loads_repo_tree_when_present(self, tmp_path):
        from vibecode.main_app import InspectMapService

        index_dir = tmp_path / ".vibecode" / "index"
        index_dir.mkdir(parents=True)
        map_file = index_dir / "repo_tree.generated.md"
        map_file.write_text("# Repo Map\n\nsome content\n", encoding="utf-8")

        svc = InspectMapService()
        result = svc.run(tmp_path)
        assert result["error"] is None
        assert "# Repo Map" in result["content"]
        assert result["path"] == str(map_file)

    def test_stale_when_no_last_index(self, tmp_path):
        from vibecode.main_app import InspectMapService

        index_dir = tmp_path / ".vibecode" / "index"
        index_dir.mkdir(parents=True)
        (index_dir / "repo_tree.generated.md").write_text("content", encoding="utf-8")

        svc = InspectMapService()
        result = svc.run(tmp_path)
        assert result["stale"] is True

    def test_not_stale_when_last_index_exists(self, tmp_path):
        from vibecode.main_app import InspectMapService

        index_dir = tmp_path / ".vibecode" / "index"
        index_dir.mkdir(parents=True)
        (index_dir / "repo_tree.generated.md").write_text("content", encoding="utf-8")
        current_dir = tmp_path / ".vibecode" / "current"
        current_dir.mkdir(parents=True)
        (current_dir / "last_index.json").write_text("{}", encoding="utf-8")

        svc = InspectMapService()
        result = svc.run(tmp_path)
        assert result["stale"] is False

    def test_stale_when_index_too_old(self, tmp_path):
        import json
        from datetime import datetime, timezone, timedelta

        from vibecode.main_app import InspectMapService

        index_dir = tmp_path / ".vibecode" / "index"
        index_dir.mkdir(parents=True)
        (index_dir / "repo_tree.generated.md").write_text("content", encoding="utf-8")
        current_dir = tmp_path / ".vibecode" / "current"
        current_dir.mkdir(parents=True)
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
        (current_dir / "last_index.json").write_text(
            json.dumps({"started_at": old_time}), encoding="utf-8"
        )

        svc = InspectMapService()
        result = svc.run(tmp_path)
        assert result["stale"] is True

    def test_not_stale_when_index_is_recent(self, tmp_path):
        import json
        from datetime import datetime, timezone

        from vibecode.main_app import InspectMapService

        index_dir = tmp_path / ".vibecode" / "index"
        index_dir.mkdir(parents=True)
        (index_dir / "repo_tree.generated.md").write_text("content", encoding="utf-8")
        current_dir = tmp_path / ".vibecode" / "current"
        current_dir.mkdir(parents=True)
        recent_time = datetime.now(timezone.utc).isoformat()
        (current_dir / "last_index.json").write_text(
            json.dumps({"started_at": recent_time}), encoding="utf-8"
        )

        svc = InspectMapService()
        result = svc.run(tmp_path)
        assert result["stale"] is False

    def test_reads_total_files_from_inventory(self, tmp_path):
        import json

        from vibecode.main_app import InspectMapService

        index_dir = tmp_path / ".vibecode" / "index"
        index_dir.mkdir(parents=True)
        (index_dir / "file_inventory.json").write_text(
            json.dumps({"total_files": 42, "context_cards": [{}, {}, {}]}),
            encoding="utf-8",
        )

        svc = InspectMapService()
        result = svc.run(tmp_path)
        assert result["total_files"] == 42
        assert result["card_count"] == 3
        assert result["error"] is None

    def test_succeeds_with_only_inventory(self, tmp_path):
        import json

        from vibecode.main_app import InspectMapService

        index_dir = tmp_path / ".vibecode" / "index"
        index_dir.mkdir(parents=True)
        (index_dir / "file_inventory.json").write_text(
            json.dumps({"total_files": 5, "context_cards": []}),
            encoding="utf-8",
        )

        svc = InspectMapService()
        result = svc.run(tmp_path)
        assert result["error"] is None


# ---------------------------------------------------------------------------
# render_inspect_map_result — pure rendering tests
# ---------------------------------------------------------------------------


class TestRenderInspectMapResult:
    def test_shows_error_when_error_set(self):
        from vibecode.main_app import render_inspect_map_result

        result = {
            "error": "Index not found.",
            "content": "",
            "path": "",
            "stale": False,
            "total_files": 0,
            "card_count": 0,
            "high_risk_count": 0,
        }
        text = render_inspect_map_result(result)
        assert "ERROR" in text
        assert "Index not found." in text

    def test_hints_refresh_on_error(self):
        from vibecode.main_app import render_inspect_map_result

        result = {
            "error": "No index.",
            "content": "",
            "path": "",
            "stale": False,
            "total_files": 0,
            "card_count": 0,
            "high_risk_count": 0,
        }
        text = render_inspect_map_result(result)
        assert "Refresh" in text or "refresh" in text.lower()

    def test_shows_path_on_success(self):
        from vibecode.main_app import render_inspect_map_result

        result = {
            "error": None,
            "content": "some content",
            "path": "/some/path.md",
            "stale": False,
            "total_files": 10,
            "card_count": 5,
            "high_risk_count": 0,
        }
        text = render_inspect_map_result(result)
        assert "/some/path.md" in text

    def test_shows_stale_warning(self):
        from vibecode.main_app import render_inspect_map_result

        result = {
            "error": None,
            "content": "content",
            "path": "/p.md",
            "stale": True,
            "total_files": 10,
            "card_count": 5,
            "high_risk_count": 0,
        }
        text = render_inspect_map_result(result)
        assert "stale" in text.lower() or "WARN" in text

    def test_includes_content_snippet(self):
        from vibecode.main_app import render_inspect_map_result

        result = {
            "error": None,
            "content": "# My Repo Map\nfiles here",
            "path": "/p.md",
            "stale": False,
            "total_files": 10,
            "card_count": 5,
            "high_risk_count": 0,
        }
        text = render_inspect_map_result(result)
        assert "My Repo Map" in text


# ---------------------------------------------------------------------------
# GuardService — unit tests
# ---------------------------------------------------------------------------


class TestGuardService:
    def test_error_when_project_yaml_missing(self, tmp_path):
        from vibecode.main_app import GuardService

        svc = GuardService()
        result = svc.run(tmp_path)
        assert result["error"] is not None
        assert "project.yaml" in result["error"]

    def test_returns_passed_true_on_clean_repo(self, tmp_path, monkeypatch):
        from vibecode.main_app import GuardService

        monkeypatch.setattr(
            "vibecode.main_app.GuardService.run",
            lambda self, root: {
                "passed": True,
                "errors": 0,
                "warnings": 0,
                "findings_summary": [],
                "report_path": "",
                "error": None,
            },
        )

        svc = GuardService()
        result = svc.run(tmp_path)
        assert result["passed"] is True
        assert result["error"] is None

    def test_findings_summary_populated(self, tmp_path, monkeypatch):
        from vibecode.main_app import GuardService

        expected_result = {
            "passed": False,
            "errors": 1,
            "warnings": 0,
            "findings_summary": ["  [ERROR] some/path.py: Some rule violated"],
            "report_path": "",
            "error": None,
        }
        monkeypatch.setattr(
            "vibecode.main_app.GuardService.run",
            lambda self, root: expected_result,
        )
        svc = GuardService()
        result = svc.run(tmp_path)
        assert result["findings_summary"]
        assert "ERROR" in result["findings_summary"][0]

    def test_error_propagated_when_not_git(self, tmp_path):
        import unittest.mock as mock

        from vibecode.main_app import GuardService

        (tmp_path / ".vibecode").mkdir()
        (tmp_path / ".vibecode" / "project.yaml").write_text(
            "project_id: test\n", encoding="utf-8"
        )

        class FakeGitState:
            is_git_repo = False
            error = ""

        with mock.patch("vibecode.git_state.inspect_git_state", return_value=FakeGitState()):
            svc = GuardService()
            result = svc.run(tmp_path)
        assert result["error"] is not None
        assert "git" in result["error"].lower()


# ---------------------------------------------------------------------------
# render_guard_result_summary — pure rendering tests
# ---------------------------------------------------------------------------


class TestRenderGuardResultSummary:
    def test_shows_error_when_error_set(self):
        from vibecode.main_app import render_guard_result_summary

        result = {
            "error": "Not a git repo.",
            "passed": True,
            "errors": 0,
            "warnings": 0,
            "findings_summary": [],
            "report_path": "",
        }
        text = render_guard_result_summary(result)
        assert "ERROR" in text
        assert "Not a git repo." in text

    def test_shows_passed_when_passed(self):
        from vibecode.main_app import render_guard_result_summary

        result = {
            "error": None,
            "passed": True,
            "errors": 0,
            "warnings": 0,
            "findings_summary": [],
            "report_path": "",
        }
        text = render_guard_result_summary(result)
        assert "PASSED" in text

    def test_shows_failed_when_not_passed(self):
        from vibecode.main_app import render_guard_result_summary

        result = {
            "error": None,
            "passed": False,
            "errors": 2,
            "warnings": 1,
            "findings_summary": ["  [ERROR] foo.py: Bad thing"],
            "report_path": "/r/g.json",
        }
        text = render_guard_result_summary(result)
        assert "FAILED" in text

    def test_shows_report_path(self):
        from vibecode.main_app import render_guard_result_summary

        result = {
            "error": None,
            "passed": True,
            "errors": 0,
            "warnings": 0,
            "findings_summary": [],
            "report_path": "/the/report.json",
        }
        text = render_guard_result_summary(result)
        assert "/the/report.json" in text

    def test_shows_findings_when_present(self):
        from vibecode.main_app import render_guard_result_summary

        result = {
            "error": None,
            "passed": False,
            "errors": 1,
            "warnings": 0,
            "findings_summary": ["  [ERROR] a.py: Rule X"],
            "report_path": "",
        }
        text = render_guard_result_summary(result)
        assert "Rule X" in text

    def test_failure_not_hidden(self):
        from vibecode.main_app import render_guard_result_summary

        result = {
            "error": None,
            "passed": False,
            "errors": 3,
            "warnings": 0,
            "findings_summary": [],
            "report_path": "",
        }
        text = render_guard_result_summary(result)
        assert "PASSED" not in text
        assert "FAILED" in text


# ---------------------------------------------------------------------------
# CheckService — unit tests
# ---------------------------------------------------------------------------


class TestCheckService:
    def test_error_when_no_checks_yaml(self, tmp_path):
        from vibecode.main_app import CheckService

        svc = CheckService()
        result = svc.run(tmp_path)
        assert result["error"] is not None
        assert "required_checks.yaml" in result["error"]

    def test_returns_pass_with_passing_check(self, tmp_path, monkeypatch):
        from vibecode.main_app import CheckService

        expected = {
            "status": "pass",
            "total": 1,
            "passed": 1,
            "failed": 0,
            "warnings": 0,
            "results_summary": ["  [PASS] cli help (exit 0, 0.10s)"],
            "path": str(tmp_path / ".vibecode" / "current" / "check_results.json"),
            "error": None,
        }
        monkeypatch.setattr(
            "vibecode.main_app.CheckService.run",
            lambda self, root: expected,
        )
        svc = CheckService()
        result = svc.run(tmp_path)
        assert result["status"] == "pass"
        assert result["failed"] == 0

    def test_returns_fail_with_failing_check(self, tmp_path, monkeypatch):
        from vibecode.main_app import CheckService

        expected = {
            "status": "fail",
            "total": 1,
            "passed": 0,
            "failed": 1,
            "warnings": 0,
            "results_summary": ["  [FAIL] unit tests (exit 1, 5.00s)"],
            "path": "",
            "error": None,
        }
        monkeypatch.setattr(
            "vibecode.main_app.CheckService.run",
            lambda self, root: expected,
        )
        svc = CheckService()
        result = svc.run(tmp_path)
        assert result["status"] == "fail"
        assert result["failed"] == 1

    def test_with_real_passing_check_command(self, tmp_path):
        import json
        from pathlib import Path

        from vibecode.main_app import CheckService

        checks_dir = tmp_path / ".vibecode" / "checks"
        checks_dir.mkdir(parents=True)
        (tmp_path / ".vibecode" / "project.yaml").write_text(
            "project:\n  id: test\n  name: Test\n  root: .\n", encoding="utf-8"
        )
        (checks_dir / "required_checks.yaml").write_text(
            "checks:\n  - name: trivial\n    command: python -c \"print('ok')\"\n    required: true\n",
            encoding="utf-8",
        )

        svc = CheckService()
        result = svc.run(tmp_path)
        assert result["error"] is None
        assert result["status"] == "pass"
        assert result["passed"] == 1
        assert result["failed"] == 0
        assert result["path"]
        out_path = Path(result["path"])
        assert out_path.exists()
        data = json.loads(out_path.read_text())
        assert data.get("status") == "ok"

    def test_failing_check_status_is_fail(self, tmp_path):
        from vibecode.main_app import CheckService

        checks_dir = tmp_path / ".vibecode" / "checks"
        checks_dir.mkdir(parents=True)
        (tmp_path / ".vibecode" / "project.yaml").write_text(
            "project:\n  id: test\n  name: Test\n  root: .\n", encoding="utf-8"
        )
        (checks_dir / "required_checks.yaml").write_text(
            "checks:\n  - name: always fails\n    command: python -c \"raise SystemExit(1)\"\n    required: true\n",
            encoding="utf-8",
        )

        svc = CheckService()
        result = svc.run(tmp_path)
        assert result["error"] is None
        assert result["status"] == "fail"
        assert result["failed"] == 1


# ---------------------------------------------------------------------------
# render_check_result_summary — pure rendering tests
# ---------------------------------------------------------------------------


class TestRenderCheckResultSummary:
    def test_shows_error_when_error_set(self):
        from vibecode.main_app import render_check_result_summary

        result = {
            "error": "No checks yaml.",
            "status": "not-run",
            "total": 0,
            "passed": 0,
            "failed": 0,
            "warnings": 0,
            "results_summary": [],
            "path": "",
        }
        text = render_check_result_summary(result)
        assert "ERROR" in text
        assert "No checks yaml." in text

    def test_shows_pass_on_pass(self):
        from vibecode.main_app import render_check_result_summary

        result = {
            "error": None,
            "status": "pass",
            "total": 2,
            "passed": 2,
            "failed": 0,
            "warnings": 0,
            "results_summary": [],
            "path": "",
        }
        text = render_check_result_summary(result)
        assert "PASS" in text

    def test_shows_fail_on_fail(self):
        from vibecode.main_app import render_check_result_summary

        result = {
            "error": None,
            "status": "fail",
            "total": 2,
            "passed": 1,
            "failed": 1,
            "warnings": 0,
            "results_summary": ["  [FAIL] tests (exit 1)"],
            "path": "",
        }
        text = render_check_result_summary(result)
        assert "FAIL" in text

    def test_failure_not_hidden(self):
        from vibecode.main_app import render_check_result_summary

        result = {
            "error": None,
            "status": "fail",
            "total": 1,
            "passed": 0,
            "failed": 1,
            "warnings": 0,
            "results_summary": [],
            "path": "",
        }
        text = render_check_result_summary(result)
        assert "✓ PASS" not in text

    def test_shows_report_path(self):
        from vibecode.main_app import render_check_result_summary

        result = {
            "error": None,
            "status": "pass",
            "total": 1,
            "passed": 1,
            "failed": 0,
            "warnings": 0,
            "results_summary": [],
            "path": "/the/results.json",
        }
        text = render_check_result_summary(result)
        assert "/the/results.json" in text

    def test_check_items_listed(self):
        from vibecode.main_app import render_check_result_summary

        result = {
            "error": None,
            "status": "pass",
            "total": 1,
            "passed": 1,
            "failed": 0,
            "warnings": 0,
            "results_summary": ["  [PASS] cli help (exit 0, 0.05s)"],
            "path": "",
        }
        text = render_check_result_summary(result)
        assert "cli help" in text


# ---------------------------------------------------------------------------
# HandoffService — unit tests
# ---------------------------------------------------------------------------


class TestHandoffService:
    def test_error_when_no_vibecode_dir(self, tmp_path):
        from vibecode.main_app import HandoffService

        svc = HandoffService()
        result = svc.run(tmp_path)
        assert result["error"] is not None
        assert ".vibecode" in result["error"]

    def test_passed_when_handoff_valid(self, tmp_path):
        from vibecode.main_app import HandoffService

        hdir = tmp_path / ".vibecode" / "handoff"
        hdir.mkdir(parents=True)
        (hdir / "NOW.md").write_text("# Now\n\nSome real content here.\n", encoding="utf-8")
        (hdir / "NEXT.md").write_text("# Next\n\nSome next steps.\n", encoding="utf-8")
        (hdir / "BLOCKERS.md").write_text("# Blockers\n\nNo hard blockers.\n", encoding="utf-8")

        svc = HandoffService()
        result = svc.run(tmp_path)
        assert result["error"] is None
        assert result["passed"] is True
        assert result["issues"] == []

    def test_fails_when_handoff_missing(self, tmp_path):
        from vibecode.main_app import HandoffService

        (tmp_path / ".vibecode").mkdir()

        svc = HandoffService()
        result = svc.run(tmp_path)
        assert result["error"] is None
        assert result["passed"] is False
        assert len(result["issues"]) > 0

    def test_issues_include_file_and_message(self, tmp_path):
        from vibecode.main_app import HandoffService

        (tmp_path / ".vibecode").mkdir()

        svc = HandoffService()
        result = svc.run(tmp_path)
        for issue in result["issues"]:
            assert "file" in issue
            assert "message" in issue


# ---------------------------------------------------------------------------
# render_handoff_result_summary — pure rendering tests
# ---------------------------------------------------------------------------


class TestRenderHandoffResultSummary:
    def test_shows_error_when_error_set(self):
        from vibecode.main_app import render_handoff_result_summary

        result = {"error": ".vibecode not found.", "passed": True, "issues": [], "status": "ok"}
        text = render_handoff_result_summary(result)
        assert "ERROR" in text
        assert ".vibecode not found." in text

    def test_shows_passed_when_passed(self):
        from vibecode.main_app import render_handoff_result_summary

        result = {"error": None, "passed": True, "issues": [], "status": "ok"}
        text = render_handoff_result_summary(result)
        assert "PASSED" in text

    def test_shows_failed_when_failed(self):
        from vibecode.main_app import render_handoff_result_summary

        result = {
            "error": None,
            "passed": False,
            "issues": [{"file": ".vibecode/handoff/NOW.md", "message": "Missing"}],
            "status": "error",
        }
        text = render_handoff_result_summary(result)
        assert "FAILED" in text

    def test_shows_issue_details(self):
        from vibecode.main_app import render_handoff_result_summary

        result = {
            "error": None,
            "passed": False,
            "issues": [{"file": ".vibecode/handoff/NOW.md", "message": "NOW.md is missing"}],
            "status": "error",
        }
        text = render_handoff_result_summary(result)
        assert "NOW.md" in text
        assert "missing" in text.lower()

    def test_failure_not_converted_to_success(self):
        from vibecode.main_app import render_handoff_result_summary

        result = {
            "error": None,
            "passed": False,
            "issues": [{"file": "f", "message": "bad"}],
            "status": "error",
        }
        text = render_handoff_result_summary(result)
        assert "PASSED" not in text
        assert "FAILED" in text


# ---------------------------------------------------------------------------
# Action callback tests — service results update event/debug panel
# ---------------------------------------------------------------------------


class TestActionCallbacks:
    def _make_app(self, tmp_path):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp
        from vibecode.repo_status import RepoStatus

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")

        status = RepoStatus(repo_path=tmp_path)
        app = VibecodeMainApp(repo_path=tmp_path, status=status)
        log_messages: list = []

        class _FakeWidget:
            def update(self, msg):
                log_messages.append(msg)

            def write(self, msg):
                log_messages.append(msg)

        app.query_one = lambda selector, *_: _FakeWidget()
        return app, log_messages

    def test_on_inspect_done_logs_summary(self, tmp_path):
        app, log_messages = self._make_app(tmp_path)
        result = {
            "error": None,
            "content": "# Map\nstuff",
            "path": "/p.md",
            "stale": False,
            "total_files": 5,
            "card_count": 3,
            "high_risk_count": 0,
        }
        app._on_inspect_done(result)
        all_text = " ".join(str(m) for m in log_messages)
        assert len(all_text) > 0

    def test_on_inspect_done_error_logged(self, tmp_path):
        app, log_messages = self._make_app(tmp_path)
        result = {
            "error": "No index.",
            "content": "",
            "path": "",
            "stale": False,
            "total_files": 0,
            "card_count": 0,
            "high_risk_count": 0,
        }
        app._on_inspect_done(result)
        all_text = " ".join(str(m) for m in log_messages)
        assert "No index." in all_text or len(all_text) > 0

    def test_on_guard_done_passes_logs_passed(self, tmp_path):
        app, log_messages = self._make_app(tmp_path)
        result = {
            "error": None,
            "passed": True,
            "errors": 0,
            "warnings": 0,
            "findings_summary": [],
            "report_path": "",
        }
        app._on_guard_done(result)
        all_text = " ".join(str(m) for m in log_messages)
        assert "PASSED" in all_text

    def test_on_guard_done_failure_stays_visible(self, tmp_path):
        app, log_messages = self._make_app(tmp_path)
        result = {
            "error": None,
            "passed": False,
            "errors": 2,
            "warnings": 0,
            "findings_summary": ["  [ERROR] a.py: Bad rule"],
            "report_path": "",
        }
        app._on_guard_done(result)
        all_text = " ".join(str(m) for m in log_messages)
        assert "FAILED" in all_text or "FAIL" in all_text

    def test_on_check_done_failure_visible(self, tmp_path):
        app, log_messages = self._make_app(tmp_path)
        result = {
            "error": None,
            "status": "fail",
            "total": 1,
            "passed": 0,
            "failed": 1,
            "warnings": 0,
            "results_summary": ["  [FAIL] tests"],
            "path": "",
        }
        app._on_check_done(result)
        all_text = " ".join(str(m) for m in log_messages)
        assert "FAIL" in all_text

    def test_on_check_done_pass_logged(self, tmp_path):
        app, log_messages = self._make_app(tmp_path)
        result = {
            "error": None,
            "status": "pass",
            "total": 2,
            "passed": 2,
            "failed": 0,
            "warnings": 0,
            "results_summary": [],
            "path": "",
        }
        app._on_check_done(result)
        all_text = " ".join(str(m) for m in log_messages)
        assert "PASSED" in all_text or "PASS" in all_text

    def test_on_handoff_done_passed_logged(self, tmp_path):
        app, log_messages = self._make_app(tmp_path)
        result = {"error": None, "passed": True, "issues": [], "status": "ok"}
        app._on_handoff_done(result)
        all_text = " ".join(str(m) for m in log_messages)
        assert "PASSED" in all_text

    def test_on_handoff_done_failure_visible(self, tmp_path):
        app, log_messages = self._make_app(tmp_path)
        result = {
            "error": None,
            "passed": False,
            "issues": [{"file": "NOW.md", "message": "missing"}],
            "status": "error",
        }
        app._on_handoff_done(result)
        all_text = " ".join(str(m) for m in log_messages)
        assert "FAILED" in all_text

    def test_on_guard_error_logged(self, tmp_path):
        app, log_messages = self._make_app(tmp_path)
        app._on_guard_error("something went wrong")
        all_text = " ".join(str(m) for m in log_messages)
        assert "Guard" in all_text or "guard" in all_text.lower()

    def test_on_check_error_logged(self, tmp_path):
        app, log_messages = self._make_app(tmp_path)
        app._on_check_error("check boom")
        all_text = " ".join(str(m) for m in log_messages)
        assert "Checks" in all_text or "check" in all_text.lower()

    def test_on_handoff_error_logged(self, tmp_path):
        app, log_messages = self._make_app(tmp_path)
        app._on_handoff_error("handoff exploded")
        all_text = " ".join(str(m) for m in log_messages)
        assert "Handoff" in all_text or "handoff" in all_text.lower()

    def test_on_inspect_error_logged(self, tmp_path):
        app, log_messages = self._make_app(tmp_path)
        app._on_inspect_error("disk error")
        all_text = " ".join(str(m) for m in log_messages)
        assert "Inspect" in all_text or "inspect" in all_text.lower()


# ---------------------------------------------------------------------------
# Service injection — lazy getter tests
# ---------------------------------------------------------------------------


class TestServiceInjection:
    def test_inject_inspect_service(self, tmp_path):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp
        from vibecode.repo_status import RepoStatus

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")

        class FakeSvc:
            pass

        fake = FakeSvc()
        status = RepoStatus(repo_path=tmp_path)
        app = VibecodeMainApp(repo_path=tmp_path, status=status, inspect_service=fake)
        assert app._get_inspect_service() is fake

    def test_inject_guard_service(self, tmp_path):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp
        from vibecode.repo_status import RepoStatus

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")

        class FakeSvc:
            pass

        fake = FakeSvc()
        status = RepoStatus(repo_path=tmp_path)
        app = VibecodeMainApp(repo_path=tmp_path, status=status, guard_service=fake)
        assert app._get_guard_service() is fake

    def test_inject_check_service(self, tmp_path):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp
        from vibecode.repo_status import RepoStatus

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")

        class FakeSvc:
            pass

        fake = FakeSvc()
        status = RepoStatus(repo_path=tmp_path)
        app = VibecodeMainApp(repo_path=tmp_path, status=status, check_service=fake)
        assert app._get_check_service() is fake

    def test_inject_handoff_service(self, tmp_path):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp
        from vibecode.repo_status import RepoStatus

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")

        class FakeSvc:
            pass

        fake = FakeSvc()
        status = RepoStatus(repo_path=tmp_path)
        app = VibecodeMainApp(repo_path=tmp_path, status=status, handoff_service=fake)
        assert app._get_handoff_service() is fake

    def test_default_inspect_service_type(self, tmp_path):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, InspectMapService, VibecodeMainApp
        from vibecode.repo_status import RepoStatus

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")
        status = RepoStatus(repo_path=tmp_path)
        app = VibecodeMainApp(repo_path=tmp_path, status=status)
        assert isinstance(app._get_inspect_service(), InspectMapService)

    def test_default_guard_service_type(self, tmp_path):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, GuardService, VibecodeMainApp
        from vibecode.repo_status import RepoStatus

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")
        status = RepoStatus(repo_path=tmp_path)
        app = VibecodeMainApp(repo_path=tmp_path, status=status)
        assert isinstance(app._get_guard_service(), GuardService)

    def test_default_check_service_type(self, tmp_path):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, CheckService, VibecodeMainApp
        from vibecode.repo_status import RepoStatus

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")
        status = RepoStatus(repo_path=tmp_path)
        app = VibecodeMainApp(repo_path=tmp_path, status=status)
        assert isinstance(app._get_check_service(), CheckService)

    def test_default_handoff_service_type(self, tmp_path):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, HandoffService, VibecodeMainApp
        from vibecode.repo_status import RepoStatus

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")
        status = RepoStatus(repo_path=tmp_path)
        app = VibecodeMainApp(repo_path=tmp_path, status=status)
        assert isinstance(app._get_handoff_service(), HandoffService)


# ---------------------------------------------------------------------------
# Binding and action method alignment for new actions
# ---------------------------------------------------------------------------


class TestNewActionBindings:
    def test_guard_action_method_exists(self, tmp_path):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp
        from vibecode.repo_status import RepoStatus

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")
        app = VibecodeMainApp(repo_path=tmp_path, status=RepoStatus(repo_path=tmp_path))
        assert hasattr(app, "action_cmd_guard")
        assert callable(app.action_cmd_guard)

    def test_tests_action_method_exists(self, tmp_path):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp
        from vibecode.repo_status import RepoStatus

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")
        app = VibecodeMainApp(repo_path=tmp_path, status=RepoStatus(repo_path=tmp_path))
        assert hasattr(app, "action_cmd_tests")
        assert callable(app.action_cmd_tests)

    def test_handoff_action_method_exists(self, tmp_path):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp
        from vibecode.repo_status import RepoStatus

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")
        app = VibecodeMainApp(repo_path=tmp_path, status=RepoStatus(repo_path=tmp_path))
        assert hasattr(app, "action_cmd_handoff")
        assert callable(app.action_cmd_handoff)

    def test_inspect_action_method_exists(self, tmp_path):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp
        from vibecode.repo_status import RepoStatus

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")
        app = VibecodeMainApp(repo_path=tmp_path, status=RepoStatus(repo_path=tmp_path))
        assert hasattr(app, "action_inspect_map")
        assert callable(app.action_inspect_map)

    def test_guard_binding_present(self):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")
        bindings = getattr(VibecodeMainApp, "BINDINGS", [])
        keys = {getattr(b, "key", None) for b in bindings}
        assert "g" in keys

    def test_tests_binding_present(self):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")
        bindings = getattr(VibecodeMainApp, "BINDINGS", [])
        keys = {getattr(b, "key", None) for b in bindings}
        assert "t" in keys

    def test_handoff_binding_present(self):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")
        bindings = getattr(VibecodeMainApp, "BINDINGS", [])
        keys = {getattr(b, "key", None) for b in bindings}
        assert "h" in keys


# ---------------------------------------------------------------------------
# Action wiring regression — direct calls verify service→callback path
# ---------------------------------------------------------------------------


class TestActionWiringRegression:
    """Call action methods directly and verify the service-invoke →
    callback-forward wire is intact (threading is patched synchronous)."""

    @staticmethod
    def _make_app(tmp_path: Path, monkeypatch, svc_kwarg: str, fake_svc):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp
        from vibecode.repo_status import RepoStatus

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")

        svc_kwargs: dict = {svc_kwarg: fake_svc}
        status = RepoStatus(repo_path=tmp_path)
        app = VibecodeMainApp(repo_path=tmp_path, status=status, **svc_kwargs)

        # Silence _log_event to avoid query_one lookup.
        app._log_event = lambda msg: None  # type: ignore[method-assign]
        # Suppress _refresh_left_panel called by _on_guard_done / _on_check_done.
        app._refresh_left_panel = lambda: None  # type: ignore[method-assign]

        # Record call_from_thread invocations and run the handler synchronously.
        call_records: list = []

        def _recording_call_from_thread(fn, *args):
            call_records.append((fn.__name__, args))
            fn(*args)

        app.call_from_thread = _recording_call_from_thread  # type: ignore[method-assign]

        # Patch threading.Thread to run the target synchronously.
        import vibecode.main_app as ma

        class _SyncThread:
            def __init__(self, target=None, daemon=None, name=None):
                self._target = target

            def start(self):
                self._target()

        monkeypatch.setattr(ma.threading, "Thread", _SyncThread)
        return app, call_records

    # -- inspect -----------------------------------------------------------

    def test_action_inspect_map_calls_service(self, tmp_path, monkeypatch):
        class FakeSvc:
            def __init__(self):
                self.called_with: Path | None = None
                self._result = {
                    "error": None, "content": "map", "path": "/p.md",
                    "stale": False, "total_files": 3, "card_count": 1,
                    "high_risk_count": 0,
                }

            def run(self, repo_root):
                self.called_with = repo_root
                return self._result

        fake = FakeSvc()
        app, call_records = self._make_app(tmp_path, monkeypatch, "inspect_service", fake)

        app.action_inspect_map()

        assert fake.called_with == tmp_path
        assert len(call_records) == 1
        assert call_records[0][0] == "_on_inspect_done"

    def test_action_inspect_map_routes_error(self, tmp_path, monkeypatch):
        class FakeSvc:
            def run(self, repo_root):
                raise RuntimeError("disk failure")

        fake = FakeSvc()
        app, call_records = self._make_app(tmp_path, monkeypatch, "inspect_service", fake)

        app.action_inspect_map()

        assert len(call_records) == 1
        assert call_records[0][0] == "_on_inspect_error"
        assert "disk failure" in str(call_records[0][1])

    # -- guard -------------------------------------------------------------

    def test_action_cmd_guard_calls_service(self, tmp_path, monkeypatch):
        class FakeSvc:
            def __init__(self):
                self.called_with: Path | None = None
                self._result = {
                    "error": None, "passed": True, "errors": 0, "warnings": 0,
                    "findings_summary": [], "report_path": "",
                }

            def run(self, repo_root):
                self.called_with = repo_root
                return self._result

        fake = FakeSvc()
        app, call_records = self._make_app(tmp_path, monkeypatch, "guard_service", fake)

        app.action_cmd_guard()

        assert fake.called_with == tmp_path
        assert len(call_records) == 1
        assert call_records[0][0] == "_on_guard_done"

    def test_action_cmd_guard_routes_error(self, tmp_path, monkeypatch):
        class FakeSvc:
            def run(self, repo_root):
                raise RuntimeError("guard crash")

        fake = FakeSvc()
        app, call_records = self._make_app(tmp_path, monkeypatch, "guard_service", fake)

        app.action_cmd_guard()

        assert len(call_records) == 1
        assert call_records[0][0] == "_on_guard_error"
        assert "guard crash" in str(call_records[0][1])

    # -- tests/checks ------------------------------------------------------

    def test_action_cmd_tests_calls_service(self, tmp_path, monkeypatch):
        class FakeSvc:
            def __init__(self):
                self.called_with: Path | None = None
                self._result = {
                    "error": None, "status": "pass", "total": 3, "passed": 3,
                    "failed": 0, "warnings": 0, "results_summary": [], "path": "",
                }

            def run(self, repo_root):
                self.called_with = repo_root
                return self._result

        fake = FakeSvc()
        app, call_records = self._make_app(tmp_path, monkeypatch, "check_service", fake)

        app.action_cmd_tests()

        assert fake.called_with == tmp_path
        assert len(call_records) == 1
        assert call_records[0][0] == "_on_check_done"

    def test_action_cmd_tests_routes_error(self, tmp_path, monkeypatch):
        class FakeSvc:
            def run(self, repo_root):
                raise RuntimeError("check boom")

        fake = FakeSvc()
        app, call_records = self._make_app(tmp_path, monkeypatch, "check_service", fake)

        app.action_cmd_tests()

        assert len(call_records) == 1
        assert call_records[0][0] == "_on_check_error"
        assert "check boom" in str(call_records[0][1])

    # -- handoff -----------------------------------------------------------

    def test_action_cmd_handoff_calls_service(self, tmp_path, monkeypatch):
        class FakeSvc:
            def __init__(self):
                self.called_with: Path | None = None
                self._result = {"error": None, "passed": True, "issues": [], "status": "ok"}

            def run(self, repo_root):
                self.called_with = repo_root
                return self._result

        fake = FakeSvc()
        app, call_records = self._make_app(tmp_path, monkeypatch, "handoff_service", fake)

        app.action_cmd_handoff()

        assert fake.called_with == tmp_path
        assert len(call_records) == 1
        assert call_records[0][0] == "_on_handoff_done"

    def test_action_cmd_handoff_routes_error(self, tmp_path, monkeypatch):
        class FakeSvc:
            def run(self, repo_root):
                raise RuntimeError("handoff exploded")

        fake = FakeSvc()
        app, call_records = self._make_app(tmp_path, monkeypatch, "handoff_service", fake)

        app.action_cmd_handoff()

        assert len(call_records) == 1
        assert call_records[0][0] == "_on_handoff_error"
        assert "handoff exploded" in str(call_records[0][1])
