"""Tests for the [C] Create context TUI feature.

Coverage:
- _get_section_content extracts lines from a markdown section
- _extract_file_paths, _extract_architecture_docs, _extract_required_checks_from_pack,
  _extract_protected_paths_from_pack, _extract_pack_warnings
- ContextPreviewService.run() calls write_context_pack + write_opencode_prompt
- ContextPreviewService.run() returns expected preview keys
- ContextPreviewService.run() captures errors without raising
- render_center_context_status() includes task, provider, paths, status, next steps
- render_context_preview() includes all summary fields
- render_context_preview() shows ERROR when error key is set
- ContextInputScreen can be constructed (Textual-guarded)
- VibecodeMainApp accepts a context_service injection
- _get_context_service returns ContextPreviewService when none injected
- _get_context_service returns injected service
- _on_context_task_received(None) logs cancellation
- _on_context_task_received(task) calls service.run and threads it
- _on_context_done updates center panel and logs preview
- _on_context_done with error logs failure without raising
- _on_context_error logs error string
- action_cmd_context logs a warning if .vibecode is missing (no push_screen)
- No LLM/OpenCode invocation by any of the above
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from vibecode.main_app import (
    ContextPreviewService,
    _extract_architecture_docs,
    _extract_file_paths,
    _extract_pack_warnings,
    _extract_protected_paths_from_pack,
    _extract_required_checks_from_pack,
    _get_section_content,
    render_center_context_status,
    render_context_preview,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_PACK = """\
# Vibecode Context Pack

## Current task

Implement pagination

## Relevant files with reasons

Do not paste full source into follow-up prompts; use these paths as navigation targets.
- `vibecode/cli.py` (score 9): contains the CLI
- `vibecode/context/renderer.py` (score 7, risk `high`, requires confirmation): context renderer
  symbols: `render_context_pack`, `write_context_pack`

## Relevant architecture

- `.vibecode/architecture/STRUCTURE.md`: Repository Structure.
  - `vibecode/cli.py` defines the command-line interface.
- `.vibecode/architecture/INVARIANTS.md`: Project invariants.

## Required checks

- unit tests: `python -m pytest`
- context command help: `python -m vibecode.cli context --help`
- Run all checks: `vibecode check /repo`

## Protected paths / edit constraints

