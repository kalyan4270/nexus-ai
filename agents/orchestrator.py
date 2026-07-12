"""
Nexus AI Orchestrator.
Coordinates all agents to complete a task
end to end autonomously.
"""

from __future__ import annotations

import asyncio
from typing import Any

from agents.coder     import CoderAgent
from agents.planner   import PlannerAgent
from agents.reviewer  import ReviewerAgent
from agents.security  import SecurityAgent
from agents.tester    import TesterAgent
from agents.validator import ValidatorAgent
from core.logging     import get_logger
from mcp.tools.git_tools import (
    create_branch,
    create_pr,
    get_status,
)

logger = get_logger(__name__)


class NexusOrchestrator:
    """
    Main orchestrator for Nexus AI.

    Coordinates all agents in the right order:
    1. PlannerAgent   → understand + plan
    2. CoderAgent     → write the code
    3. ReviewerAgent  → review the code (A2A peer)
    4. SecurityAgent  → scan for vulnerabilities
    5. TesterAgent    → run + write tests
    6. ValidatorAgent → final go/no-go decision
    7. Git operations → create branch + PR
    """

    def __init__(self) -> None:
        # Initialize all agents
        self.planner   = PlannerAgent()
        self.coder     = CoderAgent()
        self.reviewer  = ReviewerAgent()
        self.security  = SecurityAgent()
        self.tester    = TesterAgent()
        self.validator = ValidatorAgent()

        logger.info(
            "🚀 Nexus Orchestrator initialized "
            "with 6 agents"
        )

    async def run(
        self,
        instruction: str,
        context:     dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Main entry point. Takes one instruction
        and runs all agents to completion.
        """
        from rich.console import Console
        from rich.panel import Panel

        console = Console()
        context = context or {}
        task_id = f"nexus_{id(instruction)}"[:12]

        console.print()
        console.print(Panel(
            f"[bold cyan]{instruction}[/bold cyan]",
            title="[cyan]🤖 Nexus AI — Starting Task[/cyan]",
            border_style="cyan"
        ))

        try:
            # ── Step 1: Plan ─────────────────────────
            console.print(
                "\n[cyan]📋 Step 1/6 — Planning...[/cyan]"
            )
            plan_result = self.planner.execute(
                task=    instruction,
                context= {
                    **context,
                    "task_id": task_id
                }
            )

            if not plan_result.get("success"):
                return self._error_result(
                    "Planning failed",
                    plan_result.get("error", ""),
                    task_id
                )

            # Display plan
            plan = plan_result.get("plan", {})
            self.planner.display_plan(plan)

            # ── Step 2: Create Branch ─────────────────
            console.print(
                "\n[cyan]🌿 Creating branch...[/cyan]"
            )
            branch_name = (
                f"nexus/{task_id}/"
                f"{instruction[:30].replace(' ', '-').replace('.', '').lower()}"
            )
            branch_result = create_branch(branch_name)

            if not branch_result.get("success"):
                logger.warning(
                    "Branch creation failed: %s",
                    branch_result.get("error")
                )

            # ── Step 3: Code ──────────────────────────
            console.print(
                "\n[cyan]💻 Step 2/6 — Writing code...[/cyan]"
            )
            coder_result = self.coder.execute(
                task=    instruction,
                context= {
                    **context,
                    "task_id": task_id,
                    "plan":    plan
                }
            )

            if not coder_result.get("success"):
                return self._error_result(
                    "Code writing failed",
                    coder_result.get("error", ""),
                    task_id
                )

            files_changed = coder_result.get(
                "files_changed", []
            )
            console.print(
                f"[green]✅ {len(files_changed)} "
                f"file(s) changed[/green]"
            )

            
            if files_changed:
                from mcp.tools.git_tools import commit_changes
                commit_result = commit_changes(
                    message=f"[Nexus AI] {instruction[:60]}\n\n"
                            f"Files changed: {', '.join(files_changed)}",
                    files=files_changed
                )
                if commit_result.get("success"):
                    console.print(
                        f"[green]📝 Committed: "
                        f"{commit_result.get('commit_hash')}[/green]"
                    )
                else:
                    logger.warning(
                        "Commit failed: %s",
                        commit_result.get("error")
                    )

            # ── Step 4: Review + Security (parallel) ─
            console.print(
                "\n[cyan]🔍 Step 3/6 — "
                "Reviewing + Security scan "
                "(parallel)...[/cyan]"
            )

            review_context = {
                **context,
                "task_id":       task_id,
                "files_changed": files_changed,
                "original_task": instruction
            }

            # Run reviewer and security in parallel
            loop = asyncio.get_event_loop()
            reviewer_future = loop.run_in_executor(
                None,
                lambda: self.reviewer.execute(
                    instruction, review_context
                )
            )
            security_future = loop.run_in_executor(
                None,
                lambda: self.security.execute(
                    instruction, review_context
                )
            )

            reviewer_result, security_result = (
                await asyncio.gather(
                    reviewer_future,
                    security_future
                )
            )

            # Show review results
            if reviewer_result.get("approved"):
                console.print(
                    f"[green]✅ Code review passed "
                    f"(score: "
                    f"{reviewer_result.get('quality_score', 0)}"
                    f"/100)[/green]"
                )
            else:
                console.print(
                    f"[yellow]⚠ Review issues: "
                    f"{len(reviewer_result.get('issues', []))}"
                    f"[/yellow]"
                )

            # Show security results
            if security_result.get("approved"):
                console.print(
                    "[green]✅ Security scan passed[/green]"
                )
            else:
                console.print(
                    f"[red]🚨 Security issues found: "
                    f"{security_result.get('critical_count', 0)}"
                    f" critical[/red]"
                )
                # Block if critical security issues
                if security_result.get(
                    "critical_count", 0
                ) > 0:
                    return self._error_result(
                        "Blocked by SecurityAgent",
                        "Critical security vulnerabilities found",
                        task_id,
                        details={
                            "findings": security_result.get(
                                "findings", []
                            )
                        }
                    )

            # ── Step 5: Tests ─────────────────────────
            console.print(
                "\n[cyan]🧪 Step 4/6 — "
                "Running tests...[/cyan]"
            )
            tester_result = self.tester.execute(
                instruction,
                {
                    **context,
                    "task_id":       task_id,
                    "files_changed": files_changed
                }
            )

            if tester_result.get("all_passed"):
                console.print(
                    f"[green]✅ Tests passing: "
                    f"{tester_result.get('passed', 0)} "
                    f"passed[/green]"
                )
            else:
                console.print(
                    f"[red]❌ Tests failing: "
                    f"{tester_result.get('failed', 0)} "
                    f"failed[/red]"
                )

            # ── Step 6: Validate ──────────────────────
            console.print(
                "\n[cyan]✔️ Step 5/6 — "
                "Final validation...[/cyan]"
            )
            validation = self.validator.execute(
                instruction,
                {
                    **context,
                    "task_id":        task_id,
                    "coder_result":   coder_result,
                    "reviewer_result": reviewer_result,
                    "security_result": security_result,
                    "tester_result":  tester_result
                }
            )

            # Display final results
            self.validator.display_results(validation)

            if not validation.get("approved"):
                return {
                    "success":    False,
                    "task_id":    task_id,
                    "reason":     "Validation failed",
                    "confidence": validation.get(
                        "confidence", 0
                    ),
                    "summary":    validation.get(
                        "summary", ""
                    ),
                    "breakdown":  validation.get(
                        "breakdown", {}
                    )
                }

            # ── Step 7: Create PR ─────────────────────
            console.print(
                "\n[cyan]🔗 Step 6/6 — "
                "Creating PR...[/cyan]"
            )

            pr_description = self._build_pr_description(
                instruction=  instruction,
                validation=   validation,
                coder_result= coder_result,
                tester_result=tester_result
            )

            pr_result = create_pr(
                title=       f"[Nexus AI] {instruction[:60]}",
                description= pr_description
            )

            if pr_result.get("success"):
                console.print(
                    f"\n[bold green]🎉 Done! "
                    f"PR #{pr_result.get('pr_number')} "
                    f"created:[/bold green] "
                    f"{pr_result.get('pr_url')}"
                )
            else:
                console.print(
                    f"[yellow]⚠ PR creation failed: "
                    f"{pr_result.get('error')}[/yellow]"
                )

            return {
                "success":      True,
                "task_id":      task_id,
                "instruction":  instruction,
                "confidence":   validation.get(
                    "confidence", 0
                ),
                "summary":      validation.get(
                    "summary", ""
                ),
                "files_changed": files_changed,
                "pr_number":    pr_result.get("pr_number"),
                "pr_url":       pr_result.get("pr_url"),
                "breakdown":    validation.get(
                    "breakdown", {}
                )
            }

        except Exception as exc:
            logger.error(
                "Orchestrator failed: %s", exc
            )
            return self._error_result(
                "Unexpected error",
                str(exc),
                task_id
            )

    def _build_pr_description(
        self,
        instruction:   str,
        validation:    dict[str, Any],
        coder_result:  dict[str, Any],
        tester_result: dict[str, Any]
    ) -> str:
        """Build detailed PR description."""
        breakdown     = validation.get("breakdown", {})
        files_changed = coder_result.get(
            "files_changed", []
        )
        tests_written = tester_result.get(
            "new_tests_written", []
        )

        files_list = "\n".join(
            f"- `{f}`" for f in files_changed
        )
        tests_list = "\n".join(
            f"- `{t}`" for t in tests_written
        )

        return f"""## 🤖 Nexus AI Autonomous Change

### Task
{instruction}

### Summary
{validation.get('summary', '')}

### Changes Made
{files_list or '- No files changed'}

### Tests
{tests_list or '- No new tests written'}
- ✅ {tester_result.get('passed', 0)} tests passing

### Quality Metrics
| Metric | Result |
|--------|--------|
| Confidence Score | {validation.get('confidence', 0)}% |
| Code Quality | {breakdown.get('quality_score', 0)}/100 |
| Security | {'✅ Passed' if breakdown.get('security_passed') else '❌ Failed'} |
| Tests | {'✅ All passing' if breakdown.get('tests_passed') else '❌ Some failing'} |

### Agents Involved
- 📋 PlannerAgent — Task decomposition
- 💻 CoderAgent — Implementation
- 🔍 ReviewerAgent — Code review
- 🔒 SecurityAgent — Security scan
- 🧪 TesterAgent — Test execution
- ✔️ ValidatorAgent — Final approval

---
*Generated autonomously by Nexus AI*
"""

    def _error_result(
        self,
        reason:  str,
        error:   str,
        task_id: str,
        details: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Build standardized error result."""
        from rich.console import Console
        from rich.panel import Panel

        console = Console()
        console.print(Panel(
            f"[red]{reason}[/red]\n{error}",
            title="[red]❌ Nexus AI — Task Failed[/red]",
            border_style="red"
        ))

        return {
            "success": False,
            "task_id": task_id,
            "reason":  reason,
            "error":   error,
            **(details or {})
        }