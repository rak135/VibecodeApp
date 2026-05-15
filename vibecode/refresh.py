"""VibecodeRefreshService: programmatic refresh/rebuild of the Vibecode disposable layer.

This module provides a service that can safely rebuild the disposable Vibecode
layer (.vibecode/index/*, .vibecode/current/*, etc.) while preserving all
human-maintained project truth files.

It does NOT depend on Textual or any external agent runtime and is designed
to be called from the TUI, CLI, or tests.

Preservation invariants:
- Human-maintained files are NEVER overwritten.
- .vibecode/logs/* and .vibecode/runs/* are NEVER deleted.
- Deletion uses an allowlist, not broad filesystem patterns.
"""

from __future__ import annotations

import io
import json
import shutil
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace


# Individual generated index files that may be deleted and regenerated (allowlist).
_DISPOSABLE_INDEX_FILES: tuple[str, ...] = (
    ".vibecode/index/file_inventory.json",
    ".vibecode/index/symbol_map.json",
    ".vibecode/index/dependency_map.json",
    ".vibecode/index/test_map.json",
    ".vibecode/index/entrypoints.md",
    ".vibecode/index/risky_files.md",
    ".vibecode/index/repo_tree.generated.md",
    ".vibecode/index/risk_report.json",
)

# Directories whose *entire contents* are disposable.
# Note: .vibecode/logs/* and .vibecode/runs/* are intentionally excluded.
_DISPOSABLE_DIR_CONTENTS: tuple[str, ...] = (
    ".vibecode/current",
    ".vibecode/generated",
    ".vibecode/cache",
    ".vibecode/tmp",
)


@dataclass
class RefreshReport:
    """Structured result from :meth:`VibecodeRefreshService.refresh`."""

    repo_path: str
    vibecode_existed: bool
    preserved_manual_files: list[str] = field(default_factory=list)
    created_missing_manual_files: list[str] = field(default_factory=list)
    disposable_removed: list[str] = field(default_factory=list)
    generated_artifacts: list[str] = field(default_factory=list)
    validation_status: str = "skipped"
    validation_summary: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    next_recommended_action: str = ""

    def as_dict(self) -> dict:
        """Return a plain-dict representation suitable for JSON serialisation or TUI display."""
        return {
            "repo_path": self.repo_path,
            "vibecode_existed": self.vibecode_existed,
            "preserved_manual_files": self.preserved_manual_files,
            "created_missing_manual_files": self.created_missing_manual_files,
            "disposable_removed": self.disposable_removed,
            "generated_artifacts": self.generated_artifacts,
            "validation_status": self.validation_status,
            "validation_summary": self.validation_summary,
            "warnings": self.warnings,
            "errors": self.errors,
            "next_recommended_action": self.next_recommended_action,
        }


