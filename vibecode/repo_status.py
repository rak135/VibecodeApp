"""Repository status model and service.

Provides :class:`RepoStatus` (data model) and :class:`RepoStatusService`
(computation) so the TUI can display repo health without launching any UI or
calling an LLM.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

GitStateStr = Literal["clean", "dirty", "unknown"]
IndexFreshnessStr = Literal["fresh", "stale", "missing"]

_MANUAL_TRUTH_FILES: tuple[str, ...] = (
    ".vibecode/project.yaml",
    ".vibecode/architecture/OVERVIEW.md",
    ".vibecode/architecture/INVARIANTS.md",
    ".vibecode/architecture/STRUCTURE.md",
    ".vibecode/architecture/MODULE_BOUNDARIES.md",
    ".vibecode/architecture/PROTECTED_AREAS.md",
    ".vibecode/architecture/DATA_FLOW.md",
    ".vibecode/checks/required_checks.yaml",
    ".vibecode/handoff/NOW.md",
    ".vibecode/handoff/NEXT.md",
    ".vibecode/handoff/BLOCKERS.md",
    ".vibecode/agents/safe.json",
    ".vibecode/agents/fast.json",
    ".vibecode/agents/audit.json",
    ".vibecode/history/README.md",
    ".vibecode/index/README.md",
    ".vibecode/index/schema.json",
)

_GENERATED_INDEX_FILES: tuple[str, ...] = (
    ".vibecode/index/file_inventory.json",
    ".vibecode/index/symbol_map.json",
    ".vibecode/index/dependency_map.json",
    ".vibecode/index/test_map.json",
    ".vibecode/index/entrypoints.md",
    ".vibecode/index/risky_files.md",
    ".vibecode/index/repo_tree.generated.md",
    ".vibecode/index/risk_report.json",
    ".vibecode/current/last_index.json",
)


@dataclass
class RepoStatus:
    """Current status snapshot of a vibecode repository."""

    repo_path: Path
    vibecode_dir_exists: bool = False
    manual_truth: dict[str, bool] = field(default_factory=dict)
    generated_index: dict[str, bool] = field(default_factory=dict)
    context_pack_exists: bool = False
    opencode_prompt_exists: bool = False
    check_results_exist: bool = False
    git_state: GitStateStr = "unknown"
    index_freshness: IndexFreshnessStr = "missing"

    @property
    def manual_truth_count(self) -> int:
        """Number of manual truth files that are present."""
        return sum(1 for v in self.manual_truth.values() if v)

    @property
    def generated_index_count(self) -> int:
        """Number of generated index files that are present."""
        return sum(1 for v in self.generated_index.values() if v)


class RepoStatusService:
    """Compute repo status without launching any UI or calling an LLM."""

    def get_status(self, repo_path: Path) -> RepoStatus:
        """Return a :class:`RepoStatus` snapshot for *repo_path*."""
        status = RepoStatus(repo_path=repo_path)
        vdir = repo_path / ".vibecode"
        status.vibecode_dir_exists = vdir.is_dir()
        status.manual_truth = {p: (repo_path / p).exists() for p in _MANUAL_TRUTH_FILES}
        status.generated_index = {p: (repo_path / p).exists() for p in _GENERATED_INDEX_FILES}
        current = repo_path / ".vibecode" / "current"
        status.context_pack_exists = (current / "context_pack.md").exists()
        status.opencode_prompt_exists = (current / "opencode_prompt.md").exists()
        status.check_results_exist = (current / "check_results.json").exists()
        status.git_state = self._compute_git_state(repo_path)
        status.index_freshness = self._compute_index_freshness(repo_path)
        return status

    def _compute_git_state(self, repo_path: Path) -> GitStateStr:
        try:
            result = subprocess.run(
                ["git", "status", "--short"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode != 0:
                return "unknown"
            return "dirty" if result.stdout.strip() else "clean"
        except (OSError, subprocess.SubprocessError):
            return "unknown"

    def _compute_index_freshness(self, repo_path: Path) -> IndexFreshnessStr:
        last_index = repo_path / ".vibecode" / "current" / "last_index.json"
        file_inventory = repo_path / ".vibecode" / "index" / "file_inventory.json"
        if not last_index.exists() or not file_inventory.exists():
            return "missing"
        try:
            from vibecode.indexer import check_index_freshness

            is_fresh, _ = check_index_freshness(repo_path)
            return "fresh" if is_fresh else "stale"
        except Exception:
            # Best-effort: if freshness cannot be determined, assume fresh.
            return "fresh"
