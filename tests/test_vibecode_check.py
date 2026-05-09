"""Tests for vibecode check runner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecode.check import (
    CheckResult,
    CheckRun,
    run_command,
)
from vibecode.cli import main


# ---------------------------------------------------------------------------
# Unit: run_command
# ---------------------------------------------------------------------------


def test_run_command_success(tmp_path):
    exit_code, stdout, stderr = run_command("python -c \"print('ok')\"", cwd=tmp_path)
    assert exit_code == 0
    assert "ok" in stdout
    assert stderr == ""


def test_run_command_failure(tmp_path):
    exit_code, stdout, stderr = run_command("python -c \"import sys; sys.exit(1)\"", cwd=tmp_path)
    assert exit_code == 1


def test_run_command_timeout(tmp_path):
    exit_code, stdout, stderr = run_command("timeout /t 5", cwd=tmp_path)
    # timeout should be killed or fail
    assert exit_code != 0 or "timed out" in stderr.lower()


# ---------------------------------------------------------------------------
# Unit: CheckResult status
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "exit_code, required, expected_status",
    [
        (0, True, "pass"),
        (0, False, "pass"),
        (1, True, "fail"),
        (1, False, "warn"),
        (2, True, "fail"),
        (2, False, "warn"),
    ],
)
def test_check_result_status(exit_code, required, expected_status):
    result = CheckResult(
        name="test",
        command="echo test",
        required=required,
        exit_code=exit_code,
        duration_seconds=0.0,
        stdout="",
        stderr="",
    )
    assert result.status == expected_status


# ---------------------------------------------------------------------------
# Unit: CheckRun summary
# ---------------------------------------------------------------------------


def test_check_run_summary():
    run = CheckRun(root=Path("/tmp"))
    run.results = [
        CheckResult("pass1", "cmd1", True, 0, 0.1, "", ""),
        CheckResult("fail1", "cmd2", True, 1, 0.2, "", ""),
        CheckResult("warn1", "cmd3", False, 1, 0.3, "", ""),
    ]
    assert run.total == 3
    assert run.passed == 1
    assert run.failed == 1
    assert run.warnings == 1
    assert run.has_required_failures is True
    assert run.status == "error"


def test_check_run_no_failures():
    run = CheckRun(root=Path("/tmp"))
    run.results = [
        CheckResult("pass1", "cmd1", True, 0, 0.1, "", ""),
        CheckResult("pass2", "cmd2", False, 0, 0.2, "", ""),
    ]
    assert run.has_required_failures is False
    assert run.status == "ok"


# ---------------------------------------------------------------------------
# Integration: run_checks + write_check_results
# ---------------------------------------------------------------------------


def test_check_integration_passing(tmp_path, capsys):
    """All checks pass -> exit 0, report status 'ok'."""
    vdir = tmp_path / ".vibecode"
    vdir.mkdir()
    (vdir / "project.yaml").write_text(
        "project:\n  id: testproj\n  name: Test\n  root: .\n",
        encoding="utf-8",
    )
    (vdir / "checks").mkdir()
    (vdir / "checks" / "required_checks.yaml").write_text(
        """\
checks:
  - name: always pass
    command: python -c "print('ok')"
    required: true
  - name: optional pass
    command: python -c "print('optional')"
    required: false
""",
        encoding="utf-8",
    )

    rc = main(["check", str(tmp_path)])
    captured = capsys.readouterr()

    assert rc == 0
    assert "PASS" in captured.out
    assert "FAIL" not in captured.out

    report_path = vdir / "current" / "check_results.json"
    assert report_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "ok"
    assert report["summary"]["passed"] == 2
    assert report["summary"]["failed"] == 0
    assert report["summary"]["warnings"] == 0


def test_check_integration_required_failure(tmp_path, capsys):
    """A required check fails -> exit 1, report status 'error'."""
    vdir = tmp_path / ".vibecode"
    vdir.mkdir()
    (vdir / "project.yaml").write_text(
        "project:\n  id: testproj\n  name: Test\n  root: .\n",
        encoding="utf-8",
    )
    (vdir / "checks").mkdir()
    (vdir / "checks" / "required_checks.yaml").write_text(
        """\
checks:
  - name: fails
    command: python -c "import sys; sys.exit(1)"
    required: true
""",
        encoding="utf-8",
    )

    rc = main(["check", str(tmp_path)])
    captured = capsys.readouterr()

    assert rc == 1
    assert "FAIL" in captured.out

    report_path = vdir / "current" / "check_results.json"
    assert report_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "error"
    assert report["summary"]["failed"] == 1
    assert report["checks"][0]["exit_code"] == 1


def test_check_integration_optional_failure(tmp_path, capsys):
    """An optional (required=false) check fails -> exit 0 with warning."""
    vdir = tmp_path / ".vibecode"
    vdir.mkdir()
    (vdir / "project.yaml").write_text(
        "project:\n  id: testproj\n  name: Test\n  root: .\n",
        encoding="utf-8",
    )
    (vdir / "checks").mkdir()
    (vdir / "checks" / "required_checks.yaml").write_text(
        """\
checks:
  - name: optional fail
    command: python -c "import sys; sys.exit(1)"
    required: false
""",
        encoding="utf-8",
    )

    rc = main(["check", str(tmp_path)])
    captured = capsys.readouterr()

    assert rc == 0
    assert "WARN" in captured.out
    assert "FAIL" not in captured.out

    report_path = vdir / "current" / "check_results.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "ok"
    assert report["summary"]["warnings"] == 1


def test_check_missing_vibecode_dir(tmp_path, capsys):
    """No .vibecode directory -> error message and non-zero exit."""
    rc = main(["check", str(tmp_path)])

    assert rc == 1
    assert ".vibecode" in capsys.readouterr().err


def test_check_command_timeout(tmp_path):
    """A command that exceeds the timeout is reported as failed."""
    vdir = tmp_path / ".vibecode"
    vdir.mkdir()
    (vdir / "project.yaml").write_text(
        "project:\n  id: testproj\n  name: Test\n  root: .\n",
        encoding="utf-8",
    )
    (vdir / "checks").mkdir()
    (vdir / "checks" / "required_checks.yaml").write_text(
        """\
checks:
  - name: slow
    command: timeout /t 5
    required: true
""",
        encoding="utf-8",
    )

    rc = main(["check", str(tmp_path)])

    assert rc == 1
    report_path = vdir / "current" / "check_results.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["checks"][0]["exit_code"] != 0


def test_check_output_in_json_report(tmp_path):
    """stdout and stderr from commands are captured in the report."""
    vdir = tmp_path / ".vibecode"
    vdir.mkdir()
    (vdir / "project.yaml").write_text(
        "project:\n  id: testproj\n  name: Test\n  root: .\n",
        encoding="utf-8",
    )
    (vdir / "checks").mkdir()
    (vdir / "checks" / "required_checks.yaml").write_text(
        """\
checks:
  - name: with output
    command: python -c "import sys; print('stdout ok'); print('stderr ok', file=sys.stderr)"
    required: true
""",
        encoding="utf-8",
    )

    main(["check", str(tmp_path)])

    report_path = vdir / "current" / "check_results.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    check = report["checks"][0]
    assert "stdout ok" in check["stdout"]
    assert "stderr ok" in check["stderr"]
    assert "duration_seconds" in check