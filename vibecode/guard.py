"""Internal guard rule evaluation for repository changes."""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase

from vibecode.config import DEFAULT_PROTECTED_PATH_RULES, ProtectedPathRule
from vibecode.git_state import GitState
from vibecode.paths import strip_to_posix


GENERATED_RUNTIME_RULE_ID = "generated-runtime-files"
GENERATED_RUNTIME_MESSAGE = (
    "Regenerate generated files; do not manually edit them."
)
README_RULE_ID = "readme-manual-only"
README_MANUAL_ONLY_MESSAGE = (
    "README.md is manual-only until generated block markers are introduced."
)
ARCHITECTURE_TRUTH_RECORD_RULE_ID = "architecture-truth-record"
ARCHITECTURE_TRUTH_RECORD_MESSAGE = (
    "Architecture truth changed and must be recorded in handoff or history."
)
README_ALLOWED_GENERATED_BLOCK_MARKERS: tuple[tuple[str, str], ...] = (
    (
        "<!-- vibecode:readme:generated:start -->",
        "<!-- vibecode:readme:generated:end -->",
    ),
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
    rule: str = ""
    recommended_fix: str = ""
    required_tests: tuple[str, ...] = ()


@dataclass(frozen=True)
class GuardResult:
    """Aggregated guard rule result."""

    findings: tuple[GuardFinding, ...] = ()

    @property
    def passed(self) -> bool:
        return all(finding.severity != "error" for finding in self.findings)


def evaluate_guard(git_state: GitState, *, task: str = "") -> GuardResult:
    """Evaluate all internal guard rules against collected git state."""

    policy_result = check_protected_path_changes(
        git_state.changed_paths,
        DEFAULT_PROTECTED_PATH_RULES,
        task=task,
        untracked_paths=git_state.untracked_paths,
    )
    generated_result = check_generated_runtime_changes(
        git_state.changed_paths,
        task=task,
        untracked_paths=git_state.untracked_paths,
    )
    readme_result = check_readme_changes(git_state.changed_paths, task=task)
    architecture_truth_result = check_architecture_truth_recorded(
        git_state.changed_paths
    )
    return GuardResult(
        findings=_dedupe_findings(
            (
                *policy_result.findings,
                *generated_result.findings,
                *readme_result.findings,
                *architecture_truth_result.findings,
            )
        )
    )


def check_protected_path_changes(
    changed_paths: tuple[str, ...] | list[str],
    protected_rules: tuple[ProtectedPathRule, ...] | list[ProtectedPathRule],
    *,
    task: str = "",
    untracked_paths: tuple[str, ...] | list[str] = (),
    ignored_paths: tuple[str, ...] | list[str] = (),
) -> GuardResult:
    """Report changed paths covered by protected path policy records."""

    allowed_uncommitted_paths = _normalised_set((*untracked_paths, *ignored_paths))
    task_allows_generator_files = _task_tests_generator_behavior(task)
    findings: list[GuardFinding] = []

    for raw_path in changed_paths:
        path = _normalise_path(raw_path)
        if not path:
            continue
        for rule in protected_rules:
            policy_path = _normalise_path(rule.path)
            if not _path_matches_rule(path, policy_path):
                continue
            if _is_generated_runtime_path(path):
                if task_allows_generator_files and path in allowed_uncommitted_paths:
                    continue
                findings.append(_generated_policy_finding(path, rule))
                continue

            scoped = _task_mentions_scope(task, path, policy_path)
            if _requires_explicit_scope(rule) and not scoped:
                findings.append(_scope_required_finding(path, rule))
                continue
            if rule.required_tests or _requires_handoff_explanation(policy_path):
                findings.append(_protected_path_note(path, rule, policy_path))
    return GuardResult(findings=tuple(findings))


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
                rule=GENERATED_RUNTIME_MESSAGE,
                recommended_fix=(
                    "Regenerate this artifact with the owning command and do not "
                    "commit manual generated/runtime edits."
                ),
            )
        )
    return GuardResult(findings=tuple(findings))


def check_readme_changes(
    changed_paths: tuple[str, ...] | list[str],
    *,
    task: str = "",
) -> GuardResult:
    """Fail root README changes unless the task is explicitly docs-scoped.

    The allowed generated block markers are defined for future policy use, but
    this task does not add generated README block automation.
    """

    if _task_allows_readme_change(task):
        return GuardResult()

    findings = []
    for raw_path in changed_paths:
        path = _normalise_path(raw_path)
        if path != "README.md":
            continue
        findings.append(
            GuardFinding(
                rule_id=README_RULE_ID,
                path=path,
                severity="error",
                message=(
                    "README.md changed outside an explicit README/docs task "
                    f"or allowed generated block markers. {README_MANUAL_ONLY_MESSAGE} "
                    f"Offending path: {path}."
                ),
                rule=(
                    "Root README changes are allowed only for README/docs tasks "
                    "or inside future generated blocks."
                ),
                recommended_fix=(
                    "Revert README.md or rerun with explicit README/docs task "
                    "scope. Do not add generated README automation here."
                ),
            )
        )
    return GuardResult(findings=tuple(findings))


