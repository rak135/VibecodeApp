"""Run required checks from .vibecode/checks/required_checks.yaml."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from vibecode.config import load_config
from vibecode.paths import to_posix_str

_CHECK_RESULTS_SCHEMA = "vibecode/check-results/v1"


@dataclass
class CheckResult:
    name: str
    command: str
    required: bool
    exit_code: int
    duration_seconds: float
    stdout: str
    stderr: str

    @property
    def status(self) -> str:
        if self.exit_code == 0:
            return "pass"
        if self.required:
            return "fail"
        return "warn"

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "command": self.command,
            "required": self.required,
            "exit_code": self.exit_code,
            "duration_seconds": round(self.duration_seconds, 3),
            "status": self.status,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


@dataclass
class CheckRun:
    root: Path
    results: list[CheckResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.status == "pass")

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == "fail")

    @property
    def warnings(self) -> int:
        return sum(1 for r in self.results if r.status == "warn")

    @property
    def has_required_failures(self) -> bool:
        return any(r.status == "fail" for r in self.results)

    @property
    def status(self) -> str:
        return "error" if self.has_required_failures else "ok"

    def as_dict(self) -> dict:
        return {
            "$schema": _CHECK_RESULTS_SCHEMA,
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "root": to_posix_str(self.root),
            "summary": {
                "total": self.total,
                "passed": self.passed,
                "failed": self.failed,
                "warnings": self.warnings,
            },
            "status": "error" if self.has_required_failures else "ok",
            "checks": [r.as_dict() for r in self.results],
        }


def run_command(command: str, cwd: Path) -> tuple[int, str, str]:
    """Run a shell command and return (exit_code, stdout, stderr)."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out after 300 seconds"
    except Exception as exc:
        return 1, "", str(exc)


def run_checks(repo_root: Path) -> CheckRun:
    """Load and run all required checks, returning results."""
    vibecode_dir = repo_root / ".vibecode"
    config = load_config(vibecode_dir)

    check_run = CheckRun(root=repo_root)

    for record in config.required_check_records:
        name = record["name"]
        command = record["command"]
        required = record.get("required", True)

        t0 = time.monotonic()
        exit_code, stdout, stderr = run_command(command, cwd=repo_root)
        duration = time.monotonic() - t0

        check_run.results.append(
            CheckResult(
                name=name,
                command=command,
                required=required,
                exit_code=exit_code,
                duration_seconds=duration,
                stdout=stdout,
                stderr=stderr,
            )
        )

    return check_run


def write_check_results(check_run: CheckRun, vibecode_dir: Path) -> Path:
    """Write check results to .vibecode/current/check_results.json."""
    path = vibecode_dir / "current" / "check_results.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(check_run.as_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def print_check_results(check_run: CheckRun, stream=None) -> None:
    """Print check results as PASS/FAIL/WARN lines."""
    out = stream or sys.stdout
    for result in check_run.results:
        status_label = {"pass": "PASS", "fail": "FAIL", "warn": "WARN"}[result.status]
        print(f"{status_label}: {result.name} (exit code {result.exit_code}, {result.duration_seconds:.3f}s)", file=out)


def cmd_check(args) -> int:
    """CLI handler for ``vibecode check``."""
    repo_root = Path(args.repo_root).resolve()
    vibecode_dir = repo_root / ".vibecode"

    if not repo_root.exists():
        raise FileNotFoundError(f"Repository root does not exist: {repo_root}")

    if not vibecode_dir.exists():
        raise FileNotFoundError(f".vibecode directory not found: {vibecode_dir}")

    check_run = run_checks(repo_root)
    write_check_results(check_run, vibecode_dir)
    print_check_results(check_run)

    return 1 if check_run.has_required_failures else 0