class VibecodeRefreshService:
    """Rebuild the Vibecode disposable layer for a repository.

    Usage::

        from vibecode.refresh import VibecodeRefreshService
        report = VibecodeRefreshService(repo_root).refresh()

    The service is stateless after construction and safe to call multiple times.
    """

    def __init__(self, repo_root: Path) -> None:
        self._root = Path(repo_root).resolve()

    def refresh(self) -> RefreshReport:
        """Run a full refresh and return a structured :class:`RefreshReport`.

        Steps:
        1. Ensure ``.vibecode/`` exists; create from defaults when missing.
        2. Create any human-maintained truth files that are absent (never overwrite).
        3. Clean allowlisted disposable paths.
        4. Regenerate index, inventory, and risk outputs via ``cmd_index``.
        5. Capture validation results written by ``cmd_index``.
        6. Return a structured report.
        """
        root = self._root
        report = RefreshReport(
            repo_path=root.as_posix(),
            vibecode_existed=(root / ".vibecode").exists(),
        )

        self._ensure_vibecode(root, report)
        self._clean_disposable(root, report)
        self._run_index(root, report)
        report.next_recommended_action = _recommend(report)
        return report

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure_vibecode(self, root: Path, report: RefreshReport) -> None:
        """Ensure ``.vibecode/`` is fully initialised with no overwrites."""
        from vibecode.project import _GENERATED_DIRS, _file_templates
        from vibecode.permissions import PROFILES, profile_path, write_profile

        vibecode_dir = root / ".vibecode"
        project_id = root.name.lower().replace(" ", "_")
        project_name = root.name

        if (vibecode_dir / "project.yaml").exists():
            try:
                from vibecode.config import load_config
                cfg = load_config(vibecode_dir)
                project_id = cfg.project_id
                project_name = cfg.project_name
            except Exception:  # noqa: BLE001
                pass

        for rel_dir in _GENERATED_DIRS:
            (root / Path(rel_dir)).mkdir(parents=True, exist_ok=True)

        templates = _file_templates(project_id, project_name, root)
        for rel_path, content in templates.items():
            target = root / Path(rel_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                report.preserved_manual_files.append(rel_path)
            else:
                target.write_text(content, encoding="utf-8")
                report.created_missing_manual_files.append(rel_path)

        for profile_name, profile_data in PROFILES.items():
            rel = profile_path(profile_name)
            target = root / Path(rel)
            if target.exists():
                report.preserved_manual_files.append(rel)
            elif write_profile(root, profile_name, profile_data, force=False):
                report.created_missing_manual_files.append(rel)

    def _clean_disposable(self, root: Path, report: RefreshReport) -> None:
        """Delete allowlisted disposable files and directory contents."""
        for rel_dir in _DISPOSABLE_DIR_CONTENTS:
            dir_path = root / Path(rel_dir)
            if not dir_path.is_dir():
                continue
            for child in list(dir_path.iterdir()):
                rel = child.relative_to(root).as_posix()
                try:
                    if child.is_dir():
                        shutil.rmtree(child)
                    else:
                        child.unlink()
                    report.disposable_removed.append(rel)
                except OSError as exc:
                    report.warnings.append(f"Could not remove {rel}: {exc}")

        for rel in _DISPOSABLE_INDEX_FILES:
            target = root / Path(rel)
            if target.is_file():
                try:
                    target.unlink()
                    report.disposable_removed.append(rel)
                except OSError as exc:
                    report.warnings.append(f"Could not remove {rel}: {exc}")

    def _run_index(self, root: Path, report: RefreshReport) -> None:
        """Run ``cmd_index`` (which includes validation) and capture results."""
        from vibecode.indexer import cmd_index

        args = SimpleNamespace(repo_root=str(root))
        stderr_buf = io.StringIO()
        try:
            with redirect_stdout(io.StringIO()), redirect_stderr(stderr_buf):
                rc = cmd_index(args)
        except Exception as exc:  # noqa: BLE001
            report.errors.append(f"Index failed with exception: {exc}")
            self._read_validation_from_disk(root, report)
            return

        # Extract artifact names from "written to <path>" lines in captured stderr.
        for line in stderr_buf.getvalue().splitlines():
            lowered = line.lower()
            if "written to" in lowered:
                parts = line.split("written to", 1)
                if len(parts) == 2:
                    artifact = parts[1].strip()
                    if artifact:
                        report.generated_artifacts.append(artifact)

        self._read_validation_from_disk(root, report)

        if rc != 0 and not report.errors:
            report.warnings.append(
                "Index completed with non-zero exit (check validation for details)"
            )

    def _read_validation_from_disk(self, root: Path, report: RefreshReport) -> None:
        """Read the ``validation.json`` written by ``cmd_index`` into the report."""
        validation_path = root / ".vibecode" / "current" / "validation.json"
        if not validation_path.exists():
            report.validation_status = "skipped"
            return
        try:
            data = json.loads(validation_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            report.warnings.append(f"Could not read validation report: {exc}")
            report.validation_status = "skipped"
            return

        report.validation_summary = data.get("summary", {})
        report.validation_status = data.get("status", "error")

        existing_errors: set[str] = set(report.errors)
        existing_warnings: set[str] = set(report.warnings)
        for item in data.get("items", []):
            msg = item.get("message", "")
            if item.get("level") == "ERROR" and msg not in existing_errors:
                report.errors.append(msg)
                existing_errors.add(msg)
            elif item.get("level") == "WARN" and msg not in existing_warnings:
                report.warnings.append(msg)
                existing_warnings.add(msg)


def _recommend(report: RefreshReport) -> str:
    if report.errors:
        return "Review errors in the refresh report and fix before proceeding."
    if report.warnings:
        return (
            "Refresh completed with warnings. "
            "Fill in unfilled architecture templates for full agent context."
        )
    return "Vibecode layer is up to date. Ready for agent session."
