"""Tests for vibecode.session_log — run session artifact layer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecode.events import EventLevel, JsonlEventSink, VibecodeEvent, create_event
from vibecode.session_log import RunSession


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SESSION_ID = "20260511T200000000000Z"


def _make_session(tmp_path: Path, session_id: str = SESSION_ID) -> RunSession:
    return RunSession(root=tmp_path, session_id=session_id)


def _write(path: Path, content: str = "data") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# A — Construction and run_dir
# ---------------------------------------------------------------------------


def test_run_dir_path(tmp_path: Path):
    """run_dir is .vibecode/runs/<session_id>/ under the repo root."""
    rs = _make_session(tmp_path)
    expected = tmp_path / ".vibecode" / "runs" / SESSION_ID
    assert rs.run_dir == expected


def test_run_dir_not_created_on_access(tmp_path: Path):
    """Accessing run_dir does not create the directory."""
    rs = _make_session(tmp_path)
    assert not rs.run_dir.exists()


def test_ensure_dir_creates_directory(tmp_path: Path):
    """ensure_dir() creates the full directory tree."""
    rs = _make_session(tmp_path)
    returned = rs.ensure_dir()
    assert rs.run_dir.exists()
    assert rs.run_dir.is_dir()
    assert returned == rs.run_dir


def test_ensure_dir_idempotent(tmp_path: Path):
    """Calling ensure_dir() twice does not raise."""
    rs = _make_session(tmp_path)
    rs.ensure_dir()
    rs.ensure_dir()  # should not raise
    assert rs.run_dir.is_dir()


# ---------------------------------------------------------------------------
# B — Artifact paths
# ---------------------------------------------------------------------------

_EXPECTED_ARTIFACT_NAMES = [
    ("events_jsonl", "events.jsonl"),
    ("summary_json", "summary.json"),
    ("opencode_prompt_md", "opencode_prompt.md"),
    ("context_pack_md", "context_pack.md"),
    ("guard_report_json", "guard_report.json"),
    ("guard_report_md", "guard_report.md"),
    ("checks_report_json", "checks_report.json"),
    ("handoff_report_json", "handoff_report.json"),
    ("handoff_report_md", "handoff_report.md"),
    ("agent_stdout_log", "agent_stdout.log"),
    ("agent_stderr_log", "agent_stderr.log"),
]


@pytest.mark.parametrize("attr,filename", _EXPECTED_ARTIFACT_NAMES)
def test_artifact_path_is_under_run_dir(tmp_path: Path, attr: str, filename: str):
    """Each artifact path is inside run_dir with the expected filename."""
    rs = _make_session(tmp_path)
    path: Path = getattr(rs, attr)
    assert path.parent == rs.run_dir
    assert path.name == filename


def test_all_artifact_names_unique(tmp_path: Path):
    """No two artifacts share the same filename."""
    rs = _make_session(tmp_path)
    names = [getattr(rs, attr).name for attr, _ in _EXPECTED_ARTIFACT_NAMES]
    assert len(names) == len(set(names))


def test_artifact_paths_are_path_objects(tmp_path: Path):
    """All artifact properties return pathlib.Path instances."""
    rs = _make_session(tmp_path)
    for attr, _ in _EXPECTED_ARTIFACT_NAMES:
        assert isinstance(getattr(rs, attr), Path), f"{attr} is not a Path"


# ---------------------------------------------------------------------------
# C — create_event_sink
# ---------------------------------------------------------------------------


def test_create_event_sink_returns_jsonl_sink(tmp_path: Path):
    """create_event_sink() returns a JsonlEventSink."""
    rs = _make_session(tmp_path)
    sink = rs.create_event_sink()
    assert isinstance(sink, JsonlEventSink)


def test_create_event_sink_points_to_events_jsonl(tmp_path: Path):
    """The sink's path is the session events.jsonl."""
    rs = _make_session(tmp_path)
    sink = rs.create_event_sink()
    assert sink.path == rs.events_jsonl


def test_create_event_sink_creates_run_dir(tmp_path: Path):
    """create_event_sink() ensures the run directory exists."""
    rs = _make_session(tmp_path)
    rs.create_event_sink()
    assert rs.run_dir.is_dir()


def test_create_event_sink_emit_writes_jsonl(tmp_path: Path):
    """Emitting an event writes a JSONL line to events.jsonl."""
    rs = _make_session(tmp_path)
    sink = rs.create_event_sink()
    event = create_event(SESSION_ID, "run.lifecycle", EventLevel.INFO, "started")
    sink.emit(event)

    lines = rs.events_jsonl.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    obj = json.loads(lines[0])
    assert obj["session_id"] == SESSION_ID
    assert obj["message"] == "started"


def test_create_event_sink_emit_multiple_events(tmp_path: Path):
    """Multiple emits produce multiple JSONL lines."""
    rs = _make_session(tmp_path)
    sink = rs.create_event_sink()
    for i in range(3):
        sink.emit(create_event(SESSION_ID, "run.lifecycle", EventLevel.INFO, f"msg-{i}"))

    lines = rs.events_jsonl.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3


# ---------------------------------------------------------------------------
# D — snapshot_current_file
# ---------------------------------------------------------------------------


def test_snapshot_current_file_copies_file(tmp_path: Path):
    """snapshot_current_file copies an existing source to dest."""
    rs = _make_session(tmp_path)
    rs.ensure_dir()
    source = tmp_path / "src.md"
    source.write_text("hello", encoding="utf-8")
    dest = rs.run_dir / "copy.md"

    result = rs.snapshot_current_file(source, dest)

    assert result is True
    assert dest.read_text(encoding="utf-8") == "hello"


