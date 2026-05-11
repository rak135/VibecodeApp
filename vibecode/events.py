"""Observable run event spine.

Provides a lightweight event model, sink interface, and standard
implementations (in-memory, JSONL, console, multi, and null).

This module is dependency-light. It does not import high-level run, guard,
check, handoff, or context modules.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path
from typing import Any, Protocol


class EventLevel(IntEnum):
    """Event severity levels (ordered: DEBUG < INFO < WARNING < ERROR)."""

    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40


#: Run lifecycle event — session started, phase entered, etc.
EVENT_RUN_LIFECYCLE = "run.lifecycle"
#: Context pack build event.
EVENT_CONTEXT = "run.context"
#: Platform prompt generation event.
EVENT_PROMPT = "run.prompt"
#: Agent process event (spawn, stdout, stderr, exit).
EVENT_AGENT_PROCESS = "run.agent_process"
#: MCP (Model Context Protocol) tool event.
EVENT_MCP = "run.mcp"
#: Git delta / diff event.
EVENT_GIT_DELTA = "run.git_delta"
#: Git preflight / working-tree inspection event.
EVENT_GIT_PREFLIGHT = "run.git_preflight"
#: Index freshness check / generation event.
EVENT_INDEX_CHECK = "run.index_check"
#: Guard evaluation event.
EVENT_GUARD = "run.guard"
#: Required checks event.
EVENT_CHECK = "run.check"
#: Handoff validation event.
EVENT_HANDOFF = "run.handoff"
#: Run summary / terminal event.
EVENT_SUMMARY = "run.summary"


@dataclass(frozen=True)
class VibecodeEvent:
    """A single observable event within a run session.

    All fields are simple JSON-compatible types (strings, numbers, dicts,
    lists, ``None``).  The ``data`` dict must only contain JSON-compatible
    values; non-JSON values should be converted before constructing the
    event.
    """

    event_id: str
    session_id: str
    timestamp: datetime
    type: str
    level: EventLevel
    message: str
    data: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dictionary representation."""
        d: dict[str, Any] = {}
        d["event_id"] = self.event_id
        d["session_id"] = self.session_id
        d["timestamp"] = self.timestamp.isoformat()
        d["type"] = self.type
        d["level"] = self.level.name
        d["level_value"] = self.level.value
        d["message"] = self.message
        if self.data is not None:
            d["data"] = self.data
        return d

    def as_json(self) -> str:
        """Return a compact JSON string with deterministically ordered keys."""
        return json.dumps(self.as_dict(), sort_keys=True, default=_json_fallback)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> VibecodeEvent:
        """Reconstruct an event from a serialised dictionary."""
        return cls(
            event_id=d["event_id"],
            session_id=d["session_id"],
            timestamp=datetime.fromisoformat(d["timestamp"]),
            type=d["type"],
            level=EventLevel[d["level"]],
            message=d["message"],
            data=d.get("data"),
        )

    @classmethod
    def from_json(cls, text: str) -> VibecodeEvent:
        """Reconstruct an event from a JSON string (one object)."""
        return cls.from_dict(json.loads(text))


def _json_fallback(obj: Any) -> Any:
    """Fallback serialiser for non-JSON objects inside ``data``."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, os.PathLike):
        return str(obj)
    if isinstance(obj, (set, frozenset)):
        return sorted(obj)
    raise TypeError(f"Cannot serialise {type(obj).__name__} to JSON; convert it first")


class EventSink(Protocol):
    """Protocol for objects that can receive events."""

    def emit(self, event: VibecodeEvent) -> None:
        """Receive and process a single event."""
        ...


class InMemoryEventSink:
    """Captures events in a list for test inspection."""

    def __init__(self) -> None:
        self.events: list[VibecodeEvent] = []

    def emit(self, event: VibecodeEvent) -> None:
        self.events.append(event)

    def clear(self) -> None:
        self.events.clear()

    def events_by_type(self, type_: str) -> list[VibecodeEvent]:
        return [e for e in self.events if e.type == type_]

    def events_by_level(self, level: EventLevel) -> list[VibecodeEvent]:
        return [e for e in self.events if e.level == level]


class JsonlEventSink:
    """Appends one JSON object per line to a file."""

    def __init__(self, file_path: str | Path) -> None:
        self._path = Path(file_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def emit(self, event: VibecodeEvent) -> None:
        line = event.as_json()
        with self._path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


class ConsoleEventSink:
    """Prints compact readable event lines to stderr (or a custom stream)."""

    def __init__(self, *, stream: Any = None, verbose: bool = False) -> None:
        import sys

        self._stream = stream or sys.stderr
        self._verbose = verbose

    def emit(self, event: VibecodeEvent) -> None:
        ts = event.timestamp.strftime("%H:%M:%S")
        prefix = f"[{ts}] {event.level.name:8s} {event.type:20s}"
        if self._verbose:
            prefix += f" {event.event_id[:8]}"
        if event.data and self._verbose:
            payload = json.dumps(event.data, sort_keys=True, default=_json_fallback)
            print(f"{prefix} {event.message} {payload}", file=self._stream)
        else:
            print(f"{prefix} {event.message}", file=self._stream)


class MultiEventSink:
    """Fans out events to multiple sinks."""

    def __init__(self, sinks: list[EventSink] | None = None) -> None:
        self._sinks: list[EventSink] = list(sinks) if sinks else []

    def add_sink(self, sink: EventSink) -> None:
        self._sinks.append(sink)

    def emit(self, event: VibecodeEvent) -> None:
        for sink in self._sinks:
            sink.emit(event)


class NullEventSink:
    """Discards all events. Useful as a default for call sites that may
    not have a configured sink."""

    def emit(self, event: VibecodeEvent) -> None:
        pass


def create_event(
    session_id: str,
    type_: str,
    level: EventLevel,
    message: str,
    *,
    data: dict[str, Any] | None = None,
    timestamp: datetime | None = None,
) -> VibecodeEvent:
    """Create a ``VibecodeEvent`` with an auto-generated id and current
    timestamp.

    Args:
        session_id: Run session identifier (from ``run.py`` metadata).
        type_: Event type string (use the ``EVENT_*`` constants).
        level: Severity level.
        message: Human-readable event description.
        data: Optional payload (must be JSON-compatible).
        timestamp: Override for deterministic tests.
    """
    event_id = uuid.uuid4().hex
    ts = timestamp if timestamp is not None else datetime.now(tz=timezone.utc)
    return VibecodeEvent(
        event_id=event_id,
        session_id=session_id,
        timestamp=ts,
        type=type_,
        level=level,
        message=message,
        data=data or None,
    )
