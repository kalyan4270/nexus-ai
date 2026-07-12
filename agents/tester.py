"""
Tester Agent — Runs and writes tests.
Ensures code changes don't break anything.
"""

from __future__ import annotations

from typing import Any

from agents.base import NexusAgent
from core.logging import get_logger
from mcp.tools.file_tools import read_file, write_file
from mcp.tools.test_tools import (
    run_tests,
    list_tests,
    check_coverage,
)
from mcp.tools.search_tools import find_function

logger = get_logger(__name__)


class TesterAgent(NexusAgent):
    """
    TesterAgent runs existing tests and
    writes new tests for changed code.

    Responsibilities:
    - Run full test suite after changes
    - Identify which tests are affected
    - Write new tests for new code
    - Report test results to other agents
    - Block PR if tests fail
    """

    def __init__(self) -> None:
        super().__init__(
            agent_id=     "tester",
            name=         "TesterAgent",
            description=  "Runs and writes tests autonomously",
            capabilities= [
                "test_execution",
                "test_writing",
                "coverage_check",
                "regression_testing",
                "test_reporting"
            ]
        )

    def execute(
        self,
        task:    str,
        context: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Run tests and write new ones
        for changed files.
        """
        task_id = context.get(
            "task_id", self.new_task_id()
        )
        self.start_task(task_id)

        try:
            logger.info(
                "🧪 TesterAgent executing: %s",
                task
            )

            files_changed = context.get(
                "files_changed", []
            )

            # Step 1 — Run existing tests
            test_result = self._run_existing_tests()

            # Step 2 — Write new tests if needed
            new_tests_written = []
            if files_changed:
                new_tests = self._write_tests(
                    files_changed= files_changed,
                    task=          task,
                    context=       context
                )
                new_tests_written = new_tests.get(
                    "files_written", []
                )

            # Step 3 — Run tests again with new ones
            final_result = self._run_existing_tests()

            all_passed = final_result.get("all_passed", False)

            if all_passed:
                logger.info(
                    "✅ All tests passing: %d passed",
                    final_result.get("passed", 0)
                )
            else:
                logger.warning(
                    "❌ Tests failing: %d failed",
                    final_result.get("failed", 0)
                )

            return {
                "success":           True,
                "task_id":           task_id,
                "all_passed":        all_passed,
                "passed":            final_result.get("passed", 0),
                "failed":            final_result.get("failed", 0),
                "new_tests_written": new_tests_written,
                "output":            final_result.get("output", ""),
                "approved":          all_passed
            }

        except Exception as exc:
            logger.error(
                "TesterAgent failed: %s", exc
            )
            return {
                "success": False,
                "error":   str(exc),
                "task_id": task_id
            }
        finally:
            self.complete_task()

    def _run_existing_tests(self) -> dict[str, Any]:
        """Run full test suite."""
        logger.info("🧪 Running test suite...")
        result = run_tests(verbose=True)

        passed = result.get("passed", 0)
        failed = result.get("failed", 0)

        # If no tests exist at all consider it passing
        # Tests will be written by TesterAgent
        if passed == 0 and failed == 0:
            logger.info("No existing tests found — skipping")
            return {
                **result,
                "all_passed": True,
                "no_tests":   True
            }

        logger.info(
            "Tests: %d passed, %d failed",
            passed, failed
        )
        return result

    def _write_tests(
        self,
        files_changed: list[str],
        task:          str,
        context:       dict[str, Any]
    ) -> dict[str, Any]:
        """
        Write new tests for changed files.
        Uses LLM to generate test cases.
        """
        files_written = []

        for file_path in files_changed:
            # Skip test files themselves
            if "test_" in file_path:
                continue

            # Read the changed file
            result = read_file(file_path)
            if not result.get("success"):
                continue

            file_content = result["content"]

            # Generate test file
            test_content = self._generate_tests(
                file_path=    file_path,
                file_content= file_content,
                task=         task
            )

            if not test_content:
                continue

            # Determine test file path
            parts     = file_path.replace("\\", "/").split("/")
            file_name = parts[-1].replace(".py", "")
            test_path = f"tests/test_{file_name}.py"

            # Write test file
            write_result = write_file(
                file_path=   test_path,
                content=     test_content,
                description= f"Tests for {file_path}"
            )

            if write_result.get("success"):
                files_written.append(test_path)
                logger.info(
                    "✅ Tests written: %s",
                    test_path
                )

        return {
            "success":       True,
            "files_written": files_written
        }

    def _generate_tests(
        self,
        file_path:    str,
        file_content: str,
        task:         str
    ) -> str | None:
        """
        Use LLM to generate pytest test cases.
        """
        prompt = f"""
You are a senior Python test engineer.

Write comprehensive pytest tests for this file.

File: {file_path}
Task that was implemented: {task}

File content:
{file_content[:3000]}

Generate complete pytest test file.
Rules:
- Use pytest conventions
- Test happy path and edge cases
- Mock external dependencies
- Include docstrings
- Use descriptive test names
- Return ONLY the Python test code
  no explanations, no markdown

Start with:
\"\"\"Tests for {file_path}\"\"\"
import pytest
"""

        response = self.think(
            prompt,
            max_tokens=  2000,
            temperature= 0.2
        )

        # Clean response
        clean = response.strip()
        if "```python" in clean:
            clean = clean.split("```python")[1]
            clean = clean.split("```")[0]
        elif "```" in clean:
            clean = clean.split("```")[1]
            clean = clean.split("```")[0]

        return clean.strip() if clean else None

    def check_test_coverage(self) -> dict[str, Any]:
        """
        Check overall test coverage.
        Reports to other agents.
        """
        logger.info("📊 Checking test coverage...")
        result = check_coverage()

        coverage = result.get("coverage_percent", 0)
        logger.info(
            "📊 Coverage: %s%%",
            coverage or "unknown"
        )

        return {
            "success":          result.get("success", False),
            "coverage_percent": coverage,
            "all_passed":       result.get("all_passed", False),
            "output":           result.get("output", "")
        }