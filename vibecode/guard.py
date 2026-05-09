"""Internal guard rule evaluation for repository changes."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath

from vibecode.config import DEFAULT_PROTECTED_PATH_RULES, ProtectedPathRule, load_config
from vibecode.git_state import GitState, inspect_git_state
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
SOURCE_TEST_BALANCE_RULE_ID = "source-test-change-balance"
SOURCE_TEST_BALANCE_MESSAGE = "Source and test changes should usually move together."
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
_SOURCE_EXTENSIONS: frozenset[str] = frozenset({
    ".py",
    ".pyi",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
})
_DOC_EXTENSIONS: frozenset[str] = frozenset({".md", ".mdx", ".rst", ".txt", ".adoc"})
_TS_TEST_SUFFIXES: tuple[str, ...] = (
    ".test.ts",
    ".test.tsx",
    ".spec.ts",
    ".spec.tsx",
    ".test.js",
    ".test.jsx",
    ".spec.js",
    ".spec.jsx",
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

    def as_dict(self) -> dict:
        data = {
            "rule_id": self.rule_id,
            "path": self.path,
            "severity": self.severity,
            "message": self.message,
        }
        if self.rule:
            data["rule"] = self.rule
        if self.recommended_fix:
            data["recommended_fix"] = self.recommended_fix
        if self.required_tests:
            data["required_tests"] = list(self.required_tests)
        return data


@dataclass(frozen=True)
class GuardResult:
    """Aggregated guard rule result."""

    findings: tuple[GuardFinding, ...] = ()

    @property
    def passed(self) -> bool:
        return all(finding.severity != "error" for finding in self.findings)

    def as_dict(self, root: Path | None = None) -> dict:
        data: dict = {
            "$schema": "vibecode/guard-result/v1",
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "passed": self.passed,
            "errors": sum(1 for f in self.findings if f.severity == "error"),
            "warnings": sum(1 for f in self.findings if f.severity == "warning"),
            "findings": [f.as_dict() for f in self.findings],
        }
        if root is not None:
            data["root"] = root.as_posix()
        return data

    def suggested_tests(self) -> tuple[str, ...]:
        """Return unique suggested test paths from all findings."""
        tests: list[str] = []
        seen: set[str] = set()
        for finding in self.findings:
            for test in finding.required_tests:
                if test not in seen:
                    seen.add(test)
                    tests.append(test)
        return tuple(tests)


def evaluate_guard(
    git_state: GitState,
    *,
    task: str = "",
    test_map: dict | None = None,
) -> GuardResult:
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
    source_test_result = check_source_test_change_balance(
        git_state.changed_paths,
        task=task,
        test_map=test_map,
    )
    return GuardResult(
        findings=_dedupe_findings(
            (
                *policy_result.findings,
                *generated_result.findings,
                *readme_result.findings,
                *architecture_truth_result.findings,
                *source_test_result.findings,
            )
        )
    )


def write_guard_result(
    result: GuardResult,
    vibecode_dir: Path,
    root: Path,
) -> Path:
    """Write guard result to ``.vibecode/current/guard_result.json``."""
    path = vibecode_dir / "current" / "guard_result.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = result.as_dict(root=root)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def check_source_test_change_balance(
    changed_paths: tuple[str, ...] | list[str],
    *,
    task: str = "",
    test_map: dict | None = None,
) -> GuardResult:
    """Warn when source and test changes do not move together."""

    paths = tuple(
        path
        for path in (_normalise_path(raw_path) for raw_path in changed_paths)
        if path and not _is_generated_runtime_path(path)
    )
    if not paths:
        return GuardResult()

    source_paths = tuple(path for path in paths if _is_source_path(path))
    test_paths = tuple(path for path in paths if _is_test_path(path))
    if not source_paths and not test_paths:
        return GuardResult()
    if test_paths and not source_paths:
        if _task_is_test_only(task):
            return GuardResult()
        return GuardResult(
            findings=(
                GuardFinding(
                    rule_id=SOURCE_TEST_BALANCE_RULE_ID,
                    path=_summarise_paths(test_paths),
                    severity="warning",
                    message=(
                        "Tests changed without source changes. If this is test-only "
                        "work, make that explicit in the task."
                    ),
                    rule=SOURCE_TEST_BALANCE_MESSAGE,
                    recommended_fix=(
                        "Include the related source change, or note that this is a "
                        "test-only task."
                    ),
                ),
            )
        )

    unmatched_sources: list[str] = []
    suggestions: list[str] = []
    for source_path in source_paths:
        paired_tests = _paired_tests_for_source(source_path, test_map)
        if paired_tests:
            suggestions.extend(paired_tests)
            if any(test in test_paths for test in paired_tests):
                continue
        elif test_paths:
            continue
        else:
            suggestions.extend(_suggested_tests_for_source(source_path))
        unmatched_sources.append(source_path)

    if not unmatched_sources:
        return GuardResult()

    fix = "Add or update a matching test."
    suggested = _unique_paths(suggestions)[:4]
    if suggested:
        fix = f"Add or update matching tests, such as {_format_path_list(suggested)}."

    return GuardResult(
        findings=(
            GuardFinding(
                rule_id=SOURCE_TEST_BALANCE_RULE_ID,
                path=_summarise_paths(tuple(unmatched_sources)),
                severity="warning",
                message=(
                    "Source changed without corresponding test changes: "
                    f"{_format_path_list(tuple(unmatched_sources)[:3])}."
                ),
                rule=SOURCE_TEST_BALANCE_MESSAGE,
                recommended_fix=fix,
                required_tests=tuple(suggested),
            ),
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


def _is_source_path(path: str) -> bool:
    if _is_test_path(path) or _is_documentation_path(path):
        return False
    return PurePosixPath(path).suffix in _SOURCE_EXTENSIONS


def _is_test_path(path: str) -> bool:
    suffix = PurePosixPath(path).suffix
    name = PurePosixPath(path).name
    parts = path.split("/")
    if suffix == ".py":
        return (
            name.startswith("test_")
            or name.endswith("_test.py")
            or "tests" in parts[:-1]
        )
    if suffix in {".js", ".jsx", ".ts", ".tsx"}:
        return any(name.endswith(test_suffix) for test_suffix in _TS_TEST_SUFFIXES) or (
            "__tests__" in parts[:-1]
        )
    return False


def _is_documentation_path(path: str) -> bool:
    if path == "README.md" or path.startswith("docs/"):
        return True
    return PurePosixPath(path).suffix in _DOC_EXTENSIONS


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


def _task_is_test_only(task: str) -> bool:
    words = _words(task)
    return bool({"test", "tests"} & words) and "only" in words


def _paired_tests_for_source(source_path: str, test_map: dict | None) -> tuple[str, ...]:
    if not isinstance(test_map, dict):
        return ()
    matched: list[str] = []
    for rule in test_map.get("rules", []):
        if not isinstance(rule, dict):
            continue
        pattern = _normalise_path(str(rule.get("path_pattern", "")))
        if not pattern or pattern == "**" or not _path_matches_rule(source_path, pattern):
            continue
        checks = rule.get("required_checks", [])
        if not isinstance(checks, list):
            continue
        for check in checks:
            path = _normalise_path(str(check))
            if path and _is_test_path(path):
                matched.append(path)
    return tuple(_unique_paths(matched))


def _suggested_tests_for_source(source_path: str) -> tuple[str, ...]:
    path = PurePosixPath(source_path)
    stem = path.stem
    suffix = path.suffix
    if suffix == ".py":
        return (f"tests/test_{stem}.py",)
    if suffix in {".js", ".jsx", ".ts", ".tsx"}:
        return (path.with_name(f"{stem}.test{suffix}").as_posix(),)
    return ()


def _unique_paths(paths: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    unique: list[str] = []
    for raw_path in paths:
        path = _normalise_path(raw_path)
        if not path or path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return tuple(unique)


def _summarise_paths(paths: tuple[str, ...]) -> str:
    if len(paths) <= 3:
        return ", ".join(paths)
    return f"{', '.join(paths[:3])} (+{len(paths) - 3} more)"


def _format_path_list(paths: tuple[str, ...]) -> str:
    return ", ".join(f"`{path}`" for path in paths)


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
        if finding.rule_id in {
            ARCHITECTURE_TRUTH_RECORD_RULE_ID,
            SOURCE_TEST_BALANCE_RULE_ID,
        }:
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


def cmd_guard(args) -> int:
    """Run guard checks on the repository and report findings."""
    repo_root = Path(args.repo_root).resolve()
    vibecode_dir = repo_root / ".vibecode"

    # Check for project.yaml
    project_yaml = vibecode_dir / "project.yaml"
    if not project_yaml.exists():
        print(
            f"Error: .vibecode/project.yaml not found in {repo_root}. "
            "Run `vibecode init` to initialise the project.",
            file=sys.stderr,
        )
        return 1

    # Load config
    try:
        config = load_config(vibecode_dir)
    except Exception as exc:
        print(f"Error loading project config: {exc}", file=sys.stderr)
        return 1

    # Check git repo
    try:
        git_state = inspect_git_state(repo_root)
    except FileNotFoundError:
        print("Error: repository root does not exist.", file=sys.stderr)
        return 1

    if not git_state.is_git_repo:
        print("Error: not a git repository.", file=sys.stderr)
        return 1

    if git_state.error:
        print(f"Git error: {git_state.error}", file=sys.stderr)

    # Evaluate guard rules
    result = evaluate_guard(
        git_state,
        task="",
        test_map=None,
    )

    # Also check against project-level protected path rules
    if config.protected_path_records:
        project_result = check_protected_path_changes(
            git_state.changed_paths,
            config.protected_path_records,
            task="",
            untracked_paths=git_state.untracked_paths,
        )
        result = GuardResult(
            findings=_dedupe_findings(
                (*result.findings, *project_result.findings)
            )
        )

    # Write guard result as JSON (optional; failures here are non-blocking)
    try:
        write_guard_result(result, vibecode_dir, repo_root)
    except Exception:
        pass

    errors = tuple(f for f in result.findings if f.severity == "error")
    warnings = tuple(f for f in result.findings if f.severity == "warning")

    if not result.findings:
        print("Guard check passed. No violations found.")
        return 0

    if errors:
        print(f"\n{'=' * 60}", file=sys.stderr)
        print(f"  HARD FAILURES ({len(errors)})", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)
        for finding in errors:
            print(f"\n  [{finding.rule_id}] {finding.path}", file=sys.stderr)
            print(f"  {finding.message}", file=sys.stderr)
            if finding.recommended_fix:
                print(f"  Fix: {finding.recommended_fix}", file=sys.stderr)

    if warnings:
        print(f"\n{'=' * 60}", file=sys.stderr)
        print(f"  WARNINGS ({len(warnings)})", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)
        for finding in warnings:
            print(f"\n  [{finding.rule_id}] {finding.path}", file=sys.stderr)
            print(f"  {finding.message}", file=sys.stderr)
            if finding.recommended_fix:
                print(f"  Fix: {finding.recommended_fix}", file=sys.stderr)

    strict: bool = getattr(args, "strict", False)
    if errors:
        return 1
    if strict and warnings:
        return 1
    return 0
