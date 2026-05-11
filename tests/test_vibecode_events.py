"""Tests for vibecode.events — event model, sinks, and serialisation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from vibecode.events import (
    EVENT_AGENT_PROCESS,
    EVENT_CHECK,
    EVENT_CONTEXT,
    EVENT_GIT_DELTA,
    EVENT_GUARD,
    EVENT_HANDOFF,
    EVENT_MCP,
    EVENT_PROMPT,
    EVENT_RUN_LIFECYCLE,
    EVENT_SUMMARY,
    ConsoleEventSink,
    EventLevel,
    EventSink,
    InMemoryEventSink,
    JsonlEventSink,
    MultiEventSink,
    NullEventSink,
    VibecodeEvent,
    _json_fallback,
    create_event,
)


FROZEN_TS = datetime(2026, 5, 11, 12, 0, 0, tzinfo=timezone.utc)
SESSION = "sess-001"


def _make_event(**overrides: object) -> VibecodeEvent:
    kwargs: dict[str, object] = {
        "event_id": "evt-1",
        "session_id": SESSION,
        "timestamp": FROZEN_TS,
        "type": EVENT_RUN_LIFECYCLE,
        "level": EventLevel.INFO,
        "message": "hello",
    }
    kwargs.update(overrides)
    return VibecodeEvent(**kwargs)  # type: ignore[arg-type]


# ── VibecodeEvent ──────────────────────────────────────────────────────


def test_event_creation_defaults():
    e = _make_event()
    assert e.event_id == "evt-1"
    assert e.session_id == SESSION
    assert e.timestamp == FROZEN_TS
    assert e.type == EVENT_RUN_LIFECYCLE
    assert e.level == EventLevel.INFO
    assert e.message == "hello"
    assert e.data is None


def test_event_with_data():
    e = _make_event(data={"key": "value"})
    assert e.data == {"key": "value"}


def test_event_immutable():
    e = _make_event()
    with pytest.raises(Exception):
        e.type = "other"  # type: ignore[misc]


# ── as_dict / as_json / from_dict / from_json roundtrip ───────────────


def test_as_dict_structure():
    d = _make_event(data={"x": 1}).as_dict()
    assert d["event_id"] == "evt-1"
    assert d["session_id"] == SESSION
    assert d["timestamp"] == "2026-05-11T12:00:00+00:00"
    assert d["type"] == EVENT_RUN_LIFECYCLE
    assert d["level"] == "INFO"
    assert d["level_value"] == 20
    assert d["message"] == "hello"
    assert d["data"] == {"x": 1}


def test_as_dict_no_data():
    d = _make_event().as_dict()
    assert "data" not in d


def test_as_json_deterministic():
    a = _make_event(data={"a": 1, "b": 2}).as_json()
    b = _make_event(data={"b": 2, "a": 1}).as_json()
    assert a == b


def test_as_json_valid_json():
    text = _make_event(data={"nested": {"k": "v"}}).as_json()
    parsed = json.loads(text)
    assert parsed["event_id"] == "evt-1"
    assert parsed["data"] == {"nested": {"k": "v"}}


def test_roundtrip_via_dict():
    original = _make_event(data={"items": [1, 2, 3]})
    recreated = VibecodeEvent.from_dict(original.as_dict())
    assert recreated == original


def test_roundtrip_via_json():
    original = _make_event(data={"items": [1, 2, 3]})
    recreated = VibecodeEvent.from_json(original.as_json())
    assert recreated == original


def test_roundtrip_no_data():
    original = _make_event()
    recreated = VibecodeEvent.from_dict(original.as_dict())
    assert recreated == original


# ── EventLevel ordering ───────────────────────────────────────────────


def test_event_level_ordering():
    assert EventLevel.DEBUG < EventLevel.INFO < EventLevel.WARNING < EventLevel.ERROR


# ── Event type constants ──────────────────────────────────────────────


def test_event_type_constants():
    assert EVENT_RUN_LIFECYCLE == "run.lifecycle"
    assert EVENT_CONTEXT == "run.context"
    assert EVENT_PROMPT == "run.prompt"
    assert EVENT_AGENT_PROCESS == "run.agent_process"
    assert EVENT_MCP == "run.mcp"
    assert EVENT_GIT_DELTA == "run.git_delta"
    assert EVENT_GUARD == "run.guard"
    assert EVENT_CHECK == "run.check"
    assert EVENT_HANDOFF == "run.handoff"
    assert EVENT_SUMMARY == "run.summary"


# ── create_event helper ───────────────────────────────────────────────


def test_create_event_basic():
    e = create_event(SESSION, EVENT_GUARD, EventLevel.WARNING, "guard warning")
    assert e.session_id == SESSION
    assert e.type == EVENT_GUARD
    assert e.level == EventLevel.WARNING
    assert e.message == "guard warning"
    assert len(e.event_id) == 32  # uuid4 hex
    assert e.timestamp is not None
    assert e.data is None


def test_create_event_with_data():
    e = create_event(
        SESSION,
        EVENT_CHECK,
        EventLevel.INFO,
        "check passed",
        data={"command": "pytest"},
    )
    assert e.data == {"command": "pytest"}


def test_create_event_custom_timestamp():
    e = create_event(SESSION, EVENT_GUARD, EventLevel.ERROR, "err", timestamp=FROZEN_TS)
    assert e.timestamp == FROZEN_TS


# ── InMemoryEventSink ─────────────────────────────────────────────────


def test_in_memory_sink_capture():
    sink = InMemoryEventSink()
    e1 = _make_event(event_id="e1")
    e2 = _make_event(event_id="e2", type=EVENT_GUARD)
    sink.emit(e1)
    sink.emit(e2)
    assert len(sink.events) == 2
    assert sink.events[0].event_id == "e1"
    assert sink.events[1].event_id == "e2"


def test_in_memory_sink_events_by_type():
    sink = InMemoryEventSink()
    sink.emit(_make_event(event_id="e1", type=EVENT_GUARD))
    sink.emit(_make_event(event_id="e2", type=EVENT_CHECK))
    sink.emit(_make_event(event_id="e3", type=EVENT_GUARD))
    assert len(sink.events_by_type(EVENT_GUARD)) == 2
    assert len(sink.events_by_type(EVENT_CHECK)) == 1


def test_in_memory_sink_events_by_level():
    sink = InMemoryEventSink()
    sink.emit(_make_event(event_id="e1", level=EventLevel.ERROR))
    sink.emit(_make_event(event_id="e2", level=EventLevel.INFO))
    sink.emit(_make_event(event_id="e3", level=EventLevel.ERROR))
    assert len(sink.events_by_level(EventLevel.ERROR)) == 2
    assert len(sink.events_by_level(EventLevel.INFO)) == 1


def test_in_memory_sink_clear():
    sink = InMemoryEventSink()
    sink.emit(_make_event())
    sink.clear()
    assert len(sink.events) == 0


# ── JsonlEventSink ────────────────────────────────────────────────────


def test_jsonl_sink_append(tmp_path: Path):
    path = tmp_path / "events.jsonl"
    sink = JsonlEventSink(path)
    sink.emit(_make_event(event_id="e1"))
    sink.emit(_make_event(event_id="e2"))

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    obj1 = json.loads(lines[0])
    obj2 = json.loads(lines[1])
    assert obj1["event_id"] == "e1"
    assert obj2["event_id"] == "e2"


def test_jsonl_sink_creates_parent_directories(tmp_path: Path):
    path = tmp_path / "sub" / "nested" / "events.jsonl"
    sink = JsonlEventSink(path)
    sink.emit(_make_event())
    assert path.exists()


def test_jsonl_sink_line_is_valid_json(tmp_path: Path):
    path = tmp_path / "events.jsonl"
    sink = JsonlEventSink(path)
    sink.emit(_make_event(data={"list": [1, 2, 3], "nested": {"a": True}}))
    line = path.read_text(encoding="utf-8").strip()
    obj = json.loads(line)
    assert obj["data"] == {"list": [1, 2, 3], "nested": {"a": True}}


# ── ConsoleEventSink ─────────────────────────────────────────────────


def test_console_sink_writes_to_stream():
    import io

    buf = io.StringIO()
    sink = ConsoleEventSink(stream=buf)
    sink.emit(_make_event(message="test message"))
    output = buf.getvalue()
    assert "test message" in output
    assert "INFO" in output


def test_console_sink_verbose_includes_data():
    import io

    buf = io.StringIO()
    sink = ConsoleEventSink(stream=buf, verbose=True)
    sink.emit(_make_event(message="verbose test", data={"detail": 42}))
    output = buf.getvalue()
    assert "verbose test" in output
    assert '"detail": 42' in output


# ── MultiEventSink ────────────────────────────────────────────────────


def test_multi_sink_fan_out():
    mem1 = InMemoryEventSink()
    mem2 = InMemoryEventSink()
    multi = MultiEventSink([mem1, mem2])
    e = _make_event()
    multi.emit(e)
    assert len(mem1.events) == 1
    assert len(mem2.events) == 1
    assert mem1.events[0] is e
    assert mem2.events[0] is e


def test_multi_sink_add_sink():
    mem = InMemoryEventSink()
    multi = MultiEventSink()
    multi.add_sink(mem)
    multi.emit(_make_event())
    assert len(mem.events) == 1


def test_multi_sink_empty():
    multi = MultiEventSink()
    multi.emit(_make_event())  # should not raise


# ── NullEventSink ─────────────────────────────────────────────────────


def test_null_sink_noop():
    sink = NullEventSink()
    sink.emit(_make_event())  # should not raise


# ── _json_fallback ────────────────────────────────────────────────────


def test_json_fallback_datetime():
    ts = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    assert _json_fallback(ts) == "2026-05-11T12:00:00+00:00"


def test_json_fallback_path():
    from pathlib import PurePosixPath, PureWindowsPath

    p = PurePosixPath("/a/b")
    assert _json_fallback(p) == "/a/b"


def test_json_fallback_set():
    assert _json_fallback({3, 1, 2}) == [1, 2, 3]


def test_json_fallback_frozenset():
    assert _json_fallback(frozenset({3, 1, 2})) == [1, 2, 3]


def test_json_fallback_unknown_type_raises():
    class Custom:
        pass

    with pytest.raises(TypeError, match="Cannot serialise"):
        _json_fallback(Custom())


# ── non-serialisable data handling ────────────────────────────────────


def test_event_with_non_json_data_fails_at_serialize():
    """Passing a non-JSON value in data should fail during as_json()."""
    e = _make_event(data={"bad": object()})
    with pytest.raises(TypeError):
        e.as_json()


def test_event_with_datetime_in_data_serializes():
    """datetime in data should be converted via fallback."""
    ts = FROZEN_TS
    e = _make_event(data={"timestamp": ts})
    text = e.as_json()
    parsed = json.loads(text)
    assert parsed["data"]["timestamp"] == "2026-05-11T12:00:00+00:00"


def test_event_with_path_in_data_serializes():
    p = Path("tmp") / "log.txt"
    e = _make_event(data={"path": p})
    text = e.as_json()
    parsed = json.loads(text)
    assert parsed["data"]["path"] == str(p)


# ── protocol compatibility check ──────────────────────────────────────


def test_all_sinks_satisfy_protocol():
    """Verify that all sink classes conform to the EventSink protocol."""
    sinks: list[EventSink] = [
        InMemoryEventSink(),
        JsonlEventSink("test.jsonl"),
        ConsoleEventSink(),
        MultiEventSink(),
        NullEventSink(),
    ]
    for sink in sinks:
        sink.emit(_make_event())
    # Clean up the JSONL file created during this test
    Path("test.jsonl").unlink(missing_ok=True)
