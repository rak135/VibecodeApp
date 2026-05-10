"""Git working tree inspection helpers."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from vibecode.paths import strip_to_posix


def _sha1() -> str:
    """Return the current HEAD commit hash (short form), or 'unknown'."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return "unknown"
    except (OSError, subprocess.SubprocessError, FileNotFoundError):
        return "unknown"


def current_git_commit(repo_root: Path) -> str:
    """Return the current HEAD commit hash for *repo_root*, or 'unknown'."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


@dataclass(frozen=True)
class StatusPath:
    """A path reported by ``git status --short``."""

    path: str
    index_status: str
    worktree_status: str
    original_path: str | None = None

    @property
    def staged(self) -> bool:
        return self.index_status not in {" ", "?"}

    @property
    def unstaged(self) -> bool:
        return self.worktree_status != " " or self.untracked

    @property
    def untracked(self) -> bool:
        return self.index_status == "?" and self.worktree_status == "?"

    @property
    def deleted(self) -> bool:
        return "D" in {self.index_status, self.worktree_status}


@dataclass(frozen=True)
class GitState:
    """Current git change summary for a repository root."""

    is_git_repo: bool
    status_paths: tuple[StatusPath, ...] = ()
    changed_paths: tuple[str, ...] = ()
    staged_paths: tuple[str, ...] = ()
    unstaged_paths: tuple[str, ...] = ()
    untracked_paths: tuple[str, ...] = ()
    deleted_paths: tuple[str, ...] = ()
    diff_name_only: tuple[str, ...] = ()
    staged_diff_name_only: tuple[str, ...] = ()
    diff_stat: str = ""
    staged_diff_stat: str = ""
    error: str | None = None


def inspect_git_state(repo_root: Path) -> GitState:
    """Return changed-file state for *repo_root* without mutating git state.

    Non-git directories return an empty state with ``is_git_repo=False``. Other
    git command failures are captured on ``error`` so callers can decide whether
    to warn or fail.
    """

    root = repo_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Repository root does not exist: {root}")

    repo_check = _run_git(root, "rev-parse", "--is-inside-work-tree", timeout=5)
    if not repo_check.ok:
        if repo_check.error == "git executable not found":
            return GitState(is_git_repo=False, error=repo_check.error)
        return GitState(is_git_repo=False)
    if repo_check.stdout.strip().lower() != "true":
        return GitState(is_git_repo=False)

    status_result = _run_git(
        root,
        "status",
        "--short",
        "--untracked-files=all",
        timeout=10,
    )
    if not status_result.ok:
        return GitState(is_git_repo=True, error=status_result.error)

    parsed_status_paths = (
        _parse_status_line(line) for line in status_result.stdout.splitlines()
    )
    status_paths = tuple(entry for entry in parsed_status_paths if entry is not None)

    diff_name_result = _run_git(root, "diff", "--name-only", timeout=10)
    staged_name_result = _run_git(root, "diff", "--cached", "--name-only", timeout=10)
    diff_stat_result = _run_git(root, "diff", "--stat", timeout=10)
    staged_stat_result = _run_git(root, "diff", "--cached", "--stat", timeout=10)

    errors = [
        result.error
        for result in (
            diff_name_result,
            staged_name_result,
            diff_stat_result,
            staged_stat_result,
        )
        if not result.ok and result.error
    ]

    return GitState(
        is_git_repo=True,
        status_paths=status_paths,
        changed_paths=tuple(entry.path for entry in status_paths),
        staged_paths=tuple(entry.path for entry in status_paths if entry.staged),
        unstaged_paths=tuple(entry.path for entry in status_paths if entry.unstaged),
        untracked_paths=tuple(entry.path for entry in status_paths if entry.untracked),
        deleted_paths=tuple(entry.path for entry in status_paths if entry.deleted),
        diff_name_only=_paths_from_lines(diff_name_result.stdout if diff_name_result.ok else ""),
        staged_diff_name_only=_paths_from_lines(
            staged_name_result.stdout if staged_name_result.ok else ""
        ),
        diff_stat=diff_stat_result.stdout.strip() if diff_stat_result.ok else "",
        staged_diff_stat=staged_stat_result.stdout.strip() if staged_stat_result.ok else "",
        error="; ".join(errors) or None,
    )


@dataclass(frozen=True)
class _GitResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and self.error is None


def _run_git(root: Path, *args: str, timeout: int) -> _GitResult:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return _GitResult(returncode=127, error="git executable not found")
    except subprocess.TimeoutExpired:
        return _GitResult(returncode=124, error=f"git {' '.join(args)} timed out")
    except OSError as exc:
        return _GitResult(returncode=1, error=str(exc))

    stderr = result.stderr.strip()
    error = stderr if result.returncode != 0 else None
    return _GitResult(
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
        error=error,
    )


def _parse_status_line(line: str) -> StatusPath | None:
    if len(line) < 3:
        return None
    index_status = line[0]
    worktree_status = line[1]
    raw_path = line[3:] if line[2] == " " else line[2:].strip()
    original_path = None
    if " -> " in raw_path:
        original_path, raw_path = raw_path.rsplit(" -> ", 1)
        original_path = _normalise_git_path(original_path)

    path = _normalise_git_path(raw_path)
    if not path:
        return None
    return StatusPath(
        path=path,
        index_status=index_status,
        worktree_status=worktree_status,
        original_path=original_path,
    )


def _paths_from_lines(output: str) -> tuple[str, ...]:
    return tuple(
        path
        for path in (_normalise_git_path(line) for line in output.splitlines())
        if path
    )


def _normalise_git_path(path: str) -> str:
    return strip_to_posix(path.strip().strip('"'))
