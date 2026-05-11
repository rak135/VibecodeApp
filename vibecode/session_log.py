"""Run session artifact layer.

Provides a stable directory per observable run under
``.vibecode/runs/<session_id>/`` with well-defined paths for all standard
artifacts, plus safe helpers to snapshot current-session files into the run
directory.

This module is **additive**: it does not change or remove the existing
``.vibecode/current/`` behaviour.  Run-level snapshots live alongside, not
instead of, the shared current-session files.

Design notes
------------
* ``RunSession`` is a plain dataclass — no global state, no singletons.
* All path properties are computed from ``root`` + ``session_id``; the class
  does not cache them so callers always see the canonical path.
* Path objects use :class:`pathlib.Path` throughout; Windows-style separators
  are handled transparently by ``pathlib``.
* Parent directories are created on demand via :meth:`ensure_dir` or
  implicitly by :meth:`snapshot_current_file`.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from vibecode.events import JsonlEventSink


@dataclass
class RunSession:
    """Stable artifact directory for a single observable run.

    All path properties are derived from ``root`` and ``session_id`` and are
    safe to use on Windows — ``pathlib`` handles separator normalisation.

    Parameters
    ----------
    root:
        Absolute path to the repository root (the directory that contains
        ``.vibecode/``).
    session_id:
        A unique, stable identifier for this run
        (e.g. ``"20260511T200000000000Z"``).
    """

    root: Path
    session_id: str

    # ── Core directory ───────────────────────────────────────────────────

    @property
    def run_dir(self) -> Path:
        """Absolute path to the run artifact directory."""
        return self.root / ".vibecode" / "runs" / self.session_id

    def ensure_dir(self) -> Path:
        """Create the run directory tree if it does not already exist.

        Returns the :attr:`run_dir` path for convenience.
        """
        self.run_dir.mkdir(parents=True, exist_ok=True)
        return self.run_dir

    # ── Artifact paths ───────────────────────────────────────────────────

    @property
    def events_jsonl(self) -> Path:
        """Path for the JSONL event log (one JSON object per line)."""
        return self.run_dir / "events.jsonl"

    @property
    def summary_json(self) -> Path:
        """Path for the run summary JSON."""
        return self.run_dir / "summary.json"

    @property
    def opencode_prompt_md(self) -> Path:
        """Path for the snapshot of the platform prompt sent to the agent."""
        return self.run_dir / "opencode_prompt.md"

    @property
    def context_pack_md(self) -> Path:
        """Path for the snapshot of the context pack used for this run."""
        return self.run_dir / "context_pack.md"

    @property
    def guard_report_json(self) -> Path:
        """Path for the guard evaluation report (JSON)."""
        return self.run_dir / "guard_report.json"

    @property
    def guard_report_md(self) -> Path:
        """Path for the guard evaluation report (Markdown)."""
        return self.run_dir / "guard_report.md"

    @property
    def checks_report_json(self) -> Path:
        """Path for the required-checks report (JSON)."""
        return self.run_dir / "checks_report.json"

    @property
    def handoff_report_json(self) -> Path:
        """Path for the handoff validation report (JSON)."""
        return self.run_dir / "handoff_report.json"

    @property
    def handoff_report_md(self) -> Path:
        """Path for the handoff validation report (Markdown)."""
        return self.run_dir / "handoff_report.md"

    @property
    def agent_stdout_log(self) -> Path:
        """Path for the agent process standard-output log."""
        return self.run_dir / "agent_stdout.log"

    @property
    def agent_stderr_log(self) -> Path:
        """Path for the agent process standard-error log."""
        return self.run_dir / "agent_stderr.log"

    # ── Helpers ──────────────────────────────────────────────────────────

    def create_event_sink(self) -> JsonlEventSink:
        """Return a :class:`~vibecode.events.JsonlEventSink` for this session.

        Ensures the run directory exists before constructing the sink so that
        the parent directory is always present when the first event is written.
        """
        self.ensure_dir()
        return JsonlEventSink(self.events_jsonl)

    def snapshot_current_file(
        self,
        source: Path,
        dest: Path,
        *,
        missing_ok: bool = True,
    ) -> bool:
        """Copy *source* to *dest*, creating parent directories as needed.

        Parameters
        ----------
        source:
            Absolute path to the file to copy.
        dest:
            Absolute destination path (typically under :attr:`run_dir`).
        missing_ok:
            When ``True`` (default), silently return ``False`` if *source*
            does not exist.  When ``False``, raise
            :class:`FileNotFoundError`.

        Returns
        -------
        bool
            ``True`` when the file was copied; ``False`` when *source* was
            absent and *missing_ok* is ``True``.
        """
        if not source.exists():
            if missing_ok:
                return False
            raise FileNotFoundError(f"Snapshot source not found: {source}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        return True

    def snapshot_prompt(self, *, missing_ok: bool = True) -> bool:
        """Snapshot ``.vibecode/current/opencode_prompt.md`` into the run directory.

        Returns ``True`` if the file was copied, ``False`` if absent and
        *missing_ok* is ``True``.
        """
        source = self.root / ".vibecode" / "current" / "opencode_prompt.md"
        self.ensure_dir()
        return self.snapshot_current_file(source, self.opencode_prompt_md, missing_ok=missing_ok)

    def snapshot_context_pack(self, *, missing_ok: bool = True) -> bool:
        """Snapshot ``.vibecode/current/context_pack.md`` into the run directory.

        Returns ``True`` if the file was copied, ``False`` if absent and
        *missing_ok* is ``True``.
        """
        source = self.root / ".vibecode" / "current" / "context_pack.md"
        self.ensure_dir()
        return self.snapshot_current_file(source, self.context_pack_md, missing_ok=missing_ok)
