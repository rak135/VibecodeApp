"""Internal guard rule evaluation for repository changes."""

from __future__ import annotations

from dataclasses import dataclass

from vibecode.git_state import GitState
from vibecode.paths import strip_to_posix


GENERATED_RUNTIME_RULE_ID = "generated-runtime-files"
GENERATED_RUNTIME_MESSAGE = (
    "Regenerate generated files; do not manually edit them."
)

_GENERATED_RUNTIME_PREFIXES: tuple[str, ...] = (
    ".vibecode/current/",
    ".vibecode/generated/",
    ".vibecode/logs/",
    ".vibecode/runs/",
    ".vibecode/tmp/",
    ".vibecode/cache/",
)


@dataclass(frozen=True)
class GuardFinding:
    """One hard guard finding for a changed path."""

    rule_id: str
    path: str
    severity: str
    message: str


@dataclass(frozen=True)
class GuardResult:
    """Aggregated guard rule result."""

    findings: tuple[GuardFinding, ...] = ()

    @property
    def passed(self) -> bool:
        return not self.findings


def evaluate_guard(git_state: GitState, *, task: str = "") -> GuardResult:
    """Evaluate all internal guard rules against collected git state."""

    return check_generated_runtime_changes(
        git_state.changed_paths,
        task=task,
        untracked_paths=git_state.untracked_paths,
    )


def check_generated_runtime_changes(
    changed_paths: tuple[str, ...] | list[str],
    *,
    task: str = "",
    untracked_paths: tuple[str, ...] | list[str] = (),
    ignored_paths: tuple[str, ...] | list[str] = (),
) -> GuardResult:
    """Fail when changed files include generated/runtime Vibecode paths."""

    allowed_uncommitted_paths = _normalised_set((*untracked_paths, *ignored_paths))
    task_allows_generator_files = _task_tests_generator_behavior(task)

    findings = []
    for raw_path in changed_paths:
        path = _normalise_path(raw_path)
        if not path or not _is_generated_runtime_path(path):
            continue
        if task_allows_generator_files and path in allowed_uncommitted_paths:
            continue
        findings.append(
            GuardFinding(
                rule_id=GENERATED_RUNTIME_RULE_ID,
                path=path,
                severity="error",
                message=f"{GENERATED_RUNTIME_MESSAGE} Offending path: {path}",
            )
        )
    return GuardResult(findings=tuple(findings))


def _is_generated_runtime_path(path: str) -> bool:
    if path.startswith(_GENERATED_RUNTIME_PREFIXES):
        return True
    if not path.startswith(".vibecode/index/"):
        return False
    name = path.removeprefix(".vibecode/index/")
    return "/" not in name and ".generated." in name


def _task_tests_generator_behavior(task: str) -> bool:
    words = task.lower().replace("-", " ")
    return "generator" in words and ("test" in words or "testing" in words)


def _normalised_set(paths: tuple[str, ...]) -> frozenset[str]:
    return frozenset(path for path in (_normalise_path(p) for p in paths) if path)


def _normalise_path(path: str) -> str:
    return strip_to_posix(str(path).strip())
