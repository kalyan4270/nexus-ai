"""
Validator Agent — Final quality gate.
Ensures everything is ready before PR creation.
"""

from __future__ import annotations

from typing import Any

from agents.base import NexusAgent
from core.logging import get_logger
from mcp.tools.file_tools import read_file
from mcp.tools.test_tools import run_tests

logger = get_logger(__name__)


class ValidatorAgent(NexusAgent):
    """
    ValidatorAgent is the final gate before
    any PR is created.

    Responsibilities:
    - Collect results from all agents
    - Calculate confidence score
    - Make final go/no-go decision
    - Generate comprehensive summary
    - Block PR if confidence too low
    """

    def __init__(self) -> None:
        super().__init__(
            agent_id=     "validator",
            name=         "ValidatorAgent",
            description=  "Final quality gate before PR creation",
            capabilities= [
                "validation",
                "confidence_scoring",
                "final_approval",
                "summary_generation",
                "quality_gate"
            ]
        )
        # Minimum confidence to proceed
        self._min_confidence = 60

    def execute(
        self,
        task:    str,
        context: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Validate all agent results and
        make final go/no-go decision.
        """
        task_id = context.get(
            "task_id", self.new_task_id()
        )
        self.start_task(task_id)

        try:
            logger.info(
                "✔️ ValidatorAgent validating: %s",
                task
            )

            # Collect all agent results
            coder_result    = context.get("coder_result",    {})
            reviewer_result = context.get("reviewer_result", {})
            security_result = context.get("security_result", {})
            tester_result   = context.get("tester_result",   {})

            # Calculate confidence score
            confidence = self._calculate_confidence(
                coder_result=    coder_result,
                reviewer_result= reviewer_result,
                security_result= security_result,
                tester_result=   tester_result
            )

            # Generate summary
            summary = self._generate_summary(
                task=            task,
                confidence=      confidence,
                coder_result=    coder_result,
                reviewer_result= reviewer_result,
                security_result= security_result,
                tester_result=   tester_result
            )

            # Final decision
            approved = (
                confidence >= self._min_confidence and
                security_result.get("approved", False) and
                tester_result.get("all_passed", False)
            )

            if approved:
                logger.info(
                    "✅ ValidatorAgent approved "
                    "(confidence: %d%%)",
                    confidence
                )
            else:
                logger.warning(
                    "❌ ValidatorAgent blocked "
                    "(confidence: %d%%)",
                    confidence
                )

            return {
                "success":    True,
                "task_id":    task_id,
                "approved":   approved,
                "confidence": confidence,
                "summary":    summary,
                "breakdown":  {
                    "code_written":     coder_result.get(
                        "success", False
                    ),
                    "review_passed":    reviewer_result.get(
                        "approved", False
                    ),
                    "security_passed":  security_result.get(
                        "approved", False
                    ),
                    "tests_passed":     tester_result.get(
                        "all_passed", False
                    ),
                    "quality_score":    reviewer_result.get(
                        "quality_score", 0
                    ),
                    "files_changed":    coder_result.get(
                        "files_changed", []
                    ),
                    "tests_written":    tester_result.get(
                        "new_tests_written", []
                    ),
                    "security_findings": security_result.get(
                        "findings", []
                    )
                }
            }

        except Exception as exc:
            logger.error(
                "ValidatorAgent failed: %s", exc
            )
            return {
                "success": False,
                "error":   str(exc),
                "task_id": task_id
            }
        finally:
            self.complete_task()

    def _calculate_confidence(
        self,
        coder_result:    dict[str, Any],
        reviewer_result: dict[str, Any],
        security_result: dict[str, Any],
        tester_result:   dict[str, Any]
    ) -> int:
        """
        Calculate overall confidence score 0-100.

        Weights:
        - Code written successfully:  20 points
        - Reviewer approved:          25 points
        - Security approved:          30 points
        - All tests passing:          25 points
        """
        score = 0

        # Code written (20 points)
        if coder_result.get("success"):
            score += 20

        # Reviewer approval (25 points)
        if reviewer_result.get("approved"):
            quality = reviewer_result.get(
                "quality_score", 70
            )
            # Scale: 25 points × quality/100
            score += int(25 * quality / 100)

        # Security approval (30 points)
        if security_result.get("approved"):
            score += 30
        else:
            # Check if only pattern-based false positives
            critical = security_result.get("critical_count", 0)
            high     = security_result.get("high_count", 0)
            findings = security_result.get("findings", [])

            # Pattern findings on env vars = false positives
            real_findings = [
                f for f in findings
                if "environment variable" not in
                f.get("fix", "").lower()
            ]

            if len(real_findings) == 0:
                score += 30  # All false positives
            elif critical == 0 and high == 0:
                score += 15  # Only low/medium issues

        # Tests passing (25 points)
        if tester_result.get("all_passed"):
            score += 25
        else:
            # Partial credit based on pass rate
            passed = tester_result.get("passed", 0)
            failed = tester_result.get("failed", 0)
            total  = passed + failed
            if total > 0:
                pass_rate = passed / total
                score += int(25 * pass_rate)

        return min(100, score)

    def _generate_summary(
        self,
        task:            str,
        confidence:      int,
        coder_result:    dict[str, Any],
        reviewer_result: dict[str, Any],
        security_result: dict[str, Any],
        tester_result:   dict[str, Any]
    ) -> str:
        """
        Generate human readable summary
        of entire execution.
        """
        files_changed = coder_result.get(
            "files_changed", []
        )
        tests_passed  = tester_result.get("passed", 0)
        tests_failed  = tester_result.get("failed", 0)
        quality_score = reviewer_result.get(
            "quality_score", 0
        )
        security_findings = security_result.get(
            "findings", []
        )

        prompt = f"""
Write a concise 2-3 sentence summary of this
autonomous code change execution:

Task: {task}
Confidence: {confidence}%
Files changed: {files_changed}
Tests: {tests_passed} passed, {tests_failed} failed
Code quality score: {quality_score}/100
Security findings: {len(security_findings)}
Reviewer approved: {reviewer_result.get('approved')}
Security approved: {security_result.get('approved')}

Be specific and professional.
Mention the most important outcomes.
"""

        return self.think(
            prompt,
            max_tokens=  200,
            temperature= 0.3
        )

    def display_results(
        self,
        validation: dict[str, Any]
    ) -> None:
        """
        Display final results in terminal
        with rich formatting.
        """
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
        from rich import box

        console   = Console()
        breakdown = validation.get("breakdown", {})
        approved  = validation.get("approved", False)
        confidence = validation.get("confidence", 0)

        # Color based on approval
        color = "green" if approved else "red"
        icon  = "✅" if approved else "❌"

        # Summary panel
        console.print()
        console.print(Panel(
            f"[bold]{validation.get('summary', '')}[/bold]",
            title=(
                f"[{color}]{icon} "
                f"{'APPROVED' if approved else 'BLOCKED'} "
                f"— Confidence: {confidence}%[/{color}]"
            ),
            border_style=color
        ))

        # Results table
        table = Table(
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan"
        )
        table.add_column("Check",   width=25)
        table.add_column("Result",  width=15)
        table.add_column("Details", width=35)

        checks = [
            (
                "Code Written",
                breakdown.get("code_written", False),
                f"{len(breakdown.get('files_changed', []))} "
                f"file(s) changed"
            ),
            (
                "Code Review",
                breakdown.get("review_passed", False),
                f"Quality score: "
                f"{breakdown.get('quality_score', 0)}/100"
            ),
            (
                "Security Scan",
                breakdown.get("security_passed", False),
                f"{len(breakdown.get('security_findings', []))} "
                f"findings"
            ),
            (
                "Tests Passing",
                breakdown.get("tests_passed", False),
                f"{len(breakdown.get('tests_written', []))} "
                f"new tests written"
            ),
        ]

        for check, passed, details in checks:
            status = (
                "[green]✅ PASSED[/green]"
                if passed
                else "[red]❌ FAILED[/red]"
            )
            table.add_row(check, status, details)

        console.print(table)