def test_snapshot_current_file_missing_ok_true(tmp_path: Path):
    """snapshot_current_file returns False (no error) when source is absent."""
    rs = _make_session(tmp_path)
    rs.ensure_dir()
    source = tmp_path / "nonexistent.md"
    dest = rs.run_dir / "copy.md"

    result = rs.snapshot_current_file(source, dest, missing_ok=True)

    assert result is False
    assert not dest.exists()


def test_snapshot_current_file_missing_ok_false_raises(tmp_path: Path):
    """snapshot_current_file raises FileNotFoundError when missing_ok=False."""
    rs = _make_session(tmp_path)
    rs.ensure_dir()
    source = tmp_path / "nonexistent.md"
    dest = rs.run_dir / "copy.md"

    with pytest.raises(FileNotFoundError, match="nonexistent.md"):
        rs.snapshot_current_file(source, dest, missing_ok=False)


def test_snapshot_current_file_creates_dest_parents(tmp_path: Path):
    """snapshot_current_file creates dest parent directories as needed."""
    rs = _make_session(tmp_path)
    source = tmp_path / "src.md"
    source.write_text("data", encoding="utf-8")
    dest = rs.run_dir / "nested" / "dir" / "copy.md"

    rs.snapshot_current_file(source, dest)

    assert dest.exists()
    assert dest.read_text(encoding="utf-8") == "data"


# ---------------------------------------------------------------------------
# E — snapshot_prompt and snapshot_context_pack
# ---------------------------------------------------------------------------


def test_snapshot_prompt_copies_when_present(tmp_path: Path):
    """snapshot_prompt copies opencode_prompt.md from current/."""
    current_dir = tmp_path / ".vibecode" / "current"
    current_dir.mkdir(parents=True)
    (current_dir / "opencode_prompt.md").write_text("prompt content", encoding="utf-8")

    rs = _make_session(tmp_path)
    result = rs.snapshot_prompt()

    assert result is True
    assert rs.opencode_prompt_md.read_text(encoding="utf-8") == "prompt content"


def test_snapshot_prompt_returns_false_when_absent(tmp_path: Path):
    """snapshot_prompt returns False when current opencode_prompt.md is absent."""
    rs = _make_session(tmp_path)
    result = rs.snapshot_prompt()
    assert result is False
    assert not rs.opencode_prompt_md.exists()


def test_snapshot_context_pack_copies_when_present(tmp_path: Path):
    """snapshot_context_pack copies context_pack.md from current/."""
    current_dir = tmp_path / ".vibecode" / "current"
    current_dir.mkdir(parents=True)
    (current_dir / "context_pack.md").write_text("## Context\ndata", encoding="utf-8")

    rs = _make_session(tmp_path)
    result = rs.snapshot_context_pack()

    assert result is True
    assert rs.context_pack_md.read_text(encoding="utf-8") == "## Context\ndata"


def test_snapshot_context_pack_returns_false_when_absent(tmp_path: Path):
    """snapshot_context_pack returns False when current context_pack.md is absent."""
    rs = _make_session(tmp_path)
    result = rs.snapshot_context_pack()
    assert result is False
    assert not rs.context_pack_md.exists()


def test_snapshot_prompt_creates_run_dir(tmp_path: Path):
    """snapshot_prompt ensures the run directory is created."""
    rs = _make_session(tmp_path)
    assert not rs.run_dir.exists()
    rs.snapshot_prompt()  # source absent but run_dir should still be created
    assert rs.run_dir.is_dir()


def test_snapshot_context_pack_creates_run_dir(tmp_path: Path):
    """snapshot_context_pack ensures the run directory is created."""
    rs = _make_session(tmp_path)
    assert not rs.run_dir.exists()
    rs.snapshot_context_pack()
    assert rs.run_dir.is_dir()


# ---------------------------------------------------------------------------
# F — Windows-safe path assumptions
# ---------------------------------------------------------------------------


def test_run_dir_uses_pathlib(tmp_path: Path):
    """run_dir is a pathlib.Path, not a bare string."""
    rs = _make_session(tmp_path)
    assert isinstance(rs.run_dir, Path)


def test_paths_contain_session_id(tmp_path: Path):
    """All artifact paths contain the session_id in their string representation."""
    rs = _make_session(tmp_path)
    for attr, _ in _EXPECTED_ARTIFACT_NAMES:
        path: Path = getattr(rs, attr)
        assert SESSION_ID in str(path), f"{attr} path does not contain session_id"


def test_different_session_ids_produce_different_dirs(tmp_path: Path):
    """Two RunSession instances with different session_ids have separate directories."""
    rs1 = RunSession(root=tmp_path, session_id="session-A")
    rs2 = RunSession(root=tmp_path, session_id="session-B")
    assert rs1.run_dir != rs2.run_dir
    rs1.ensure_dir()
    rs2.ensure_dir()
    assert rs1.run_dir.is_dir()
    assert rs2.run_dir.is_dir()


def test_run_dirs_are_independent(tmp_path: Path):
    """Files written into one session's run_dir do not appear in another."""
    rs1 = RunSession(root=tmp_path, session_id="sess-X")
    rs2 = RunSession(root=tmp_path, session_id="sess-Y")
    rs1.ensure_dir()
    rs2.ensure_dir()
    (rs1.run_dir / "marker.txt").write_text("x", encoding="utf-8")
    assert not (rs2.run_dir / "marker.txt").exists()