def check_architecture_truth_recorded(
    changed_paths: tuple[str, ...] | list[str],
    *,
    override: bool = False,
) -> GuardResult:
    """Require handoff/history acknowledgement for architecture truth changes."""

    if override:
        return GuardResult()

    paths = tuple(
        path
        for path in (_normalise_path(raw_path) for raw_path in changed_paths)
        if path
    )
    architecture_paths = tuple(path for path in paths if _is_architecture_doc_path(path))
    if not architecture_paths or _has_architecture_truth_record(paths):
        return GuardResult()

    return GuardResult(
        findings=tuple(
            GuardFinding(
                rule_id=ARCHITECTURE_TRUTH_RECORD_RULE_ID,
                path=path,
                severity="error",
                message=(
                    f"{ARCHITECTURE_TRUTH_RECORD_MESSAGE} Offending path: {path}"
                ),
                rule=(
                    "Changes to .vibecode/architecture/*.md must be recorded in "
                    ".vibecode/handoff/NOW.md or .vibecode/history/*.md."
                ),
                recommended_fix=(
                    "Add a relevant note to .vibecode/handoff/NOW.md or a relevant "
                    "summary in .vibecode/history/*.md, or use the future explicit "
                    "override flag when available."
                ),
            )
            for path in architecture_paths
        )
    )


def _generated_policy_finding(path: str, rule: ProtectedPathRule) -> GuardFinding:
    return GuardFinding(
        rule_id="protected-path-generated",
        path=path,
        severity="error",
        message=f"Generated/runtime protected path changed: {path}",
        rule=rule.rule,
        recommended_fix=(
            "Regenerate this artifact with the owning Vibecode command; do not "
            "manually edit or commit it."
        ),
        required_tests=rule.required_tests,
    )


def _scope_required_finding(path: str, rule: ProtectedPathRule) -> GuardFinding:
    fix = f"Add explicit task scope for `{rule.path}` or revert `{path}`."
    if rule.required_tests:
        fix = f"{fix} Run required tests: {_format_required_tests(rule.required_tests)}."
    return GuardFinding(
        rule_id="protected-path-scope",
        path=path,
        severity="error",
        message=f"Protected path changed without explicit task scope: {path}",
        rule=rule.rule,
        recommended_fix=fix,
        required_tests=rule.required_tests,
    )


def _protected_path_note(
    path: str,
    rule: ProtectedPathRule,
    policy_path: str,
) -> GuardFinding:
    fixes: list[str] = []
    if rule.required_tests:
        fixes.append(f"Run required tests: {_format_required_tests(rule.required_tests)}.")
    if _requires_handoff_explanation(policy_path):
        fixes.append(
            "Explain the protected truth-doc change in handoff before marking done."
        )
    return GuardFinding(
        rule_id="protected-path-requirements",
        path=path,
        severity="warning",
        message=f"Protected path requirements apply: {path}",
        rule=rule.rule,
        recommended_fix=" ".join(fixes),
        required_tests=rule.required_tests,
    )


def _is_generated_runtime_path(path: str) -> bool:
    if path.startswith(_GENERATED_RUNTIME_PREFIXES):
        return True
    if not path.startswith(".vibecode/index/"):
        return False
    name = path.removeprefix(".vibecode/index/")
    return "/" not in name and ".generated." in name


def _path_matches_rule(path: str, rule_path: str) -> bool:
    if not rule_path:
        return False
    if rule_path.endswith("/"):
        return path.startswith(rule_path)
    return path == rule_path or fnmatchcase(path, rule_path)


def _requires_explicit_scope(rule: ProtectedPathRule) -> bool:
    if rule.explicit_task_scope_required is not None:
        return rule.explicit_task_scope_required
    return True


def _requires_handoff_explanation(policy_path: str) -> bool:
    return policy_path.startswith((
        ".vibecode/architecture/",
        ".vibecode/checks/",
        ".vibecode/handoff/",
    ))


def _is_architecture_doc_path(path: str) -> bool:
    if not path.startswith(".vibecode/architecture/") or not path.endswith(".md"):
        return False
    return "/" not in path.removeprefix(".vibecode/architecture/")


def _has_architecture_truth_record(paths: tuple[str, ...]) -> bool:
    return any(
        path == ".vibecode/handoff/NOW.md"
        or (
            path.startswith(".vibecode/history/")
            and path.endswith(".md")
            and "/" not in path.removeprefix(".vibecode/history/")
        )
        for path in paths
    )


def _task_mentions_scope(task: str, path: str, rule_path: str) -> bool:
    task_words = _words(task)
    if not task_words:
        return False
    if _normalise_path(path).lower() in task.lower().replace("\\", "/"):
        return True
    scope_words = _words(f"{path} {rule_path}") - {"vibecode", "py", "md", "yaml"}
    return bool(task_words & scope_words)


def _task_tests_generator_behavior(task: str) -> bool:
    words = task.lower().replace("-", " ")
    return "generator" in words and ("test" in words or "testing" in words)


def _task_allows_readme_change(task: str) -> bool:
    return bool(_words(task) & {"readme", "docs", "doc", "documentation"})


def _format_required_tests(required_tests: tuple[str, ...]) -> str:
    return ", ".join(f"`{test}`" for test in required_tests)


def _words(value: str) -> set[str]:
    translated = "".join(char.lower() if char.isalnum() else " " for char in value)
    return {word for word in translated.split() if word}


def _dedupe_findings(findings: tuple[GuardFinding, ...]) -> tuple[GuardFinding, ...]:
    deduped: list[GuardFinding] = []
    seen: set[tuple[str, ...]] = set()
    for finding in findings:
        key = (finding.severity, finding.path)
        if finding.rule_id == ARCHITECTURE_TRUTH_RECORD_RULE_ID:
            key = (*key, finding.rule_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(finding)
    return tuple(deduped)


def _normalised_set(paths: tuple[str, ...]) -> frozenset[str]:
    return frozenset(path for path in (_normalise_path(p) for p in paths) if path)


def _normalise_path(path: str) -> str:
    return strip_to_posix(str(path).strip())