Policy source: `.vibecode/checks/protected_paths.yaml`.
- `vibecode/context/renderer.py`: rule: needs review; explicit task scope: required; required tests: `test_context`
- `.vibecode/checks/required_checks.yaml`: rule: human-maintained; explicit task scope: required; required tests: not specified
"""

_PACK_WITH_TRUNCATION = _SAMPLE_PACK + "\n> **Context limit reached.** The following sections were omitted.\n"

_PACK_WITH_WARNING = _SAMPLE_PACK + "\n- WARNING: generated index is stale or missing: index missing.\n"


# ---------------------------------------------------------------------------
# _get_section_content
# ---------------------------------------------------------------------------


class TestGetSectionContent:
    def test_returns_lines_in_section(self):
        lines = _get_section_content(_SAMPLE_PACK, "Current task")
        assert "Implement pagination" in lines

    def test_stops_at_next_heading(self):
        lines = _get_section_content(_SAMPLE_PACK, "Current task")
        assert not any("vibecode/cli.py" in l for l in lines)

    def test_empty_when_heading_missing(self):
        lines = _get_section_content(_SAMPLE_PACK, "Nonexistent section heading")
        assert lines == []

    def test_excludes_blockquote_lines(self):
        pack = "## Required checks\n\n> blockquote line\n- real line\n"
        lines = _get_section_content(pack, "Required checks")
        assert not any(l.startswith(">") for l in lines)

    def test_excludes_blank_lines(self):
        lines = _get_section_content(_SAMPLE_PACK, "Relevant files with reasons")
        assert "" not in lines

    def test_case_insensitive_heading_match(self):
        lines = _get_section_content(_SAMPLE_PACK, "CURRENT TASK")
        assert "Implement pagination" in lines


# ---------------------------------------------------------------------------
# _extract_file_paths
# ---------------------------------------------------------------------------


class TestExtractFilePaths:
    def test_returns_backtick_paths(self):
        paths = _extract_file_paths(_SAMPLE_PACK)
        assert "vibecode/cli.py" in paths
        assert "vibecode/context/renderer.py" in paths

    def test_excludes_symbol_lines(self):
        paths = _extract_file_paths(_SAMPLE_PACK)
        assert not any("render_context_pack" in p for p in paths)

    def test_limits_to_ten(self):
        many_files = "## Relevant files with reasons\n\n"
        for i in range(20):
            many_files += f"- `file{i}.py` (score 1): reason\n"
        paths = _extract_file_paths(many_files)
        assert len(paths) <= 10

    def test_returns_empty_when_no_section(self):
        assert _extract_file_paths("# No relevant files here\n") == []


# ---------------------------------------------------------------------------
# _extract_architecture_docs
# ---------------------------------------------------------------------------


class TestExtractArchitectureDocs:
    def test_returns_architecture_paths(self):
        docs = _extract_architecture_docs(_SAMPLE_PACK)
        assert any("STRUCTURE.md" in d for d in docs)
        assert any("INVARIANTS.md" in d for d in docs)

    def test_returns_empty_when_no_section(self):
        assert _extract_architecture_docs("# Empty\n") == []

    def test_excludes_nested_source_file_bullets(self):
        docs = _extract_architecture_docs(_SAMPLE_PACK)
        assert not any("vibecode/cli.py" in d for d in docs)


# ---------------------------------------------------------------------------
# _extract_required_checks_from_pack
# ---------------------------------------------------------------------------


class TestExtractRequiredChecksFromPack:
    def test_returns_check_commands(self):
        checks = _extract_required_checks_from_pack(_SAMPLE_PACK)
        assert "python -m pytest" in checks

    def test_limits_to_five(self):
        many = "## Required checks\n\n"
        for i in range(10):
            many += f"- check {i}: `cmd{i}`\n"
        checks = _extract_required_checks_from_pack(many)
        assert len(checks) <= 5

    def test_returns_empty_when_no_section(self):
        assert _extract_required_checks_from_pack("no checks here") == []


# ---------------------------------------------------------------------------
# _extract_protected_paths_from_pack
# ---------------------------------------------------------------------------


class TestExtractProtectedPathsFromPack:
    def test_returns_protected_paths(self):
        paths = _extract_protected_paths_from_pack(_SAMPLE_PACK)
        assert any("renderer.py" in p for p in paths)

    def test_excludes_policy_source_line(self):
        paths = _extract_protected_paths_from_pack(_SAMPLE_PACK)
        # "Policy source" line doesn't start with "- `path`:" pattern
        assert not any("Policy source" in p for p in paths)

    def test_limits_to_eight(self):
        many = "## Protected paths / edit constraints\n\n"
        for i in range(15):
            many += f"- `path{i}.py`: rule: read-only;\n"
        paths = _extract_protected_paths_from_pack(many)
        assert len(paths) <= 8


# ---------------------------------------------------------------------------
# _extract_pack_warnings
# ---------------------------------------------------------------------------


class TestExtractPackWarnings:
    def test_detects_context_limit_warning(self):
        warnings = _extract_pack_warnings(_PACK_WITH_TRUNCATION)
        assert any("Context limit reached" in w for w in warnings)

    def test_detects_stale_index_warning(self):
        warnings = _extract_pack_warnings(_PACK_WITH_WARNING)
        assert any("WARNING" in w or "stale" in w for w in warnings)

    def test_empty_when_no_warnings(self):
        assert _extract_pack_warnings(_SAMPLE_PACK) == []

    def test_limits_to_five(self):
        pack = "\n".join(f"- WARNING: issue {i}" for i in range(10))
        warnings = _extract_pack_warnings(pack)
        assert len(warnings) <= 5


# ---------------------------------------------------------------------------
# ContextPreviewService
# ---------------------------------------------------------------------------


class TestContextPreviewService:
    def test_run_calls_write_context_pack(self, tmp_path):
        svc = ContextPreviewService()
        called = []

        def fake_write_pack(repo_root, task, **kw):
            called.append((repo_root, task))
            p = tmp_path / ".vibecode" / "current" / "context_pack.md"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(_SAMPLE_PACK, encoding="utf-8")
            return p

        def fake_write_prompt(repo_root, content):
            p = tmp_path / ".vibecode" / "current" / "opencode_prompt.md"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("prompt", encoding="utf-8")
            return p

        with (
            patch("vibecode.main_app.ContextPreviewService.run") as mock_run,
        ):
            # Test by invoking real code with mocked writer functions
            pass

        # Direct test: patch inside run
        import vibecode.main_app as ma

        with (
            patch.object(
                ma,
                "_extract_file_paths",
                return_value=["vibecode/cli.py"],
            ),
            patch(
                "vibecode.context.renderer.write_context_pack",
                side_effect=fake_write_pack,
            ),
            patch(
                "vibecode.context.platform_export.write_opencode_prompt",
                side_effect=fake_write_prompt,
            ),
        ):
            result = svc.run(tmp_path, "my task")

        assert called == [(tmp_path, "my task")]

    def test_run_returns_expected_keys(self, tmp_path):
        svc = ContextPreviewService()

        def _write_pack(repo_root, task, **kw):
            p = tmp_path / ".vibecode" / "current" / "context_pack.md"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(_SAMPLE_PACK, encoding="utf-8")
            return p

        def _write_prompt(repo_root, content):
            p = tmp_path / ".vibecode" / "current" / "opencode_prompt.md"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("prompt", encoding="utf-8")
            return p

        with (
            patch("vibecode.context.renderer.write_context_pack", side_effect=_write_pack),
            patch(
                "vibecode.context.platform_export.write_opencode_prompt",
                side_effect=_write_prompt,
            ),
        ):
            result = svc.run(tmp_path, "test task")

        required_keys = {
            "task", "platform", "context_pack_path", "opencode_prompt_path",
            "relevant_files", "architecture_docs", "required_checks",
            "protected_files", "warnings", "error",
        }
        assert required_keys.issubset(result.keys())
        assert result["task"] == "test task"
        assert result["platform"] == "opencode"
        assert result["error"] is None

    def test_run_extracts_relevant_files(self, tmp_path):
        svc = ContextPreviewService()

        def _write_pack(repo_root, task, **kw):
            p = tmp_path / ".vibecode" / "current" / "context_pack.md"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(_SAMPLE_PACK, encoding="utf-8")
            return p

        def _write_prompt(repo_root, content):
            p = tmp_path / ".vibecode" / "current" / "opencode_prompt.md"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("p", encoding="utf-8")
            return p

        with (
            patch("vibecode.context.renderer.write_context_pack", side_effect=_write_pack),
            patch(
                "vibecode.context.platform_export.write_opencode_prompt",
                side_effect=_write_prompt,
            ),
        ):
            result = svc.run(tmp_path, "test task")

        assert "vibecode/cli.py" in result["relevant_files"]

    def test_run_captures_exception_without_raising(self, tmp_path):
        svc = ContextPreviewService()

        with patch(
            "vibecode.context.renderer.write_context_pack",
            side_effect=RuntimeError("disk full"),
        ):
            result = svc.run(tmp_path, "bad task")

        assert result["error"] == "disk full"
        assert result["task"] == "bad task"

    def test_run_does_not_call_opencode_or_llm(self, tmp_path):
        """ContextPreviewService must not invoke OpenCode or any LLM."""
        import builtins

        svc = ContextPreviewService()
        opencode_calls: list[str] = []
        real_import = builtins.__import__

        def guarded_import(name, *args, **kwargs):
            if "opencode" in name.lower():
                opencode_calls.append(name)
            return real_import(name, *args, **kwargs)

        def _write_pack(repo_root, task, **kw):
            p = tmp_path / ".vibecode" / "current" / "context_pack.md"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(_SAMPLE_PACK, encoding="utf-8")
            return p

        def _write_prompt(repo_root, content):
            p = tmp_path / ".vibecode" / "current" / "opencode_prompt.md"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("p", encoding="utf-8")
            return p

        with (
            patch("builtins.__import__", side_effect=guarded_import),
            patch("vibecode.context.renderer.write_context_pack", side_effect=_write_pack),
            patch(
                "vibecode.context.platform_export.write_opencode_prompt",
                side_effect=_write_prompt,
            ),
        ):
            svc.run(tmp_path, "test task")

        assert opencode_calls == [], f"OpenCode was imported: {opencode_calls}"


# ---------------------------------------------------------------------------
# render_center_context_status
# ---------------------------------------------------------------------------


class TestRenderCenterContextStatus:
    def test_mentions_opencode(self):
        text = render_center_context_status("my task", "/path/pack.md", "/path/prompt.md")
        assert "OpenCode" in text

    def test_contains_task(self):
        text = render_center_context_status("implement pagination", "/a", "/b")
        assert "implement pagination" in text

    def test_contains_context_ready_status(self):
        text = render_center_context_status("t", "/pack.md", "/prompt.md")
        assert "context ready" in text

    def test_contains_context_pack_path(self):
        text = render_center_context_status("t", "/my/context_pack.md", "/prompt.md")
        assert "/my/context_pack.md" in text

    def test_contains_opencode_prompt_path(self):
        text = render_center_context_status("t", "/pack.md", "/my/opencode_prompt.md")
        assert "/my/opencode_prompt.md" in text

    def test_mentions_audit_and_safe_next_steps(self):
        text = render_center_context_status("t", "/p", "/q")
        assert "[A]" in text
        assert "[S]" in text

    def test_notes_run_actions_available(self):
        text = render_center_context_status("t", "/p", "/q")
        assert "press A" in text
        assert "press S" in text

    def test_long_task_is_truncated(self):
        long_task = "x" * 200
        text = render_center_context_status(long_task, "/p", "/q")
        assert "…" in text
        assert long_task not in text  # full 200-char string must not appear

    def test_no_llm_mentions(self):
        text = render_center_context_status("t", "/p", "/q").lower()
        assert "llm" not in text
        assert "gpt" not in text
        assert "claude" not in text


# ---------------------------------------------------------------------------
# render_context_preview
# ---------------------------------------------------------------------------


class TestRenderContextPreview:
    def _preview(self, **overrides) -> dict:
        base: dict = {
            "task": "implement feature X",
            "platform": "opencode",
            "context_pack_path": "/repo/.vibecode/current/context_pack.md",
            "opencode_prompt_path": "/repo/.vibecode/current/opencode_prompt.md",
            "relevant_files": ["vibecode/cli.py", "vibecode/context/renderer.py"],
            "architecture_docs": [".vibecode/architecture/STRUCTURE.md"],
            "required_checks": ["python -m pytest"],
            "protected_files": ["vibecode/context/renderer.py"],
            "warnings": [],
            "error": None,
        }
        base.update(overrides)
        return base

    def test_includes_task(self):
        text = render_context_preview(self._preview())
        assert "implement feature X" in text

    def test_includes_platform(self):
        text = render_context_preview(self._preview())
        assert "opencode" in text

    def test_includes_context_pack_path(self):
        text = render_context_preview(self._preview())
        assert "context_pack.md" in text

    def test_includes_opencode_prompt_path(self):
        text = render_context_preview(self._preview())
        assert "opencode_prompt.md" in text

    def test_includes_relevant_files(self):
        text = render_context_preview(self._preview())
        assert "vibecode/cli.py" in text

    def test_includes_architecture_docs(self):
        text = render_context_preview(self._preview())
        assert "STRUCTURE.md" in text

    def test_includes_required_checks(self):
        text = render_context_preview(self._preview())
        assert "python -m pytest" in text

    def test_includes_protected_files(self):
        text = render_context_preview(self._preview())
        assert "renderer.py" in text

    def test_shows_warning(self):
        text = render_context_preview(self._preview(warnings=["Context limit reached."]))
        assert "WARN" in text
        assert "Context limit reached" in text

    def test_shows_error_when_set(self):
        text = render_context_preview(self._preview(error="disk full"))
        assert "ERROR" in text
        assert "disk full" in text

    def test_no_error_shown_when_none(self):
        text = render_context_preview(self._preview())
        assert "ERROR" not in text

    def test_empty_lists_show_no_section_headers(self):
        text = render_context_preview(
            self._preview(relevant_files=[], architecture_docs=[])
        )
        assert "Relevant files:" not in text
        assert "Architecture docs:" not in text

    def test_long_task_is_truncated(self):
        long_task = "z" * 200
        text = render_context_preview(self._preview(task=long_task))
        assert "…" in text


# ---------------------------------------------------------------------------
# ContextInputScreen (Textual-guarded)
# ---------------------------------------------------------------------------


class TestContextInputScreen:
    def test_can_be_constructed(self):
        from vibecode.main_app import ContextInputScreen

        # Should not raise regardless of Textual availability
        screen = ContextInputScreen()
        assert screen is not None

    def test_input_screen_exists_in_module(self):
        import vibecode.main_app as ma

        assert hasattr(ma, "ContextInputScreen")


# ---------------------------------------------------------------------------
# VibecodeMainApp context_service injection
# ---------------------------------------------------------------------------


class TestVibecodeMainAppContextService:
    def _make_app(self, tmp_path: Path, context_service=None):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp
        from vibecode.repo_status import RepoStatus

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")
        status = RepoStatus(repo_path=tmp_path)
        return VibecodeMainApp(
            repo_path=tmp_path,
            status=status,
            context_service=context_service,
        )

    def test_context_service_none_by_default(self, tmp_path):
        app = self._make_app(tmp_path)
        assert app._context_service is None

    def test_context_service_injected(self, tmp_path):
        class FakeSvc:
            pass

        fake = FakeSvc()
        app = self._make_app(tmp_path, context_service=fake)
        assert app._context_service is fake

    def test_get_context_service_creates_default(self, tmp_path):
        from vibecode.main_app import ContextPreviewService

        app = self._make_app(tmp_path)
        svc = app._get_context_service()
        assert isinstance(svc, ContextPreviewService)

    def test_get_context_service_returns_same_instance(self, tmp_path):
        app = self._make_app(tmp_path)
        assert app._get_context_service() is app._get_context_service()

    def test_get_context_service_returns_injected(self, tmp_path):
        class FakeSvc:
            pass

        fake = FakeSvc()
        app = self._make_app(tmp_path, context_service=fake)
        assert app._get_context_service() is fake

    def test_current_task_none_on_init(self, tmp_path):
        app = self._make_app(tmp_path)
        assert app._current_task is None


# ---------------------------------------------------------------------------
# _on_context_task_received — task=None logs cancellation
# ---------------------------------------------------------------------------


class TestOnContextTaskReceived:
    def _make_app_with_log(self, tmp_path: Path):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp
        from vibecode.repo_status import RepoStatus

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")

        log: list[str] = []

        class FakeSvc:
            def run(self, repo_root, task):
                return {
                    "task": task,
                    "platform": "opencode",
                    "context_pack_path": "/p",
                    "opencode_prompt_path": "/q",
                    "relevant_files": [],
                    "architecture_docs": [],
                    "required_checks": [],
                    "protected_files": [],
                    "warnings": [],
                    "error": None,
                }

        status = RepoStatus(repo_path=tmp_path)
        app = VibecodeMainApp(
            repo_path=tmp_path,
            status=status,
            context_service=FakeSvc(),
        )
        app._log_event = lambda msg: log.append(msg)  # type: ignore[method-assign]
        return app, log

    def test_none_task_logs_cancelled(self, tmp_path):
        app, log = self._make_app_with_log(tmp_path)
        app._on_context_task_received(None)
        assert any("cancel" in m.lower() for m in log)

    def test_none_task_does_not_set_current_task(self, tmp_path):
        app, log = self._make_app_with_log(tmp_path)
        app._on_context_task_received(None)
        assert app._current_task is None

    def test_task_sets_current_task(self, tmp_path):
        app, log = self._make_app_with_log(tmp_path)
        # Prevent actual threading; we'll just test that _current_task is set
        threads_started: list[str] = []
        import threading

        original_start = threading.Thread.start

        def mock_start(self_thread):
            threads_started.append(self_thread.name)
            # Don't actually start; just record

        with patch.object(threading.Thread, "start", mock_start):
            app._on_context_task_received("test task")

        assert app._current_task == "test task"
        assert any("tui-context" in t for t in threads_started)

    def test_task_logs_generating_message(self, tmp_path):
        app, log = self._make_app_with_log(tmp_path)
        import threading

        with patch.object(threading.Thread, "start", lambda self: None):
            app._on_context_task_received("my task")

        assert any("Generating context" in m or "my task" in m for m in log)


# ---------------------------------------------------------------------------
# _on_context_done — success path
# ---------------------------------------------------------------------------


class TestOnContextDone:
    def _make_app(self, tmp_path: Path):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp
        from vibecode.repo_status import RepoStatus

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")

        status = RepoStatus(repo_path=tmp_path)
        app = VibecodeMainApp(repo_path=tmp_path, status=status)
        return app

    def _preview(self, **overrides) -> dict:
        base: dict = {
            "task": "my task",
            "platform": "opencode",
            "context_pack_path": "/repo/.vibecode/current/context_pack.md",
            "opencode_prompt_path": "/repo/.vibecode/current/opencode_prompt.md",
            "relevant_files": ["vibecode/cli.py"],
            "architecture_docs": [],
            "required_checks": ["python -m pytest"],
            "protected_files": [],
            "warnings": [],
            "error": None,
        }
        base.update(overrides)
        return base

    def test_success_logs_context_ready(self, tmp_path):
        app = self._make_app(tmp_path)
        log: list[str] = []
        app._log_event = lambda msg: log.append(msg)  # type: ignore[method-assign]

        class FakeStatic:
            def update(self, text):
                pass

        app.query_one = lambda sel, *_: FakeStatic()
        app._on_context_done(self._preview())
        assert any("context ready" in m.lower() or "Context ready" in m for m in log)

    def test_error_logs_failure(self, tmp_path):
        app = self._make_app(tmp_path)
        log: list[str] = []
        app._log_event = lambda msg: log.append(msg)  # type: ignore[method-assign]
        app._on_context_done(self._preview(error="disk full"))
        assert any("failed" in m.lower() or "disk full" in m for m in log)

    def test_error_does_not_update_center(self, tmp_path):
        app = self._make_app(tmp_path)
        app._log_event = lambda msg: None  # type: ignore[method-assign]
        updates: list[str] = []

        class TrackingStatic:
            def update(self, text):
                updates.append(text)

        app.query_one = lambda sel, *_: TrackingStatic()
        app._on_context_done(self._preview(error="bad"))
        assert updates == []

    def test_success_does_not_raise_when_query_fails(self, tmp_path):
        app = self._make_app(tmp_path)
        log: list[str] = []
        app._log_event = lambda msg: log.append(msg)  # type: ignore[method-assign]

        def _raise(*a, **kw):
            raise RuntimeError("no widget")

        app.query_one = _raise
        # Should not propagate exception
        app._on_context_done(self._preview())

    def test_preview_text_written_to_log(self, tmp_path):
        app = self._make_app(tmp_path)
        log: list[str] = []
        app._log_event = lambda msg: log.append(msg)  # type: ignore[method-assign]

        class FakeStatic:
            def update(self, text):
                pass

        app.query_one = lambda sel, *_: FakeStatic()
        app._on_context_done(self._preview())
        combined = "\n".join(log)
        assert "context_pack.md" in combined


# ---------------------------------------------------------------------------
# _on_context_error
# ---------------------------------------------------------------------------


class TestOnContextError:
    def test_logs_error_message(self, tmp_path):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp
        from vibecode.repo_status import RepoStatus

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")

        log: list[str] = []
        status = RepoStatus(repo_path=tmp_path)
        app = VibecodeMainApp(repo_path=tmp_path, status=status)
        app._log_event = lambda msg: log.append(msg)  # type: ignore[method-assign]
        app._on_context_error("something went wrong")
        assert any("something went wrong" in m for m in log)


# ---------------------------------------------------------------------------
# action_cmd_context — missing .vibecode warns without push_screen
# ---------------------------------------------------------------------------


class TestActionCmdContextMissingVibecode:
    def test_logs_warning_when_vibecode_missing(self, tmp_path):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp
        from vibecode.repo_status import RepoStatus

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")

        # tmp_path has no .vibecode directory
        log: list[str] = []
        status = RepoStatus(repo_path=tmp_path)
        app = VibecodeMainApp(repo_path=tmp_path, status=status)
        app._log_event = lambda msg: log.append(msg)  # type: ignore[method-assign]

        push_calls: list = []
        app.push_screen = lambda *a, **kw: push_calls.append(a)  # type: ignore[method-assign]

        app.action_cmd_context()

        assert push_calls == [], "push_screen should not be called when .vibecode is missing"
        assert any(".vibecode" in m for m in log)

    def test_does_not_raise_when_vibecode_missing(self, tmp_path):
        from vibecode.main_app import _TEXTUAL_AVAILABLE, VibecodeMainApp
        from vibecode.repo_status import RepoStatus

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")

        status = RepoStatus(repo_path=tmp_path)
        app = VibecodeMainApp(repo_path=tmp_path, status=status)
        app._log_event = lambda msg: None  # type: ignore[method-assign]
        app.push_screen = lambda *a, **kw: None  # type: ignore[method-assign]
        app.action_cmd_context()  # Must not raise


# ---------------------------------------------------------------------------
# action_cmd_context — .vibecode present pushes screen
# ---------------------------------------------------------------------------


class TestActionCmdContextWithVibecode:
    def test_pushes_context_input_screen(self, tmp_path):
        from vibecode.main_app import (
            ContextInputScreen,
            _TEXTUAL_AVAILABLE,
            VibecodeMainApp,
        )
        from vibecode.repo_status import RepoStatus

        if not _TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")

        (tmp_path / ".vibecode").mkdir()
        log: list[str] = []
        status = RepoStatus(repo_path=tmp_path)
        app = VibecodeMainApp(repo_path=tmp_path, status=status)
        app._log_event = lambda msg: log.append(msg)  # type: ignore[method-assign]

        pushed: list = []
        app.push_screen = lambda screen, cb=None: pushed.append((screen, cb))  # type: ignore[method-assign]

        app.action_cmd_context()

        assert len(pushed) == 1
        screen, cb = pushed[0]
        assert isinstance(screen, ContextInputScreen)
        assert cb is not None
