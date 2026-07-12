"""Test execution tools for Nexus AI MCP server."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from core.config import get_settings
from core.logging import get_logger
from safety.guardrails import check_operation

logger   = get_logger(__name__)
settings = get_settings()


def run_tests(
    test_path:  str | None = None,
    verbose:    bool = True
) -> dict[str, Any]:
    """
    Run pytest on the target repository.
    Risk: LOW — fully automatic.
    Never modifies files.
    """
    result = check_operation(
        "run_tests",
        safety_level=settings.safety_level
    )

    if not result.allowed:
        return {"error": result.reason, "success": False}

    try:
        repo_path = Path(settings.target_repo_path)

        # Build pytest command
        cmd = ["python", "-m", "pytest"]

        if verbose:
            cmd.append("-v")

        if test_path:
            cmd.append(test_path)

        cmd.extend([
            "--tb=short",
            "--no-header",
            "-q"
        ])

        logger.info(
            "🧪 Running tests: %s",
            " ".join(cmd)
        )

        # Run tests
        proc = subprocess.run(
            cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=120
        )

        # Parse results
        output   = proc.stdout + proc.stderr
        passed   = 0
        failed   = 0
        errors   = 0

        for line in output.splitlines():
            if " passed" in line:
                try:
                    passed = int(
                        line.strip().split(" passed")[0]
                        .split()[-1]
                    )
                except ValueError:
                    pass
            if " failed" in line:
                try:
                    failed = int(
                        line.strip().split(" failed")[0]
                        .split()[-1]
                    )
                except ValueError:
                    pass
            if " error" in line:
                try:
                    errors = int(
                        line.strip().split(" error")[0]
                        .split()[-1]
                    )
                except ValueError:
                    pass

        all_passed = proc.returncode == 0

        logger.info(
            "🧪 Tests: %d passed, %d failed, %d errors",
            passed, failed, errors
        )

        return {
            "success":    True,
            "all_passed": all_passed,
            "passed":     passed,
            "failed":     failed,
            "errors":     errors,
            "output":     output,
            "returncode": proc.returncode
        }

    except subprocess.TimeoutExpired:
        logger.error("Tests timed out after 120s")
        return {
            "error":   "Tests timed out after 120 seconds",
            "success": False
        }
    except Exception as exc:
        logger.error("Failed to run tests: %s", exc)
        return {"error": str(exc), "success": False}


def run_single_test(
    test_name: str
) -> dict[str, Any]:
    """
    Run a single test by name.
    Risk: LOW — fully automatic.
    """
    result = check_operation(
        "run_tests",
        safety_level=settings.safety_level
    )

    if not result.allowed:
        return {"error": result.reason, "success": False}

    try:
        repo_path = Path(settings.target_repo_path)

        cmd = [
            "python", "-m", "pytest",
            "-v", "-k", test_name,
            "--tb=short"
        ]

        proc = subprocess.run(
            cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=60
        )

        output = proc.stdout + proc.stderr

        return {
            "success":    True,
            "test_name":  test_name,
            "passed":     proc.returncode == 0,
            "output":     output,
            "returncode": proc.returncode
        }

    except Exception as exc:
        logger.error(
            "Failed to run test %s: %s",
            test_name, exc
        )
        return {"error": str(exc), "success": False}


def check_coverage(
    module_path: str | None = None
) -> dict[str, Any]:
    """
    Run tests with coverage report.
    Risk: LOW — fully automatic.
    """
    result = check_operation(
        "run_tests",
        safety_level=settings.safety_level
    )

    if not result.allowed:
        return {"error": result.reason, "success": False}

    try:
        repo_path = Path(settings.target_repo_path)

        cmd = [
            "python", "-m", "pytest",
            "--cov",
            "--cov-report=term-missing",
            "-q"
        ]

        if module_path:
            cmd.extend([f"--cov={module_path}"])

        proc = subprocess.run(
            cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=120
        )

        output = proc.stdout + proc.stderr

        # Extract coverage percentage
        coverage = None
        for line in output.splitlines():
            if "TOTAL" in line:
                try:
                    coverage = int(
                        line.split()[-1].replace("%", "")
                    )
                except ValueError:
                    pass

        logger.info(
            "📊 Coverage: %s%%",
            coverage or "unknown"
        )

        return {
            "success":          True,
            "coverage_percent": coverage,
            "output":           output,
            "all_passed":       proc.returncode == 0
        }

    except Exception as exc:
        logger.error("Coverage check failed: %s", exc)
        return {"error": str(exc), "success": False}


def list_tests(
    directory: str = "tests"
) -> dict[str, Any]:
    """
    List all available tests.
    Risk: LOW — fully automatic.
    """
    result = check_operation(
        "read_file",
        safety_level=settings.safety_level
    )

    if not result.allowed:
        return {"error": result.reason, "success": False}

    try:
        repo_path = Path(settings.target_repo_path)
        test_dir  = repo_path / directory

        if not test_dir.exists():
            return {
                "success":  True,
                "tests":    [],
                "count":    0,
                "message":  f"No tests directory found at {directory}"
            }

        tests = []
        for test_file in test_dir.glob("**/test_*.py"):
            content = test_file.read_text(encoding="utf-8")
            # Extract test function names
            test_fns = [
                line.strip().replace("def ", "").split("(")[0]
                for line in content.splitlines()
                if line.strip().startswith("def test_")
            ]
            tests.append({
                "file":      str(test_file.relative_to(repo_path)),
                "functions": test_fns,
                "count":     len(test_fns)
            })

        total = sum(t["count"] for t in tests)
        logger.info(
            "📋 Found %d tests in %d files",
            total, len(tests)
        )

        return {
            "success": True,
            "tests":   tests,
            "count":   total
        }

    except Exception as exc:
        logger.error("Failed to list tests: %s", exc)
        return {"error": str(exc), "success": False}